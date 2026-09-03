from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import mimetypes
import os
import shutil
import tempfile
import threading
import time
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import webbrowser
import sys


def _configure_utf8_stdio() -> None:
    """Keep hidden/background Windows launches independent from the active code page.

    pythonw.exe inherits the Windows locale for redirected stdout/stderr unless
    explicitly overridden. SleepMate writes Hungarian/Unicode status messages,
    so cp1250 must never be allowed to crash the service during startup.
    """
    for stream in (getattr(sys, "stdout", None), getattr(sys, "stderr", None)):
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (AttributeError, ValueError, OSError):
            pass


_configure_utf8_stdio()

from cpap.resmed import ResMedDataset
from cpap.patient_store import PatientStore
from cpap.ai_store import AIStore, dataset_signature
from cpap.ai_payload import PROMPT_VERSION, analysis_prompts, build_safe_payload, build_comparison_payload, chat_prompts, external_analysis_prompt
from cpap.ai_provider import AIProviderError, stream_provider, groq_transport_name
from cpap.report_pdf import generate_report_pdf
from cpap.remote_access import RemoteAccessManager
from cpap.push_service import PushService
from cpap.version import APP_NAME, APP_VERSION, API_VERSION, BUILD_CHANNEL
from cpap.maintenance import GitHubUpdateManager, SelfCheckService, SupportBundleService
from cpap.runtime import app_root, resource_root, state_root, config_path, ensure_state_layout, migrate_legacy_state
from cpap.services import (
    AutoScanner, AutoBackupScheduler, JobManager, PersistentLog, create_full_backup, delete_measurement_data,
    ensure_data_root, find_resmed_sd, import_resmed_tree, restore_full_backup, safe_extract_zip,
)

APP_BASE = app_root()
RESOURCE_BASE = resource_root()
STATE_BASE = ensure_state_layout(APP_BASE)
# BASE remains the program tree for compatibility with code that inventories or updates binaries.
BASE = APP_BASE
WEB = RESOURCE_BASE / "web"
ASSETS = WEB / "assets"
EQUIPMENT_IMAGE = ASSETS / "airsense11.jpg"
EQUIPMENT_IMAGE_URL = "https://www.craftopoulos.gr/wp-content/uploads/2025/07/resmed-airsense-11-autoset-auto-cpap-machine-with-humidair.jpg"
MANAGED_DATA_ROOT = STATE_BASE / "private" / "measurement"
MANAGED_MARKER = MANAGED_DATA_ROOT / ".managed-store-v1"


