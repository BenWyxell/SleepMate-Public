from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from .patient_store import LocalProtector
from .services import create_full_backup, restore_full_backup, safe_extract_zip
from .version import APP_NAME, APP_VERSION, API_VERSION, BUILD_CHANNEL, UPDATE_MANIFEST_FORMAT, SUPPORT_BUNDLE_FORMAT

OFFICIAL_GITHUB_REPO = "BenWyxell/SleepMate-Public"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _version_tuple(text: str) -> tuple[int, ...]:
    parts = []
    for part in str(text or "0").strip().lstrip("vV").split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        parts.append(int(digits or 0))
    return tuple((parts + [0, 0, 0])[:3])


def version_newer(candidate: str, current: str = APP_VERSION) -> bool:
    return _version_tuple(candidate) > _version_tuple(current)


class UpdateSecretStore:
    """DPAPI-protected GitHub updater credentials.

    The token is intentionally not stored in config.json and never enters the
    support bundle. On non-Windows development systems LocalProtector keeps the
    same interface using its local fallback mode.
    """
    def __init__(self, base: Path):
        self.private = base / "private"
        self.private.mkdir(parents=True, exist_ok=True)
        self.path = self.private / "update_secrets.bin"
        self.protector = LocalProtector(self.private)

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            raw = self.protector.unprotect(self.path.read_bytes())
            obj = json.loads(raw.decode("utf-8"))
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}

    def _write(self, obj: dict[str, Any]) -> None:
        raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.path.write_bytes(self.protector.protect(raw))

    def github_token(self) -> str:
        return str(self._read().get("github_token") or "").strip()

    def save_github_token(self, token: str = "", clear: bool = False) -> None:
        obj = self._read()
        if clear:
            obj.pop("github_token", None)
        elif token.strip():
            obj["github_token"] = token.strip()
        self._write(obj)

    @staticmethod
    def mask(value: str) -> str:
        value = str(value or "").strip()
        if not value:
            return ""
        if len(value) < 12:
            return "••••••••"
        return f"{value[:4]}••••••••{value[-4:]}"

    def status(self) -> dict[str, Any]:
        token = self.github_token()
        return {"configured": bool(token), "token_hint": self.mask(token), "protection": self.protector.mode}


