from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import urllib.parse
from typing import Any

from .o2ring_integration import get_service
from .o2ring_restore import _stop_and_wait


_installed = False
_CONFIRM_TOKEN = "DELETE_OXIMETRY"
_TOMBSTONE_SCHEMA = 1


def _tombstone_path(service) -> Path:
    return service.store.root / "oximetry" / "deleted_sources.json"


def _normalize_source_names(values) -> set[str]:
    return {
        str(value or "").strip()
        for value in (values or [])
        if str(value or "").strip()
    }


def _load_tombstones(service) -> set[str]:
    path = _tombstone_path(service)
    if not path.is_file():
        return set()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or int(raw.get("schema") or 0) != _TOMBSTONE_SCHEMA:
            return set()
        return _normalize_source_names(raw.get("source_names"))
    except Exception:
        return set()


def _save_tombstones(service, source_names: set[str]) -> Path:
    path = _tombstone_path(service)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": _TOMBSTONE_SCHEMA,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source_names": sorted(_normalize_source_names(source_names)),
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return path


def _apply_tombstones(service) -> set[str]:
    """Keep explicitly deleted ring files from being imported again later.

    O2Ring keeps a few completed sessions in its own memory. Deleting only the
    local JSON/VLD copies would therefore make the next automatic BLE sync
    download the same health data again. Tombstones remember only source file
    names, never samples, and are treated as already-known ring files.
    """
    tombstones = _load_tombstones(service)
    if tombstones:
        with service._lock:
            service._known_source_names.update(tombstones)
    return tombstones


def _delete_local_oximetry(service) -> dict[str, Any]:
    cfg = service.settings()
    rows = service.store.list_recordings()
    old_sources = _normalize_source_names(row.get("source_name") for row in rows)
    tombstones = _load_tombstones(service) | old_sources

    # Persist the anti-resync marker before deleting health data. A crash between
    # these steps is safe: the worst case is a harmless tombstone for data still
    # present locally, never silent re-import of data the user already deleted.
    _save_tombstones(service, tombstones)

    # stop() alone is asynchronous. Prove that the BLE worker has exited before
    # deleting files so an in-flight download callback cannot recreate health
    # data while the deletion transaction is running.
    _stop_and_wait(service.manager)
    deleted_recordings = 0
    deleted_raw = 0
    try:
        for path in list(service.store.recordings_dir.glob("*.json")):
            try:
                path.unlink()
                deleted_recordings += 1
            except FileNotFoundError:
                pass
        for path in list(service.store.raw_dir.glob("*.vld")):
            try:
                path.unlink()
                deleted_raw += 1
            except FileNotFoundError:
                pass

        # Rebuild the runtime known-file set from the persisted tombstones only.
        # Device address and all O2Ring settings live in config and are untouched.
        with service._lock:
            service._known_source_names = set(tombstones)
    finally:
        if service._ble_should_run(cfg):
            # Never trigger an immediate post-delete historical sync. Future
            # automatic/manual syncs are safe because tombstoned files are known.
            service.manager.start(sync_on_start=False)

    try:
        service.app.Handler.persistent_log.append(
            "INFO",
            "o2ring",
            "A helyi O2Ring mérési adatok törölve lettek.",
            {
                "recordings_deleted": deleted_recordings,
                "raw_files_deleted": deleted_raw,
                "tombstones": len(tombstones),
            },
        )
    except Exception:
        pass

    return {
        "ok": True,
        "recordings_deleted": deleted_recordings,
        "raw_files_deleted": deleted_raw,
        "protected_source_names": len(tombstones),
        "remembered_device_preserved": bool(str(cfg.get("o2ring_preferred_address") or "").strip()),
        "recordings_remaining": len(service.store.list_recordings()),
    }


def install_o2ring_data_management(app_module) -> None:
    global _installed
    if _installed:
        return

    service = get_service(app_module)
    _apply_tombstones(service)
    handler_cls = app_module.Handler
    original_post = handler_cls.do_POST

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/o2ring/delete-data":
            try:
                body = self._read_json_body(max_bytes=20_000)
                if str(body.get("confirm") or "") != _CONFIRM_TOKEN:
                    return self._json({"error": "Az oximetriai adatok törléséhez explicit megerősítés szükséges."}, 400)
                return self._json(_delete_local_oximetry(service))
            except Exception as exc:
                return self._json({"error": str(exc)}, 500)
        return original_post(self)

    handler_cls.do_POST = do_POST
    _installed = True


__all__ = [
    "install_o2ring_data_management",
    "_apply_tombstones",
    "_delete_local_oximetry",
    "_load_tombstones",
    "_save_tombstones",
]
