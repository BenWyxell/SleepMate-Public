from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import threading
import time
import uuid
import zipfile
from datetime import datetime, timedelta
from contextlib import closing
from typing import Any, Callable

from .version import APP_VERSION


ROOT_FILE_NAMES = {"STR.EDF", "IDENTIFICATION.JSON", "IDENTIFICATION.TGT"}
ROOT_EXTENSIONS = {".edf", ".json", ".tgt", ".crc"}


class PersistentLog:
    def __init__(self, base: Path):
        self.path = base / "private" / "system_log.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def append(self, level: str, kind: str, message: str, details: dict[str, Any] | None = None) -> None:
        row = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "level": str(level).upper(),
            "kind": kind,
            "message": message,
            "details": details or {},
        }
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def list(self, limit: int = 250) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self._lock:
            lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines()[-max(1, limit):]
        out = []
        for line in reversed(lines):
            try:
                out.append(json.loads(line))
            except Exception:
                continue
        return out

    def clear(self) -> None:
        with self._lock:
            if self.path.exists():
                self.path.unlink()


class JobManager:
    def __init__(self, log: PersistentLog):
        self.log = log
        self.jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def create(self, kind: str, label: str) -> str:
        jid = uuid.uuid4().hex[:12]
        row = {
            "id": jid,
            "kind": kind,
            "label": label,
            "status": "queued",
            "phase": "Várakozás",
            "message": "A művelet várakozik.",
            "progress": 0,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "result": None,
            "error": None,
        }
        with self._lock:
            self.jobs[jid] = row
        return jid

    def update(self, jid: str, **fields: Any) -> None:
        with self._lock:
            if jid not in self.jobs:
                return
            self.jobs[jid].update(fields)
            self.jobs[jid]["updated_at"] = datetime.now().isoformat(timespec="seconds")

    def get(self, jid: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.jobs.get(jid)
            return dict(row) if row else None

    def start(self, jid: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        def runner():
            current = self.get(jid) or {}; self.update(jid, status="running", phase="Indítás", message="A művelet elindult.", progress=max(1, int(current.get("progress") or 0)))
            try:
                result = fn(jid, *args, **kwargs)
                self.update(jid, status="done", phase="Kész", message="A művelet sikeresen befejeződött.", progress=100, result=result)
                self.log.append("INFO", self.jobs[jid]["kind"], self.jobs[jid]["label"] + " – kész", result if isinstance(result, dict) else {})
            except Exception as exc:
                self.update(jid, status="error", phase="Hiba", message=str(exc), error=str(exc))
                self.log.append("HIBA", self.jobs[jid]["kind"], f"{self.jobs[jid]['label']} – {type(exc).__name__}: {exc}")
        threading.Thread(target=runner, daemon=True, name=f"cpap-job-{jid}").start()


def ensure_data_root(path: str | Path) -> Path:
    root = Path(path).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    (root / "DATALOG").mkdir(parents=True, exist_ok=True)
    return root


def locate_resmed_root(source: Path) -> Path:
    source = source.expanduser().resolve()
    if (source / "DATALOG").is_dir():
        return source
    # ZIP-ek gyakran egyetlen felső mappát tartalmaznak.
    candidates = []
    try:
        for p in source.iterdir():
            if p.is_dir() and (p / "DATALOG").is_dir():
                candidates.append(p)
    except OSError:
        pass
    if len(candidates) == 1:
        return candidates[0]
    raise FileNotFoundError(f"A megadott helyen nem található ResMed DATALOG mappa: {source}")


def _copy_candidates(source_root: Path) -> list[tuple[Path, Path]]:
    items: list[tuple[Path, Path]] = []
    datalog = source_root / "DATALOG"
    for src in datalog.rglob("*"):
        if src.is_file():
            items.append((src, Path("DATALOG") / src.relative_to(datalog)))
    for src in source_root.iterdir():
        if not src.is_file():
            continue
        if src.name.upper() in ROOT_FILE_NAMES or src.suffix.lower() in ROOT_EXTENSIONS:
            items.append((src, Path(src.name)))
    return items


_VERIFY_CHUNK = 4 * 1024 * 1024


def _stat_signature(path: Path) -> tuple[int, int]:
    st = path.stat()
    return int(st.st_size), int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)))


def _files_equal_bytes(source: Path, target: Path) -> bool:
    """Compare two files byte-for-byte; timestamps are never trusted as content proof."""
    try:
        if source.stat().st_size != target.stat().st_size:
            return False
        with source.open("rb") as left, target.open("rb") as right:
            while True:
                a = left.read(_VERIFY_CHUNK)
                b = right.read(_VERIFY_CHUNK)
                if a != b:
                    return False
                if not a:
                    return True
    except (OSError, PermissionError):
        return False