class GitHubUpdateManager:
    """Versioned GitHub Releases updater with verified MSI installation.

    Release contract:
      - asset `sleepmate-update.json`
      - an MSI named exactly `SleepMate_Setup_vX.Y.Z.msi`
      - manifest contains format/version/min_version/sha256/asset

    The updater never starts an unverified package. The running process only
    downloads, validates and backs up user state. A small onedir coordinator
    waits for SleepMate to exit and delegates the transactional program-file
    replacement to Windows Installer instead of editing executables itself.
    """
    def __init__(self, base: Path, log=None, state_base: Path | None = None):
        self.base = base.resolve()
        self.state_base = (state_base or base).resolve()
        self.private = self.state_base / "private"
        self.runtime = self.private / "update_runtime"
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.state_path = self.runtime / "state.json"
        self.secrets = UpdateSecretStore(self.state_base)
        # v5.2.20+: official SleepMate releases are public. Any credential saved
        # by an older build is obsolete and must never be reused or sent.
        try:
            self.secrets.path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass
        self.log = log
        self._lock = threading.RLock()

    def _log(self, level: str, message: str, details: dict | None = None) -> None:
        try:
            if self.log:
                self.log.append(level, "update", message, details or {})
        except Exception:
            pass

    def _load_state(self) -> dict[str, Any]:
        try:
            obj = json.loads(self.state_path.read_text(encoding="utf-8"))
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}

    def _save_state(self, **updates: Any) -> dict[str, Any]:
        state = self._load_state()
        state.update(updates)
        state["updated_at"] = _now()
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.state_path)
        return state

    @staticmethod
    def normalize_repo(repo: str) -> str:
        value = str(repo or "").strip().strip("/")
        for prefix in ("https://github.com/", "http://github.com/", "github.com/"):
            if value.lower().startswith(prefix):
                value = value[len(prefix):]
                break
        if value.endswith(".git"):
            value = value[:-4]
        parts = [p for p in value.split("/") if p]
        if not value:
            return ""
        if len(parts) != 2 or any(" " in p for p in parts):
            raise ValueError("A GitHub repository formátuma owner/repo legyen.")
        return f"{parts[0]}/{parts[1]}"

    def configure_token(self, token: str = "", clear: bool = False) -> dict[str, Any]:
        """Compatibility no-op: the public updater never accepts credentials."""
        try:
            self.secrets.path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass
        return {"configured": False, "required": False, "protection": "none"}

    def _request(self, url: str, *, accept: str = "application/vnd.github+json", timeout: float = 30) -> bytes:
        headers = {
            "Accept": accept,
            "User-Agent": f"{APP_NAME}/{APP_VERSION}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        # Official SleepMate releases are public; never attach a shared or user GitHub credential.
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:600]
            except Exception:
                pass
            if exc.code in (401, 403, 404):
                raise RuntimeError(f"A hivatalos SleepMate GitHub-kiadás jelenleg nem érhető el (HTTP {exc.code}). {detail}".strip()) from exc
            raise RuntimeError(f"GitHub frissítésellenőrzési hiba: HTTP {exc.code}. {detail}".strip()) from exc
        except Exception as exc:
            raise RuntimeError(f"A GitHub nem érhető el: {exc}") from exc

    def _json_request(self, url: str) -> dict[str, Any]:
        obj = json.loads(self._request(url).decode("utf-8"))
        if not isinstance(obj, dict):
            raise RuntimeError("A GitHub váratlan választ adott.")
        return obj

    def status(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        cfg = config or {}
        repo = OFFICIAL_GITHUB_REPO
        state = self._load_state()
        rollback_root = self.runtime / "rollback"
        rollbacks = []
        if rollback_root.exists():
            for p in sorted((x for x in rollback_root.iterdir() if x.is_dir()), key=lambda x: x.stat().st_mtime, reverse=True):
                meta = {}
                try:
                    meta = json.loads((p / "rollback.json").read_text(encoding="utf-8"))
                except Exception:
                    pass
                rollbacks.append({"path": str(p), "version": meta.get("version") or p.name, "created_at": meta.get("created_at")})
        try:
            build = json.loads((self.base / "build_info.json").read_text(encoding="utf-8"))
            if not isinstance(build, dict): build = {}
        except Exception:
            build = {}
        return {
            "current_version": APP_VERSION,
            "build_id": build.get("build_id"),
            "git_commit": build.get("git_commit"),
            "channel": str(cfg.get("update_channel") or BUILD_CHANNEL),
            "github_repo": repo,
            "configured": True,
            "auto_check": bool(cfg.get("update_auto_check", True)),
            "authentication": "public-anonymous",
            "last_check": state.get("last_check"),
            "latest_version": state.get("latest_version"),
            "update_available": bool(state.get("update_available")),
            "last_error": state.get("last_error"),
            "last_install": state.get("last_install"),
            "last_result": state.get("last_result"),
            "rollback_available": bool(rollbacks),
            "rollbacks": rollbacks[:3],
            "release": state.get("release") if isinstance(state.get("release"), dict) else None,
        }

    def check(self, config: dict[str, Any], force: bool = False) -> dict[str, Any]:
        with self._lock:
            repo = OFFICIAL_GITHUB_REPO
            url = f"https://api.github.com/repos/{repo}/releases/latest"
            try:
                release = self._json_request(url)
                tag = str(release.get("tag_name") or release.get("name") or "").strip().lstrip("vV")
                if not tag:
                    raise RuntimeError("A legfrissebb GitHub release nem tartalmaz verziószámot.")
                assets = []
                for a in release.get("assets") or []:
                    if isinstance(a, dict):
                        assets.append({"name": str(a.get("name") or ""), "url": str(a.get("url") or ""), "size": int(a.get("size") or 0)})
                manifest_asset = next((a for a in assets if a["name"].lower() == "sleepmate-update.json"), None)
                compact = {
                    "tag": tag,
                    "name": str(release.get("name") or f"SleepMate {tag}"),
                    "published_at": release.get("published_at"),
                    "html_url": str(release.get("html_url") or ""),
                    "prerelease": bool(release.get("prerelease")),
                    "assets": assets,
                    "manifest_asset": manifest_asset,
                }
                available = version_newer(tag, APP_VERSION) and not compact["prerelease"]
                self._save_state(last_check=_now(), latest_version=tag, update_available=available, release=compact, last_error=None)
                self._log("INFO", "GitHub frissítésellenőrzés kész.", {"repo": repo, "current": APP_VERSION, "latest": tag, "available": available})
                return {"ok": True, **self.status(config), "message": "Új verzió érhető el." if available else "A SleepMate naprakész."}
            except Exception as exc:
                self._save_state(last_check=_now(), last_error=str(exc))
                self._log("WARN", "GitHub frissítésellenőrzés sikertelen.", {"repo": repo, "error": str(exc)})
                raise

    def _download_asset(self, asset_url: str, destination: Path) -> None:
        if not asset_url:
            raise RuntimeError("A GitHub release asset URL hiányzik.")
        parsed = urllib.parse.urlparse(asset_url)
        if parsed.scheme.lower() != "https":
            raise RuntimeError("A SleepMate frissítési asset csak HTTPS kapcsolaton tölthető le.")
        data = self._request(asset_url, accept="application/octet-stream", timeout=120)
        destination.parent.mkdir(parents=True, exist_ok=True)
        tmp = destination.with_suffix(destination.suffix + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, destination)

    @staticmethod
    def _locate_package_root(extract_root: Path) -> Path:
        def valid(root: Path) -> bool:
            source_tree = (root / "app.py").is_file() and (root / "SleepMate.vbs").is_file()
            frozen_tree = (root / "SleepMate.exe").is_file() and (root / "build_info.json").is_file()
            return source_tree or frozen_tree
        if valid(extract_root):
            return extract_root
        candidates = [p for p in extract_root.iterdir() if p.is_dir() and valid(p)]
        if len(candidates) == 1:
            return candidates[0]
        raise RuntimeError("A frissítési ZIP nem tartalmaz egyértelmű SleepMate programgyökeret.")

    @staticmethod
    def _read_package_version(package_root: Path) -> str:
        build = package_root / "build_info.json"
        if build.is_file():
            try:
                obj = json.loads(build.read_text(encoding="utf-8"))
                value = str(obj.get("version") or "").strip()
                if value:
                    return value
            except Exception:
                pass
        vp = package_root / "cpap" / "version.py"
        if not vp.exists():
            raise RuntimeError("A frissítési csomag verziója nem olvasható (build_info.json / cpap/version.py hiányzik).")
        text = vp.read_text(encoding="utf-8", errors="replace")
        import re
        m = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', text, re.M)
        if not m:
            raise RuntimeError("A frissítési csomag verziója nem olvasható.")
        return m.group(1).strip()

    @staticmethod
    def _validate_msi_package(path: Path, target_version: str, manifest: dict[str, Any]) -> None:
        expected_name = f"SleepMate_Setup_v{target_version}.msi"
        if path.name != expected_name:
            raise RuntimeError(f"A frissítési MSI neve nem a várt release asset: {expected_name}")
        if str(manifest.get("package_type") or "") != "windows-msi-x64":
            raise RuntimeError("A frissítési manifest nem Windows MSI csomagot jelöl.")
        if manifest.get("requires_installer") is not True:
            raise RuntimeError("A frissítési manifestből hiányzik a kötelező Windows Installer jelölés.")
        # MSI files use the OLE Compound File header. This is not a signature,
        # but rejects a renamed HTML/ZIP/executable before Windows Installer is
        # ever started; SHA-256 remains the cryptographic integrity check.
        with path.open("rb") as source:
            if source.read(8) != bytes.fromhex("D0CF11E0A1B11AE1"):
                raise RuntimeError("A letöltött csomag nem érvényes MSI konténer.")

    def _snapshot_program(self, target: Path, version: str) -> dict[str, Any]:
        target.mkdir(parents=True, exist_ok=True)
        excluded = {"private", "__pycache__", ".git", ".pytest_cache"}
        files = 0
        for src in self.base.rglob("*"):
            rel = src.relative_to(self.base)
            if rel.parts and rel.parts[0] in excluded:
                continue
            if src.is_dir():
                (target / rel).mkdir(parents=True, exist_ok=True)
            elif src.is_file():
                dst = target / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                files += 1
        meta = {"version": version, "created_at": _now(), "files": files}
        (target / "rollback.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return meta

    def _cleanup_dirs(self, root: Path, keep: int) -> None:
        try:
            rows = sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True) if root.exists() else []
            for old in rows[max(1, keep):]:
                shutil.rmtree(old, ignore_errors=True)
        except Exception:
            pass

    def _cleanup_files(self, root: Path, pattern: str, keep: int) -> None:
        try:
            rows = sorted((p for p in root.glob(pattern) if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True) if root.exists() else []
            for old in rows[max(1, keep):]:
                try: old.unlink()
                except OSError: pass
        except Exception:
            pass

    def _prepare_binary_state_transition(self, package_root: Path, backup_path: Path, config: dict[str, Any]) -> Path:
        """Move a legacy portable/source install to per-user state before 5.x binary boot.

        The transition is copy/restore based; the old in-folder private state is
        never deleted. This allows a 4.2.x bridge release to install a frozen
        SleepMate program tree without losing patient, push or therapy state.
        """
        frozen_package = (package_root / "SleepMate.exe").is_file()
        if not frozen_package or os.name != "nt" or self.state_base != self.base:
            return self.state_base
        local = str(os.environ.get("LOCALAPPDATA") or "").strip()
        if not local:
            return self.state_base
        target_state = (Path(local) / "SleepMate").resolve()
        if target_state == self.state_base:
            return self.state_base
        target_state.mkdir(parents=True, exist_ok=True)
        target_measurement = target_state / "private" / "measurement"
        restore_full_backup(target_state, backup_path, target_measurement)
        (target_state / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        (target_state / "private" / "update_runtime").mkdir(parents=True, exist_ok=True)
        self._log("INFO", "5.x bináris állapotátmenet előkészítve.", {"from": str(self.state_base), "to": str(target_state), "source_preserved": True})
        return target_state

    def prepare_install(self, config: dict[str, Any], data_dir: Path, port: int, progress: Callable[[int, str, str], None] | None = None) -> dict[str, Any]:
        with self._lock:
            checked = self.check(config, force=True)
            if not checked.get("update_available"):
                raise RuntimeError("Nincs telepíthető új SleepMate verzió.")
            release = checked.get("release") or {}
            manifest_asset = release.get("manifest_asset")
            if not isinstance(manifest_asset, dict) or not manifest_asset.get("url"):
                raise RuntimeError("A GitHub release-ből hiányzik a sleepmate-update.json manifest.")
            if progress: progress(5, "Frissítés ellenőrzése", "Release manifest letöltése…")
            work = self.runtime / f"stage-{uuid.uuid4().hex[:10]}"
            work.mkdir(parents=True, exist_ok=True)
            manifest_path = work / "sleepmate-update.json"
            self._download_asset(str(manifest_asset["url"]), manifest_path)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict) or manifest.get("format") != UPDATE_MANIFEST_FORMAT:
                raise RuntimeError("Nem támogatott SleepMate frissítési manifest.")
            target_version = str(manifest.get("version") or "").strip().lstrip("vV")
            if target_version != str(release.get("tag") or "").strip().lstrip("vV"):
                raise RuntimeError("A release és a frissítési manifest verziója nem egyezik.")
            if not version_newer(target_version, APP_VERSION):
                raise RuntimeError("A frissítési csomag nem újabb a telepített verziónál.")
            min_version = str(manifest.get("min_version") or "0.0.0")
            if _version_tuple(APP_VERSION) < _version_tuple(min_version):
                raise RuntimeError(f"Ez a frissítés legalább SleepMate {min_version} verziót igényel.")
            asset_name = str(manifest.get("asset") or f"SleepMate_v{target_version}.zip")
            if Path(asset_name).name != asset_name:
                raise RuntimeError("A frissítési manifest érvénytelen asset nevet tartalmaz.")
            expected_hash = str(manifest.get("sha256") or "").lower().strip()
            if len(expected_hash) != 64:
                raise RuntimeError("A frissítési manifestből hiányzik az érvényes SHA-256 hash.")
            asset = next((a for a in (release.get("assets") or []) if a.get("name") == asset_name), None)
            if not asset:
                raise RuntimeError(f"A GitHub release-ből hiányzik a manifestben megadott csomag: {asset_name}")
            package_path = work / asset_name
            if progress: progress(15, "Frissítés letöltése", f"{asset_name} letöltése…")
            self._download_asset(str(asset.get("url") or ""), package_path)
            actual_hash = _sha256(package_path)
            if actual_hash.lower() != expected_hash:
                raise RuntimeError("A letöltött frissítési csomag SHA-256 ellenőrzése sikertelen.")

            if str(manifest.get("package_type") or "") == "windows-msi-x64":
                self._validate_msi_package(package_path, target_version, manifest)
                if progress: progress(30, "Csomag ellenőrzése", "A hitelesített MSI frissítési szerződés ellenőrzése kész.")

                # User data still receives the same full safety backup. Program
                # files are no longer snapshotted or manually replaced: MSI's
                # transactional rollback owns that responsibility.
                pre_dir = self.private / "pre_update_backups"
                pre_dir.mkdir(parents=True, exist_ok=True)
                backup_path = pre_dir / f"SleepMate_pre_update_{APP_VERSION}_to_{target_version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                if progress: progress(55, "Biztonsági mentés", "Teljes rendszerbackup készítése frissítés előtt…")
                create_full_backup(self.state_base, data_dir, config, backup_path)
                self._cleanup_files(pre_dir, "SleepMate_pre_update_*.zip", 5)

                marker = self.runtime / "update_boot_ok.json"
                try: marker.unlink()
                except FileNotFoundError: pass
                installer_log = self.runtime / f"msi-{target_version}-{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
                plan = {
                    "format": "sleepmate-update-plan",
                    "install_kind": "msi",
                    "created_at": _now(),
                    "from_version": APP_VERSION,
                    "to_version": target_version,
                    "app_dir": str(self.base),
                    "installer_path": str(package_path),
                    "installer_sha256": expected_hash,
                    "pre_update_backup": str(backup_path),
                    "health_marker": str(marker),
                    "old_pid": os.getpid(),
                    "port": int(port),
                    "tray_pid": self._read_tray_pid(),
                    "launch_vbs": str(self.base / "SleepMate.vbs"),
                    "launcher_exe": str(self.base / "SleepMate.exe"),
                    "state_dir": str(self.state_base),
                    "worker_log": str(self.runtime / "update_worker.log"),
                    "installer_log": str(installer_log),
                    "timeout_seconds": 90,
                }
                plan_path = work / "update-plan.json"
                plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
                self._save_state(last_install={"status": "prepared", "method": "windows-installer", "from": APP_VERSION, "to": target_version, "prepared_at": _now(), "backup": str(backup_path)}, last_error=None)
                if progress: progress(100, "Frissítés előkészítve", f"SleepMate {target_version} csendes MSI telepítése készen áll.")
                self._log("INFO", "MSI frissítés biztonságosan előkészítve.", {"from": APP_VERSION, "to": target_version, "asset": asset_name, "sha256": expected_hash, "backup": str(backup_path)})
                return {"ok": True, "target_version": target_version, "plan": str(plan_path), "backup": str(backup_path), "install_method": "windows-installer"}

            # Compatibility for historical portable/source update manifests.
            # New official releases are generated as windows-msi-x64 above.
            if str(manifest.get("package_type") or "") not in {"", "windows-x64-program-tree"}:
                raise RuntimeError("A frissítési manifest ismeretlen csomagtípust tartalmaz.")
            zip_path = package_path
            if progress: progress(30, "Csomag ellenőrzése", "Frissítési ZIP biztonságos kibontása…")
            extract_root = work / "package"
            extract_root.mkdir(parents=True, exist_ok=True)
            safe_extract_zip(zip_path, extract_root)
            package_root = self._locate_package_root(extract_root)
            package_version = self._read_package_version(package_root)
            if package_version != target_version:
                raise RuntimeError(f"A csomag belső verziója ({package_version}) nem egyezik a release verziójával ({target_version}).")

            # Full data backup before any program file can be replaced.
            pre_dir = self.private / "pre_update_backups"
            pre_dir.mkdir(parents=True, exist_ok=True)
            backup_path = pre_dir / f"SleepMate_pre_update_{APP_VERSION}_to_{target_version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            if progress: progress(45, "Biztonsági mentés", "Teljes rendszerbackup készítése frissítés előtt…")
            create_full_backup(self.state_base, data_dir, config, backup_path)
            target_state_base = self._prepare_binary_state_transition(package_root, backup_path, config)

            rollback_dir = self.runtime / "rollback" / f"{APP_VERSION}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            if progress: progress(65, "Rollback pont", "A jelenlegi programverzió teljes pillanatképének készítése…")
            self._snapshot_program(rollback_dir, APP_VERSION)
            self._cleanup_dirs(self.runtime / "rollback", 3)
            self._cleanup_files(pre_dir, "SleepMate_pre_update_*.zip", 5)

            target_runtime = target_state_base / "private" / "update_runtime"
            target_runtime.mkdir(parents=True, exist_ok=True)
            marker = target_runtime / "update_boot_ok.json"
            try: marker.unlink()
            except FileNotFoundError: pass
            plan = {
                "format": "sleepmate-update-plan",
                "created_at": _now(),
                "from_version": APP_VERSION,
                "to_version": target_version,
                "app_dir": str(self.base),
                "package_dir": str(package_root),
                "rollback_dir": str(rollback_dir),
                "pre_update_backup": str(backup_path),
                "health_marker": str(marker),
                "old_pid": os.getpid(),
                "port": int(port),
                "tray_pid": self._read_tray_pid(),
                "launch_vbs": str(self.base / "SleepMate.vbs"),
                "launcher_exe": str(self.base / "SleepMate.exe"),
                "state_dir": str(target_state_base),
                "worker_log": str(self.runtime / "update_worker.log"),
                "timeout_seconds": 70,
            }
            plan_path = work / "update-plan.json"
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            self._save_state(last_install={"status": "prepared", "from": APP_VERSION, "to": target_version, "prepared_at": _now(), "backup": str(backup_path)}, last_error=None)
            if progress: progress(100, "Frissítés előkészítve", f"SleepMate {target_version} készen áll a telepítésre.")
            self._log("INFO", "Frissítés biztonságosan előkészítve.", {"from": APP_VERSION, "to": target_version, "backup": str(backup_path), "rollback": str(rollback_dir)})
            return {"ok": True, "target_version": target_version, "plan": str(plan_path), "backup": str(backup_path), "rollback": str(rollback_dir)}

    def launch_worker(self, plan_path: str) -> dict[str, Any]:
        import subprocess
        plan = Path(plan_path)
        if not plan.is_file():
            raise FileNotFoundError("A frissítési terv nem található.")
        flags = 0x08000000 if os.name == "nt" else 0
        updater_dir = self.base / "Updater"
        updater_exe = updater_dir / "SleepMateUpdater.exe"
        legacy_updater_exe = self.base / "SleepMateUpdater.exe"
        if getattr(sys, "frozen", False) and updater_exe.is_file():
            # The coordinator uses the same transparent PyInstaller onedir
            # layout as SleepMate. It runs from the already-created update stage
            # so MSI can replace the installed tree without onefile extraction
            # or a randomly named executable.
            coordinator_dir = plan.parent / "coordinator"
            shutil.copytree(updater_dir, coordinator_dir, dirs_exist_ok=True)
            worker_copy = coordinator_dir / "SleepMateUpdater.exe"
            subprocess.Popen([str(worker_copy), str(plan)], cwd=str(coordinator_dir), creationflags=flags, close_fds=(os.name != "nt"))
        elif getattr(sys, "frozen", False) and legacy_updater_exe.is_file():
            # One transition release may still contain the former onefile
            # worker. It can install the first MSI-based update; new builds no
            # longer produce or package this layout.
            worker_copy = plan.parent / "SleepMateUpdater-legacy.exe"
            shutil.copy2(legacy_updater_exe, worker_copy)
            subprocess.Popen([str(worker_copy), str(plan)], cwd=str(plan.parent), creationflags=flags, close_fds=(os.name != "nt"))
        else:
            worker = self.base / "update_worker.py"
            if not worker.is_file():
                raise FileNotFoundError("A SleepMate update_worker.py fájl hiányzik.")
            subprocess.Popen([sys.executable, str(worker), str(plan)], cwd=str(self.base), creationflags=flags, close_fds=(os.name != "nt"))
        self._save_state(last_install={**(self._load_state().get("last_install") or {}), "status": "worker_started", "worker_started_at": _now()})
        return {"ok": True, "message": "A frissítő elindult. A SleepMate leáll és az új verzióban újraindul."}

    def _read_tray_pid(self) -> int:
        try:
            pid = int((self.private / "tray.pid").read_text(encoding="ascii").strip())
            heartbeat = self.private / "tray_heartbeat.json"
            obj = json.loads(heartbeat.read_text(encoding="utf-8"))
            if int(obj.get("pid") or 0) != pid:
                return 0
            # Never terminate a process using a stale PID file. A live v4.2+ tray
            # refreshes this heartbeat every 10 seconds.
            if time.time() - heartbeat.stat().st_mtime > 35:
                return 0
            return pid if pid > 0 else 0
        except Exception:
            return 0

    def prepare_rollback(self, port: int) -> dict[str, Any]:
        status = self.status({})
        rows = status.get("rollbacks") or []
        if not rows:
            raise RuntimeError("Nincs elérhető korábbi SleepMate verzió a visszaállításhoz.")
        chosen = Path(str(rows[0]["path"]))
        version = str(rows[0].get("version") or "korábbi")
        work = self.runtime / f"rollback-{uuid.uuid4().hex[:10]}"
        work.mkdir(parents=True, exist_ok=True)
        marker = self.runtime / "update_boot_ok.json"
        try: marker.unlink()
        except FileNotFoundError: pass
        # To make rollback itself reversible, snapshot the currently running app.
        current_snapshot = self.runtime / "rollback" / f"{APP_VERSION}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_before_manual_rollback"
        self._snapshot_program(current_snapshot, APP_VERSION)
        self._cleanup_dirs(self.runtime / "rollback", 3)
        plan = {
            "format": "sleepmate-update-plan", "created_at": _now(),
            "from_version": APP_VERSION, "to_version": version,
            "app_dir": str(self.base), "package_dir": str(chosen),
            "rollback_dir": str(current_snapshot), "pre_update_backup": "",
            "health_marker": str(marker), "old_pid": os.getpid(), "port": int(port),
            "tray_pid": self._read_tray_pid(), "launch_vbs": str(self.base / "SleepMate.vbs"),
            "launcher_exe": str(self.base / "SleepMate.exe"), "state_dir": str(self.state_base),
            "worker_log": str(self.runtime / "update_worker.log"), "timeout_seconds": 70,
            "manual_rollback": True,
        }
        plan_path = work / "update-plan.json"
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, "target_version": version, "plan": str(plan_path)}

    def mark_boot_ok(self) -> None:
        marker = self.runtime / "update_boot_ok.json"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({"version": APP_VERSION, "time": _now(), "pid": os.getpid()}, ensure_ascii=False, indent=2), encoding="utf-8")
        state = self._load_state()
        last = state.get("last_install") if isinstance(state.get("last_install"), dict) else {}
        if last and str(last.get("to") or "") == APP_VERSION:
            last = {**last, "status": "boot_ok", "completed_at": _now()}
            self._save_state(last_install=last, last_result={"status": "success", "version": APP_VERSION, "time": _now()})


