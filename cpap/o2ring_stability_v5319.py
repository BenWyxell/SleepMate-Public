from __future__ import annotations

"""v5.3.19 startup hardening for the O2Ring integration.

The O2 HTTP/UI control plane must never wait for historical recording parsing.
Known recording source names are hydrated in the background. While that bounded
hydration is running, incoming device files are conservatively treated as known
so auto-sync cannot duplicate or resurrect data before the index is ready.
"""

import json
import threading
from typing import Any


def install_o2ring_stability_v5319() -> None:
    from . import o2ring_integration as integration

    cls = integration.O2RingService
    if getattr(cls, "__sleepmate_v5319_stability__", False):
        return

    original_load_known_names = cls._load_known_names
    original_known_file = cls._known_file

    def load_known_names_nonblocking(self) -> None:
        # Deleted-source tombstones are security/data-integrity critical and are
        # tiny, so load them synchronously before BLE may start.
        known: set[str] = set()
        tombstone_path = self.store.root / "oximetry" / "deleted_sources.json"
        if tombstone_path.is_file():
            try:
                payload = json.loads(tombstone_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict) and int(payload.get("schema") or 0) == 1:
                    known.update(
                        str(value or "").strip()
                        for value in (payload.get("source_names") or [])
                        if str(value or "").strip()
                    )
            except Exception:
                pass
        with self._lock:
            self._known_source_names = known

        ready = threading.Event()
        self._known_names_ready_v5319 = ready

        def hydrate() -> None:
            try:
                historical = {
                    str(row.get("source_name") or "").strip()
                    for row in self.store.list_recordings()
                    if str(row.get("source_name") or "").strip()
                }
                with self._lock:
                    self._known_source_names.update(historical)
            except Exception as exc:
                try:
                    self.app.Handler.persistent_log.append(
                        "WARN",
                        "o2ring",
                        "Az O2Ring előzményindex háttérbetöltése nem sikerült; a felület ettől még elindult.",
                        {"error": str(exc)},
                    )
                except Exception:
                    pass
            finally:
                ready.set()

        threading.Thread(
            target=hydrate,
            name="SleepMate-O2Ring-Metadata",
            daemon=True,
        ).start()

    def known_file_safe_during_hydration(self, name: str) -> bool:
        ready = getattr(self, "_known_names_ready_v5319", None)
        if ready is not None and not ready.is_set():
            # Never import anything until persisted names have been indexed.
            return True
        return original_known_file(self, name)

    def status_without_recording_parse(self) -> dict[str, Any]:
        cfg = self.settings()
        ready = getattr(self, "_known_names_ready_v5319", None)
        return {
            "settings": cfg,
            "feature_enabled": bool(cfg.get("o2ring_enabled")),
            "ble_enabled": bool(cfg.get("o2ring_enabled") and cfg.get("o2ring_ble_enabled", True)),
            "live": self.manager.snapshot(),
            # Directory enumeration only: no JSON file is opened here.
            "recordings": self.store.count_recordings(),
            "metadata_ready": bool(ready is None or ready.is_set()),
        }

    cls._load_known_names = load_known_names_nonblocking
    cls._known_file = known_file_safe_during_hydration
    cls.status = status_without_recording_parse
    cls.__sleepmate_v5319_stability__ = True


__all__ = ["install_o2ring_stability_v5319"]
