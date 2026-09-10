from __future__ import annotations

from datetime import datetime
import re
import threading
import time

from cpap.o2ring_clock import DAY_SECONDS, detect_recent_one_day_lag, format_device_time, shifted_recording_payload
from cpap.o2ring_integration import O2RingService
from cpap.oximetry import OximetrySample, OximetryStore


def test_vendor_settime_format_is_local_wall_clock() -> None:
    value = format_device_time(datetime(2026, 9, 10, 6, 7, 8))
    assert value == "2026-09-10,06:07:08"


def test_exact_recent_one_day_lag_is_detected_but_normal_import_is_not() -> None:
    now = time.time()
    stale = {
        "start_ts": now - DAY_SECONDS - 7 * 3600,
        "end_ts": now - DAY_SECONDS - 60,
        "created_at": datetime.now().astimezone().isoformat(),
    }
    assert detect_recent_one_day_lag(stale, now_ts=now) == DAY_SECONDS

    normal = dict(stale)
    normal["end_ts"] = now - 60
    assert detect_recent_one_day_lag(normal, now_ts=now) is None


def test_timestamp_shift_preserves_recording_identity_and_moves_all_samples() -> None:
    payload = {
        "recording_id": "stable-id",
        "start_ts": 1000.0,
        "end_ts": 1010.0,
        "summary": {"spo2_average": 96.2},
        "samples": [
            {"timestamp": 1000.0, "spo2": 97, "heart_rate": 60, "valid": True},
            {"timestamp": 1004.0, "spo2": 96, "heart_rate": 61, "valid": True},
        ],
    }
    fixed = shifted_recording_payload(payload, DAY_SECONDS)
    assert fixed["recording_id"] == "stable-id"
    assert fixed["start_ts"] == 1000.0 + DAY_SECONDS
    assert fixed["end_ts"] == 1010.0 + DAY_SECONDS
    assert fixed["samples"][0]["timestamp"] == 1000.0 + DAY_SECONDS
    assert fixed["samples"][1]["timestamp"] == 1004.0 + DAY_SECONDS
    assert fixed["summary"] == payload["summary"]
    assert fixed["time_repair"]["raw_vld_preserved"] is True


class _Log:
    def append(self, *_args, **_kwargs):
        return None


class _Handler:
    persistent_log = _Log()


class _App:
    Handler = _Handler


class _Manager:
    def __init__(self):
        self.queued = []

    def queue_device_config(self, update):
        self.queued.append(dict(update))


def _service_without_init(store: OximetryStore) -> O2RingService:
    service = O2RingService.__new__(O2RingService)
    service.app = _App
    service.store = store
    service._lock = threading.RLock()
    service._known_source_names = set()
    service._last_export_folder = None
    service._last_clock_sync_monotonic = 0.0
    return service


def test_v5326_repairs_already_saved_latest_recording_exactly_once(tmp_path) -> None:
    store = OximetryStore(tmp_path)
    now = time.time()
    stale_end = now - DAY_SECONDS - 30
    stale_start = stale_end - 3600
    saved = store.save_recording(
        device_id="ring",
        start_ts=stale_start,
        end_ts=stale_end,
        samples=[OximetrySample(timestamp=stale_start, spo2=96, heart_rate=60)],
        source_name="stale.vld",
        raw_bytes=b"raw-vld-kept",
    )
    service = _service_without_init(store)

    fixed = service._repair_latest_one_day_clock_lag()
    assert fixed is not None
    row = store.get_recording(saved["recording_id"])
    assert row is not None
    assert abs(float(row["start_ts"]) - (stale_start + DAY_SECONDS)) < 0.01
    assert abs(float(row["end_ts"]) - (stale_end + DAY_SECONDS)) < 0.01
    assert abs(float(row["samples"][0]["timestamp"]) - (stale_start + DAY_SECONDS)) < 0.01
    assert (store.raw_dir / f"{saved['recording_id']}.vld").read_bytes() == b"raw-vld-kept"
    assert service._clock_repair_marker_path().is_file()

    # Marker makes the migration idempotent; a restart cannot shift the same
    # recording by another day.
    assert service._repair_latest_one_day_clock_lag() is None
    again = store.get_recording(saved["recording_id"])
    assert again is not None
    assert abs(float(again["start_ts"]) - (stale_start + DAY_SECONDS)) < 0.01


def test_clock_sync_is_queued_only_when_ring_is_not_recording(tmp_path) -> None:
    service = _service_without_init(OximetryStore(tmp_path))
    service.manager = _Manager()

    service._queue_device_clock_sync({"connected": True, "worn": True, "measuring": True})
    assert service.manager.queued == []

    service._queue_device_clock_sync({"connected": True, "worn": False, "measuring": False})
    assert len(service.manager.queued) == 1
    value = service.manager.queued[0]["SetTIME"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2},\d{2}:\d{2}:\d{2}", value)

    # Repeated live packets must not spam device configuration writes.
    service._queue_device_clock_sync({"connected": True, "worn": False, "measuring": False})
    assert len(service.manager.queued) == 1
