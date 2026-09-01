"""Parser for Wellue/Viatom O2Ring VLD3 overnight recordings.

The binary layout follows the Viatom VLD3 header used by the O2Ring family:
``<HHBBBBBHHHHBBBBBHBB`` for the first 26 bytes, followed by padding to a
40-byte header and then 5-byte records ``<BB?BB``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import struct
from typing import Any

from .oximetry import OximetrySample


HEADER_SIZE = 40
RECORD_SIZE_V3 = 5
HEADER_STRUCT = struct.Struct("<HHBBBBBHHHHBBBBBHBB")
RECORD_STRUCT = struct.Struct("<BB?BB")


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
    if len(data) < HEADER_SIZE + RECORD_SIZE_V3:
        raise ValueError("Az O2Ring VLD fájl túl rövid.")

    fields = HEADER_STRUCT.unpack(data[:HEADER_STRUCT.size])
    (
        version, year, month, day, hour, minute, second,
        file_size, file_size_2, duration, duration_2,
        _spo2_avg, _spo2_min, _spo2_3pct, _spo2_4pct, _unknown1,
        _time_under_90pct, _events_under_90pct, _o2_score,
    ) = fields

    if version != 3:
        raise ValueError(f"Nem támogatott O2Ring VLD verzió: {version}")
    try:
        start = datetime(year, month, day, hour, minute, second)
    except ValueError as exc:
        raise ValueError("Az O2Ring felvétel kezdő időpontja hibás.") from exc

    records = data[HEADER_SIZE:]
    if len(records) % RECORD_SIZE_V3:
        raise ValueError("Az O2Ring VLD mérési blokkja csonka.")
    count = len(records) // RECORD_SIZE_V3
    if count <= 0:
        raise ValueError("Az O2Ring felvételben nincs mérési minta.")

    if duration <= 0:
        duration = int(duration_2)
    interval = float(duration) / float(count) if duration > 0 else 0.0
    if not (abs(interval - 2.0) < 1e-6 or abs(interval - 4.0) < 1e-6):
        raise ValueError(f"Ismeretlen vagy sérült O2Ring mintavételi felbontás: {interval:.3f} s")

    actual_size = len(data)
    for declared in (file_size, file_size_2):
        if declared and declared not in {actual_size, actual_size - HEADER_SIZE, len(records)}:
            break

    samples: list[OximetrySample] = []
    start_ts = start.timestamp()
    for index in range(count):
        offset = index * RECORD_SIZE_V3
        spo2_raw, hr_raw, invalid_flag, motion, _vibration = RECORD_STRUCT.unpack(
            records[offset:offset + RECORD_SIZE_V3]
        )
        invalid = bool(invalid_flag) or spo2_raw < 10 or spo2_raw > 100
        spo2 = int(spo2_raw) if not invalid and 50 <= spo2_raw <= 100 else None
        hr = int(hr_raw) if not invalid and 20 <= hr_raw <= 250 else None
        samples.append(
            OximetrySample(
                timestamp=start_ts + index * interval,
                spo2=spo2,
                heart_rate=hr,
                motion=int(motion),
                valid=bool(not invalid and spo2 is not None and hr is not None),
            )
        )

    return ParsedVLD(
        version=version,
        start=start,
        duration_seconds=int(duration),
        interval_seconds=interval,
        samples=samples,
    )


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


__all__ = [
    "ParsedVLD", "parse_vld", "recording_public_payload",
    "HEADER_SIZE", "RECORD_SIZE_V3", "HEADER_STRUCT", "RECORD_STRUCT",
]
