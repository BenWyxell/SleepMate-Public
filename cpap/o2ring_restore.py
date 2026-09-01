"""Restore-safe O2Ring runtime rehydration for SleepMate v5.3.

Full backup restore replaces the private O2 recording/configuration snapshot.
The BLE worker must therefore be completely quiescent before restore starts,
and its in-memory live/device state must never survive across the restore
boundary. This layer wraps the proven v5.2.20 restore job without changing the
base maintenance implementation.
"""
from __future__ import annotations

from typing import Any

from .o2ring_ble import O2RingBLEManager
from .o2ring_integration import get_service
from .oximetry import OximetryStore


_installed = False
_STOP_TIMEOUT_SECONDS = 20.0


def _stop_and_wait(manager, timeout: float = _STOP_TIMEOUT_SECONDS) -> None:
    """Stop BLE and prove the worker cannot write into the restore target."""
    manager.stop()
    thread = getattr(manager, "_thread", None)
    if thread is not None and thread.is_alive():
        thread.join(max(0.1, float(timeout)))
    if thread is not None and thread.is_alive():
        raise RuntimeError(
            "Az O2Ring Bluetooth háttérfolyamata nem állt le időben; "
            "a backup visszaállítása biztonsági okból megszakadt."
        )


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
        manager.start(sync_on_start=False)

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

        self._progress(jid, 98, "O2Ring visszaállítása", "Oximetriai állapot és Bluetooth runtime újraépítése…")
        runtime = _rehydrate_service(service, restart=True)
        if isinstance(result, dict):
            result["o2ring_rehydrated"] = True
            result["o2ring_recordings"] = int(runtime.get("recordings") or 0)
            result["o2ring_ble_restarted"] = bool(runtime.get("ble_restarted"))

        try:
            self.persistent_log.append(
                "INFO", "o2ring", "O2Ring állapot teljes backupból újrahidratálva.",
                {
                    "recordings": int(runtime.get("recordings") or 0),
                    "known_sources": int(runtime.get("known_sources") or 0),
                    "remembered_device": bool(runtime.get("remembered_device")),
                    "ble_restarted": bool(runtime.get("ble_restarted")),
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
    "_rehydrate_service",
]
