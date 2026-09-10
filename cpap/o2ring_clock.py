from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


DAY_SECONDS = 86_400.0
ONE_DAY_LAG_MIN_SECONDS = 20 * 60 * 60
ONE_DAY_LAG_MAX_SECONDS = 28 * 60 * 60
REPAIRED_END_MAX_DISTANCE_SECONDS = 4 * 60 * 60
MAX_REPAIR_RECORD_AGE_SECONDS = 7 * DAY_SECONDS


def format_device_time(now: datetime | None = None) -> str:
    """Return the O2Ring SetTIME value in the vendor's local-wall-clock format."""
    value = now or datetime.now()
    if value.tzinfo is not None:
        value = value.astimezone().replace(tzinfo=None)
    return value.strftime("%Y-%m-%d,%H:%M:%S")


def created_at_epoch(value: Any) -> float | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def detect_recent_one_day_lag(recording: dict[str, Any], *, now_ts: float) -> float | None:
    """Detect the narrow v5.3.26 migration case: a fresh recording exactly one day late.

    The O2Ring VLD header contains local device date/time. If the ring RTC is one
    calendar day behind, a freshly auto-downloaded session has a created_at about
    24 hours after its stored end_ts. We intentionally do not repair arbitrary old
    recordings: only the newest, recently-created item is eligible and only when
    adding exactly one day puts its end close to the import time.
    """
    created_ts = created_at_epoch(recording.get("created_at"))
    try:
        end_ts = float(recording.get("end_ts") or 0.0)
        start_ts = float(recording.get("start_ts") or 0.0)
    except (TypeError, ValueError):
        return None
    if created_ts is None or end_ts <= start_ts:
        return None
    if abs(float(now_ts) - created_ts) > MAX_REPAIR_RECORD_AGE_SECONDS:
        return None
    lag = created_ts - end_ts
    if not (ONE_DAY_LAG_MIN_SECONDS <= lag <= ONE_DAY_LAG_MAX_SECONDS):
        return None
    repaired_end = end_ts + DAY_SECONDS
    if abs(created_ts - repaired_end) > REPAIRED_END_MAX_DISTANCE_SECONDS:
        return None
    return DAY_SECONDS


def shifted_recording_payload(payload: dict[str, Any], delta_seconds: float) -> dict[str, Any]:
    """Shift one stored recording while preserving its stable recording_id/raw VLD."""
    delta = float(delta_seconds)
    result = deepcopy(payload)
    original_start = float(result.get("start_ts") or 0.0)
    original_end = float(result.get("end_ts") or 0.0)
    result["start_ts"] = original_start + delta
    result["end_ts"] = original_end + delta
    samples = result.get("samples")
    if isinstance(samples, list):
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            try:
                sample["timestamp"] = float(sample.get("timestamp") or 0.0) + delta
            except (TypeError, ValueError):
                continue
    result["time_repair"] = {
        "schema": 1,
        "reason": "device_clock_one_day_lag",
        "delta_seconds": delta,
        "original_start_ts": original_start,
        "original_end_ts": original_end,
        "repaired_at": datetime.now(timezone.utc).isoformat(),
        "raw_vld_preserved": True,
    }
    return result


__all__ = [
    "DAY_SECONDS",
    "format_device_time",
    "created_at_epoch",
    "detect_recent_one_day_lag",
    "shifted_recording_payload",
]