def _copy_verified_atomic(source: Path, target: Path, retries: int = 4) -> bool:
    """Copy a ResMed file via a sibling temp file and verify it byte-for-byte.

    ResMed/Wi-Fi SD files may still be growing while SleepMate reads them.  We retry
    when the source changes during the copy, and replace the managed file only after
    the copied snapshot matches the source.  A later refresh will still detect any
    bytes appended after this snapshot, because every refresh compares content again.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for _attempt in range(max(1, retries)):
        tmp = target.with_name(f".{target.name}.sleepmate-{uuid.uuid4().hex}.tmp")
        try:
            before = _stat_signature(source)
            shutil.copy2(source, tmp)
            after = _stat_signature(source)
            if before != after:
                try:
                    tmp.unlink()
                except OSError:
                    pass
                time.sleep(0.05)
                continue
            if not _files_equal_bytes(source, tmp):
                try:
                    tmp.unlink()
                except OSError:
                    pass
                time.sleep(0.05)
                continue
            os.replace(tmp, target)
            return True
        except Exception as exc:
            last_error = exc
            try:
                tmp.unlink()
            except OSError:
                pass
            time.sleep(0.05)
    if last_error:
        raise last_error
    return False


def _changed_day_from_rel(rel: Path) -> str | None:
    parts = rel.parts
    if len(parts) >= 3 and parts[0].upper() == "DATALOG" and len(parts[1]) == 8 and parts[1].isdigit():
        return parts[1]
    return None


def _mirror_manifest_path(dst_root: Path) -> Path:
    return dst_root.parent / "primary_sync_manifest.json"


def _load_mirror_manifest(dst_root: Path) -> dict[str, Any] | None:
    path = _mirror_manifest_path(dst_root)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _save_mirror_manifest(dst_root: Path, src_root: Path, source_rels: set[str]) -> None:
    path = _mirror_manifest_path(dst_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = {
        "version": 1,
        "source": str(src_root.resolve()),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "files": sorted(source_rels),
    }
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _candidate_snapshot(source_root: Path) -> tuple[list[tuple[Path, Path]], dict[str, tuple[int, int]]]:
    """Enumerate the whole source and prove that every candidate is readable.

    The snapshot is used only as a deletion safety gate. A destructive mirror pass is
    never allowed from a source tree that cannot be enumerated/read completely.
    """
    items = _copy_candidates(source_root)
    snapshot: dict[str, tuple[int, int]] = {}
    for src, rel in items:
        sig = _stat_signature(src)
        # Opening each file catches transient network/SD permission failures before
        # we are allowed to remove anything from the managed mirror.
        with src.open("rb") as fh:
            fh.read(1)
        snapshot[rel.as_posix()] = sig
    return items, snapshot


def _stable_authoritative_snapshot(source_root: Path, delay: float = 0.12) -> tuple[list[tuple[Path, Path]], bool, str | None]:
    """Take two complete source snapshots before allowing mirror deletions."""
    try:
        items1, snap1 = _candidate_snapshot(source_root)
        if not items1:
            return items1, False, "Az elsődleges forrás üres; biztonsági okból törlés nem történt."
        time.sleep(max(0.0, delay))
        items2, snap2 = _candidate_snapshot(source_root)
        if snap1 != snap2:
            return items2, False, "A forrás a vizsgálat közben változott; törlés csak stabil forrásból engedélyezett."
        return items2, True, None
    except Exception as exc:
        return [], False, f"A forrás nem olvasható teljesen ({exc}); törlés biztonsági okból kihagyva."


def _prune_sync_quarantine(private_root: Path, *, max_batches: int = 10, max_age_days: int = 30) -> None:
    """Bound quarantine growth without ever touching active measurement/source data."""
    root = private_root / "sync_quarantine"
    if not root.is_dir():
        return
    now = time.time()
    batches = []
    for p in root.iterdir():
        if not p.is_dir():
            continue
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue
        batches.append((mtime, p))
    batches.sort(reverse=True)
    keep = set(p for _, p in batches[:max(1, max_batches)])
    for mtime, p in batches:
        too_old = (now - mtime) > max_age_days * 86400
        if p not in keep or too_old:
            try:
                shutil.rmtree(p)
            except OSError:
                pass


def _quarantine_missing_managed_files(
    dst_root: Path,
    missing_rels: list[Path],
) -> tuple[list[str], str | None]:
    """Remove files from the active dataset without permanently destroying them."""
    if not missing_rels:
        return [], None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    quarantine_root = dst_root.parent / "sync_quarantine" / stamp
    removed: list[str] = []
    for rel in missing_rels:
        src = dst_root / rel
        if not src.is_file():
            continue
        qdst = quarantine_root / rel
        qdst.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(src, qdst)
        except OSError:
            shutil.move(str(src), str(qdst))
        removed.append(rel.as_posix())

    # Empty ResMed day directories are not data and should disappear from the
    # managed mirror too. Never touch the external source tree.
    datalog = dst_root / "DATALOG"
    if datalog.is_dir():
        dirs = sorted((p for p in datalog.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True)
        for directory in dirs:
            try:
                directory.rmdir()
            except OSError:
                pass
    if removed:
        _prune_sync_quarantine(dst_root.parent)
    return removed, str(quarantine_root) if removed else None


def import_resmed_tree(
    source: str | Path,
    target: str | Path,
    progress: Callable[[int, str, str], None] | None = None,
    *,
    authoritative: bool = False,
) -> dict[str, Any]:
    """Synchronize a ResMed tree into SleepMate's managed mirror safely.

    Every import path compares existing files byte-for-byte. ``authoritative=True``
    is reserved for the configured primary source (startup, instant refresh and
    scheduled refresh). In that mode the managed machine-data mirror also follows
    deletions, but only after a complete, stable two-pass source scan. Removed files
    are moved to a private quarantine instead of being permanently destroyed.

    Manual folder/SD/ZIP imports remain additive/update-only, so a partial import can
    never erase unrelated therapy days. Patient/manual data live outside measurement
    and are never touched here.
    """
    src_root = locate_resmed_root(Path(source))
    dst_root = ensure_data_root(target)
    try:
        if src_root.samefile(dst_root):
            items = _copy_candidates(src_root)
            if progress:
                progress(100, "Tartalmi ellenőrzés", f"{len(items)} fájl a kezelt adattárban; külön másolat nem szükséges.")
            return {
                "source": str(src_root), "target": str(dst_root), "copied": 0, "updated": 0,
                "removed": 0, "skipped": len(items), "verified": len(items), "files": len(items),
                "changed_days": [], "same_folder": True, "verification": "byte-for-byte",
                "authoritative": bool(authoritative), "source_read_only": True,
            }
    except Exception:
        pass

    deletion_safe = False
    deletion_skip_reason: str | None = None
    if authoritative:
        items, deletion_safe, deletion_skip_reason = _stable_authoritative_snapshot(src_root)
        # Even when deletion is blocked, non-destructive add/update is still useful.
        if not items:
            items = _copy_candidates(src_root)
    else:
        items = _copy_candidates(src_root)

    total = max(1, len(items))
    copied = updated = skipped = verified = 0
    changed_days: set[str] = set()
    changed_files: list[str] = []

    for idx, (src, rel) in enumerate(items, start=1):
        dst = dst_root / rel
        existed = dst.exists()
        identical = existed and _files_equal_bytes(src, dst)
        verified += 1
        if identical:
            skipped += 1
        else:
            if not _copy_verified_atomic(src, dst):
                raise RuntimeError(f"A forrásfájl nem volt stabilan beolvasható: {src}")
            if existed:
                updated += 1
            else:
                copied += 1
            changed_files.append(rel.as_posix())
            day = _changed_day_from_rel(rel)
            if day:
                changed_days.add(day)

        if progress and (idx == total or idx % max(1, total // 100) == 0):
            progress(
                min(88 if authoritative else 100, int(idx * (88 if authoritative else 100) / total)),
                "Tartalmi ellenőrzés",
                f"{idx}/{total} fájl byte-pontos ellenőrzése • {copied} új • {updated} frissült",
            )

    removed_files: list[str] = []
    quarantine_path: str | None = None
    manifest_status = "not-used"
    if authoritative:
        source_rels = {rel.as_posix() for _, rel in items}
        manifest = _load_mirror_manifest(dst_root)
        resolved_source = str(src_root.resolve())
        if manifest is None:
            # v4.1.8 migration: the existing managed measurement tree was created by
            # the configured source in previous releases, so it is a safe baseline.
            known_primary = {rel.as_posix() for _, rel in _copy_candidates(dst_root)}
            manifest_status = "initialized-from-managed-mirror"
        elif str(manifest.get("source") or "") != resolved_source:
            # Switching to a different primary source must never erase data on the
            # first pass. Establish a new baseline and allow deletions next refresh.
            known_primary = set()
            deletion_safe = False
            deletion_skip_reason = "Az elsődleges forrás megváltozott; az első ellenőrzés csak új alapállapotot rögzít, nem töröl."
            manifest_status = "source-changed-baseline"
        else:
            known_primary = {str(x) for x in (manifest.get("files") or []) if isinstance(x, str)}
            manifest_status = "loaded"

        if deletion_safe:
            missing = sorted(known_primary - source_rels)
            # Only files previously known to belong to the primary mirror may be
            # removed. Files added by a manual ZIP/folder import are therefore safe.
            missing_rels = [Path(rel) for rel in missing if (dst_root / Path(rel)).is_file()]
            if progress and missing_rels:
                progress(92, "Tükörszinkron", f"{len(missing_rels)} forrásból törölt fájl biztonságos leválasztása…")
            removed_files, quarantine_path = _quarantine_missing_managed_files(dst_root, missing_rels)
            changed_files.extend(removed_files)
            for rel_text in removed_files:
                day = _changed_day_from_rel(Path(rel_text))
                if day:
                    changed_days.add(day)
        # A stable source becomes the authoritative baseline. If deletion was blocked
        # due only to a source-change baseline, this still records the new source.
        if deletion_safe or manifest_status == "source-changed-baseline":
            _save_mirror_manifest(dst_root, src_root, source_rels)
        elif manifest is None and items:
            # Keep a baseline even if the first source scan happened to be changing;
            # do not use it for destructive action until a later stable pass.
            _save_mirror_manifest(dst_root, src_root, source_rels)

    if progress:
        progress(100, "Szinkron kész", f"{copied} új • {updated} frissült • {len(removed_files)} eltűnt a forrásból")

    return {
        "source": str(src_root), "target": str(dst_root), "copied": copied, "updated": updated,
        "removed": len(removed_files), "removed_files": removed_files,
        "quarantine_path": quarantine_path,
        "skipped": skipped, "verified": verified, "files": len(items),
        "changed_days": sorted(changed_days), "changed_files": changed_files,
        "verification": "byte-for-byte", "source_read_only": True,
        "authoritative": bool(authoritative), "mirror_deletion_safe": bool(deletion_safe),
        "mirror_deletion_skipped_reason": deletion_skip_reason,
        "mirror_manifest": manifest_status,
    }


def safe_extract_zip(zip_path: Path, dest: Path, progress: Callable[[int, str, str], None] | None = None) -> None:
    with zipfile.ZipFile(zip_path) as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        total_uncompressed = sum(max(0, i.file_size) for i in infos)
        if total_uncompressed > 25 * 1024**3:
            raise ValueError("A ZIP kibontott mérete túl nagy (25 GB felett).")
        total = max(1, len(infos))
        for idx, info in enumerate(infos, start=1):
            name = info.filename.replace("\\", "/")
            if name.startswith("/") or ".." in Path(name).parts:
                raise ValueError("A ZIP veszélyes útvonalat tartalmaz.")
            target = (dest / name).resolve()
            if dest.resolve() not in target.parents and target != dest.resolve():
                raise ValueError("A ZIP érvénytelen útvonalat tartalmaz.")
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, target.open("wb") as out:
                shutil.copyfileobj(src, out, length=1024 * 1024)
            if progress and (idx == total or idx % max(1, total // 50) == 0):
                progress(int(idx * 100 / total), "ZIP kibontása", f"{idx}/{total} fájl")


def windows_drive_roots() -> list[Path]:
    if os.name != "nt":
        return []
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    roots = []
    system_drive = (os.environ.get("SystemDrive") or "C:").upper().rstrip("\\")
    for i in range(26):
        if not (mask & (1 << i)):
            continue
        letter = chr(65 + i)
        root = Path(f"{letter}:\\")
        if str(root).upper().rstrip("\\") == system_drive:
            continue
        try:
            dtype = ctypes.windll.kernel32.GetDriveTypeW(str(root))
        except Exception:
            dtype = 0
        if dtype in (2, 3):  # removable vagy helyi meghajtó/card reader
            roots.append(root)
    return roots


def find_resmed_sd() -> list[str]:
    found = []
    for root in windows_drive_roots():
        try:
            if (root / "DATALOG").is_dir():
                found.append(str(root))
                continue
            # Egyes kártyaolvasók egy további könyvtárszintet adnak.
            for p in root.iterdir():
                if p.is_dir() and (p / "DATALOG").is_dir():
                    found.append(str(p))
        except (OSError, PermissionError):
            continue
    return found


def _sqlite_snapshot(source: Path, destination: Path) -> None:
    """Create a transactionally consistent SQLite snapshot, including WAL data.

    Copying only the main .db file is not sufficient when SQLite is in WAL mode:
    recent patient/equipment rows can live exclusively in -wal. Python's backup
    API reads the logical live database and writes a standalone snapshot file.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    last_exc: Exception | None = None
    for attempt in range(6):
        try:
            if destination.exists():
                destination.unlink()
            # sqlite3.Connection.__exit__ commits/rolls back but DOES NOT close
            # the OS file handle. On Windows that left the temporary snapshot
            # locked and TemporaryDirectory cleanup failed with WinError 32.
            with closing(sqlite3.connect(str(source), timeout=5.0)) as src, \
                 closing(sqlite3.connect(str(destination), timeout=5.0)) as dst:
                src.execute('PRAGMA busy_timeout=5000')
                dst.execute('PRAGMA busy_timeout=5000')
                src.backup(dst, pages=256, sleep=0.05)
                dst.execute('PRAGMA journal_mode=DELETE')
                dst.commit()
            return
        except Exception as exc:
            last_exc = exc
            time.sleep(0.15 * (attempt + 1))
    raise RuntimeError(f'A SQLite adatbázis konzisztens mentése nem sikerült: {source.name}: {last_exc}')