class SelfCheckService:
    def __init__(self, base: Path, log=None, state_base: Path | None = None):
        self.base = base.resolve()
        self.state_base = (state_base or base).resolve()
        self.private = self.state_base / "private"
        self.log = log

    @staticmethod
    def _row(check_id: str, level: str, title: str, message: str, details: dict | None = None) -> dict[str, Any]:
        return {"id": check_id, "level": level, "title": title, "message": message, "details": details or {}}

    @staticmethod
    def _sqlite_integrity(path: Path) -> tuple[bool, str]:
        try:
            with closing(sqlite3.connect(str(path), timeout=3)) as con:
                row = con.execute("PRAGMA integrity_check").fetchone()
                value = str(row[0] if row else "")
                return value.lower() == "ok", value or "Nincs válasz"
        except Exception as exc:
            return False, str(exc)

    def run(self, *, dataset, config: dict[str, Any], scanner_status: dict, backup_status: dict,
            push_status: dict | None, remote_status: dict | None, update_status: dict | None) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        source_raw = str(config.get("data_dir") or "").strip()
        if not source_raw:
            rows.append(self._row("source", "ERROR", "Elsődleges adatforrás", "Nincs beállítva ResMed adatforrás."))
        else:
            source = Path(source_raw).expanduser()
            if not source.exists():
                rows.append(self._row("source", "ERROR", "Elsődleges adatforrás", "A beállított forrásmappa nem érhető el.", {"path": str(source)}))
            elif not (source / "DATALOG").is_dir():
                rows.append(self._row("source", "WARN", "Elsődleges adatforrás", "A forrás elérhető, de közvetlenül nem található benne DATALOG mappa.", {"path": str(source)}))
            else:
                rows.append(self._row("source", "OK", "Elsődleges adatforrás", "A ResMed forrásmappa elérhető és olvasható.", {"path": str(source)}))

        try:
            diag = dataset.diagnostics()
            errors = list(diag.get("errors") or [])
            if errors:
                rows.append(self._row("edf", "WARN", "EDF adatintegritás", f"{len(errors)} diagnosztikai figyelmeztetés van.", {"days": diag.get("days"), "edf_files": diag.get("edf_files")}))
            else:
                rows.append(self._row("edf", "OK", "EDF adatintegritás", f"{diag.get('edf_files', 0)} EDF ellenőrizve, nincs adatminőségi figyelmeztetés."))
        except Exception as exc:
            rows.append(self._row("edf", "ERROR", "EDF adatintegritás", f"A terápiás adatok ellenőrzése sikertelen: {exc}"))

        # Only live SleepMate databases belong to the runtime integrity check.
        # v4.2.0 recursively treated every *.db / *.sqlite3 under private as a
        # live database, so stale/restored/staging files could create a false ERROR.
        # Never infer SQLite solely from the extension.
        sqlite_candidates = [
            self.private / "patient.db",
            self.private / "push" / "push.sqlite3",
        ]
        sqlite_results = []
        for db_path in sqlite_candidates:
            if not db_path.is_file():
                continue
            try:
                with db_path.open("rb") as fh:
                    signature = fh.read(16)
            except Exception as exc:
                sqlite_results.append({
                    "file": str(db_path.relative_to(self.state_base)),
                    "ok": False,
                    "result": f"A fájl nem olvasható: {exc}",
                })
                continue
            if signature != b"SQLite format 3\x00":
                sqlite_results.append({
                    "file": str(db_path.relative_to(self.state_base)),
                    "ok": False,
                    "result": "Érvénytelen SQLite fájlfejléc.",
                })
                continue
            ok, detail = self._sqlite_integrity(db_path)
            sqlite_results.append({
                "file": str(db_path.relative_to(self.state_base)),
                "ok": ok,
                "result": detail,
            })

        failed_sqlite = [r for r in sqlite_results if not r.get("ok")]
        sqlite_ok = not failed_sqlite
        if not sqlite_results:
            sqlite_message = "Nincs aktív SQLite adatbázis ellenőrzésre."
        elif sqlite_ok:
            sqlite_message = f"{len(sqlite_results)} aktív adatbázis integritása rendben."
        else:
            names = ", ".join(r.get("file", "?") for r in failed_sqlite[:3])
            more = f" (+{len(failed_sqlite)-3} további)" if len(failed_sqlite) > 3 else ""
            sqlite_message = f"{len(sqlite_results)} aktív adatbázisból {len(failed_sqlite)} hibás: {names}{more}."
        rows.append(self._row(
            "sqlite",
            "OK" if sqlite_ok else "ERROR",
            "SQLite adatbázisok",
            sqlite_message,
            {"databases": sqlite_results, "failed": failed_sqlite},
        ))

        backup_dir = Path(str(config.get("auto_backup_dir") or (self.private / "automatic_backups"))).expanduser()
        candidates = []
        for d, pattern in ((backup_dir, "SleepMate_auto_backup_*.zip"), (self.private / "backups", "SleepMate_teljes_backup_*.zip"), (self.private / "pre_update_backups", "SleepMate_pre_update_*.zip")):
            try:
                if d.exists(): candidates.extend(d.glob(pattern))
            except Exception: pass
        candidates = [p for p in candidates if p.is_file()]
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates:
            age = datetime.now() - datetime.fromtimestamp(candidates[0].stat().st_mtime)
            level = "OK" if age <= timedelta(days=8) else "WARN"
            rows.append(self._row("backup", level, "Biztonsági mentés", f"Utolsó teljes mentés: {datetime.fromtimestamp(candidates[0].stat().st_mtime).strftime('%Y.%m.%d. %H:%M')}", {"file": str(candidates[0]), "age_hours": round(age.total_seconds()/3600, 1)}))
        else:
            rows.append(self._row("backup", "WARN", "Biztonsági mentés", "Még nem található teljes SleepMate backup."))

        if bool(config.get("auto_scan_enabled", True)):
            if scanner_status.get("next_run"):
                rows.append(self._row("scheduler", "OK", "Automatikus adatfrissítés", f"Következő futás: {scanner_status.get('next_run')}"))
            else:
                rows.append(self._row("scheduler", "WARN", "Automatikus adatfrissítés", "Be van kapcsolva, de nincs következő futási idő."))
        else:
            rows.append(self._row("scheduler", "WARN", "Automatikus adatfrissítés", "Ki van kapcsolva."))

        if push_status and push_status.get("available") is not False:
            subs = int(push_status.get("subscriptions") or 0)
            rows.append(self._row("push", "OK" if subs else "WARN", "PWA Web Push", f"{subs} aktív push-feliratkozás." if subs else "A Web Push elérhető, de nincs aktív eszköz feliratkozva."))
        else:
            rows.append(self._row("push", "WARN", "PWA Web Push", "A Web Push szolgáltatás jelenleg nem érhető el."))

        try:
            usage = shutil.disk_usage(self.state_base)
            free_gb = usage.free / 1024**3
            free_pct = (usage.free / usage.total * 100) if usage.total else 0
            level = "ERROR" if free_gb < 0.5 else ("WARN" if free_gb < 2 or free_pct < 5 else "OK")
            rows.append(self._row("disk", level, "Szabad lemezterület", f"{free_gb:.1f} GB szabad ({free_pct:.0f}%).", {"free_bytes": usage.free, "total_bytes": usage.total}))
        except Exception as exc:
            rows.append(self._row("disk", "WARN", "Szabad lemezterület", f"Nem ellenőrizhető: {exc}"))

        if update_status:
            if update_status.get("configured"):
                msg = "Új verzió érhető el." if update_status.get("update_available") else "A hivatalos SleepMate frissítési forrás elérhető."
                level = "WARN" if update_status.get("update_available") else "OK"
            else:
                msg = "A hivatalos SleepMate frissítési forrás nem érhető el."
                level = "WARN"
            rows.append(self._row("updater", level, "Frissítési rendszer", msg, {"repo": update_status.get("github_repo"), "latest": update_status.get("latest_version")}))

        installed_tree = (self.base / "SleepMate.exe").is_file() or (self.base / "installed.marker").exists()
        required = (["SleepMate.exe", "Updater/SleepMateUpdater.exe", "build_info.json", "installed.marker"] if installed_tree else
                    ["app.py", "SleepMate.vbs", "sleepmate_tray.pyw", "web/index.html", "web/app.js", "web/service-worker.js", "cpap/version.py", "update_worker.py"])
        missing = [name for name in required if not (self.base / name).is_file()]
        rows.append(self._row("program", "ERROR" if missing else "OK", "Programfájlok", "Hiányzó alapfájlok: " + ", ".join(missing) if missing else "A kötelező SleepMate programfájlok megvannak.", {"missing": missing}))

        counts = {"OK": 0, "WARN": 0, "ERROR": 0}
        for r in rows: counts[r["level"]] = counts.get(r["level"], 0) + 1
        overall = "ERROR" if counts["ERROR"] else ("WARN" if counts["WARN"] else "OK")
        result = {"generated_at": _now(), "version": APP_VERSION, "overall": overall, "counts": counts, "checks": rows}
        try:
            if self.log:
                log_details = dict(counts)
                failed_checks = []
                for check in rows:
                    if check.get("level") != "ERROR":
                        continue
                    item = {"id": check.get("id"), "title": check.get("title"), "message": check.get("message")}
                    if check.get("id") == "sqlite":
                        item["failed_databases"] = (check.get("details") or {}).get("failed") or []
                    failed_checks.append(item)
                if failed_checks:
                    log_details["failed_checks"] = failed_checks
                self.log.append("INFO" if overall == "OK" else "WARN", "self_check", f"SleepMate önellenőrzés: {overall}", log_details)
        except Exception:
            pass
        return result