def load_build_info() -> dict:
    try:
        obj = json.loads((RESOURCE_BASE / "build_info.json").read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _normalize_profile_photo(binary: bytes, mime_hint: str = "image/jpeg") -> tuple[bytes, str]:
    """Normalize uploaded patient profile photos to compact WEBP.

    This keeps page/PWA loading snappy on slower phones and networks and makes
    the stored asset format consistent regardless of what the user selected.
    """
    try:
        from PIL import Image, ImageOps
        with Image.open(io.BytesIO(binary)) as img:
            img = ImageOps.exif_transpose(img)
            # Keep profile photos light and consistent.
            max_edge = 512
            if max(img.size) > max_edge:
                img.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
            has_alpha = 'A' in img.getbands()
            if has_alpha:
                img = img.convert('RGBA')
            else:
                img = img.convert('RGB')
            out = io.BytesIO()
            save_kwargs = {
                'format': 'WEBP',
                'method': 6,
                'quality': 82,
            }
            if has_alpha:
                save_kwargs['lossless'] = False
            img.save(out, **save_kwargs)
            data = out.getvalue()
            if data:
                return data, 'image/webp'
    except Exception:
        pass
    return binary, mime_hint


def load_config() -> dict:
    defaults = {
        "data_dir": str(Path.home() / "Documents" / "CPAP_mentes"),
        "host": "127.0.0.1",
        "port": 8895,
        "port_mode": "auto",
        "show_spo2": False,
        "show_hr": False,
        "ai_luna_visible": True,
        "ai_milo_visible": True,
        "ai_prompting_enabled": False,
        "pwa_bottom_nav_labels": {},
        "auto_scan_enabled": True,
        "auto_scan_mode": "interval",
        "auto_scan_interval_minutes": 30,
        "auto_scan_time": "06:00",
        "auto_scan_days": [0, 1, 2, 3, 4, 5, 6],
        "auto_scan_last_run": None,
        "tray_notifications": True,
        "start_with_windows": False,
        "auto_backup_enabled": False,
        "auto_backup_mode": "weekly",
        "auto_backup_time": "03:00",
        "auto_backup_weekday": 6,
        "auto_backup_monthday": 1,
        "auto_backup_dir": str(STATE_BASE / "private" / "automatic_backups"),
        "auto_backup_keep": 5,
        "auto_backup_last_run": None,
        "auto_backup_last_file": "",
        "cloudflare_hostname": "",
        "cloudflare_access_confirmed": False,
        "tailscale_auto_serve": False,
        "update_github_repo": "BenWyxell/SleepMate-Public",
        "update_channel": "stable",
        "update_auto_check": True,
        "update_last_check": None,
    }
    p = config_path(APP_BASE)
    if p.exists():
        try:
            loaded = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                defaults.update(loaded)
                # The separate Luna/Milo switches are additive. Older settings
                # without these keys retain the previously visible UI default.
                for key, fallback in (
                    ("ai_luna_visible", True),
                    ("ai_milo_visible", True),
                    ("ai_prompting_enabled", False),
                ):
                    value = loaded.get(key, fallback)
                    defaults[key] = value if isinstance(value, bool) else fallback
                if not isinstance(loaded.get("pwa_bottom_nav_labels", {}), dict):
                    defaults["pwa_bottom_nav_labels"] = {}
                # v5.2.20+: the update origin is product-owned, not a user setting.
                defaults["update_github_repo"] = "BenWyxell/SleepMate-Public"
                # v3.5+: the web backend stays local-only; remote access is via
                # Tailscale Serve or Cloudflare Tunnel reverse proxy.
                if str(defaults.get("host") or "") in {"0.0.0.0", "::"}:
                    defaults["host"] = "127.0.0.1"
        except Exception:
            pass
    return defaults



def datetime_now_file() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def save_config(update: dict) -> dict:
    p = config_path(APP_BASE)
    cfg = load_config()
    cfg.update(update)
    p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg


class Handler(BaseHTTPRequestHandler):
    dataset: ResMedDataset
    patient_store: PatientStore
    ai_store: AIStore
    jobs: JobManager
    persistent_log: PersistentLog
    scanner: AutoScanner | None = None
    backup_scheduler: AutoBackupScheduler | None = None
    remote_manager: RemoteAccessManager | None = None
    push_service: PushService | None = None
    server_instance: ThreadingHTTPServer | None = None
    backup_files: dict[str, Path] = {}
    support_files: dict[str, Path] = {}
    update_manager: GitHubUpdateManager | None = None
    self_check_service: SelfCheckService | None = None
    support_service: SupportBundleService | None = None
    upload_files: dict[str, Path] = {}
    _dataset_lock = threading.RLock()

    def log_message(self, fmt, *args):
        print("[HTTP] " + fmt % args)

    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


    def _system_status_payload(self) -> dict:
        """Build the compact status shown on the Naplók page.

        Every WARN from ResMedDataset.diagnostics() is surfaced here as well,
        so the compact card cannot stay green while detailed diagnostics warn.
        """
        cfg = load_config()
        source_raw = str(cfg.get("data_dir") or "").strip()
        source_ok = False
        source_message = "Nincs beállítva adatforrás."
        if source_raw:
            try:
                root = self._validate_source_dir(source_raw)
                source_ok = True
                source_message = str(root)
            except Exception as exc:
                source_message = str(exc)

        diag = self.dataset.diagnostics()
        damaged = len(diag.get("damaged_files") or [])
        missing = len(diag.get("missing_required") or [])
        diagnostic_warnings = list(diag.get("errors") or [])
        days = len(self.dataset.days())
        scan = self.scanner.status() if self.scanner else {}
        backup = self.backup_scheduler.status() if self.backup_scheduler else {}

        backup_dir = Path(str(cfg.get("auto_backup_dir") or (STATE_BASE / "private" / "automatic_backups"))).expanduser()
        backup_files = sorted(
            backup_dir.glob("SleepMate_auto_backup_*.zip"),
            key=lambda x: x.stat().st_mtime if x.exists() else 0,
            reverse=True,
        ) if backup_dir.exists() else []
        manual_dir = STATE_BASE / "private" / "backups"
        manual_files = sorted(
            manual_dir.glob("*.zip"),
            key=lambda x: x.stat().st_mtime if x.exists() else 0,
            reverse=True,
        ) if manual_dir.exists() else []
        candidates = backup_files + manual_files
        candidates.sort(key=lambda x: x.stat().st_mtime if x.exists() else 0, reverse=True)
        last_backup = datetime.fromtimestamp(candidates[0].stat().st_mtime).isoformat(timespec="seconds") if candidates else None

        ai_cfg = self.ai_store.get_provider_config().get("providers") or {}
        diagnostic_value = "Nincs diagnosztikai figyelmeztetés."
        if diagnostic_warnings:
            diagnostic_value = " • ".join(
                f"{str(row.get('title') or 'Figyelmeztetés')}: {str(row.get('message') or '')}"
                for row in diagnostic_warnings
            )

        components = {
            "source": {"ok": source_ok, "label": "Adatforrás", "value": source_message},
            "sync": {"ok": bool(scan.get("last_run") or days), "label": "Utolsó szinkron", "value": scan.get("last_run") or diag.get("last_successful_refresh")},
            "next_sync": {"ok": bool(scan.get("next_run")) if cfg.get("auto_scan_enabled", True) else True, "label": "Következő frissítés", "value": scan.get("next_run") if cfg.get("auto_scan_enabled", True) else "Automatika kikapcsolva"},
            "edf": {
                "ok": damaged == 0 and missing == 0,
                "warning": damaged == 0 and missing > 0,
                "label": "EDF állapot",
                "value": f"{diag.get('edf_files',0)} fájl • {damaged} sérült • {missing} hiányos szakasz",
            },
            "diagnostics": {
                "ok": not diagnostic_warnings,
                "warning": bool(diagnostic_warnings),
                "label": "Diagnosztika",
                "value": diagnostic_value,
            },
            "luna": {"ok": bool((ai_cfg.get("gemini") or {}).get("configured")), "optional": True, "label": "Luna", "value": "Beállítva" if (ai_cfg.get("gemini") or {}).get("configured") else "Nincs API-kulcs"},
            "milo": {"ok": bool((ai_cfg.get("groq") or {}).get("configured")), "optional": True, "label": "Milo", "value": "Beállítva" if (ai_cfg.get("groq") or {}).get("configured") else "Nincs API-kulcs"},
            "backup": {"ok": bool(last_backup), "warning": not bool(last_backup), "label": "Legutóbbi backup", "value": last_backup or "Még nem készült"},
        }
        critical_bad = (not source_ok) or damaged > 0
        warning = (days == 0) or bool(diagnostic_warnings) or not last_backup
        overall = "error" if critical_bad else ("warning" if warning else "ok")
        return {
            "overall": overall,
            "days": days,
            "components": components,
            "diagnostic_warning_count": len(diagnostic_warnings),
            "auto_backup": {**backup, "directory": str(backup_dir), "last_backup": last_backup},
        }

    def _update_status_payload(self) -> dict:
        if not self.update_manager:
            return {"configured": False, "current_version": APP_VERSION, "last_error": "A frissítési modul nem érhető el."}
        return self.update_manager.status(load_config())

    def _self_check_payload(self) -> dict:
        if not self.self_check_service:
            raise RuntimeError("Az önellenőrzési modul nem érhető el.")
        cfg = load_config()
        scan = self.scanner.status() if self.scanner else {}
        backup = self.backup_scheduler.status() if self.backup_scheduler else {}
        push = self.push_service.status() if self.push_service else None
        remote = None
        try:
            if self.remote_manager:
                remote = {
                    "tailscale": self.remote_manager.tailscale_status(),
                    "cloudflare": self.remote_manager.cloudflare_status(str(cfg.get("cloudflare_hostname") or "")),
                }
        except Exception:
            remote = None
        return self.self_check_service.run(
            dataset=self.dataset, config=cfg, scanner_status=scan, backup_status=backup,
            push_status=push, remote_status=remote, update_status=self._update_status_payload(),
        )

    def _support_bundle_job(self, jid: str):
        if not self.support_service:
            raise RuntimeError("A szervizcsomag modul nem érhető el.")
        self._progress(jid, 10, "Önellenőrzés", "A SleepMate állapotának ellenőrzése…")
        self_check = self._self_check_payload()
        self._progress(jid, 35, "Diagnosztika", "Terápiás és rendszerdiagnosztika összegyűjtése…")
        cfg = load_config()
        remote = {}
        try:
            if self.remote_manager:
                remote = {
                    "tailscale": self.remote_manager.tailscale_status(),
                    "cloudflare": self.remote_manager.cloudflare_status(str(cfg.get("cloudflare_hostname") or "")),
                }
        except Exception as exc:
            remote = {"error": str(exc)}
        push = self.push_service.status() if self.push_service else {}
        self._progress(jid, 65, "Szervizcsomag", "Programfájlok ujjlenyomatának és adatbázissémák összeírása…")
        out = self.support_service.create(
            config=cfg, self_check=self_check, diagnostics=self.dataset.diagnostics(),
            system_status=self._system_status_payload(), update_status=self._update_status_payload(),
            remote_status=remote, push_status=push, logs=list(reversed(self.persistent_log.list(500))),
        )
        Handler.support_files[jid] = out
        self._progress(jid, 100, "Kész", "A titokmentes SleepMate szervizcsomag elkészült.")
        return {"file": str(out), "size": out.stat().st_size, "download_url": f"/api/support/download?job={jid}", "contains_edf": False, "contains_secrets": False}

    def _update_install_job(self, jid: str):
        if not self.update_manager:
            raise RuntimeError("A frissítési modul nem érhető el.")
        cfg = load_config()
        def cb(p, ph, msg): self._progress(jid, p, ph, msg)
        result = self.update_manager.prepare_install(cfg, self.dataset.root, int(self.server.server_address[1]), cb)
        self._progress(jid, 100, "Újraindítás", f"SleepMate {result.get('target_version')} ellenőrzött, csendes Windows Installer telepítése indul.")
        self.update_manager.launch_worker(str(result["plan"]))
        srv = self.server_instance
        if srv:
            threading.Timer(1.0, srv.shutdown).start()
        return {**result, "restarting": True}

    def _update_rollback_job(self, jid: str):
        if not self.update_manager:
            raise RuntimeError("A frissítési modul nem érhető el.")
        self._progress(jid, 20, "Rollback előkészítése", "Az előző működő programverzió előkészítése…")
        result = self.update_manager.prepare_rollback(int(self.server.server_address[1]))
        self._progress(jid, 90, "Újraindítás", f"Visszaállás a(z) {result.get('target_version')} verzióra…")
        self.update_manager.launch_worker(str(result["plan"]))
        srv = self.server_instance
        if srv:
            threading.Timer(1.0, srv.shutdown).start()
        return {**result, "restarting": True}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/version":
                return self._json({"app": APP_NAME, "version": APP_VERSION, "api": API_VERSION, "channel": BUILD_CHANNEL, "build": load_build_info()})
            if path == "/api/update/status":
                return self._json(self._update_status_payload())
            if path == "/api/self-check":
                return self._json(self._self_check_payload())
            if path == "/api/support/download":
                q = parse_qs(parsed.query); jid = q.get("job", [""])[0]
                fp = self.support_files.get(jid)
                if not fp or not fp.is_file():
                    return self._json({"error": "A szervizcsomag nem található vagy még nincs kész."}, 404)
                return self._send_file(fp, fp.name, "application/zip")
            if path == "/api/days":
                return self._json({"days": self.dataset.days()})
            if path == "/api/day-table":
                return self._json({"rows": self.dataset.day_table()})
            if path == "/api/config":
                host, port = self.server.server_address[:2]
                cfg = load_config()
                scan = self.scanner.status() if self.scanner else {"enabled": bool(cfg.get("auto_scan_enabled", True)), "next_run": None, "last_run": cfg.get("auto_scan_last_run")}
                backup_status = self.backup_scheduler.status() if self.backup_scheduler else {"enabled": bool(cfg.get("auto_backup_enabled", False)), "next_run": None, "last_run": cfg.get("auto_backup_last_run")}
                return self._json({
                    "data_dir": str(cfg.get("data_dir") or ""), "host": str(host), "port": int(port),
                    "port_mode": str(cfg.get("port_mode") or "auto"), "port_preferred": int(cfg.get("port", 8895) or 8895),
                    "port_auto_start": int(cfg.get("port", 8895) or 8895), "port_auto_end": min(65535, int(cfg.get("port", 8895) or 8895) + 100),
                    "show_spo2": bool(cfg.get("show_spo2", False)), "show_hr": bool(cfg.get("show_hr", False)),
                    "auto_scan_enabled": bool(cfg.get("auto_scan_enabled", True)),
                    "auto_scan_mode": cfg.get("auto_scan_mode", "interval"),
                    "auto_scan_interval_minutes": int(cfg.get("auto_scan_interval_minutes", 30) or 30),
                    "auto_scan_time": cfg.get("auto_scan_time", "06:00"),
                    "managed_data_dir": str(self.dataset.root),
                    "auto_scan_days": cfg.get("auto_scan_days") or [0,1,2,3,4,5,6],
                    "auto_scan_last_run": scan.get("last_run"), "auto_scan_next_run": scan.get("next_run"),
                    "tray_notifications": bool(cfg.get("tray_notifications", True)),
                    "start_with_windows": bool(cfg.get("start_with_windows", False)),
                    "auto_backup_enabled": bool(cfg.get("auto_backup_enabled", False)),
                    "auto_backup_mode": cfg.get("auto_backup_mode", "weekly"),
                    "auto_backup_time": cfg.get("auto_backup_time", "03:00"),
                    "auto_backup_weekday": int(cfg.get("auto_backup_weekday", 6) or 0),
                    "auto_backup_monthday": int(cfg.get("auto_backup_monthday", 1) or 1),
                    "auto_backup_dir": str(cfg.get("auto_backup_dir") or (STATE_BASE / "private" / "automatic_backups")),
                    "auto_backup_keep": int(cfg.get("auto_backup_keep", 5) or 5),
                    "auto_backup_last_run": backup_status.get("last_run"), "auto_backup_next_run": backup_status.get("next_run"),
                    "auto_backup_last_file": str(cfg.get("auto_backup_last_file") or ""),
                    "cloudflare_hostname": str(cfg.get("cloudflare_hostname") or ""),
                    "cloudflare_access_confirmed": bool(cfg.get("cloudflare_access_confirmed", False)),
                    "tailscale_auto_serve": bool(cfg.get("tailscale_auto_serve", False)),
                    "update_github_repo": str(cfg.get("update_github_repo") or ""),
                    "update_channel": str(cfg.get("update_channel") or "stable"),
                    "update_auto_check": bool(cfg.get("update_auto_check", True)),
                })
            if path == "/api/push/status":
                if not self.push_service:
                    return self._json({"available": False, "public_key": "", "subscriptions": 0, "dependency_error": "A Web Push szolgáltatás nem érhető el."}, 503)
                return self._json(self.push_service.status())
            if path == "/api/remote/status":
                cfg = load_config()
                rm = self.remote_manager
                if not rm:
                    return self._json({"error": "A távoli elérés modul nem érhető el."}, 503)
                return self._json({
                    "backend": {"host": "127.0.0.1", "port": int(rm.port), "local_only": True},
                    "tailscale": rm.tailscale_status(),
                    "cloudflare": {**rm.cloudflare_status(str(cfg.get("cloudflare_hostname") or "")), "access_confirmed": bool(cfg.get("cloudflare_access_confirmed", False))},
                    "pwa": {"ready": True, "requires_https_for_install": True},
                })
            if path == "/api/remote/tailscale/qr":
                rm = self.remote_manager
                if not rm:
                    return self._json({"error": "A távoli elérés modul nem érhető el."}, 503)
                status = rm.tailscale_status()
                url = str(status.get("url") or "").strip()
                if not (status.get("serve_active") and url.startswith("https://")):
                    return self._json({"error": "A Tailscale Serve HTTPS címe még nem érhető el. Előbb kapcsold be a Tailscale elérést."}, 409)
                try:
                    import io
                    import qrcode
                    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=3)
                    qr.add_data(url)
                    qr.make(fit=True)
                    img = qr.make_image(fill_color="black", back_color="white")
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    body = buf.getvalue()
                except ImportError:
                    return self._json({"error": "A QR-kód modul hiányzik. Futtasd a SleepMate_fuggosegek_telepitese.bat fájlt."}, 503)
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(body)
                return
            if path == "/api/system/status":
                return self._json(self._system_status_payload())
            if path == "/api/comparison":
                q = parse_qs(parsed.query)
                def one(name): return str(q.get(name, [""])[0])
                return self._json(self.dataset.compare_periods(one("a_start"), one("a_end"), one("b_start"), one("b_end")))
            if path == "/api/ai/config":
                return self._json(self.ai_store.get_provider_config())
            if path == "/api/ai/status":
                sig = self._ai_dataset_signature()
                return self._json({"dataset_signature": sig, **self.ai_store.usage_status(sig), **self.ai_store.get_provider_config(), "ui_prototype": False, "live_api": True})
            if path == "/api/ai/history":
                q = parse_qs(parsed.query)
                return self._json({"rows": self.ai_store.list_history(int(q.get("limit", ["100"])[0]))})
            if path.startswith("/api/ai/history/"):
                analysis_id = path.rsplit("/", 1)[-1]
                row = self.ai_store.get_analysis(analysis_id)
                if not row:
                    return self._json({"error": "A mentett AI-kiértékelés nem található."}, 404)
                # safe_payload intentionally stays server-side; the UI only needs the result + chat.
                public = {k:v for k,v in row.items() if k != "safe_payload"}
                return self._json(public)
            if path.startswith("/api/job/"):
                jid = path.rsplit("/", 1)[-1]
                job = self.jobs.get(jid)
                return self._json(job if job else {"error": "A művelet nem található."}, 200 if job else 404)
            if path == "/api/logs/history":
                q = parse_qs(parsed.query)
                return self._json({"rows": self.persistent_log.list(int(q.get("limit", ["250"])[0]))})
            if path == "/api/backup/download":
                q = parse_qs(parsed.query); jid = q.get("job", [""])[0]
                fp = self.backup_files.get(jid)
                if not fp or not fp.is_file():
                    return self._json({"error": "A backup fájl nem található vagy még nincs kész."}, 404)
                return self._send_file(fp, f"SleepMate_teljes_backup_{datetime_now_file()}.zip", "application/zip")
            if path == "/api/equipment":
                return self._json(self.dataset.equipment())
            if path == "/equipment-image":
                return self._equipment_image()
            if path == "/api/patient":
                return self._json(self.patient_store.all_data())
            if path == "/api/patient/export":
                return self._json(self.patient_store.export_bundle())
            if path == "/api/patient/security":
                return self._json(self.patient_store.security_info())
            if path == "/api/patient/photo":
                return self._patient_photo()
            if path == "/api/patient/therapy":
                q = parse_qs(parsed.query)
                period = q.get("period", ["30"])[0]
                return self._json(self.dataset.period_therapy_stats(period))
            if path == "/api/dashboard/overview":
                q = parse_qs(parsed.query)
                period = q.get("period", ["30"])[0]
                return self._json(self.dataset.dashboard_overview(period))
            if path == "/api/logs/diagnostics":
                return self._json(self.dataset.diagnostics())
            if path.startswith("/api/day/"):
                parts = [p for p in path.split("/") if p]
                # /api/day/YYYYMMDD
                if len(parts) == 3:
                    return self._json(self.dataset.summary(parts[2]))
                # /api/day/YYYYMMDD/stats
                if len(parts) == 4 and parts[3] == "stats":
                    return self._json(self.dataset.statistics(parts[2]))
                # /api/day/YYYYMMDD/signal/flow
                if len(parts) == 5 and parts[3] == "signal":
                    q = parse_qs(parsed.query)
                    max_points = int(q.get("max_points", ["8000"])[0])
                    max_points = min(20000, max(200, max_points))
                    range_start_s = float(q["range_start_s"][0]) if "range_start_s" in q else None
                    range_end_s = float(q["range_end_s"][0]) if "range_end_s" in q else None
                    return self._json(self.dataset.signal(
                        parts[2], parts[4], max_points=max_points,
                        range_start_s=range_start_s, range_end_s=range_end_s,
                    ))
            if path == "/api/refresh":
                source = str(load_config().get("data_dir") or "").strip()
                if not source:
                    raise FileNotFoundError("Nincs beállítva alapértelmezett ResMed beolvasási mappa.")
                before_days = self.dataset.days()
                before_latest = before_days[-1] if before_days else None
                with self._dataset_lock:
                    result = import_resmed_tree(source, self.dataset.root, authoritative=True)
                    self.dataset.refresh()
                result.update({"ok": True, "days": self.dataset.days(), "manual_data_preserved": True, "version": APP_VERSION})
                self.persistent_log.append("INFO", "refresh", "Azonnali adatfrissítés byte-pontos ellenőrzéssel lefutott.", result)
                self._push_after_refresh(before_latest, result, "Azonnali adatfrissítés")
                return self._json(result)
            if path.startswith("/api/"):
                return self._json({"error": f"Ismeretlen API végpont: {path}", "version": APP_VERSION}, 404)
            return self._static(path)
        except FileNotFoundError as e:
            return self._json({"error": str(e)}, 404)
        except KeyError as e:
            return self._json({"error": f"Ismeretlen adatsor: {e.args[0]}"}, 404)
        except Exception as e:
            return self._json({"error": str(e)}, 500)

    def _read_json_body(self, max_bytes=4_000_000):
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0 or length > max_bytes:
            raise ValueError("Hiányzó vagy túl nagy kérés.")
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _validate_source_dir(self, data_dir: str | Path):
        raw = Path(data_dir).expanduser()
        if not raw.exists():
            raise FileNotFoundError(f"A megadott beolvasási mappa nem található: {raw}")
        # Csak olvasási ellenőrzés: itt soha nem hozunk létre vagy módosítunk fájlt.
        from cpap.services import locate_resmed_root
        return locate_resmed_root(raw)

    def _progress(self, jid: str, progress: int, phase: str, message: str):
        self.jobs.update(jid, progress=max(0, min(100, int(progress))), phase=phase, message=message)

    @staticmethod
    def _changed_file_count(result: dict) -> int:
        total = 0
        for key in ("changed_files", "copied_files", "new_files"):
            value = result.get(key)
            if isinstance(value, (list, tuple, set, dict)):
                total += len(value)
            elif isinstance(value, (int, float)):
                total += int(value)
        return total

    @classmethod
    def _push_after_refresh(cls, before_latest: str | None, result: dict, reason: str = "Adatfrissítés") -> None:
        """Send server-side Web Push after a completed data refresh.

        Push delivery is deliberately derived from the final refreshed dataset,
        not from the browser, so it can work while the installed PWA is closed.
        """
        ps = cls.push_service
        if not ps:
            return
        try:
            days = cls.dataset.days()
            after_latest = days[-1] if days else None
            new_night = bool(after_latest and after_latest != before_latest)
            changed_count = cls._changed_file_count(result)
            if new_night:
                summary = cls.dataset.summary(after_latest)
                usage_minutes = int(round(float(summary.get("usage_minutes") or (float(summary.get("therapy_seconds") or 0) / 60))))
                hours, minutes = divmod(usage_minutes, 60)
                ahi = float(summary.get("ahi") or 0)
                ps.send(
                    "new_night",
                    "Új CPAP éjszaka feldolgozva",
                    f"{hours}:{minutes:02d} használat • AHI {ahi:.2f}",
                    f"/#dashboard/{after_latest}",
                    {"day": after_latest},
                )
            elif changed_count > 0:
                ps.send(
                    "data_update",
                    "SleepMate adatfrissítés kész",
                    "A megváltozott CPAP-adatok ellenőrizve és újra beolvasva.",
                    "/#dashboard",
                )

            # A diagnostic push means NEW/CHANGED data produced a warning. Merely
            # creating/restoring a backup or re-checking byte-identical files must
            # not re-send an old warning because the push meta DB was rolled back.
            if new_night or changed_count > 0:
                diag = cls.dataset.diagnostics()
                warning_rows = [x for x in (diag.get("errors") or []) if isinstance(x, dict)]
                if warning_rows:
                    normalized = [f"{str(x.get('title') or '').strip()}|{str(x.get('message') or '').strip()}" for x in warning_rows]
                    signature = hashlib.sha256("\n".join(sorted(normalized)).encode("utf-8")).hexdigest()
                    first = warning_rows[0]
                    title = str(first.get("title") or "Adatfigyelmeztetés").strip()
                    message = str(first.get("message") or "Ellenőrizd a Naplók oldalt.").strip()
                    body = f"{title} – {message}"
                    if len(warning_rows) > 1:
                        body += f" (+{len(warning_rows)-1} további figyelmeztetés)"
                    ps.send_warning_once(signature, "Adatfigyelmeztetés", body, "/#logs")
        except Exception as exc:
            try:
                cls.persistent_log.append("WARN", "push", "A frissítés utáni Web Push feldolgozás sikertelen.", {"reason": reason, "error": str(exc)})
            except Exception:
                pass

    def _refresh_job(self, jid: str, reason: str = "Azonnali adatfrissítés"):
        source = str(load_config().get("data_dir") or "").strip()
        if not source:
            raise FileNotFoundError("Nincs beállítva alapértelmezett ResMed beolvasási mappa.")
        before_days = self.dataset.days()
        before_latest = before_days[-1] if before_days else None
        self._progress(jid, 10, "Forrás ellenőrzése", "Az alapértelmezett ResMed mappa ellenőrzése…")
        def cb(p, ph, msg): self._progress(jid, 12 + int(p * .68), ph, msg)
        with self._dataset_lock:
            result = import_resmed_tree(source, self.dataset.root, cb, authoritative=True)
            self._progress(jid, 84, "Napok betöltése", "A változott terápiás napok újraolvasása…")
            self.dataset.refresh()
        diag = self.dataset.diagnostics()
        self._progress(jid, 94, "Integritásellenőrzés", f"{diag.get('edf_files',0)} EDF ellenőrizve.")
        result.update({"days": len(self.dataset.days()), "edf_files": diag.get("edf_files",0), "source_read_only": True, "manual_data_preserved": True})
        self.persistent_log.append("INFO", "refresh", reason, result)
        self._push_after_refresh(before_latest, result, reason)
        return result

    def _folder_import_job(self, jid: str, source: str, label: str = "Mappa import"):
        before_days = self.dataset.days()
        before_latest = before_days[-1] if before_days else None
        target = self.dataset.root
        def cb(p, ph, msg): self._progress(jid, max(3, min(88, int(p * .88))), ph, msg)
        with self._dataset_lock:
            result = import_resmed_tree(source, target, cb)
            self._progress(jid, 92, "Adatok frissítése", "A változott terápiás napok újraolvasása…")
            self.dataset.refresh()
        result["days"] = len(self.dataset.days())
        result["manual_data_preserved"] = True
        self._push_after_refresh(before_latest, result, label)
        return result

    def _sd_search_job(self, jid: str):
        before_days = self.dataset.days()
        before_latest = before_days[-1] if before_days else None
        self._progress(jid, 12, "Meghajtók keresése", "SD-kártya és kártyaolvasó keresése…")
        roots = find_resmed_sd()
        if not roots:
            raise FileNotFoundError("Nem található ResMed adatokat tartalmazó SD-kártya. Ellenőrizd, hogy a kártya be van-e dugva és látható-e a Windowsban.")
        self._progress(jid, 28, "Kártya megtalálva", f"Forrás: {roots[0]}")
        def cb(p, ph, msg): self._progress(jid, 30 + int(p * .64), ph, msg)
        with self._dataset_lock:
            result = import_resmed_tree(roots[0], self.dataset.root, cb)
            self._progress(jid, 96, "Adatok frissítése", "A változott terápiás napok újraolvasása…")
            self.dataset.refresh()
        result["days"] = len(self.dataset.days()); result["detected_sources"] = roots; result["manual_data_preserved"] = True
        self._push_after_refresh(before_latest, result, "SD-kártya keresés és import")
        return result

    def _zip_import_job(self, jid: str, zip_path: str):
        before_days = self.dataset.days()
        before_latest = before_days[-1] if before_days else None
        zp = Path(zip_path)
        with tempfile.TemporaryDirectory(prefix="cpap-zip-") as td:
            tmp = Path(td)
            def extract_cb(p, ph, msg): self._progress(jid, 35 + int(p * .28), ph, msg)
            safe_extract_zip(zp, tmp, extract_cb)
            self._progress(jid, 52, "ResMed adatok keresése", "DATALOG könyvtár azonosítása…")
            def copy_cb(p, ph, msg): self._progress(jid, 63 + int(p * .33), ph, msg)
            with self._dataset_lock:
                result = import_resmed_tree(tmp, self.dataset.root, copy_cb)
                self._progress(jid, 96, "Adatok frissítése", "A változott terápiás napok újraolvasása…")
                self.dataset.refresh()
        try: zp.unlink()
        except OSError: pass
        result["days"] = len(self.dataset.days())
        result["manual_data_preserved"] = True
        self._push_after_refresh(before_latest, result, "ZIP import")
        return result

    def _backup_job(self, jid: str):
        try:
            with self.patient_store._db() as con:
                con.execute("PRAGMA wal_checkpoint(FULL)")
        except Exception:
            pass
        out_dir = STATE_BASE / "private" / "backups"
        out = out_dir / f"SleepMate_teljes_backup_{datetime_now_file()}_{jid}.zip"
        def cb(p, ph, msg): self._progress(jid, p, ph, msg)
        result = create_full_backup(STATE_BASE, self.dataset.root, load_config(), out, cb)
        Handler.backup_files[jid] = out
        result["download_url"] = f"/api/backup/download?job={jid}"
        return result

    def _restore_backup_job(self, jid: str, uploaded: str):
        up = Path(uploaded)
        def cb(p, ph, msg): self._progress(jid, 35 + int(p * .62), ph, msg)
        # Full restore replaces private state, including the Web Push SQLite store.
        # Hold the push maintenance lock so no test/automatic push can open the DB
        # while Windows is restoring it. PushService itself now uses only explicitly
        # closed short-lived SQLite connections.
        ps = Handler.push_service
        if ps:
            with ps.maintenance():
                result = restore_full_backup(STATE_BASE, up, self.dataset.root, cb)
        else:
            result = restore_full_backup(STATE_BASE, up, self.dataset.root, cb)
        try: up.unlink()
        except OSError: pass
        Handler.patient_store = PatientStore(STATE_BASE)
        Handler.ai_store = AIStore(STATE_BASE)
        # Recreate the push service from the restored snapshot (or generate a new
        # empty push store when restoring a backup made before Web Push existed).
        Handler.push_service = PushService(STATE_BASE, Handler.persistent_log)
        self.dataset.refresh()
        saved = result.get("manifest", {}).get("config") or {}
        # A teljes rendszerbackup a teljes ismert SleepMate-konfigurációt állítja
        # vissza, nem csak a régi részhalmazt. Így a távoli elérés, automatikák,
        # megjelenítési és backup-beállítások is a mentett állapotot kapják.
        known_keys = set(load_config().keys())
        allowed = {k: v for k, v in saved.items() if k in known_keys}
        if allowed:
            save_config(allowed)
        return {
            "restored": result.get("restored", 0),
            "private_files": result.get("private_files", 0),
            "sqlite_databases": result.get("sqlite_databases", 0),
            "measurement_replaced": bool(result.get("measurement_replaced")),
            "days": len(self.dataset.days()),
        }

    def _delete_data_job(self, jid: str, options: dict):
        result = {"measurement_deleted": 0, "patient_deleted": False, "logs_deleted": False}
        if options.get("measurement"):
            managed = Path(self.dataset.root).resolve()
            expected = MANAGED_DATA_ROOT.resolve()
            if managed != expected:
                raise RuntimeError("Biztonsági védelem: mérési adat csak a program saját belső adattárából törölhető.")
            result["measurement_deleted"] = delete_measurement_data(managed, lambda p,ph,msg:self._progress(jid, int(p*.7), ph, msg))
            result["source_folder_untouched"] = True
            self.dataset.refresh()
        if options.get("patient"):
            self._progress(jid, 78, "Személyes adatok törlése", "A kezelt személy és felszerelési metaadatok törlése…")
            self.patient_store.delete_patient_only()
            result["patient_deleted"] = True
        if options.get("logs"):
            self._progress(jid, 88, "Naplók törlése", "A tartós rendszernapló ürítése…")
            self.persistent_log.clear()
            result["logs_deleted"] = True
        return result

    def _ai_dataset_signature(self) -> str:
        h = hashlib.sha256(dataset_signature(self.dataset.root).encode("ascii"))
        try:
            st = self.patient_store.db_path.stat()
            h.update(f"patient:{st.st_size}:{st.st_mtime_ns}".encode())
        except OSError:
            pass
        return h.hexdigest()

    @staticmethod
    def _seconds_to_hm(seconds: float) -> str:
        mins = int(round(float(seconds or 0) / 60))
        return f"{mins//60} ó {mins%60:02d} p"

    def _mock_ai_analysis(self, provider: str, analysis_type: str, month: str = "") -> dict:
        rows = list(self.dataset.day_table())
        if not rows:
            raise ValueError("Még nincs kiértékelhető terápiás adat.")
        rows = sorted(rows, key=lambda r: r.get("day", ""))
        if analysis_type == "night":
            selected = rows[-1:]
            label = "Előző alvás"
        elif analysis_type == "week":
            selected = rows[-7:]
            label = "Előző hét"
        elif analysis_type == "month":
            if not month:
                month = rows[-1]["date"][:7]
            selected = [r for r in rows if str(r.get("date", "")).startswith(month)]
            if not selected:
                raise ValueError("A kiválasztott hónapban nincs terápiás adat.")
            label = month
        else:
            selected = rows
            label = "Teljes terápiás időszak"
        therapy_seconds = sum(float(r.get("therapy_seconds") or 0) for r in selected)
        events = sum(int(r.get("events") or 0) for r in selected)
        ahi = (events / (therapy_seconds / 3600.0)) if therapy_seconds > 0 else 0.0
        leak_vals = [float(r["leak_p95"]) for r in selected if r.get("leak_p95") is not None]
        pressure_vals = [float(r["pressure_p95"]) for r in selected if r.get("pressure_p95") is not None]
        last = selected[-1]
        counts = {k: sum(int((r.get("counts") or {}).get(k) or 0) for r in selected) for k in ("OA", "CA", "H", "RERA", "UA")}
        cfg = self.ai_store.get_provider_config()["providers"][provider]
        ai_name = cfg["display_name"]
        status = "very_good" if ahi < 1 else ("good" if ahi < 5 else "attention")
        status_hu = {"very_good":"nagyon jó", "good":"jó", "attention":"figyelmet érdemlő"}[status]
        leak_p95 = (sum(leak_vals)/len(leak_vals)) if leak_vals else None
        pressure_p95 = (sum(pressure_vals)/len(pressure_vals)) if pressure_vals else None
        period_start, period_end = selected[0].get("date"), selected[-1].get("date")
        summary = (
            f"A vizsgált időszak PAP-terápiája összességében {status_hu} képet mutat. "
            f"A terápiás idővel súlyozott AHI {ahi:.2f}/óra, {len(selected)} terápiás nap alapján. "
            + (f"A szivárgás 95%-os szintje átlagosan {leak_p95:.1f} L/perc körül alakult. " if leak_p95 is not None else "")
            + "Ez a v2.0 élő AI-modul mintaszövege; valódi AI-értelmezés a következő fejlesztési lépésben kerül mögé."
        )
        positives=[]
        if ahi < 5: positives.append(f"Az összesített AHI {ahi:.2f}/óra, ami a vizsgált saját adatokban kedvező kontrollt jelez.")
        if counts["CA"] == 0: positives.append("A vizsgált időszakban nem látható centrális apnoe esemény a rendelkezésre álló adatokban.")
        if therapy_seconds >= len(selected)*4*3600: positives.append("Az átlagos használati idő eléri a napi 4 órát.")
        attention=[]
        if therapy_seconds < len(selected)*4*3600: attention.append("A használati idő néhány/összes vizsgált napon 4 óra alatt maradhat; ezt érdemes a saját alvási idővel együtt értelmezni.")
        if counts["OA"] > 0: attention.append(f"Obstruktív eseményből összesen {counts['OA']} került rögzítésre; az időbeli eloszlásuk a részletes elemzésben vizsgálandó.")
        if leak_p95 is None: attention.append("Nincs elegendő szivárgási statisztika a teljes időszakhoz.")
        recs=[
            {"priority":"low", "type":"monitor", "text":"A következő napok saját trendjeit érdemes ugyanilyen feltételek mellett tovább követni."},
            {"priority":"low", "type":"data", "text":"SpO₂ és pulzusadat később pontosíthatja az események élettani jelentőségének megítélését."},
        ]
        return {
            "analysis_type": analysis_type,
            "provider": provider,
            "ai_name": ai_name,
            "prototype": True,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "period": {"label": label, "start": period_start, "end": period_end, "days": len(selected)},
            "overall": {"status": status, "title": f"{ai_name}: {status_hu.capitalize()} terápiás kép", "summary": summary},
            "therapy_effectiveness": {"text": f"A súlyozott AHI {ahi:.2f}/óra. A vizsgált időszak teljes használata {self._seconds_to_hm(therapy_seconds)}, {len(selected)} terápiás napból.", "confidence":"high"},
            "events": {"text": f"OA: {counts['OA']}, CA: {counts['CA']}, H: {counts['H']}, RERA: {counts['RERA']}, UA: {counts['UA']}. Az eseménytípusokat külön kell értelmezni, nem csak az összesített AHI-t.", "confidence":"high"},
            "pressure": {"text": (f"A napi 95%-os nyomásértékek átlaga {pressure_p95:.2f} cmH₂O. A következő verzióban az AI az időbeli nyomásmintázatokat és az eseményekkel való együttmozgást is értelmezi." if pressure_p95 is not None else "Nincs elegendő nyomásadat ehhez a szekcióhoz."), "confidence":"medium"},
            "leak": {"text": (f"A napi szivárgás P95 értékek átlaga {leak_p95:.1f} L/perc. A tényleges AI később a leak-epizódok időbeli mintázatát is vizsgálja." if leak_p95 is not None else "Nincs elegendő szivárgási adat ehhez a szekcióhoz."), "confidence":"high" if leak_p95 is not None else "low"},
            "trends": [{"title":"Saját adatokhoz viszonyítás", "text":"A végleges AI-réteg elsődlegesen a saját előző éjszakához, 7 és 30 napos átlaghoz fog viszonyítani.", "confidence":"medium"}],
            "positives": positives or ["A rendelkezésre álló adatok feldolgozhatók."],
            "attention_points": attention or ["A jelenlegi adatok alapján nincs kiemelt figyelmeztetés a demó-szabályok szerint."],
            "recommendations": recs,
            "medical_review": {"suggested": False, "reason": None},
            "data_quality": {"sufficient": True, "missing_useful_data": [] if last.get("spo2") is not None else ["SpO₂ / pulzus"]},
            "metrics": {"ahi": round(ahi,2), "therapy_seconds": therapy_seconds, "events": events, "counts": counts, "leak_p95": leak_p95, "pressure_p95": pressure_p95},
        }

    def _mock_ai_chat_reply(self, provider: str, question: str) -> str:
        cfg = self.ai_store.get_provider_config()["providers"][provider]
        name = cfg["display_name"]
        q = question.strip().lower()
        if "sziv" in q or "leak" in q:
            core = "A szivárgást önmagában nem egyetlen maximum alapján érdemes megítélni; a P95, az időtartam és az eseményekkel való időbeli együttmozgás fontosabb."
        elif "nyom" in q:
            core = "A nyomásnál a medián és a 95%-os érték együtt mutatja, hogy a gép jellemzően hol dolgozik és mennyire gyakran igényel magasabb nyomást."
        elif "ahi" in q or "apno" in q:
            core = "Az AHI hasznos összesítő, de az OA, CA, H és RERA külön bontása nélkül könnyű félreérteni, mi adja az értéket."
        else:
            core = "A válaszomat a kiértékelés kontextusához kell majd kötni, és csak a rendelkezésre álló anonim terápiás adatokból szabad következtetnem."
        return f"{name}: {core} Ez még a v2.0 élő AI-modul válasza; a valódi szolgáltatói chat a prompt- és API-réteg bekötésekor kerül mögé."

    @staticmethod
    def _parse_ai_json(raw: str) -> dict:
        text = str(raw or "").strip()
        if text.startswith("```"):
            text = text.strip("`").strip()
            if text.lower().startswith("json"):
                text = text[4:].lstrip()
        first, last = text.find("{"), text.rfind("}")
        if first >= 0 and last > first:
            text = text[first:last+1]
        try:
            obj = json.loads(text)
        except Exception as exc:
            raise ValueError("Az AI válasza nem feldolgozható strukturált JSON-ként. Próbáld újra, vagy válts szolgáltatót.") from exc
        if not isinstance(obj, dict):
            raise ValueError("Az AI válasza nem a várt objektumformátumú.")
        return obj

    @staticmethod
    def _friendly_ai_title(title: str, status: str, analysis_type: str) -> str:
        text = str(title or "").strip()
        lower = text.lower()
        english_markers = ("therapy", "performance", "summary", "analysis", "for 20", "cpap therapy", "pap therapy")
        if text and not any(x in lower for x in english_markers):
            return text
        by_status = {
            "very_good": "A terápia stabil és eredményes",
            "good": "A terápia összességében eredményes",
            "acceptable": "A terápia megfelelő, néhány érték figyelmet érdemel",
            "attention": "Több terápiás érték is figyelmet érdemel",
            "unfavorable": "A terápiás eredmények felülvizsgálatra érdemesek",
        }
        return by_status.get(str(status or "acceptable"), "A terápia aktuális összképe")

    def _normalize_ai_result(self, obj: dict, provider: str, analysis_type: str, meta: dict, model: str, fallback_used: bool) -> dict:
        cfg = self.ai_store.get_provider_config()["providers"][provider]
        overall = obj.get("overall") if isinstance(obj.get("overall"), dict) else {}
        live = str(obj.get("live_text") or overall.get("summary") or "").strip()
        overall.setdefault("summary", live)
        overall.setdefault("status", "acceptable")
        overall["title"] = self._friendly_ai_title(overall.get("title"), overall.get("status"), analysis_type)
        obj["overall"] = overall
        obj["analysis_type"] = analysis_type
        obj["provider"] = provider
        obj["ai_name"] = cfg.get("display_name") or ("Luna" if provider == "gemini" else "Milo")
        obj["generated_at"] = datetime.now().isoformat(timespec="seconds")
        obj["period"] = {
            "label": analysis_type,
            "start": meta.get("period_start"),
            "end": meta.get("period_end"),
            "days": meta.get("therapy_days", 0),
        }
        obj["model"] = model
        obj["fallback_used"] = bool(fallback_used)
        obj["prompt_version"] = PROMPT_VERSION
        for key in ("positives", "attention_points", "recommendations", "trends"):
            if not isinstance(obj.get(key), list): obj[key] = []
        if not isinstance(obj.get("data_quality"), dict): obj["data_quality"] = {"sufficient": True, "missing_useful_data": []}
        return obj

    def _begin_ndjson(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Connection", "close")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.close_connection = True

    def _ndjson_event(self, obj: dict):
        self.wfile.write((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))
        self.wfile.flush()

    def _ai_provider_debug(self, provider: str, model: str | None = None, api_key: str | None = None) -> dict:
        cfg_all = self.ai_store.get_provider_config().get("providers", {})
        cfg = cfg_all.get(provider, {}) if isinstance(cfg_all, dict) else {}
        key = api_key if api_key is not None else self.ai_store.get_api_key(provider)
        return {
            "provider": provider,
            "provider_label": cfg.get("provider_label") or ("Google Gemini" if provider == "gemini" else "Groq"),
            "display_name": cfg.get("display_name") or ("Luna" if provider == "gemini" else "Milo"),
            "model": model or self.ai_store.provider_model(provider),
            "key_source": cfg.get("key_source") or "unknown",
            "key_hint": cfg.get("key_hint") or "",
            "key_fingerprint": cfg.get("key_fingerprint") or (hashlib.sha256(key.encode("utf-8")).hexdigest()[:12] if key else ""),
            "endpoint": "https://generativelanguage.googleapis.com/v1beta/models/...:streamGenerateContent" if provider == "gemini" else "https://api.groq.com/openai/v1/chat/completions",
            "transport": "gemini_http_sse" if provider == "gemini" else groq_transport_name(),
        }

    def _ai_log(self, level: str, event: str, message: str, details: dict | None = None) -> None:
        safe = dict(details or {})
        for forbidden in ("api_key", "system_prompt", "user_prompt", "prompt", "question", "safe_payload"):
            safe.pop(forbidden, None)
        safe["event"] = event
        self.persistent_log.append(level, "ai", message, safe)

    def _ai_test_provider(self, data: dict) -> dict:
        provider = str(data.get("provider") or "groq").lower()
        if provider not in {"gemini", "groq"}:
            raise ValueError("Ismeretlen AI szolgáltató.")
        api_key = self.ai_store.get_api_key(provider)
        model = self.ai_store.provider_model(provider)
        dbg = self._ai_provider_debug(provider, model, api_key)
        request_id = "aitest-" + hashlib.sha256(f"{time.time_ns()}-{provider}".encode()).hexdigest()[:10]
        start = time.perf_counter()
        self._ai_log("INFO", "provider_test_start", "AI kapcsolat teszt indult.", {**dbg, "request_id": request_id, "json_mode": False, "timeout_s": 60})
        if not api_key:
            self._ai_log("HIBA", "provider_test_error", "AI kapcsolat teszt sikertelen: nincs API-kulcs.", {**dbg, "request_id": request_id})
            raise AIProviderError(("Gemini" if provider == "gemini" else "Groq") + ": Nincs beállított API-kulcs.", transient=False)
        chunks = []
        try:
            system = "Ez kizárólag technikai kapcsolatellenőrzés. Ne adj egészségügyi tanácsot."
            user = "Válaszolj pontosan ennyit: SLEEPMATE AI MŰKÖDIK"
            for delta in stream_provider(provider, api_key, model, system, user, json_mode=False, timeout=60):
                chunks.append(delta)
                if sum(map(len, chunks)) > 500:
                    break
            text = ''.join(chunks).strip()
            ms = int((time.perf_counter() - start) * 1000)
            self._ai_log("INFO", "provider_test_success", "AI kapcsolat teszt sikeres.", {**dbg, "request_id": request_id, "response_ms": ms, "response_chars": len(text), "response_preview": text[:180]})
            return {"ok": True, "provider": provider, "model": model, "response": text[:500], "response_ms": ms, "key_source": dbg["key_source"], "key_hint": dbg["key_hint"], "key_fingerprint": dbg["key_fingerprint"]}
        except AIProviderError as exc:
            ms = int((time.perf_counter() - start) * 1000)
            self._ai_log("HIBA", "provider_test_error", "AI kapcsolat teszt API-hibával leállt.", {**dbg, "request_id": request_id, "response_ms": ms, "http_status": exc.status, "transient": exc.transient, "provider_error_type": getattr(exc, "remote_type", None), "provider_error_code": getattr(exc, "remote_code", None), "provider_error_detail": getattr(exc, "remote_detail", None), "error_type": type(exc).__name__, "error": str(exc)})
            raise
        except Exception as exc:
            ms = int((time.perf_counter() - start) * 1000)
            self._ai_log("HIBA", "provider_test_error", "AI kapcsolat teszt váratlan hibával leállt.", {**dbg, "request_id": request_id, "response_ms": ms, "error_type": type(exc).__name__, "error": str(exc)})
            raise

    def _prepare_analysis_prompt(self, data: dict) -> dict:
        provider = str(data.get("provider") or "gemini").lower()
        analysis_type = str(data.get("analysis_type") or "night")
        month = str(data.get("month") or "").strip()
        if provider not in {"gemini", "groq"}: raise ValueError("Ismeretlen AI szolgáltató.")
        if analysis_type not in {"night", "week", "month", "full_period", "comparison"}: raise ValueError("Ismeretlen kiértékelési mód.")
        comparison = data.get("comparison") if isinstance(data.get("comparison"), dict) else {}
        if analysis_type == "comparison":
            parts = [str(comparison.get(k) or "") for k in ("a_start","a_end","b_start","b_end")]
            if not all(parts): raise ValueError("Az összehasonlításhoz add meg mindkét időszak kezdő és záró dátumát.")
            analysis_key = "comparison:" + ":".join(parts)
        else:
            analysis_key = analysis_type + ((":" + month) if analysis_type == "month" and month else "")
        if analysis_type == "comparison":
            safe_payload, meta = build_comparison_payload(self.dataset, self.patient_store, comparison)
        else:
            safe_payload, meta = build_safe_payload(self.dataset, self.patient_store, analysis_type, month)
        system_prompt, user_prompt = analysis_prompts(analysis_type, safe_payload)
        return {
            "provider": provider,
            "analysis_type": analysis_type,
            "analysis_key": analysis_key,
            "safe_payload": safe_payload,
            "meta": meta,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
        }

    def _analysis_prompt_export(self, data: dict) -> dict:
        prepared = self._prepare_analysis_prompt(data)
        # The anonymous therapy payload is built once in _prepare_analysis_prompt.
        # Luna/Milo keep their strict JSON contract, while external AI receives a
        # presentation layer aimed at the SleepMate user.
        full_prompt = external_analysis_prompt(prepared["analysis_type"], prepared["safe_payload"])
        meta = prepared["meta"]
        stamp = str(meta.get("period_end") or datetime.now().date().isoformat())
        kind = {
            "night": "napi_elemzes", "week": "heti_elemzes", "month": "havi_elemzes",
            "full_period": "teljes_idoszak", "comparison": "idoszak_osszehasonlitas",
        }[prepared["analysis_type"]]
        return {
            "ok": True,
            "analysis_type": prepared["analysis_type"],
            "analysis_key": prepared["analysis_key"],
            "period": meta,
            "prompt_version": PROMPT_VERSION,
            "prompt": full_prompt,
            "filename": f"SleepMate_{kind}_{stamp}_prompt.txt",
        }

    def _live_analysis_stream(self, data: dict):
        prepared = self._prepare_analysis_prompt(data)
        provider = prepared["provider"]
        analysis_type = prepared["analysis_type"]
        analysis_key = prepared["analysis_key"]
        safe_payload = prepared["safe_payload"]
        meta = prepared["meta"]
        system_prompt = prepared["system_prompt"]
        user_prompt = prepared["user_prompt"]
        sig = self._ai_dataset_signature()
        ok, reason = self.ai_store.can_analyze(analysis_key, sig)
        if not ok:
            raise ValueError(reason)
        selected_provider = provider
        actual_provider = selected_provider
        fallback_used = False
        raw = ""
        start = time.perf_counter()
        request_id = "aia-" + hashlib.sha256(f"{time.time_ns()}-{analysis_key}-{selected_provider}".encode()).hexdigest()[:10]
        self._ai_log("INFO", "analysis_requested", "AI kiértékelés indult.", {
            "request_id": request_id, "selected_provider": selected_provider, "analysis_type": analysis_type, "analysis_key": analysis_key,
            "dataset_signature": sig[:16], "prompt_version": PROMPT_VERSION, "system_prompt_chars": len(system_prompt), "user_prompt_chars": len(user_prompt),
            "safe_payload_bytes": len(json.dumps(safe_payload, ensure_ascii=False).encode("utf-8")), "period": meta,
        })
        self._begin_ndjson()
        self._ndjson_event({"type":"start","provider":selected_provider,"analysis_key":analysis_key,"period":meta})
        try:
            while True:
                api_key = self.ai_store.get_api_key(actual_provider)
                if not api_key:
                    raise AIProviderError(("Gemini" if actual_provider == "gemini" else "Groq") + ": Nincs beállított API-kulcs.", transient=False)
                model = self.ai_store.provider_model(actual_provider)
                dbg = self._ai_provider_debug(actual_provider, model, api_key)
                call_start = time.perf_counter(); chunks = 0
                self._ai_log("INFO", "provider_call_start", "AI szolgáltatói hívás indult.", {**dbg, "request_id": request_id, "operation": "analysis", "analysis_key": analysis_key, "json_mode": True, "reasoning_effort": "medium" if model.startswith("openai/gpt-oss-") else None, "timeout_s": 150, "fallback_used": fallback_used})
                try:
                    self._ndjson_event({"type":"provider","provider":actual_provider,"model":model,"fallback_used":fallback_used})
                    for delta in stream_provider(actual_provider, api_key, model, system_prompt, user_prompt, json_mode=True, timeout=150):
                        chunks += 1
                        raw += delta
                        self._ndjson_event({"type":"delta","text":delta})
                    self._ai_log("INFO", "provider_call_success", "AI szolgáltatói hívás sikeres.", {**dbg, "request_id": request_id, "operation": "analysis", "chunks": chunks, "response_chars": len(raw), "response_ms": int((time.perf_counter()-call_start)*1000), "fallback_used": fallback_used})
                    break
                except AIProviderError as exc:
                    self._ai_log("HIBA", "provider_call_error", "AI szolgáltatói hívás API-hibával leállt.", {**dbg, "request_id": request_id, "operation": "analysis", "http_status": exc.status, "transient": exc.transient, "provider_error_type": getattr(exc, "remote_type", None), "provider_error_code": getattr(exc, "remote_code", None), "provider_error_detail": getattr(exc, "remote_detail", None), "error_type": type(exc).__name__, "error": str(exc), "response_ms": int((time.perf_counter()-call_start)*1000), "fallback_used": fallback_used})
                    if actual_provider == "gemini" and exc.transient and self.ai_store.get_api_key("groq"):
                        actual_provider = "groq"; fallback_used = True; raw = ""
                        self._ai_log("WARN", "fallback", "Gemini → Groq fallback aktiválva.", {"request_id": request_id, "from_provider": "gemini", "to_provider": "groq", "reason": str(exc)})
                        self._ndjson_event({"type":"fallback","provider":"groq","message":"Luna szolgáltatója átmenetileg nem elérhető. Milo / Groq veszi át a kiértékelést."})
                        continue
                    raise
            try:
                obj = self._parse_ai_json(raw)
                self._ai_log("INFO", "response_parse_success", "AI válasz strukturált feldolgozása sikeres.", {"request_id": request_id, "provider": actual_provider, "response_chars": len(raw)})
            except Exception as parse_exc:
                self._ai_log("HIBA", "response_parse_error", "AI válasz strukturált feldolgozása sikertelen.", {"request_id": request_id, "provider": actual_provider, "response_chars": len(raw), "error_type": type(parse_exc).__name__, "error": str(parse_exc), "response_preview": raw[:240]})
                raise
            model = self.ai_store.provider_model(actual_provider)
            result = self._normalize_ai_result(obj, actual_provider, analysis_type, meta, model, fallback_used)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            saved = self.ai_store.save_analysis(actual_provider, analysis_key, sig, result, safe_payload, {
                "model": model, "fallback_used": fallback_used, "prompt_version": PROMPT_VERSION,
                "period_start": meta.get("period_start"), "period_end": meta.get("period_end"),
                "session_count": meta.get("session_count"), "response_ms": elapsed_ms,
            })
            self._ai_log("INFO", "analysis_saved", "AI kiértékelés elkészült és mentve.", {"request_id": request_id, "provider": actual_provider, "model": model, "analysis_type": analysis_type, "analysis_key": analysis_key, "analysis_id": saved["id"], "response_ms": elapsed_ms, "fallback_used": fallback_used})
            self._ndjson_event({"type":"final","analysis_id":saved["id"],"result":result,"usage":self.ai_store.usage_status(sig)})
        except Exception as exc:
            self._ai_log("HIBA", "analysis_failed", "AI kiértékelés sikertelen.", {"request_id": request_id, "selected_provider": selected_provider, "actual_provider": actual_provider, "analysis_type": analysis_type, "analysis_key": analysis_key, "error_type": type(exc).__name__, "error": str(exc), "response_ms": int((time.perf_counter()-start)*1000)})
            self._ndjson_event({"type":"error","message":str(exc)})

    def _live_chat_stream(self, data: dict):
        analysis_id = str(data.get("analysis_id") or "").strip()
        question = str(data.get("question") or "").strip()
        if not analysis_id: raise ValueError("Nincs kiválasztott mentett AI-kiértékelés.")
        if not question: raise ValueError("Írj be egy kérdést.")
        if len(question) > 2000: raise ValueError("A kérdés túl hosszú.")
        analysis = self.ai_store.get_analysis(analysis_id)
        if not analysis: raise ValueError("A mentett AI-kiértékelés nem található.")
        provider = str(analysis.get("provider") or "gemini")
        ok, reason, status = self.ai_store.can_chat(provider)
        if not ok: raise ValueError(reason)
        system_prompt, user_prompt = chat_prompts(analysis, question)
        actual_provider = provider
        fallback_used = False
        answer = ""
        request_id = "aic-" + hashlib.sha256(f"{time.time_ns()}-{analysis_id}-{provider}".encode()).hexdigest()[:10]
        chat_start = time.perf_counter()
        self._ai_log("INFO", "chat_requested", "AI chat kérdés indult.", {"request_id": request_id, "analysis_id": analysis_id, "selected_provider": provider, "question_chars": len(question), "remaining_before": status.get("remaining"), "history_messages": len(analysis.get("messages") or [])})
        self._begin_ndjson()
        self._ndjson_event({"type":"start","provider":provider,"remaining":status.get("remaining")})
        try:
            while True:
                api_key = self.ai_store.get_api_key(actual_provider)
                if not api_key:
                    raise AIProviderError(("Gemini" if actual_provider == "gemini" else "Groq") + ": Nincs beállított API-kulcs.", transient=False)
                model = self.ai_store.provider_model(actual_provider)
                dbg = self._ai_provider_debug(actual_provider, model, api_key)
                call_start = time.perf_counter(); chunks = 0
                self._ai_log("INFO", "provider_call_start", "AI szolgáltatói hívás indult.", {**dbg, "request_id": request_id, "operation": "chat", "analysis_id": analysis_id, "json_mode": False, "reasoning_effort": "medium" if model.startswith("openai/gpt-oss-") else None, "timeout_s": 120, "fallback_used": fallback_used})
                try:
                    for delta in stream_provider(actual_provider, api_key, model, system_prompt, user_prompt, json_mode=False, timeout=120):
                        chunks += 1
                        answer += delta
                        self._ndjson_event({"type":"delta","text":delta})
                    self._ai_log("INFO", "provider_call_success", "AI szolgáltatói hívás sikeres.", {**dbg, "request_id": request_id, "operation": "chat", "analysis_id": analysis_id, "chunks": chunks, "response_chars": len(answer), "response_ms": int((time.perf_counter()-call_start)*1000), "fallback_used": fallback_used})
                    break
                except AIProviderError as exc:
                    self._ai_log("HIBA", "provider_call_error", "AI szolgáltatói hívás API-hibával leállt.", {**dbg, "request_id": request_id, "operation": "chat", "analysis_id": analysis_id, "http_status": exc.status, "transient": exc.transient, "provider_error_type": getattr(exc, "remote_type", None), "provider_error_code": getattr(exc, "remote_code", None), "provider_error_detail": getattr(exc, "remote_detail", None), "error_type": type(exc).__name__, "error": str(exc), "response_ms": int((time.perf_counter()-call_start)*1000), "fallback_used": fallback_used})
                    if actual_provider == "gemini" and exc.transient and self.ai_store.get_api_key("groq"):
                        actual_provider = "groq"; fallback_used = True; answer = ""
                        self._ai_log("WARN", "fallback", "Gemini → Groq fallback aktiválva chat közben.", {"request_id": request_id, "analysis_id": analysis_id, "from_provider": "gemini", "to_provider": "groq", "reason": str(exc)})
                        self._ndjson_event({"type":"fallback","provider":"groq","message":"Luna kapcsolata megszakadt; Milo / Groq folytatja a választ."})
                        continue
                    raise
            self.ai_store.append_chat(analysis_id, "user", question)
            self.ai_store.append_chat(analysis_id, "assistant", answer, actual_provider)
            usage = self.ai_store.record_chat_question(actual_provider)
            self._ai_log("INFO", "chat_saved", "AI chat válasz elkészült és mentve.", {"request_id": request_id, "analysis_id": analysis_id, "provider": actual_provider, "model": self.ai_store.provider_model(actual_provider), "response_chars": len(answer), "response_ms": int((time.perf_counter()-chat_start)*1000), "fallback_used": fallback_used, "remaining_after": usage.get("remaining")})
            self._ndjson_event({"type":"final","provider":actual_provider,"fallback_used":fallback_used,"usage":usage})
        except Exception as exc:
            self._ai_log("HIBA", "chat_failed", "AI chat kérdés sikertelen.", {"request_id": request_id, "analysis_id": analysis_id, "selected_provider": provider, "actual_provider": actual_provider, "question_chars": len(question), "error_type": type(exc).__name__, "error": str(exc), "response_ms": int((time.perf_counter()-chat_start)*1000)})
            self._ndjson_event({"type":"error","message":str(exc)})

    def _pick_folder(self, initial_dir: str | None = None):
        """Open the native folder chooser only after an explicit UI button click.

        Never use the process TEMP directory as an implicit start location: that can
        look as if SleepMate opened a random Temp folder on the desktop.
        """
        try:
            import tkinter as tk
            from tkinter import filedialog
            initial = str(initial_dir or "").strip()
            if not initial or not Path(initial).expanduser().exists():
                cfg_dir = str(load_config().get("data_dir") or "").strip()
                initial = cfg_dir if cfg_dir and Path(cfg_dir).expanduser().exists() else str(Path.home())
            root = tk.Tk(); root.withdraw()
            try: root.attributes('-topmost', True)
            except Exception: pass
            try:
                folder = filedialog.askdirectory(title="CPAP / ResMed mappa kiválasztása", initialdir=initial)
            finally:
                root.destroy()
            return folder or ""
        except Exception as exc:
            raise RuntimeError(f"A Windows mappaválasztó nem nyitható meg: {exc}")

    def _start_job(self, kind: str, label: str, fn, *args):
        jid = self.jobs.create(kind, label)
        self.jobs.start(jid, fn, *args)
        return jid

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/report/pdf":
                data = self._read_json_body(max_bytes=500_000)
                start = str(data.get("start") or "").strip()
                end = str(data.get("end") or "").strip()
                if not start or not end:
                    raise ValueError("Add meg a jelentés kezdő és záró dátumát.")
                cfg = data.get("config") if isinstance(data.get("config"), dict) else {}
                report_dir = STATE_BASE / "private" / "reports"
                report_dir.mkdir(parents=True, exist_ok=True)
                stamp = datetime_now_file()
                tmp = report_dir / f"SleepMate_report_{stamp}.pdf"
                generate_report_pdf(self.dataset, self.patient_store, start, end, cfg, RESOURCE_BASE, tmp)
                safe_start = start.replace("-", ".")
                safe_end = end.replace("-", ".")
                name = f"SleepMate_PAP_jelentes_{safe_start}-{safe_end}.pdf"
                inline = bool(data.get("preview"))
                try:
                    return self._send_pdf_file(tmp, name, inline=inline)
                finally:
                    try: tmp.unlink(missing_ok=True)
                    except Exception: pass
            if path == "/api/remote/config":
                data = self._read_json_body(max_bytes=100_000)
                rm = self.remote_manager
                if not rm: raise RuntimeError("A távoli elérés modul nem érhető el.")
                cfg_update = {}
                if "cloudflare_hostname" in data:
                    host_name = str(data.get("cloudflare_hostname") or "").strip().lower()
                    if host_name.startswith("http://") or host_name.startswith("https://"):
                        host_name = urlparse(host_name).hostname or ""
                    if host_name and (" " in host_name or "." not in host_name):
                        raise ValueError("Adj meg érvényes Cloudflare hostnevet, például sleepmate.pelda.hu.")
                    cfg_update["cloudflare_hostname"] = host_name
                if "cloudflare_access_confirmed" in data:
                    cfg_update["cloudflare_access_confirmed"] = bool(data.get("cloudflare_access_confirmed"))
                if "cloudflare_token" in data or data.get("cloudflare_clear_token"):
                    rm.save_cloudflare_token(str(data.get("cloudflare_token") or ""), bool(data.get("cloudflare_clear_token")))
                if cfg_update: save_config(cfg_update)
                cfg_now = load_config()
                return self._json({"ok": True, "status": {
                    "tailscale": rm.tailscale_status(),
                    "cloudflare": {**rm.cloudflare_status(str(cfg_now.get("cloudflare_hostname") or "")), "access_confirmed": bool(cfg_now.get("cloudflare_access_confirmed", False))}
                }})
            if path == "/api/remote/install":
                data = self._read_json_body(max_bytes=20_000)
                component = str(data.get("component") or "").strip().lower()
                rm = self.remote_manager
                if not rm: raise RuntimeError("A távoli elérés modul nem érhető el.")
                if component == "tailscale":
                    result = rm.install_tailscale()
                elif component in {"cloudflare", "cloudflared"}:
                    result = rm.install_cloudflared()
                else:
                    raise ValueError("Ismeretlen telepítendő távoli elérési komponens.")
                return self._json({"ok": bool(result.get("ok")), "component": component, "result": result})
            if path == "/api/remote/tailscale":
                data = self._read_json_body(max_bytes=20_000)
                action = str(data.get("action") or "status")
                rm = self.remote_manager
                if not rm: raise RuntimeError("A távoli elérés modul nem érhető el.")
                if action == "enable":
                    result = rm.tailscale_enable()
                    if result.get("serve_active"):
                        save_config({"tailscale_auto_serve": True})
                elif action == "disable":
                    result = rm.tailscale_disable()
                    save_config({"tailscale_auto_serve": False})
                else:
                    result = rm.tailscale_status()
                return self._json({"ok": True, "tailscale": result, "auto_serve": bool(load_config().get("tailscale_auto_serve", False))})
            if path == "/api/remote/cloudflare":
                data = self._read_json_body(max_bytes=20_000)
                action = str(data.get("action") or "status")
                cfg_now = load_config(); hostname = str(cfg_now.get("cloudflare_hostname") or "")
                rm = self.remote_manager
                if not rm: raise RuntimeError("A távoli elérés modul nem érhető el.")
                if action == "start":
                    if not hostname:
                        raise ValueError("A Cloudflare Tunnel indításához add meg a publikus hostnevet.")
                    if not bool(cfg_now.get("cloudflare_access_confirmed", False)):
                        raise ValueError("Biztonsági védelem: előbb igazold, hogy a Cloudflare Access / Zero Trust védelem be van állítva a hostname elé.")
                    result = rm.cloudflare_start(hostname)
                else:
                    result = rm.cloudflare_stop(hostname) if action == "stop" else rm.cloudflare_status(hostname)
                return self._json({"ok": True, "cloudflare": {**result, "access_confirmed": bool(cfg_now.get("cloudflare_access_confirmed", False))}})
            if path == "/api/push/subscribe":
                if not self.push_service: raise RuntimeError("A Web Push szolgáltatás nem érhető el.")
                data = self._read_json_body(max_bytes=100_000)
                subscription = data.get("subscription") if isinstance(data.get("subscription"), dict) else data
                prefs = data.get("preferences") if isinstance(data.get("preferences"), dict) else None
                origin = str(data.get("origin") or self.headers.get("Origin") or "").strip()
                result = self.push_service.subscribe(subscription, prefs, self.headers.get("User-Agent", ""), origin=origin)
                return self._json({**result, "status": self.push_service.status()})
            if path == "/api/push/unsubscribe":
                if not self.push_service: raise RuntimeError("A Web Push szolgáltatás nem érhető el.")
                data = self._read_json_body(max_bytes=100_000)
                return self._json(self.push_service.unsubscribe(str(data.get("endpoint") or "")))
            if path == "/api/push/preferences":
                if not self.push_service: raise RuntimeError("A Web Push szolgáltatás nem érhető el.")
                data = self._read_json_body(max_bytes=100_000)
                return self._json(self.push_service.update_preferences(str(data.get("endpoint") or ""), data.get("preferences") or {}))
            if path == "/api/push/test":
                if not self.push_service: raise RuntimeError("A Web Push szolgáltatás nem érhető el.")
                data = self._read_json_body(max_bytes=100_000)
                endpoint = str(data.get("endpoint") or "").strip() or None
                result = self.push_service.send(
                    "test",
                    "SleepMate próbaértesítés",
                    "A valódi Web Push kapcsolat működik ezen az eszközön.",
                    "/#settings",
                    {"requested": True},
                    endpoint=endpoint,
                )
                return self._json({"ok": True, **result})
            if path == "/api/update/config":
                data = self._read_json_body(max_bytes=100_000)
                if not self.update_manager:
                    raise RuntimeError("A frissítési modul nem érhető el.")
                allowed = {"update_github_repo": "BenWyxell/SleepMate-Public", "update_channel": "stable"}
                if "update_channel" in data:
                    channel = str(data.get("update_channel") or "stable").strip().lower()
                    if channel not in {"stable"}:
                        raise ValueError("Jelenleg csak a stable frissítési csatorna támogatott.")
                if "update_auto_check" in data:
                    allowed["update_auto_check"] = bool(data.get("update_auto_check"))
                # Compatibility cleanup only: old clients may still send token fields,
                # but v5.2.20 never stores or uses a GitHub credential.
                self.update_manager.configure_token(clear=True)
                save_config(allowed)
                return self._json({"ok": True, **self._update_status_payload()})
            if path == "/api/update/check":
                if not self.update_manager:
                    raise RuntimeError("A frissítési modul nem érhető el.")
                return self._json(self.update_manager.check(load_config(), force=True))
            if path == "/api/update/install":
                jid = self._start_job("update", "SleepMate frissítés telepítése", self._update_install_job)
                return self._json({"ok": True, "job": jid})
            if path == "/api/update/rollback":
                jid = self._start_job("rollback", "SleepMate előző verzió visszaállítása", self._update_rollback_job)
                return self._json({"ok": True, "job": jid})
            if path == "/api/self-check/run":
                return self._json(self._self_check_payload())
            if path == "/api/support/create":
                jid = self._start_job("support", "SleepMate szervizcsomag készítése", self._support_bundle_job)
                return self._json({"ok": True, "job": jid})
            if path == "/api/settings":
                data = self._read_json_body()
                allowed = {}
                for key in ("show_spo2","show_hr","auto_scan_enabled","tray_notifications","start_with_windows","auto_backup_enabled","cloudflare_access_confirmed"):
                    if key in data: allowed[key] = bool(data.get(key))
                if "port_mode" in data:
                    mode = str(data.get("port_mode") or "auto").strip().lower()
                    if mode not in {"auto", "fixed"}: raise ValueError("Ismeretlen portválasztási mód.")
                    allowed["port_mode"] = mode
                if "port" in data:
                    port_value = int(data.get("port") or 8895)
                    if not (1024 <= port_value <= 65435): raise ValueError("A helyi port 1024 és 65435 közötti szám lehet.")
                    allowed["port"] = port_value
                if "auto_scan_mode" in data:
                    mode = str(data.get("auto_scan_mode") or "interval")
                    if mode not in {"interval","daily","weekly"}: raise ValueError("Ismeretlen automatikus vizsgálati mód.")
                    allowed["auto_scan_mode"] = mode
                if "auto_scan_interval_minutes" in data:
                    allowed["auto_scan_interval_minutes"] = max(15, min(10080, int(data.get("auto_scan_interval_minutes") or 30)))
                if "auto_scan_time" in data:
                    t = str(data.get("auto_scan_time") or "06:00")
                    if len(t) != 5 or t[2] != ':': raise ValueError("Érvénytelen időpont.")
                    allowed["auto_scan_time"] = t
                if "auto_scan_days" in data:
                    allowed["auto_scan_days"] = sorted({int(x) for x in (data.get("auto_scan_days") or []) if 0 <= int(x) <= 6})
                if "auto_backup_mode" in data:
                    mode = str(data.get("auto_backup_mode") or "weekly")
                    if mode not in {"daily","weekly","monthly"}: raise ValueError("Ismeretlen automatikus backup ütemezés.")
                    allowed["auto_backup_mode"] = mode
                if "auto_backup_time" in data:
                    t = str(data.get("auto_backup_time") or "03:00")
                    if len(t) != 5 or t[2] != ':': raise ValueError("Érvénytelen backup időpont.")
                    allowed["auto_backup_time"] = t
                if "auto_backup_weekday" in data:
                    allowed["auto_backup_weekday"] = max(0, min(6, int(data.get("auto_backup_weekday") or 0)))
                if "auto_backup_monthday" in data:
                    allowed["auto_backup_monthday"] = max(1, min(28, int(data.get("auto_backup_monthday") or 1)))
                if "auto_backup_keep" in data:
                    allowed["auto_backup_keep"] = max(1, min(50, int(data.get("auto_backup_keep") or 5)))
                if "auto_backup_dir" in data:
                    raw_backup = str(data.get("auto_backup_dir") or "").strip()
                    if not raw_backup: raise ValueError("A backup mappa nem lehet üres.")
                    bdir = Path(raw_backup).expanduser().resolve()
                    source_cfg = Path(str(load_config().get("data_dir") or "")).expanduser().resolve() if str(load_config().get("data_dir") or "").strip() else None
                    if source_cfg and (bdir == source_cfg or source_cfg in bdir.parents):
                        raise ValueError("A backup mappa nem lehet a ResMed beolvasási forrásmappa része. A forrásmappát a SleepMate csak olvassa.")
                    bdir.mkdir(parents=True, exist_ok=True)
                    allowed["auto_backup_dir"] = str(bdir)
                if "data_dir" in data:
                    raw = str(data.get("data_dir") or "").strip()
                    if not raw: raise ValueError("Az alapértelmezett beolvasási mappa nem lehet üres.")
                    root = self._validate_source_dir(raw)
                    allowed["data_dir"] = str(root)
                if "cloudflare_hostname" in data:
                    host_name = str(data.get("cloudflare_hostname") or "").strip().lower()
                    if host_name.startswith("http://") or host_name.startswith("https://"):
                        host_name = urlparse(host_name).hostname or ""
                    if host_name and (" " in host_name or "." not in host_name):
                        raise ValueError("Adj meg érvényes Cloudflare hostnevet, például sleepmate.pelda.hu.")
                    allowed["cloudflare_hostname"] = host_name
                cfg = save_config(allowed)
                scan = self.scanner.status() if self.scanner else {}
                backup = self.backup_scheduler.status() if self.backup_scheduler else {}
                return self._json({"ok": True, **{k:cfg.get(k) for k in cfg}, "auto_scan_next_run": scan.get("next_run"), "auto_backup_next_run": backup.get("next_run")})
            if path == "/api/ai/test":
                data = self._read_json_body(max_bytes=50_000)
                try:
                    return self._json(self._ai_test_provider(data))
                except AIProviderError as exc:
                    status = exc.status if exc.status and 400 <= exc.status < 600 else 502
                    return self._json({"error": str(exc), "status": exc.status, "transient": exc.transient}, status)
            if path == "/api/system/status":
                return self._json(self._system_status_payload())
            if path == "/api/comparison":
                q = parse_qs(parsed.query)
                def one(name): return str(q.get(name, [""])[0])
                return self._json(self.dataset.compare_periods(one("a_start"), one("a_end"), one("b_start"), one("b_end")))
            if path == "/api/ai/config":
                data = self._read_json_body(max_bytes=200_000)
                return self._json({"ok": True, **self.ai_store.save_provider_config(data)})
            if path == "/api/ai/prompt":
                if not bool(load_config().get("ai_prompting_enabled", False)):
                    return self._json({"error": "Az AI promptolás nincs bekapcsolva."}, 403)
                data = self._read_json_body(max_bytes=300_000)
                return self._json(self._analysis_prompt_export(data))
            if path == "/api/ai/analysis-stream":
                data = self._read_json_body(max_bytes=300_000)
                return self._live_analysis_stream(data)
            if path == "/api/ai/chat-stream":
                data = self._read_json_body(max_bytes=100_000)
                return self._live_chat_stream(data)
            if path in {"/api/ai/mock-analysis", "/api/ai/mock-chat"}:
                return self._json({"error":"A demó AI végpont a v2.0-ben megszűnt; használd az élő AI-modult."}, 410)
            if path == "/api/logs/clear":
                self.persistent_log.clear()
                return self._json({"ok": True})
            if path == "/api/system/shutdown":
                self.persistent_log.append("INFO", "shutdown", "A SleepMate leállítása a tálcaalkalmazásból kezdeményezve.")
                self._json({"ok": True, "message": "Leállítás folyamatban."})
                srv = self.server_instance
                if srv:
                    threading.Thread(target=srv.shutdown, daemon=True).start()
                return
            if path == "/api/system/pick-folder":
                data = self._read_json_body(max_bytes=20_000)
                if not bool(data.get("user_initiated")):
                    raise ValueError("A mappaválasztó csak közvetlen felhasználói kérésre nyitható meg.")
                return self._json({"folder": self._pick_folder(str(data.get("initial_dir") or ""))})
            if path == "/api/import/folder":
                data = self._read_json_body(); source = str(data.get("source") or "").strip()
                if not source: raise ValueError("Add meg az SD/mappa elérési útját.")
                jid = self._start_job("folder_import", "SD/mappa kézi import", self._folder_import_job, source)
                return self._json({"ok": True, "job": jid})
            if path == "/api/import/sd-search":
                jid = self._start_job("sd_search", "SD-kártya keresése és importálása", self._sd_search_job)
                return self._json({"ok": True, "job": jid})
            if path == "/api/import/refresh":
                jid = self._start_job("refresh", "Azonnali adatfrissítés", self._refresh_job, "Azonnali adatfrissítés")
                return self._json({"ok": True, "job": jid})
            if path == "/api/import/zip/create":
                jid = self.jobs.create("zip_import", "ZIP feltöltése és importálása")
                self.jobs.update(jid, status="uploading", phase="Feltöltés", message="Várakozás a ZIP fájlra…", progress=0)
                return self._json({"ok": True, "job": jid, "upload_url": f"/api/import/zip/{jid}"})
            if path == "/api/backup/create":
                jid = self._start_job("backup", "Teljes rendszerbackup készítése", self._backup_job)
                return self._json({"ok": True, "job": jid})
            if path == "/api/backup/restore/create":
                jid = self.jobs.create("backup_restore", "Teljes rendszerbackup visszatöltése")
                self.jobs.update(jid, status="uploading", phase="Feltöltés", message="Várakozás a backup fájlra…", progress=0)
                return self._json({"ok": True, "job": jid, "upload_url": f"/api/backup/restore/{jid}"})
            if path == "/api/data/delete":
                data = self._read_json_body(); opts = {k: bool(data.get(k)) for k in ("measurement","patient","logs")}
                if not any(opts.values()): raise ValueError("Nincs kiválasztva törlendő adattípus.")
                jid = self._start_job("data_delete", "Programadatok törlése", self._delete_data_job, opts)
                return self._json({"ok": True, "job": jid})
            if path == "/api/patient/profile":
                data = self._read_json_body()
                return self._json({"ok": True, "profile": self.patient_store.save_profile(data)})
            if path == "/api/patient/import":
                data = self._read_json_body(max_bytes=8_000_000)
                bundle = data.get("bundle")
                if not isinstance(bundle, dict): raise ValueError("Hiányzó mentési csomag.")
                result = self.patient_store.import_bundle(bundle, str(data.get("mode") or "merge"), bool(data.get("include_equipment", True)))
                return self._json({"ok": True, **result})
            if path == "/api/patient/photo":
                data = self._read_json_body(max_bytes=7_000_000)
                data_url = str(data.get("data_url") or "")
                if not data_url.startswith("data:image/") or ";base64," not in data_url: raise ValueError("Érvénytelen profilkép.")
                header, encoded = data_url.split(",", 1); mime = header[5:].split(";", 1)[0]
                binary = base64.b64decode(encoded, validate=True)
                if len(binary) > 3_500_000: raise ValueError("A profilkép túl nagy.")
                binary, mime = _normalize_profile_photo(binary, mime)
                self.patient_store.set_photo(binary, mime); return self._json({"ok": True, "mime": mime})
            if path.startswith("/api/patient/record/"):
                kind = path.rsplit("/", 1)[-1]; data = self._read_json_body()
                return self._json({"ok": True, "record": self.patient_store.save_record(kind, data)})
            return self._json({"error": f"Ismeretlen API végpont: {path}", "version": APP_VERSION}, 404)
        except Exception as e:
            return self._json({"error": str(e)}, 400)

    def do_PUT(self):
        parsed = urlparse(self.path); path = parsed.path
        try:
            parts = [p for p in path.split('/') if p]
            if len(parts) == 4 and parts[:3] == ['api','import','zip']:
                jid = parts[3]; kind = 'zip'
            elif len(parts) == 4 and parts[:3] == ['api','backup','restore']:
                jid = parts[3]; kind = 'backup'
            else:
                return self._json({"error": "Ismeretlen feltöltési végpont."}, 404)
            job = self.jobs.get(jid)
            if not job: return self._json({"error": "A feltöltési művelet nem található."}, 404)
            length = int(self.headers.get('Content-Length','0') or 0)
            if length <= 0: raise ValueError("Üres feltöltés.")
            suffix = '.zip'
            tmp_dir = BASE / 'private' / 'uploads'; tmp_dir.mkdir(parents=True, exist_ok=True)
            tmp = tmp_dir / f'{kind}_{jid}{suffix}'
            received = 0
            with tmp.open('wb') as out:
                while received < length:
                    chunk = self.rfile.read(min(1024*1024, length-received))
                    if not chunk: break
                    out.write(chunk); received += len(chunk)
                    self.jobs.update(jid, status='uploading', phase='Feltöltés', progress=min(35, int(received*35/length)), message=f'{received/1024/1024:.1f} / {length/1024/1024:.1f} MB')
            if received != length: raise IOError("A feltöltés megszakadt.")
            if not zipfile.is_zipfile(tmp): raise ValueError("A feltöltött fájl nem érvényes ZIP/backup.")
            if kind == 'zip': self.jobs.start(jid, self._zip_import_job, str(tmp))
            else: self.jobs.start(jid, self._restore_backup_job, str(tmp))
            return self._json({"ok": True, "job": jid})
        except Exception as e:
            return self._json({"error": str(e)}, 400)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/patient/photo":
                self.patient_store.delete_photo()
                return self._json({"ok": True})
            if path == "/api/patient":
                self.patient_store.delete_patient_only()
                return self._json({"ok": True, "measurement_data_deleted": False})
            if path.startswith("/api/patient/record/"):
                parts = [p for p in path.split("/") if p]
                if len(parts) == 5:
                    _, _, _, kind, rid = parts
                    return self._json({"ok": self.patient_store.delete_record(kind, rid)})
            return self._json({"error": f"Ismeretlen API végpont: {path}", "version": APP_VERSION}, 404)
        except Exception as e:
            return self._json({"error": str(e)}, 400)

    def _send_pdf_file(self, path: Path, download_name: str, inline: bool = False):
        size = path.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        disposition = "inline" if inline else "attachment"
        self.send_header("Content-Disposition", f'{disposition}; filename="{download_name}"')
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        with path.open("rb") as f:
            shutil.copyfileobj(f, self.wfile, length=1024 * 1024)

    def _send_file(self, path: Path, download_name: str, mime: str = "application/octet-stream"):
        size = path.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        with path.open("rb") as f:
            shutil.copyfileobj(f, self.wfile, length=1024 * 1024)

    def _patient_photo(self):
        item = self.patient_store.get_photo()
        if not item:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        mime, data = item
        versioned = bool(parse_qs(urlparse(self.path).query).get("v"))
        etag = '"' + hashlib.sha256(data).hexdigest()[:24] + '"'
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", "private, max-age=31536000, immutable" if versioned else "private, no-cache")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("ETag", etag)
        self.send_header("Cache-Control", "private, max-age=31536000, immutable" if versioned else "private, no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _equipment_image(self):
        ASSETS.mkdir(parents=True, exist_ok=True)
        if not EQUIPMENT_IMAGE.is_file() or EQUIPMENT_IMAGE.stat().st_size < 10000:
            try:
                req = urllib.request.Request(
                    EQUIPMENT_IMAGE_URL,
                    headers={"User-Agent": "Mozilla/5.0 CPAP-Elemzo/1.7"},
                )
                with urllib.request.urlopen(req, timeout=12) as response:
                    data = response.read()
                if len(data) >= 10000:
                    EQUIPMENT_IMAGE.write_bytes(data)
            except Exception as exc:
                print(f"[FELSZERELÉS] A készülékkép letöltése most nem sikerült: {exc}")

        if EQUIPMENT_IMAGE.is_file() and EQUIPMENT_IMAGE.stat().st_size >= 10000:
            data = EQUIPMENT_IMAGE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self.wfile.write(data)
            return

        # Offline-safe fallback. On a machine with internet, the exact requested
        # photo is downloaded once and then served locally from web/assets.
        svg = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 420"><rect width="640" height="420" rx="28" fill="#eef2f5"/><rect x="72" y="118" width="430" height="190" rx="44" fill="#f8fafb" stroke="#9aa7b4" stroke-width="7"/><path d="M100 126h220c48 0 82 26 82 70v87H118c-27 0-46-18-46-45v-66c0-28 11-46 28-46Z" fill="#202833"/><rect x="130" y="164" width="145" height="92" rx="13" fill="#354252"/><rect x="151" y="180" width="103" height="55" rx="5" fill="#65c9ef"/><path d="M497 151h63c28 0 45 21 45 47v81c0 27-17 44-45 44h-88Z" fill="#dbe5eb" stroke="#9aa7b4" stroke-width="7"/><path d="M514 169h58v129h-77v-85c0-26 6-44 19-44Z" fill="#bfd0d9" opacity=".75"/><text x="307" y="350" text-anchor="middle" font-family="Segoe UI,Arial" font-size="25" font-weight="700" fill="#536171">ResMed AirSense 11 AutoSet</text></svg>'''
        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
        self.send_header("Content-Length", str(len(svg)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(svg)

    def _static(self, path: str):
        rel = "index.html" if path in ("", "/") else path.lstrip("/")
        target = (WEB / rel).resolve()
        if WEB.resolve() not in target.parents and target != WEB.resolve():
            self.send_error(403)
            return
        if not target.is_file():
            target = WEB / "index.html"
        data = target.read_bytes()
        mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", mime + ("; charset=utf-8" if mime.startswith("text/") else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def main():
    migration = migrate_legacy_state(APP_BASE)
    cfg = load_config()
    ap = argparse.ArgumentParser(description="SleepMate - helyi ResMed áttekintő")
    ap.add_argument("--data", default=cfg.get("data_dir"), help="A DATALOG mappát tartalmazó mentési könyvtár")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=int(cfg.get("port", 8895)))
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--check", metavar="YYYYMMDD", help="Print one day's JSON summary and exit")
    args = ap.parse_args()

    # A külső beolvasási mappa kizárólag olvasási forrás. A program a saját
    # private/measurement tükrén dolgozik, így soha nem ír/töröl az SD-n vagy mentési mappában.
    source_root = Path(args.data).expanduser() if args.data else Path()
    data_root = ensure_data_root(MANAGED_DATA_ROOT)
    MANAGED_MARKER.touch(exist_ok=True)
    # Minden indításkor ugyanaz a byte-pontos szinkron fut le, mint a kézi és
    # ütemezett frissítéseknél. Így egy korábban részlegesen beolvasott, később
    # megnőtt ResMed EDF nem maradhat tartósan a kezelt adattárban.
    startup_sync = {}
    startup_before_ds = ResMedDataset(data_root)
    startup_before_days = startup_before_ds.days()
    startup_before_latest = startup_before_days[-1] if startup_before_days else None
    if source_root and source_root.exists():
        try:
            startup_sync = import_resmed_tree(source_root, data_root, authoritative=True)
            changed = len(startup_sync.get("changed_files") or [])
            print(f"[ADATFORRÁS] Indításkori byte-pontos ellenőrzés kész: {changed} változott fájl.")
        except Exception as exc:
            print(f"[ADATFORRÁS] Indításkori ellenőrzés most nem történt meg: {exc}")
    ds = ResMedDataset(data_root)
    if args.check:
        print(json.dumps(ds.summary(args.check), ensure_ascii=False, indent=2))
        return

    Handler.dataset = ds
    Handler.patient_store = PatientStore(STATE_BASE)
    Handler.ai_store = AIStore(STATE_BASE)
    Handler.persistent_log = PersistentLog(STATE_BASE)
    Handler.update_manager = GitHubUpdateManager(APP_BASE, Handler.persistent_log, state_base=STATE_BASE)
    Handler.self_check_service = SelfCheckService(APP_BASE, Handler.persistent_log, state_base=STATE_BASE)
    Handler.support_service = SupportBundleService(APP_BASE, Handler.persistent_log, state_base=STATE_BASE)
    Handler.push_service = PushService(STATE_BASE, Handler.persistent_log)
    if startup_sync:
        Handler._push_after_refresh(startup_before_latest, startup_sync, "Indításkori adatellenőrzés")
    Handler.jobs = JobManager(Handler.persistent_log)
    Handler.remote_manager = RemoteAccessManager(STATE_BASE, int(args.port), Handler.persistent_log)
    def auto_refresh(reason: str):
        jid = Handler.jobs.create("auto_scan", reason)
        def run(jid_inner):
            cfg_now = load_config(); source = str(cfg_now.get("data_dir") or "").strip()
            if not source:
                raise FileNotFoundError("Nincs beállítva automatikusan vizsgálható ResMed mappa.")
            before_days = Handler.dataset.days()
            before_latest = before_days[-1] if before_days else None
            Handler.jobs.update(jid_inner, progress=10, phase="Forrás ellenőrzése", message="Automatikus ResMed könyvtárfelülvizsgálat…")
            def cb(p, ph, msg): Handler.jobs.update(jid_inner, progress=12+int(p*.68), phase=ph, message=msg)
            with Handler._dataset_lock:
                result = import_resmed_tree(source, Handler.dataset.root, cb, authoritative=True)
                Handler.dataset.refresh()
            diag = Handler.dataset.diagnostics()
            Handler.jobs.update(jid_inner, progress=92, phase="Integritásellenőrzés", message=f"{diag.get('edf_files',0)} EDF ellenőrizve.")
            result.update({"days":diag.get("days"),"edf_files":diag.get("edf_files"),"warnings":len(diag.get("errors",[])),"source_read_only":True,"manual_data_preserved":True})
            Handler.persistent_log.append("INFO", "auto_scan", reason, result)
            Handler._push_after_refresh(before_latest, result, reason)
            return result
        Handler.jobs.start(jid, run)
    Handler.scanner = AutoScanner(load_config, save_config, auto_refresh, Handler.persistent_log)
    Handler.scanner.start()
    def auto_backup(reason: str):
        try:
            cfg_now = load_config()
            out_dir = Path(str(cfg_now.get("auto_backup_dir") or (STATE_BASE / "private" / "automatic_backups"))).expanduser().resolve()
            source = Path(str(cfg_now.get("data_dir") or "")).expanduser().resolve() if str(cfg_now.get("data_dir") or "").strip() else None
            if source and (out_dir == source or source in out_dir.parents):
                raise RuntimeError("Biztonsági védelem: automatikus backup nem írható a ResMed forrásmappába.")
            out_dir.mkdir(parents=True, exist_ok=True)
            try:
                with Handler.patient_store._db() as con:
                    con.execute("PRAGMA wal_checkpoint(FULL)")
            except Exception:
                pass
            out = out_dir / f"SleepMate_auto_backup_{datetime_now_file()}.zip"
            result = create_full_backup(STATE_BASE, Handler.dataset.root, cfg_now, out)
            # Persist the exact produced file so the UI can show where the last
            # automatic backup really landed. This is intentionally separate from
            # auto_backup_last_run, which the scheduler records after success.
            save_config({"auto_backup_last_file": str(out)})
            keep = max(1, min(50, int(cfg_now.get("auto_backup_keep") or 5)))
            backups = sorted(out_dir.glob("SleepMate_auto_backup_*.zip"), key=lambda p:p.stat().st_mtime, reverse=True)
            removed = 0
            for old in backups[keep:]:
                try:
                    old.unlink()
                    removed += 1
                except OSError:
                    pass
            Handler.persistent_log.append("INFO", "auto_backup", reason, {**result, "directory": str(out_dir), "keep": keep, "removed_old": removed})
        except Exception as exc:
            if Handler.push_service:
                try:
                    Handler.push_service.send("backup_error", "SleepMate backup hiba", str(exc), "/#settings")
                except Exception:
                    pass
            raise
    Handler.backup_scheduler = AutoBackupScheduler(load_config, save_config, auto_backup, Handler.persistent_log)
    Handler.backup_scheduler.start()
    Handler.persistent_log.append("INFO", "startup", f"SleepMate v{APP_VERSION} elindult.", {"data_dir": str(data_root), "app_root": str(APP_BASE), "state_root": str(STATE_BASE), "state_migration": migration})
    def _background_update_check():
        # Check immediately after startup and then twice per day. Installation is
        # always explicit; this thread only reads the public release metadata.
        while True:
            try:
                cfg = load_config()
                if bool(cfg.get("update_auto_check", True)) and Handler.update_manager:
                    Handler.update_manager.check(cfg)
            except Exception:
                pass
            time.sleep(12 * 60 * 60)
    threading.Thread(target=_background_update_check, name="sleepmate-update-check", daemon=True).start()
    try:
        server = ThreadingHTTPServer((args.host, args.port), Handler)
        Handler.server_instance = server
        # This marker is consumed by update_worker.py. Reaching this point proves
        # the new build completed initialization and successfully bound the HTTP port.
        if Handler.update_manager:
            Handler.update_manager.mark_boot_ok()
    except OSError as e:
        print("\nHIBA: A(z) %s port már foglalt." % args.port)
        print("Valószínűleg egy korábbi SleepMate / CPAP Local példány még fut.")
        print("Zárd be a régi fekete parancssori ablakot (vagy Ctrl+C), majd indítsd újra ezt a verziót.")
        print(f"Részletek: {e}")
        if not args.no_browser:
            input("\nEnter a bezáráshoz...")
        return
    # v4.0.9: if the user enabled Tailscale Serve once, keep it aligned with
    # SleepMate's currently selected port after every restart/auto-port change.
    if bool(load_config().get("tailscale_auto_serve", False)):
        def _restore_tailscale_serve():
            try:
                rm = Handler.remote_manager
                if not rm:
                    return
                status = rm.tailscale_status()
                if status.get("installed") and status.get("online") and not (status.get("serve_active") and status.get("url")):
                    result = rm.tailscale_enable()
                    Handler.persistent_log.append("INFO", "remote", "Tailscale Serve automatikusan az aktuális SleepMate portra igazítva.", {"port": int(args.port), "url": result.get("url") or ""})
                elif status.get("serve_active"):
                    Handler.persistent_log.append("INFO", "remote", "Tailscale Serve automatikus ellenőrzése rendben.", {"port": int(args.port), "url": status.get("url") or ""})
            except Exception as exc:
                Handler.persistent_log.append("WARN", "remote", "A Tailscale Serve automatikus helyreállítása nem sikerült.", {"port": int(args.port), "error": str(exc)})
        threading.Thread(target=_restore_tailscale_serve, name="sleepmate-tailscale-restore", daemon=True).start()

    local_url = f"http://sleepmate.localhost:{args.port}"
    print("=" * 64)
    print(f"SleepMate v{APP_VERSION}")
    print(f"Beolvasási forrás (csak olvasás): {Path(args.data).resolve() if args.data else "—"}")
    print(f"Program saját adattára:           {data_root.resolve()}")
    print(f"Helyi elérés:    {local_url}")
    print("Távoli elérés: Beállítások → Távoli elérés (Tailscale / Cloudflare)")
    print("Ctrl+C = leállítás")
    print("=" * 64)
    if not args.no_browser:
        webbrowser.open(local_url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nLeállítás.")
    finally:
        try:
            if Handler.remote_manager:
                Handler.remote_manager.stop_managed_processes()
        except Exception:
            pass
        if Handler.scanner:
            Handler.scanner.stop()
        if Handler.backup_scheduler:
            Handler.backup_scheduler.stop()
        server.server_close()


if __name__ == "__main__":
    main()