def _sqlite_restore(snapshot: Path, target: Path) -> None:
    """Restore a standalone SQLite snapshot into the live target database."""
    target.parent.mkdir(parents=True, exist_ok=True)
    last_exc: Exception | None = None
    for attempt in range(8):
        try:
            # Explicitly close both database handles before returning. This is
            # important on Windows because subsequent cleanup/replacement cannot
            # remove an SQLite file while a connection still owns its handle.
            with closing(sqlite3.connect(str(snapshot), timeout=5.0)) as src, \
                 closing(sqlite3.connect(str(target), timeout=5.0)) as dst:
                src.execute('PRAGMA busy_timeout=5000')
                dst.execute('PRAGMA busy_timeout=5000')
                src.backup(dst, pages=256, sleep=0.05)
                # Fold any target WAL back into the main file so the restored DB
                # is immediately self-contained for a fresh PatientStore.
                try:
                    dst.execute('PRAGMA wal_checkpoint(TRUNCATE)')
                except sqlite3.DatabaseError:
                    pass
                dst.commit()
            return
        except Exception as exc:
            last_exc = exc
            time.sleep(0.2 * (attempt + 1))
    raise RuntimeError(f'A SQLite adatbázis visszatöltése nem sikerült: {target.name}: {last_exc}')


_FULL_BACKUP_TRANSIENT_PRIVATE_ROOTS = {
    'backups', 'automatic_backups', 'uploads', 'browser_profile',
    'reports', 'measurement', 'sync_quarantine', 'support', 'update_runtime', 'pre_update_backups',
}