class SupportBundleService:
    """Create a diagnostic ZIP without therapy EDFs, DB row data, API keys or tokens."""
    def __init__(self, base: Path, log=None, state_base: Path | None = None):
        self.base = base.resolve()
        self.state_base = (state_base or base).resolve()
        self.private = self.state_base / "private"
        self.log = log

    @staticmethod
    def _sanitize_config(config: dict[str, Any]) -> dict[str, Any]:
        secret_tokens = ("token", "secret", "password", "api_key", "apikey", "credential")
        out = {}
        for k, v in config.items():
            low = str(k).lower()
            if any(t in low for t in secret_tokens):
                out[k] = "<REDACTED>" if v else ""
            else:
                out[k] = v
        return out

    @staticmethod
    def _inventory(base: Path) -> list[dict[str, Any]]:
        roots = ["app.py", "SleepMate.pyw", "SleepMate.vbs", "sleepmate_tray.pyw", "update_worker.py", "requirements.txt", "cpap", "web"]
        rows = []
        for name in roots:
            p = base / name
            candidates = [p] if p.is_file() else (list(p.rglob("*")) if p.is_dir() else [])
            for f in candidates:
                if not f.is_file() or "__pycache__" in f.parts:
                    continue
                rel = f.relative_to(base).as_posix()
                try:
                    rows.append({"path": rel, "size": f.stat().st_size, "sha256": _sha256(f)})
                except Exception as exc:
                    rows.append({"path": rel, "error": str(exc)})
        return sorted(rows, key=lambda x: x.get("path", ""))

    @staticmethod
    def _sqlite_schema(path: Path) -> dict[str, Any]:
        result = {"file": path.name, "tables": [], "integrity": None}
        try:
            with closing(sqlite3.connect(str(path), timeout=3)) as con:
                row = con.execute("PRAGMA integrity_check").fetchone()
                result["integrity"] = row[0] if row else None
                for name, sql in con.execute("SELECT name, sql FROM sqlite_master WHERE type IN ('table','index') AND name NOT LIKE 'sqlite_%' ORDER BY type,name"):
                    result["tables"].append({"name": name, "sql": sql})
        except Exception as exc:
            result["error"] = str(exc)
        return result

    @staticmethod
    def _mask_remote(obj: Any) -> Any:
        if isinstance(obj, dict):
            out = {}
            for k, v in obj.items():
                low = str(k).lower()
                if any(x in low for x in ("token", "endpoint", "secret", "auth")):
                    out[k] = "<REDACTED>" if v else v
                else:
                    out[k] = SupportBundleService._mask_remote(v)
            return out
        if isinstance(obj, list):
            return [SupportBundleService._mask_remote(x) for x in obj]
        return obj

    def create(self, *, config: dict[str, Any], self_check: dict[str, Any], diagnostics: dict[str, Any],
               system_status: dict[str, Any], update_status: dict[str, Any], remote_status: dict[str, Any] | None,
               push_status: dict[str, Any] | None, logs: list[dict[str, Any]]) -> Path:
        out_dir = self.private / "support"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"SleepMate_szervizcsomag_{APP_VERSION}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        try:
            build_info = json.loads((self.base / "build_info.json").read_text(encoding="utf-8"))
            if not isinstance(build_info, dict): build_info = {}
        except Exception:
            build_info = {}
        env = {
            "app": APP_NAME, "version": APP_VERSION, "api": API_VERSION, "channel": BUILD_CHANNEL, "build": build_info,
            "created_at": _now(), "python": sys.version, "executable": sys.executable,
            "platform": platform.platform(), "machine": platform.machine(), "processor": platform.processor(),
            "os_name": os.name, "cwd": str(self.base), "app_root": str(self.base), "state_root": str(self.state_base), "frozen": bool(getattr(sys, "frozen", False)),
        }
        sqlite_rows = []
        for p in (self.private / "patient.db", self.private / "push" / "push.sqlite3"):
            if not p.is_file():
                continue
            try:
                with p.open("rb") as fh:
                    if fh.read(16) != b"SQLite format 3\x00":
                        continue
            except Exception:
                continue
            row = self._sqlite_schema(p)
            try: row["file"] = p.relative_to(self.state_base).as_posix()
            except Exception: pass
            sqlite_rows.append(row)
        update_public = dict(update_status or {})
        if isinstance(update_public.get("token"), dict):
            update_public["token"] = {k:v for k,v in update_public["token"].items() if k != "token"}
        if update_public.get("release") and isinstance(update_public["release"], dict):
            # Release metadata is public-ish repository metadata; safe for support.
            pass
        push_public = {"available": bool(push_status), "subscriptions": int((push_status or {}).get("subscriptions") or 0), "dependency_error": (push_status or {}).get("dependency_error")}
        items = {
            "support_manifest.json": {"format": SUPPORT_BUNDLE_FORMAT, "version": 1, "created_at": _now(), "app_version": APP_VERSION, "contains_therapy_edf": False, "contains_database_rows": False, "contains_secrets": False},
            "environment.json": env,
            "config_sanitized.json": self._sanitize_config(config),
            "self_check.json": self_check,
            "diagnostics.json": diagnostics,
            "system_status.json": system_status,
            "update_status.json": update_public,
            "remote_status_sanitized.json": self._mask_remote(remote_status or {}),
            "push_status_sanitized.json": push_public,
            "sqlite_schema_and_integrity.json": sqlite_rows,
            "app_inventory.json": self._inventory(self.base),
            "system_log_recent.json": self._mask_remote(logs[-500:] if len(logs) > 500 else logs),
        }
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for name, obj in items.items():
                zf.writestr(name, json.dumps(obj, ensure_ascii=False, indent=2, default=str))
        try:
            if self.log:
                self.log.append("INFO", "support", "SleepMate szervizcsomag elkészült.", {"file": str(out), "size": out.stat().st_size})
        except Exception:
            pass
        return out
