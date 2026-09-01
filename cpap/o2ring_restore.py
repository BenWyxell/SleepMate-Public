"""Restore-safe O2Ring runtime rehydration for SleepMate v5.3.

Full backup restore replaces the private O2 recording/configuration snapshot.
The BLE worker must therefore be completely quiescent before restore starts,
and its in-memory live/device state must never survive across the restore
boundary. This layer wraps the proven v5.2.20 restore job without changing the
base maintenance implementation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import zipfile

from .o2ring_ble import O2RingBLEManager
from .o2ring_integration import DEFAULTS, get_service
from .o2ring_lifecycle import start_reliably, stop_and_wait as _stop_and_wait
from .oximetry import OximetryStore


_installed = False
_BOOL_KEYS = {
    "o2ring_enabled",
    "o2ring_ble_enabled",
    "o2ring_auto_connect",
    "o2ring_auto_sync",
    "o2ring_auto_match",
    "o2ring_show_motion",
}


def _bool_value(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
    return bool(default)


def _normalized_restore_config(saved: dict[str, Any] | None) -> dict[str, Any]:
    """Return a complete, validated v5.3 O2 config snapshot.

    Old backups predate O2Ring. Restoring one must not leave a newer machine's
    pairing or feature state behind, so missing O2 keys intentionally fall back
    to the v5.3 defaults (master OFF, no remembered ring).
    """
    source = saved if isinstance(saved, dict) else {}
    result = dict(DEFAULTS)
    for key, default in DEFAULTS.items():
        if key not in source:
            continue
        value = source.get(key)
        if key in _BOOL_KEYS:
            result[key] = _bool_value(value, bool(default))
        elif key == "o2ring_clock_offset_seconds":
            try:
                result[key] = max(-900.0, min(900.0, float(value or 0.0)))
            except (TypeError, ValueError):
                result[key] = float(default)
        elif key in {"o2ring_spo2_reference", "o2ring_spo2_secondary_reference"}:
            try:
                result[key] = max(70, min(100, int(value)))
            except (TypeError, ValueError):
                result[key] = int(default)
        else:
            result[key] = str(value or "").strip()
    return result


def _read_backup_o2_config(uploaded: str | Path) -> dict[str, Any] | None:
    """Read the manifest before base restore deletes the uploaded ZIP."""
    try:
        with zipfile.ZipFile(Path(uploaded)) as zf:
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        if not isinstance(manifest, dict):
            return None
        config = manifest.get("config") if isinstance(manifest.get("config"), dict) else {}
        return _normalized_restore_config(config)
    except Exception:
        # The base restore remains the authority for ZIP/manifest validation and
        # will raise its own user-facing error if the archive is invalid.
        return None


def _fresh_manager(service) -> O2RingBLEManager:
    manager = O2RingBLEManager(
        known_file=service._known_file,
        on_file=service._on_file,
        auto_sync_enabled=lambda: bool(service.settings().get("o2ring_auto_sync", True)),
    )
    manager.add_listener(service._remember_connected_device)
    return manager


def _rehydrate_service(service, *, restart: bool = True) -> dict[str, Any]:
    """Rebuild every O2 runtime cache from the files/config currently on disk."""
    root = service.store.root
    service.store = OximetryStore(root)
    service._load_known_names()

    manager = _fresh_manager(service)
    service.manager = manager
    cfg = service.settings()
    manager.set_preferred_device(cfg.get("o2ring_preferred_address"))

    should_run = bool(restart and service._ble_should_run(cfg))
    if should_run:
        # Preserve the restored snapshot as a stable restore point. Do not
        # immediately pull additional historical files from ring memory during
        # the restore operation; normal later/manual sync remains available.
        start_reliably(manager, sync_on_start=False)

    with service._lock:
        known_count = len(service._known_source_names)
    return {
        "recordings": len(service.store.list_recordings()),
        "known_sources": known_count,
        "remembered_device": bool(str(cfg.get("o2ring_preferred_address") or "").strip()),
        "ble_restarted": should_run,
        "sync_on_restore": False,
    }


def install_o2ring_restore(app_module) -> None:
    """Wrap Handler._restore_backup_job with an O2-safe lifecycle boundary."""
    global _installed
    if _installed:
        return

    service = get_service(app_module)
    handler_cls = app_module.Handler
    original_restore = handler_cls._restore_backup_job

    def _restore_backup_job(self, jid: str, uploaded: str):
        # app.py's base restore only re-applies keys present in its v5.2.20
        # defaults. O2 settings are v5.3-owned, so capture and validate them from
        # the full-backup manifest before the uploaded ZIP is removed.
        restored_o2_config = _read_backup_o2_config(uploaded)

        old_manager = service.manager
        self._progress(jid, 3, "O2Ring leállítása", "Bluetooth háttérfolyamat biztonságos leállítása…")
        _stop_and_wait(old_manager)

        try:
            result = original_restore(self, jid, uploaded)
        except Exception:
            # Restore may fail after partially touching private state. Rebuild
            # from whatever state the proven restore layer left on disk, but do
            # not let a secondary O2 recovery error hide the original failure.
            try:
                _rehydrate_service(service, restart=True)
            except Exception as recovery_exc:
                try:
                    self.persistent_log.append(
                        "HIBA", "o2ring", "O2Ring runtime helyreállítása sikertelen backup-hiba után.",
                        {"error": str(recovery_exc)},
                    )
                except Exception:
                    pass
            raise

        if restored_o2_config is not None:
            app_module.save_config(restored_o2_config)

        self._progress(jid, 98, "O2Ring visszaállítása", "Oximetriai állapot és Bluetooth runtime újraépítése…")
        runtime = _rehydrate_service(service, restart=True)
        if isinstance(result, dict):
            result["o2ring_rehydrated"] = True
            result["o2ring_recordings"] = int(runtime.get("recordings") or 0)
            result["o2ring_ble_restarted"] = bool(runtime.get("ble_restarted"))
            result["o2ring_config_restored"] = restored_o2_config is not None

        try:
            self.persistent_log.append(
                "INFO", "o2ring", "O2Ring állapot teljes backupból újrahidratálva.",
                {
                    "recordings": int(runtime.get("recordings") or 0),
                    "known_sources": int(runtime.get("known_sources") or 0),
                    "remembered_device": bool(runtime.get("remembered_device")),
                    "ble_restarted": bool(runtime.get("ble_restarted")),
                    "config_restored": restored_o2_config is not None,
                },
            )
        except Exception:
            pass
        return result

    handler_cls._restore_backup_job = _restore_backup_job
    _installed = True


__all__ = [
    "install_o2ring_restore",
    "_stop_and_wait",
    "_normalized_restore_config",
    "_read_backup_o2_config",
    "_rehydrate_service",
]
