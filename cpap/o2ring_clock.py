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
    """Never infer a stored one-day correction from import time alone.

    v5.3.26 attempted a deliberately narrow automatic repair when ``created_at``
    was about one day after a VLD's stored end timestamp. Field evidence showed
    that a *missing newest VLD download* can look like a calendar-day problem in
    the UI while the last visible historical recording is actually correct.

    Rewriting health-data timestamps from import timing is therefore too
    speculative. The VLD header remains the source of truth; recovery now happens
    in the BLE/sync lifecycle instead of mutating an existing recording.
    """
    _ = recording, now_ts
    return None


def shifted_recording_payload(payload: dict[str, Any], delta_seconds: float) -> dict[str, Any]:
    """Shift a recording payload explicitly; retained for controlled/manual tooling.

    This helper is intentionally not used for automatic migration in v5.3.27.
    """
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
        "reason": "explicit_timestamp_shift",
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
