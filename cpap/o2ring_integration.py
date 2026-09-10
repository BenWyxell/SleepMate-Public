from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
import time
import urllib.parse
from typing import Any

from .o2ring_ble import O2RingBLEManager
from .o2ring_clock import (
    DAY_SECONDS,
    created_at_epoch,
    detect_recent_one_day_lag,
    format_device_time,
    shifted_recording_payload,
)
from .o2ring_export import export_o2ring_data
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
    "o2ring_export_dir": "",
}


class O2RingService:
    CLOCK_SYNC_COOLDOWN_SECONDS = 6 * 60 * 60
    CLOCK_REPAIR_MARKER = "clock_repair_v5326.json"

    def __init__(self, app_module):
        self.app = app_module
        self.store = OximetryStore(app_module.STATE_BASE / "private")
        self._lock = threading.RLock()
        self._known_source_names: set[str] = set()
        self._last_export_folder: Path | None = None
        self._last_clock_sync_monotonic = 0.0
        # v5.3.26 one-time migration runs before BLE can import anything new.
        # It only touches the newest recording when created_at proves that its
        # VLD clock was almost exactly one day behind at download time.
        self._repair_latest_one_day_clock_lag()
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

    def _clock_repair_marker_path(self) -> Path:
        return self.store.root / "oximetry" / self.CLOCK_REPAIR_MARKER

    def _write_clock_repair_marker(self, payload: dict[str, Any]) -> None:
        path = self._clock_repair_marker_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        body = {
            "schema": 1,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)

    def _repair_latest_one_day_clock_lag(self) -> dict[str, Any] | None:
        """One-time, conservative repair for a freshly saved VLD exactly one day late."""
        marker = self._clock_repair_marker_path()
        if marker.is_file():
            return None
        try:
            rows = list(self.store.list_recordings())
            if not rows:
                return None

            def imported_at(row: dict[str, Any]) -> float:
                return float(created_at_epoch(row.get("created_at")) or 0.0)

            latest = max(rows, key=imported_at)
            created_ts = imported_at(latest)
            if created_ts <= 0:
                return None
            delta = detect_recent_one_day_lag(latest, now_ts=time.time())
            if delta != DAY_SECONDS:
                return None

            rid = str(latest.get("recording_id") or "").strip()
            if not rid:
                return None
            payload = self.store.get_recording(rid)
            if not isinstance(payload, dict):
                return None
            start_ts = float(payload.get("start_ts") or 0.0)
            end_ts = float(payload.get("end_ts") or 0.0)
            if end_ts <= start_ts:
                return None

            repaired_start = start_ts + delta
            repaired_end = end_ts + delta
            # Never create an accidental duplicate. Two genuine recordings on the
            # same calendar day are valid, so collision means same near-identical
            # time interval, not merely the same date.
            for other in rows:
                if str(other.get("recording_id") or "") == rid:
                    continue
                try:
                    other_start = float(other.get("start_ts") or 0.0)
                    other_end = float(other.get("end_ts") or 0.0)
                except (TypeError, ValueError):
                    continue
                if abs(other_start - repaired_start) <= 120 and abs(other_end - repaired_end) <= 120:
                    return None

            repaired = shifted_recording_payload(payload, delta)
            target = self.store.recordings_dir / f"{rid}.json"
            tmp = target.with_suffix(".repair.tmp")
            tmp.write_text(
                json.dumps(repaired, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            os.replace(tmp, target)
            self._write_clock_repair_marker({
                "status": "repaired",
                "recording_id": rid,
                "source_name": payload.get("source_name"),
                "delta_seconds": delta,
                "original_start_ts": start_ts,
                "original_end_ts": end_ts,
                "repaired_start_ts": repaired_start,
                "repaired_end_ts": repaired_end,
            })
            try:
                self.app.Handler.persistent_log.append(
                    "INFO",
                    "o2ring",
                    "O2Ring időbélyeg automatikusan javítva: a friss felvétel eszközórája egy nappal késett.",
                    {"recording_id": rid, "delta_seconds": delta, "source_name": payload.get("source_name")},
                )
            except Exception:
                pass
            return repaired
        except Exception as exc:
            # No data loss on migration failure. The raw VLD and original JSON
            # remain untouched unless the complete repaired JSON was atomically
            # written. Keep the marker absent so a later clean startup can retry.
            try:
                self.app.Handler.persistent_log.append(
                    "WARN", "o2ring", f"O2Ring egyszeri időbélyeg-javítás kihagyva: {exc}", {}
                )
            except Exception:
                pass
            return None

    def _queue_device_clock_sync(self, state: dict[str, Any]) -> None:
        """Keep the ring's local clock aligned without ever changing an active recording."""
        if not state.get("connected"):
            return
        if state.get("measuring") or state.get("worn") is True:
            return
        now = time.monotonic()
        if self._last_clock_sync_monotonic and now - self._last_clock_sync_monotonic < self.CLOCK_SYNC_COOLDOWN_SECONDS:
            return
        # Viatom Oxy CMD_CONFIG expects SetTIME as "yyyy-MM-dd,HH:mm:ss".
        value = format_device_time()
        self.manager.queue_device_config({"SetTIME": value})
        self._last_clock_sync_monotonic = now
        try:
            self.app.Handler.persistent_log.append(
                "INFO", "o2ring", "O2Ring eszközóra szinkronizálása előkészítve.", {"device_time": value}
            )
        except Exception:
            pass

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
        # If the one-day-late file was still only on the ring when v5.3.26
        # started, give the just-imported newest recording the same conservative
        # migration check. Once repaired, the marker makes this permanently
        # idempotent.
        self._repair_latest_one_day_clock_lag()

    def _remember_connected_device(self, state: dict[str, Any]) -> None:
        address = str(state.get("device_address") or "").strip()
        if address:
            cfg = self.settings()
            if not str(cfg.get("o2ring_preferred_address") or "").strip():
                self.app.save_config({"o2ring_preferred_address": address})
                self.manager.set_preferred_device(address)
        self._queue_device_clock_sync(state)

    def settings(self) -> dict[str, Any]:
        cfg = dict(DEFAULTS)
        cfg.update({k: v for k, v in self.app.load_config().items() if k in DEFAULTS})
        if not str(cfg.get("o2ring_export_dir") or "").strip():
            cfg["o2ring_export_dir"] = str(self.app.STATE_BASE / "private" / "o2ring_exports")
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
        if not current.get("o2ring_auto_sync", True):
            self.manager.cancel_auto_sync()

        if self._ble_should_run(current):
            start_reliably(self.manager, sync_on_start=bool(current.get("o2ring_auto_sync", True)))
        else:
            # Configuration OFF is complete only when the worker can no longer
            # reconnect or write another VLD into local state.
            stop_and_wait(self.manager)
        return self.settings()

    def prepare_export_sync(self, timeout: float = 8.0) -> dict[str, Any]:
        """Try one ordinary sync before export, without ever blocking BLE work."""
        live = self.manager.snapshot()
        attempted = bool(live.get("connected") and not live.get("measuring"))
        if not attempted:
            return {"sync_attempted": False, "sync_completed": True}
        self.manager.request_sync()
        completed = self.manager.wait_for_sync(max(0.0, min(15.0, float(timeout))))
        return {"sync_attempted": True, "sync_completed": bool(completed)}

    def export_all(self, *, destination: str | None = None,
                   sync_before: bool = True, sync_timeout: float = 8.0) -> dict[str, Any]:
        if destination is not None:
            destination = str(destination).strip()
            if not destination:
                raise ValueError("Válassz exportálási mappát.")
            self.save_settings({"o2ring_export_dir": destination})
        export_dir = str(self.settings().get("o2ring_export_dir") or "").strip()
        if not export_dir:
            raise ValueError("Válassz exportálási mappát.")
        sync = self.prepare_export_sync(sync_timeout) if sync_before else {
            "sync_attempted": False, "sync_completed": True,
        }
        result = export_o2ring_data(self.store, export_dir)
        self._last_export_folder = Path(result["folder"]).resolve()
        result.update(sync)
        if sync.get("sync_attempted") and not sync.get("sync_completed"):
            result["warning"] = (
                "A gyűrű szinkronizálása most nem fejeződött be. Az export a jelenleg "
                "rendelkezésre álló lezárt mérésekből elkészült."
            )
        return result

    def open_last_export_folder(self) -> dict[str, Any]:
        folder = self._last_export_folder
        if folder is None or not folder.is_dir():
            raise ValueError("Nincs megnyitható O2Ring exportmappa.")
        if os.name != "nt" or not hasattr(os, "startfile"):
            raise RuntimeError("A mappa automatikus megnyitása ezen a platformon nem érhető el.")
        os.startfile(str(folder))  # type: ignore[attr-defined]
        return {"ok": True, "folder": str(folder)}

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
        if path == "/api/o2ring/export-sync":
            try:
                data = self._read_json_body(max_bytes=10_000)
                return self._json(service.prepare_export_sync(float(data.get("timeout") or 8.0)))
            except Exception as exc:
                return self._json({"error": str(exc)}, 409)
        if path == "/api/o2ring/export":
            try:
                data = self._read_json_body(max_bytes=100_000)
                return self._json(service.export_all(
                    destination=data.get("export_dir"),
                    sync_before=bool(data.get("sync_before", True)),
                ))
            except Exception as exc:
                return self._json({"error": str(exc)}, 400)
        if path == "/api/o2ring/open-export-folder":
            try:
                return self._json(service.open_last_export_folder())
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
