"""SleepMate O2Ring / oximetry domain services.

This module intentionally contains no UI code. It owns the local, reproducible
representation of O2Ring recordings and the CPAP-session matching rules.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from statistics import median
from typing import Iterable, Sequence


@dataclass(frozen=True)
class OximetrySample:
    timestamp: float
    spo2: int | None
    heart_rate: int | None
    motion: int | None = None
    valid: bool = True


@dataclass(frozen=True)
class OximetrySummary:
    sample_count: int
    valid_sample_count: int
    coverage_percent: float
    spo2_average: float | None
    spo2_median: float | None
    spo2_minimum: int | None
    spo2_maximum: int | None
    heart_rate_average: float | None
    heart_rate_median: float | None
    heart_rate_minimum: int | None
    heart_rate_maximum: int | None
    t90_seconds: float
    t90_percent: float
    odi3: float | None
    odi4: float | None


@dataclass(frozen=True)
class SessionMatch:
    recording_id: str
    cpap_start: float
    cpap_end: float
    overlap_start: float
    overlap_end: float
    overlap_seconds: float
    cpap_coverage_percent: float
    clock_offset_seconds: float = 0.0


class OximetryStore:
    """Simple file-backed store kept separate from the external CPAP source."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.recordings_dir = self.root / "oximetry" / "recordings"
        self.raw_dir = self.root / "oximetry" / "raw"
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def recording_id(device_id: str, start_ts: float, end_ts: float) -> str:
        payload = f"{device_id}|{start_ts:.3f}|{end_ts:.3f}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:24]

    def save_recording(self, *, device_id: str, start_ts: float, end_ts: float,
                       samples: Sequence[OximetrySample], source_name: str | None = None,
                       raw_bytes: bytes | None = None) -> dict:
        rid = self.recording_id(device_id, start_ts, end_ts)
        summary = summarize_samples(samples, start_ts=start_ts, end_ts=end_ts)
        payload = {
            "schema": 1,
            "recording_id": rid,
            "device_id": device_id,
            "source_name": source_name,
            "start_ts": start_ts,
            "end_ts": end_ts,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "summary": asdict(summary),
            "samples": [asdict(item) for item in samples],
        }
        target = self.recordings_dir / f"{rid}.json"
        target.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        if raw_bytes is not None:
            (self.raw_dir / f"{rid}.vld").write_bytes(raw_bytes)
        return payload

    def list_recordings(self) -> list[dict]:
        result: list[dict] = []
        for path in sorted(self.recordings_dir.glob("*.json"), reverse=True):
            try:
                result.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
        return sorted(result, key=lambda item: float(item.get("start_ts") or 0), reverse=True)

    def get_recording(self, recording_id: str) -> dict | None:
        safe_id = "".join(ch for ch in str(recording_id) if ch.isalnum() or ch in "-_")
        path = self.recordings_dir / f"{safe_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))


def _valid_values(samples: Iterable[OximetrySample], attr: str) -> list[int]:
    values: list[int] = []
    for sample in samples:
        value = getattr(sample, attr)
        if sample.valid and value is not None:
            values.append(int(value))
    return values


def _nominal_interval(samples: Sequence[OximetrySample], start_ts: float, end_ts: float) -> float:
    ordered = sorted(samples, key=lambda s: float(s.timestamp))
    deltas = [
        float(b.timestamp) - float(a.timestamp)
        for a, b in zip(ordered, ordered[1:])
        if 0 < float(b.timestamp) - float(a.timestamp) <= 60.0
    ]
    if deltas:
        return float(median(deltas))
    duration = max(0.0, float(end_ts) - float(start_ts))
    return duration / len(ordered) if ordered and duration > 0 else 0.0


