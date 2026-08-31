from __future__ import annotations

from typing import Any

from . import sleep_analysis as sa
from .sleepsync_engine_v2 import SleepSyncService


_installed = False


def _invalidate_sleep_analysis(app_module, reason: str, sync_service: SleepSyncService | None = None) -> None:
    """Drop the adaptive sleep-analysis cache after therapy data changed.

    ResMedDataset.refresh() already clears the EDF/session caches and advances
    ``last_refresh_at``.  Sleep analysis has its own memoized payload on top of
    that dataset though, and an already-open PWA can keep rendering the previous
    rows until another analysis request happens.  Clear that memo explicitly at
    the data-import boundary so the next request must rebuild blocks from the
    freshly imported EDF files.
    """
    try:
        service = sa.get_sleep_analysis_service(app_module)
        with service._lock:
            service._cache_key = None
            service._cache_payload = None
        if sync_service is not None:
            sync_service.log(f"Alvások elemzési cache érvénytelenítve: {reason}.")
    except Exception as exc:
        # A successful CPAP import must never be converted into a failed sync just
        # because the derived sleep view could not be invalidated. The next normal
        # dataset refresh still changes last_refresh_at and therefore remains a
        # fallback invalidation path.
        if sync_service is not None:
            sync_service.log(f"Alvások cache-ének érvénytelenítése kihagyva: {exc}", "WARN")


def install_sleep_refresh_v5212(app_module) -> None:
    """Keep Szekciók → Alvások synchronized with successful SleepSync imports."""
    global _installed
    if _installed:
        return

    original_sync_connected = SleepSyncService._sync_connected
    original_backup_connected = SleepSyncService._backup_connected

    def sync_connected(self: SleepSyncService, jid: str) -> dict[str, Any]:
        result = original_sync_connected(self, jid)
        _invalidate_sleep_analysis(app_module, "SleepSync szinkron", self)
        return result

    def backup_connected(self: SleepSyncService, jid: str) -> dict[str, Any]:
        result = original_backup_connected(self, jid)
        _invalidate_sleep_analysis(app_module, "SleepSync teljes SD mentés", self)
        return result

    SleepSyncService._sync_connected = sync_connected
    SleepSyncService._backup_connected = backup_connected
    _installed = True


__all__ = ["install_sleep_refresh_v5212"]
