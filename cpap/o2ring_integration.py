from __future__ import annotations

from dataclasses import asdict
import json
import threading
import urllib.parse
from typing import Any

from .o2ring_ble import O2RingBLEManager
from .o2ring_lifecycle import start_reliably, stop_and_wait
from .o2ring_vld import parse_vld
from .oximetry import OximetrySample, OximetryStore, match_recording_to_cpap, summarize_samples


_installed = False
_service = None


DEFAULTS = {
    # Master feature switch. When false the UI must look like O2Ring does not exist.
    "o2ring_enabled": False,
    # BLE runtime switch. Turning this off never forgets the remembered ring.
    "o2ring_ble_enabled": True,
    "o2ring_auto_connect": True,
    "o2ring_auto_sync": True,
    "o2ring_auto_match": True,
    "o2ring_preferred_address": "",
    "o2ring_clock_offset_seconds": 0.0,
    "o2ring_show_motion": False,
    "o2ring_spo2_reference": 90,
    "o2ring_spo2_secondary_reference": 88,
}


class O2RingService:
    def __init__(self, app_module):
        self.app = app_module
        self.store = OximetryStore(app_module.STATE_BASE / "private")
        self._lock = threading.RLock()
        self._known_source_names: set[str] = set()
        # This must happen before the BLE manager is allowed to start. Deleted
        # O2Ring sessions can still remain in ring memory; treating persisted
        # tombstones as known at construction time closes the restart race where
        # automatic sync could otherwise re-import already deleted health data.
        self._load_known_names()
        self.manager = O2RingBLEManager(
            known_file=self._known_file,
            on_file=self._on_file,
            auto_sync_enabled=lambda: bool(self.settings().get("o2ring_auto_sync", True)),
        )
        cfg = self.settings()
        self.manager.set_preferred_device(cfg.get("o2ring_preferred_address"))
        self.manager.add_listener(self._remember_connected_device)
        if self._ble_should_run(cfg):
            self.manager.start(sync_on_start=bool(cfg.get("o2ring_auto_sync", True)))

    @staticmethod
    def _ble_should_run(cfg: dict[str, Any]) -> bool:
        return bool(
            cfg.get("o2ring_enabled")
            and cfg.get("o2ring_ble_enabled", True)
            and cfg.get("o2ring_auto_connect", True)
        )

    def _load_known_names(self) -> None:
        known = {
            str(row.get("source_name") or "").strip()
            for row in self.store.list_recordings()
            if str(row.get("source_name") or "").strip()
        }
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
                # A malformed tombstone file must not make SleepMate fail to
                # start. Data management can rewrite it on the next deletion.
                pass
        with self._lock:
            self._known_source_names = known

    def _known_file(self, name: str) -> bool:
        with self._lock:
            return name in self._known_source_names

    def _on_file(self, name: str, raw: bytes, info: dict[str, Any]) -> None:
        parsed = parse_vld(raw)
        snap = self.manager.snapshot()
        device_id = str(info.get("SN") or snap.get("remembered_address") or snap.get("device_address") or info.get("Model") or "O2Ring")
        payload = self.store.save_recording(
            device_id=device_id,
            start_ts=parsed.start_ts,
            end_ts=parsed.end_ts,
            samples=parsed.samples,
            source_name=name,
            raw_bytes=raw,
        )
        with self._lock:
            self._known_source_names.add(name)
        try:
            self.app.Handler.persistent_log.append(
                "INFO", "o2ring", "Új O2Ring felvétel automatikusan letöltve.",
                {"source_name": name, "recording_id": payload.get("recording_id"), "samples": len(parsed.samples)},
            )
        except Exception:
            pass

    def _remember_connected_device(self, state: dict[str, Any]) -> None:
        address = str(state.get("device_address") or "").strip()
        if not address:
            return
        cfg = self.settings()
        if not str(cfg.get("o2ring_preferred_address") or "").strip():
            self.app.save_config({"o2ring_preferred_address": address})
            self.manager.set_preferred_device(address)

    def settings(self) -> dict[str, Any]:
        cfg = dict(DEFAULTS)
        cfg.update({k: v for k, v in self.app.load_config().items() if k in DEFAULTS})
        return cfg

    def save_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        current = self.settings()
        update: dict[str, Any] = {}
        bool_keys = {
            "o2ring_enabled", "o2ring_ble_enabled", "o2ring_auto_connect",
            "o2ring_auto_sync", "o2ring_auto_match", "o2ring_show_motion",
        }
        for key in DEFAULTS:
            if key not in data:
                continue
            value = data[key]
            if key in bool_keys:
                update[key] = bool(value)
            elif key == "o2ring_clock_offset_seconds":
                update[key] = max(-900.0, min(900.0, float(value or 0)))
            elif key in {"o2ring_spo2_reference", "o2ring_spo2_secondary_reference"}:
                update[key] = max(70, min(100, int(value)))
            else:
                update[key] = str(value or "").strip()

        current.update(update)
        self.app.save_config(update)
        self.manager.set_preferred_device(current.get("o2ring_preferred_address"))

        if self._ble_should_run(current):
            start_reliably(self.manager, sync_on_start=bool(current.get("o2ring_auto_sync", True)))
        else:
            # Configuration OFF is complete only when the worker can no longer
            # reconnect or write another VLD into local state.
            stop_and_wait(self.manager)
        return self.settings()

    def forget_device(self) -> dict[str, Any]:
        """Explicitly forget the selected ring without deleting historical data."""
        # Wait before clearing pairing so a final callback from the old connection
        # cannot immediately remember the address again.
        stop_and_wait(self.manager)
        self.manager.set_preferred_device(None)
        self.app.save_config({"o2ring_preferred_address": ""})
        return self.status()

    def status(self) -> dict[str, Any]:
        cfg = self.settings()
        return {
            "settings": cfg,
            "feature_enabled": bool(cfg.get("o2ring_enabled")),
            "ble_enabled": bool(cfg.get("o2ring_enabled") and cfg.get("o2ring_ble_enabled", True)),
            "live": self.manager.snapshot(),
            "recordings": len(self.store.list_recordings()),
        }

    def recordings(self) -> list[dict[str, Any]]:
        rows = []
        for item in self.store.list_recordings():
            rows.append({k: item.get(k) for k in (
                "recording_id", "device_id", "source_name", "start_ts", "end_ts", "created_at", "summary"
            )})
        return rows

    def recording(self, recording_id: str, max_points: int = 8000) -> dict[str, Any] | None:
        row = self.store.get_recording(recording_id)
        if not row:
            return None
        samples = list(row.get("samples") or [])
        if max_points > 0 and len(samples) > max_points:
            step = max(1, len(samples) // max_points)
            samples = samples[::step]
        return {
            **{k: row.get(k) for k in (
                "recording_id", "device_id", "source_name", "start_ts", "end_ts", "created_at", "summary"
            )},
            "samples": samples,
        }

    def daily(self, day: str, max_points: int = 8000) -> dict[str, Any]:
        sessions = list(self.app.Handler.dataset.sessions(day))
        if not sessions:
            return {"day": day, "available": False, "matches": [], "samples": [], "summary": None}
        day_start = sessions[0].start.timestamp()
        cfg = self.settings()
        offset = float(cfg.get("o2ring_clock_offset_seconds") or 0.0)
        matches: list[dict[str, Any]] = []
        selected: dict[tuple[float, int | None, int | None], OximetrySample] = {}
        for rec in self.store.list_recordings():
            raw_samples = list(rec.get("samples") or [])
            for session_index, session in enumerate(sessions):
                match = match_recording_to_cpap(
                    rec, session.start.timestamp(), session.end.timestamp(),
                    clock_offset_seconds=offset,
                )
                if not match:
                    continue
                matches.append({
                    **asdict(match), "session_index": session_index,
                    "source_name": rec.get("source_name"),
                })
                for sample in raw_samples:
                    ts = float(sample.get("timestamp") or 0) + offset
                    if match.overlap_start <= ts <= match.overlap_end:
                        obj = OximetrySample(
                            timestamp=ts,
                            spo2=sample.get("spo2"),
                            heart_rate=sample.get("heart_rate"),
                            motion=sample.get("motion"),
                            valid=bool(sample.get("valid", True)),
                        )
                        selected[(ts, obj.spo2, obj.heart_rate)] = obj
        samples = sorted(selected.values(), key=lambda x: x.timestamp)
        if not samples:
            return {"day": day, "available": False, "matches": matches, "samples": [], "summary": None}
        full_samples = samples
        if len(samples) > max_points:
            step = max(1, len(samples) // max_points)
            samples = samples[::step]
        summary = summarize_samples(
            full_samples,
            start_ts=full_samples[0].timestamp,
            end_ts=full_samples[-1].timestamp,
        )
        return {
            "day": day,
            "available": True,
            "matches": matches,
            "summary": asdict(summary),
            "samples": [
                {
                    "t": round(s.timestamp - day_start, 3),
                    "timestamp": s.timestamp,
                    "spo2": s.spo2,
                    "heart_rate": s.heart_rate,
                    "motion": s.motion,
                    "valid": s.valid,
                }
                for s in samples
            ],
        }

    def trends(self, limit: int = 90) -> dict[str, Any]:
        rows = self.recordings()[:max(1, min(1000, limit))]
        rows.reverse()
        return {"rows": rows, "count": len(rows)}


def get_service(app_module=None) -> O2RingService:
    global _service
    if _service is None:
        if app_module is None:
            raise RuntimeError("Az O2Ring szolgáltatás még nincs inicializálva.")
        _service = O2RingService(app_module)
    return _service


def install_o2ring_integration(app_module) -> None:
    global _installed
    if _installed:
        return
    service = get_service(app_module)
    handler_cls = app_module.Handler
    original_get = handler_cls.do_GET
    original_post = handler_cls.do_POST

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        if path == "/api/o2ring/status":
            return self._json(service.status())
        if path == "/api/o2ring/settings":
            return self._json(service.settings())
        if path == "/api/o2ring/recordings":
            return self._json({"rows": service.recordings()})
        if path == "/api/o2ring/trends":
            return self._json(service.trends(int(query.get("limit", ["90"])[0])))
        if path == "/api/o2ring/recording":
            rid = str(query.get("id", [""])[0])
            row = service.recording(rid, int(query.get("max_points", ["8000"])[0]))
            return self._json(row if row else {"error": "Az O2Ring felvétel nem található."}, 200 if row else 404)
        if path == "/api/o2ring/day":
            day = str(query.get("day", [""])[0]).replace("-", "")[:8]
            if len(day) != 8 or not day.isdigit():
                return self._json({"error": "Érvénytelen nap."}, 400)
            return self._json(service.daily(day, int(query.get("max_points", ["8000"])[0])))
        return original_get(self)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/o2ring/settings":
            try:
                return self._json(service.save_settings(self._read_json_body(max_bytes=100_000)))
            except Exception as exc:
                return self._json({"error": str(exc)}, 400)
        if path == "/api/o2ring/connect":
            cfg = service.settings()
            if not cfg.get("o2ring_enabled"):
                return self._json({"error": "Az O2Ring integráció nincs bekapcsolva."}, 409)
            if not cfg.get("o2ring_ble_enabled", True):
                return self._json({"error": "Az O2Ring Bluetooth funkció ki van kapcsolva."}, 409)
            try:
                start_reliably(service.manager, sync_on_start=False)
                return self._json({"ok": True})
            except Exception as exc:
                return self._json({"error": str(exc)}, 409)
        if path == "/api/o2ring/sync":
            cfg = service.settings()
            if not cfg.get("o2ring_enabled"):
                return self._json({"error": "Az O2Ring integráció nincs bekapcsolva."}, 409)
            if not cfg.get("o2ring_ble_enabled", True):
                return self._json({"error": "Az O2Ring Bluetooth funkció ki van kapcsolva."}, 409)
            try:
                start_reliably(service.manager, sync_on_start=False)
                service.manager.request_sync()
                return self._json({"ok": True, "message": "O2Ring szinkron kérése elindult."})
            except Exception as exc:
                return self._json({"error": str(exc)}, 409)
        if path == "/api/o2ring/forget-device":
            try:
                return self._json(service.forget_device())
            except Exception as exc:
                return self._json({"error": str(exc)}, 409)
        return original_post(self)

    handler_cls.do_GET = do_GET
    handler_cls.do_POST = do_POST
    _installed = True


__all__ = ["DEFAULTS", "O2RingService", "get_service", "install_o2ring_integration"]