def _odi(samples: Sequence[OximetrySample], threshold: int, duration_hours: float) -> float | None:
    if duration_hours <= 0:
        return None
    valid = [s for s in sorted(samples, key=lambda x: x.timestamp) if s.valid and s.spo2 is not None]
    if len(valid) < 2:
        return None
    events = 0
    baseline = int(valid[0].spo2)
    in_drop = False
    for sample in valid[1:]:
        value = int(sample.spo2)
        if not in_drop and baseline - value >= threshold:
            events += 1
            in_drop = True
        if in_drop and value >= baseline - 1:
            in_drop = False
            baseline = value
        elif not in_drop and value > baseline:
            baseline = value
    return round(events / duration_hours, 2)


def summarize_samples(samples: Sequence[OximetrySample], *, start_ts: float, end_ts: float) -> OximetrySummary:
    ordered = sorted(samples, key=lambda s: float(s.timestamp))
    nominal_interval = _nominal_interval(ordered, start_ts, end_ts)
    provided_duration = max(0.0, float(end_ts) - float(start_ts))
    sampled_duration = nominal_interval * len(ordered) if nominal_interval > 0 else provided_duration
    duration = max(provided_duration, sampled_duration)

    valid_samples = [s for s in ordered if s.valid]
    spo2 = _valid_values(ordered, "spo2")
    heart_rate = _valid_values(ordered, "heart_rate")
    t90_samples = sum(1 for s in ordered if s.valid and s.spo2 is not None and int(s.spo2) < 90)
    t90_seconds = t90_samples * nominal_interval if nominal_interval > 0 else 0.0
    valid_seconds = len(valid_samples) * nominal_interval if nominal_interval > 0 else 0.0
    duration_hours = duration / 3600.0

    coverage_percent = (
        valid_seconds / duration * 100.0
        if duration > 0 and nominal_interval > 0
        else ((len(valid_samples) / len(ordered) * 100.0) if ordered else 0.0)
    )
    coverage_percent = max(0.0, min(100.0, coverage_percent))

    return OximetrySummary(
        sample_count=len(ordered),
        valid_sample_count=len(valid_samples),
        coverage_percent=round(coverage_percent, 2),
        spo2_average=round(sum(spo2) / len(spo2), 2) if spo2 else None,
        spo2_median=round(float(median(spo2)), 2) if spo2 else None,
        spo2_minimum=min(spo2) if spo2 else None,
        spo2_maximum=max(spo2) if spo2 else None,
        heart_rate_average=round(sum(heart_rate) / len(heart_rate), 2) if heart_rate else None,
        heart_rate_median=round(float(median(heart_rate)), 2) if heart_rate else None,
        heart_rate_minimum=min(heart_rate) if heart_rate else None,
        heart_rate_maximum=max(heart_rate) if heart_rate else None,
        t90_seconds=round(t90_seconds, 1),
        t90_percent=round((t90_seconds / duration * 100.0) if duration else 0.0, 2),
        odi3=_odi(ordered, 3, duration_hours),
        odi4=_odi(ordered, 4, duration_hours),
    )


def match_recording_to_cpap(recording: dict, cpap_start: float, cpap_end: float,
                            *, clock_offset_seconds: float = 0.0,
                            minimum_overlap_seconds: float = 300.0) -> SessionMatch | None:
    rec_start = float(recording.get("start_ts") or 0) + clock_offset_seconds
    rec_end = float(recording.get("end_ts") or 0) + clock_offset_seconds
    overlap_start = max(rec_start, cpap_start)
    overlap_end = min(rec_end, cpap_end)
    overlap = max(0.0, overlap_end - overlap_start)
    if overlap < minimum_overlap_seconds:
        return None
    cpap_duration = max(1.0, cpap_end - cpap_start)
    return SessionMatch(
        recording_id=str(recording.get("recording_id") or ""),
        cpap_start=cpap_start,
        cpap_end=cpap_end,
        overlap_start=overlap_start,
        overlap_end=overlap_end,
        overlap_seconds=overlap,
        cpap_coverage_percent=round(min(100.0, overlap / cpap_duration * 100.0), 2),
        clock_offset_seconds=clock_offset_seconds,
    )