# Runtime log files belong to the currently running SleepMate instance. On
# Windows service_startup.log is held open by the child pythonw process, so a
# restore must never try to delete or overwrite it. These files may remain in
# older backup archives for diagnostics, but restore deliberately preserves the
# live copies instead of treating them as application state.
_FULL_BACKUP_RUNTIME_PRIVATE_FILES = {
    Path('service_startup.log'),
    Path('launcher.log'),
    Path('system_log.jsonl'),
    Path('tray.pid'),
    Path('tray_heartbeat.json'),
}

def _is_runtime_private_file(rel: Path) -> bool:
    return rel in _FULL_BACKUP_RUNTIME_PRIVATE_FILES


def _looks_like_sqlite(path: Path) -> bool:
    """Detect SQLite by file signature, not extension.

    SleepMate's push store is named push.sqlite3, while older stores use .db.
    Full backup/restore must treat both transactionally and never raw-copy a live
    SQLite file on Windows.
    """
    try:
        with path.open('rb') as f:
            return f.read(16) == b'SQLite format 3\x00'
    except OSError:
        return False


def create_full_backup(base: Path, data_dir: Path, config: dict[str, Any], out_path: Path, progress: Callable[[int, str, str], None] | None = None) -> dict[str, Any]:
    private = base / 'private'
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # SQLite must be snapshotted logically. In WAL mode the 4 KB patient.db can
    # be almost empty while all current profile/equipment data sits in -wal.
    # A raw file ZIP therefore looked successful but restored an empty person.
    with tempfile.TemporaryDirectory(prefix='sleepmate-full-backup-') as td:
        tmp_root = Path(td)
        files: list[tuple[Path, Path]] = []
        sqlite_names: list[str] = []

        if private.exists():
            for p in private.rglob('*'):
                try:
                    if not p.is_file():
                        continue
                except OSError:
                    continue
                rel = p.relative_to(private)
                if rel.parts and rel.parts[0] in _FULL_BACKUP_TRANSIENT_PRIVATE_ROOTS:
                    continue
                if p.name.endswith('-wal') or p.name.endswith('-shm'):
                    continue
                arc = Path('private') / rel
                if _looks_like_sqlite(p):
                    snap = tmp_root / 'sqlite' / rel
                    _sqlite_snapshot(p, snap)
                    files.append((snap, arc))
                    sqlite_names.append(arc.as_posix())
                else:
                    files.append((p, arc))

        if data_dir.exists():
            for p in data_dir.rglob('*'):
                if p.is_file():
                    files.append((p, Path('measurement') / p.relative_to(data_dir)))

        manifest = {
            'format': 'cpap-elemzo-full-backup',
            'version': 2,
            'created_at': datetime.now().isoformat(timespec='seconds'),
            'app_version': APP_VERSION,
            'managed_measurement_dir': str(data_dir),
            'config': dict(config),
            'private_data_encrypted_at_rest': True,
            'sqlite_snapshots': sqlite_names,
            'restore_semantics': 'replace-private-and-measurement-snapshot',
            'note': 'A backup a program saját kezelt mérési tárát, kezelt személyét, felszereléseit, profilképét, AI adatait és helyi beállításait tartalmazza. A böngésző futásidejű profilja és gyorsítótára nem része a mentésnek. Windows DPAPI esetén a privát adatok ugyanazon Windows-felhasználóval állíthatók vissza.',
        }
        total = max(1, len(files))
        with zipfile.ZipFile(out_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            zf.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
            for idx, (src, arc) in enumerate(files, start=1):
                zf.write(src, arc.as_posix())
                if progress and (idx == total or idx % max(1, total // 80) == 0):
                    progress(int(idx * 100 / total), 'Backup készítése', f'{idx}/{total} fájl')
    return {'file': str(out_path), 'files': len(files), 'size': out_path.stat().st_size, 'sqlite_snapshots': sqlite_names}


def _clear_restore_private(private_dir: Path, backed_rel_paths: set[Path], sqlite_rel_paths: set[Path] | None = None) -> None:
    """Make private state match the snapshot without deleting live SQLite targets.

    The old implementation removed whole subdirectories. A live push.sqlite3 in
    private/push therefore made shutil.rmtree fail with WinError 32 before the
    logical SQLite restore even started. We now delete file-by-file, preserving
    target SQLite files and their WAL/SHM sidecars until sqlite3.backup replaces
    their logical contents.
    """
    private_dir.mkdir(parents=True, exist_ok=True)
    sqlite_rel_paths = set(sqlite_rel_paths or set())

    def protected_sqlite(rel: Path) -> bool:
        if rel in sqlite_rel_paths:
            return True
        raw = rel.as_posix()
        for suffix in ('-wal', '-shm'):
            if raw.endswith(suffix) and Path(raw[:-len(suffix)]) in sqlite_rel_paths:
                return True
        return False

    files = sorted((p for p in private_dir.rglob('*') if p.is_file()), key=lambda x: len(x.parts), reverse=True)
    for child in files:
        rel = child.relative_to(private_dir)
        if rel.parts and rel.parts[0] in _FULL_BACKUP_TRANSIENT_PRIVATE_ROOTS:
            continue
        if _is_runtime_private_file(rel):
            continue
        if protected_sqlite(rel):
            continue
        try:
            child.unlink()
        except FileNotFoundError:
            pass

    dirs = sorted((p for p in private_dir.rglob('*') if p.is_dir()), key=lambda x: len(x.parts), reverse=True)
    for child in dirs:
        rel = child.relative_to(private_dir)
        if rel.parts and rel.parts[0] in _FULL_BACKUP_TRANSIENT_PRIVATE_ROOTS:
            continue
        try:
            child.rmdir()
        except (OSError, FileNotFoundError):
            pass


def _replace_measurement_tree(source: Path, target: Path) -> None:
    """Replace, rather than overlay, the managed measurement snapshot."""
    target.mkdir(parents=True, exist_ok=True)
    for child in list(target.iterdir()):
        try:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        except FileNotFoundError:
            pass
    if source.exists():
        for p in source.rglob('*'):
            rel = p.relative_to(source)
            dst = target / rel
            if p.is_dir():
                dst.mkdir(parents=True, exist_ok=True)
            elif p.is_file():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dst)
    (target / 'DATALOG').mkdir(parents=True, exist_ok=True)
    (target / '.managed-store-v1').touch(exist_ok=True)


def restore_full_backup(base: Path, backup_path: Path, target_data_dir: Path, progress: Callable[[int, str, str], None] | None = None) -> dict[str, Any]:
    # Stage the complete archive first. This validates every path and means the
    # uploaded ZIP can live inside private/uploads without being touched midway.
    with tempfile.TemporaryDirectory(prefix='sleepmate-full-restore-') as td:
        stage = Path(td)
        with zipfile.ZipFile(backup_path) as zf:
            try:
                manifest = json.loads(zf.read('manifest.json').decode('utf-8'))
            except Exception as exc:
                raise ValueError('A backup manifest nem olvasható.') from exc
            if manifest.get('format') != 'cpap-elemzo-full-backup':
                raise ValueError('Nem támogatott teljes backup.')
            if int(manifest.get('version') or 1) not in {1, 2}:
                raise ValueError('A teljes backup verziója nem támogatott.')
            infos = [i for i in zf.infolist() if not i.is_dir() and i.filename != 'manifest.json']
            total = max(1, len(infos))
            for idx, info in enumerate(infos, start=1):
                name = info.filename.replace('\\', '/')
                parts = Path(name).parts
                if not parts or '..' in parts or parts[0] not in {'private', 'measurement'}:
                    raise ValueError('A backup érvénytelen útvonalat tartalmaz.')
                target = (stage / Path(*parts)).resolve()
                if stage.resolve() not in target.parents:
                    raise ValueError('A backup érvénytelen útvonalat tartalmaz.')
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, target.open('wb') as out:
                    shutil.copyfileobj(src, out, length=1024 * 1024)
                if progress and (idx == total or idx % max(1, total // 80) == 0):
                    progress(int(idx * 45 / total), 'Backup ellenőrzése', f'{idx}/{total} fájl')

        stage_private = stage / 'private'
        private_dir = base / 'private'
        private_files = [p for p in stage_private.rglob('*') if p.is_file()] if stage_private.exists() else []
        backed_private = {p.relative_to(stage_private) for p in private_files}
        staged_sqlite_rel = {p.relative_to(stage_private) for p in private_files if _looks_like_sqlite(p)}
        _clear_restore_private(private_dir, backed_private, staged_sqlite_rel)

        sqlite_files = []
        normal_files = []
        skipped_runtime_files: list[str] = []
        for p in private_files:
            rel = p.relative_to(stage_private)
            if _is_runtime_private_file(rel):
                skipped_runtime_files.append(rel.as_posix())
                continue
            is_sqlite = _looks_like_sqlite(p)
            (sqlite_files if is_sqlite else normal_files).append(p)
        steps = max(1, len(normal_files) + len(sqlite_files))
        done = 0

        # Restore encryption keys/secrets and ordinary state first. On the dev
        # AES fallback this also restores .patient.key before the DB is reopened.
        for src in normal_files:
            rel = src.relative_to(stage_private)
            dst = private_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            done += 1
            if progress:
                progress(45 + int(done * 30 / steps), 'Privát adatok visszatöltése', rel.as_posix())

        for src in sqlite_files:
            rel = src.relative_to(stage_private)
            dst = private_dir / rel
            _sqlite_restore(src, dst)
            done += 1
            if progress:
                progress(45 + int(done * 30 / steps), 'Adatbázis visszatöltése', rel.as_posix())

        if progress:
            progress(78, 'CPAP mérési adatok', 'A mentett mérési állapot visszaállítása…')
        _replace_measurement_tree(stage / 'measurement', target_data_dir)
        if progress:
            progress(100, 'Kész', 'A teljes SleepMate állapot visszatöltve.')

    return {
        'restored': len(normal_files) + len(sqlite_files),
        'private_files': len(normal_files),
        'sqlite_databases': len(sqlite_files),
        'measurement_replaced': True,
        'runtime_files_preserved': skipped_runtime_files,
        'manifest': manifest,
    }


def delete_measurement_data(data_dir: Path, progress: Callable[[int, str, str], None] | None = None) -> int:
    """Delete ONLY the application-managed measurement mirror.

    The caller must pass the program-owned private/measurement directory. External
    source folders and SD cards are intentionally never modified by this function.
    """
    data_dir = Path(data_dir).resolve()
    if not data_dir.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "DATALOG").mkdir(parents=True, exist_ok=True)
        return 0
    files = [p for p in data_dir.rglob("*") if p.is_file() and p.name != ".managed-store-v1"]
    total = max(1, len(files))
    deleted = 0
    for idx, p in enumerate(files, start=1):
        try:
            p.unlink()
            deleted += 1
        except OSError:
            pass
        if progress and (idx == total or idx % max(1, total // 50) == 0):
            progress(int(idx * 90 / total), "Programadatok törlése", f"{idx}/{total} belső fájl")
    for p in sorted([p for p in data_dir.rglob("*") if p.is_dir()], key=lambda x: len(x.parts), reverse=True):
        try:
            p.rmdir()
        except OSError:
            pass
    (data_dir / "DATALOG").mkdir(parents=True, exist_ok=True)
    (data_dir / ".managed-store-v1").touch(exist_ok=True)
    if progress:
        progress(100, "Kész", f"{deleted} programon belüli mérési fájl törölve. A forrásmappa változatlan.")
    return deleted


def compute_next_run(cfg: dict[str, Any], now: datetime | None = None) -> datetime | None:
    if not cfg.get("auto_scan_enabled", True):
        return None
    now = now or datetime.now()
    mode = cfg.get("auto_scan_mode", "interval")
    last_raw = cfg.get("auto_scan_last_run")
    try:
        last = datetime.fromisoformat(last_raw) if last_raw else now
    except Exception:
        last = now
    if mode == "interval":
        # v1.6: félórás alapértelmezés és percalapú ütemezés.
        minutes = cfg.get("auto_scan_interval_minutes")
        if minutes is None:
            # Régi config kompatibilitás, de új telepítésnél 30 perc az alap.
            legacy = cfg.get("auto_scan_interval_hours")
            minutes = int(legacy) * 60 if legacy not in (None, "") else 30
        minutes = max(15, min(10080, int(minutes or 30)))
        return last + timedelta(minutes=minutes)
    hhmm = str(cfg.get("auto_scan_time") or "06:00")
    try:
        hour, minute = [int(x) for x in hhmm.split(":", 1)]
    except Exception:
        hour, minute = 6, 0
    # A következő futást az UTOLSÓ futás után keressük. Így ha a program
    # a tervezett időpont után ébred fel, a vizsgálat azonnal esedékes lesz.
    base = last
    if mode == "daily":
        candidate = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= base:
            candidate += timedelta(days=1)
        return candidate
    days = cfg.get("auto_scan_days") or [0,1,2,3,4,5,6]
    days = {int(x) for x in days if str(x).isdigit() and 0 <= int(x) <= 6}
    if not days:
        days = {0,1,2,3,4,5,6}
    for offset in range(0, 8):
        d = base + timedelta(days=offset)
        if d.weekday() not in days:
            continue
        candidate = d.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate > base:
            return candidate
    return base + timedelta(days=1)


class AutoScanner:
    def __init__(self, get_config: Callable[[], dict[str, Any]], save_config: Callable[[dict[str, Any]], dict[str, Any]], callback: Callable[[str], None], log: PersistentLog):
        self.get_config = get_config
        self.save_config = save_config
        self.callback = callback
        self.log = log
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True, name="cpap-auto-scan")

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def status(self) -> dict[str, Any]:
        cfg = self.get_config()
        nxt = compute_next_run(cfg)
        return {
            "enabled": bool(cfg.get("auto_scan_enabled", True)),
            "mode": cfg.get("auto_scan_mode", "interval"),
            "last_run": cfg.get("auto_scan_last_run"),
            "next_run": nxt.isoformat(timespec="seconds") if nxt else None,
        }

    def _loop(self):
        # Az első automata vizsgálat nem azonnal indul, hanem az alap 30 perces ciklus szerint.
        cfg = self.get_config()
        if cfg.get("auto_scan_enabled", True) and not cfg.get("auto_scan_last_run"):
            self.save_config({"auto_scan_last_run": datetime.now().isoformat(timespec="seconds")})
        while not self.stop_event.wait(20):
            try:
                cfg = self.get_config()
                nxt = compute_next_run(cfg)
                if nxt and datetime.now() >= nxt:
                    self.callback("Automatikus könyvtárfelülvizsgálat")
                    self.save_config({"auto_scan_last_run": datetime.now().isoformat(timespec="seconds")})
            except Exception as exc:
                self.log.append("HIBA", "auto_scan", f"Automatikus könyvtárfelülvizsgálat sikertelen: {exc}")


def compute_next_backup_run(cfg: dict[str, Any], now: datetime | None = None) -> datetime | None:
    if not cfg.get("auto_backup_enabled", False):
        return None
    now = now or datetime.now()
    last_raw = cfg.get("auto_backup_last_run")
    try:
        base = datetime.fromisoformat(last_raw) if last_raw else now
    except Exception:
        base = now
    hhmm = str(cfg.get("auto_backup_time") or "03:00")
    try:
        hour, minute = [int(x) for x in hhmm.split(":", 1)]
    except Exception:
        hour, minute = 3, 0
    mode = str(cfg.get("auto_backup_mode") or "weekly")
    if mode == "daily":
        candidate = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= base:
            candidate += timedelta(days=1)
        return candidate
    if mode == "monthly":
        day = max(1, min(28, int(cfg.get("auto_backup_monthday") or 1)))
        y, m = base.year, base.month
        for _ in range(14):
            candidate = datetime(y, m, day, hour, minute)
            if candidate > base:
                return candidate
            m += 1
            if m > 12:
                m = 1; y += 1
        return base + timedelta(days=31)
    weekday = max(0, min(6, int(cfg.get("auto_backup_weekday") or 6)))
    for offset in range(0, 8):
        d = base + timedelta(days=offset)
        if d.weekday() != weekday:
            continue
        candidate = d.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate > base:
            return candidate
    return base + timedelta(days=7)


class AutoBackupScheduler:
    """Background scheduler for explicit SleepMate backup destinations.

    The next due time is cached instead of being recalculated from ``now`` on
    every polling cycle. Recalculating it after the requested minute had just
    passed caused weekly/daily jobs to jump straight to the next period before
    they could ever run.
    """
    def __init__(self, get_config: Callable[[], dict[str, Any]], save_config: Callable[[dict[str, Any]], dict[str, Any]], callback: Callable[[str], None], log: PersistentLog):
        self.get_config = get_config
        self.save_config = save_config
        self.callback = callback
        self.log = log
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True, name="sleepmate-auto-backup")
        self._lock = threading.RLock()
        self._signature = None
        self._next_run: datetime | None = None

    @staticmethod
    def _schedule_signature(cfg: dict[str, Any]):
        return (
            bool(cfg.get("auto_backup_enabled", False)),
            str(cfg.get("auto_backup_mode") or "weekly"),
            str(cfg.get("auto_backup_time") or "03:00"),
            int(cfg.get("auto_backup_weekday") or 0),
            int(cfg.get("auto_backup_monthday") or 1),
        )

    def _refresh_schedule(self, cfg: dict[str, Any], now: datetime | None = None, force: bool = False):
        sig = self._schedule_signature(cfg)
        with self._lock:
            if force or sig != self._signature:
                self._signature = sig
                self._next_run = compute_next_backup_run(cfg, now=now or datetime.now())
            return self._next_run

    def start(self):
        # Prime the due time once. Do not fake a "last run" timestamp here.
        self._refresh_schedule(self.get_config(), force=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def status(self) -> dict[str, Any]:
        cfg = self.get_config()
        nxt = self._refresh_schedule(cfg)
        return {
            "enabled": bool(cfg.get("auto_backup_enabled", False)),
            "mode": cfg.get("auto_backup_mode", "weekly"),
            "last_run": cfg.get("auto_backup_last_run"),
            "next_run": nxt.isoformat(timespec="seconds") if nxt else None,
        }

    def _loop(self):
        # Five-second polling gives near-minute-accurate execution while the
        # cached target prevents the old "skip to next week" race condition.
        while not self.stop_event.wait(5):
            try:
                cfg = self.get_config()
                nxt = self._refresh_schedule(cfg)
                now = datetime.now()
                if nxt and now >= nxt:
                    try:
                        self.callback("Automatikus biztonsági mentés")
                    except Exception as exc:
                        # Keep the scheduled job alive and retry shortly instead
                        # of silently losing the entire period.
                        with self._lock:
                            self._next_run = now + timedelta(minutes=5)
                        self.log.append("HIBA", "auto_backup", "Az automatikus biztonsági mentés sikertelen; 5 perc múlva újrapróbáljuk.", {"error": str(exc)})
                        continue
                    finished = datetime.now()
                    self.save_config({"auto_backup_last_run": finished.isoformat(timespec="seconds")})
                    cfg = self.get_config()
                    self._refresh_schedule(cfg, now=finished, force=True)
            except Exception as exc:
                self.log.append("HIBA", "auto_backup", "Az automatikus biztonsági mentés ütemezése hibát jelzett.", {"error": str(exc)})
