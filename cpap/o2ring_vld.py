"""Parser for Wellue/Viatom O2Ring VLD3 overnight recordings."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .oximetry import OximetrySample


@dataclass(frozen=True)
class ParsedVLD:
    version: int
    start: datetime
    duration_seconds: int
    interval_seconds: float
    samples: list[OximetrySample]

    @property
    def start_ts(self) -> float:
        return self.start.timestamp()

    @property
    def end_ts(self) -> float:
        return self.start_ts + self.duration_seconds


def parse_vld(data: bytes) -> ParsedVLD:
    if len(data) < 45:
        raise ValueError("Az O2Ring VLD fájl túl rövid.")
    version = int.from_bytes(data[0:2], "little")
    if version != 3:
        raise ValueError(f"Nem támogatott O2Ring VLD verzió: {version}")
    year = int.from_bytes(data[2:4], "little")
    month, day, hour, minute, second = [int(x) for x in data[4:9]]
    try:
        start = datetime(year, month, day, hour, minute, second)
    except ValueError as exc:
        raise ValueError("Az O2Ring felvétel kezdő időpontja hibás.") from exc
    duration = int.from_bytes(data[18:20], "little")
    records = data[40:]
    count = len(records) // 5
    if count <= 0:
        raise ValueError("Az O2Ring felvételben nincs mérési minta.")
    interval = float(duration) / count if duration > 0 else 4.0
    samples: list[OximetrySample] = []
    start_ts = start.timestamp()
    for index in range(count):
        row = records[index * 5:index * 5 + 5]
        spo2_raw = int(row[0])
        hr_raw = int(row[1])
        invalid = bool(row[2]) or spo2_raw == 0xFF or hr_raw == 0xFF
        spo2 = spo2_raw if not invalid and 50 <= spo2_raw <= 100 else None
        hr = hr_raw if not invalid and 20 <= hr_raw <= 250 else None
        samples.append(OximetrySample(
            timestamp=start_ts + index * interval,
            spo2=spo2,
            heart_rate=hr,
            motion=int(row[3]),
            valid=bool(not invalid and spo2 is not None and hr is not None),
        ))
    return ParsedVLD(version=version, start=start, duration_seconds=duration,
                     interval_seconds=interval, samples=samples)


def recording_public_payload(parsed: ParsedVLD, *, recording_id: str, summary: dict[str, Any], source_name: str) -> dict[str, Any]:
    return {
        "recording_id": recording_id,
        "source_name": source_name,
        "start_ts": parsed.start_ts,
        "end_ts": parsed.end_ts,
        "duration_seconds": parsed.duration_seconds,
        "interval_seconds": parsed.interval_seconds,
        "summary": summary,
    }


__all__ = ["ParsedVLD", "parse_vld", "recording_public_payload"]
