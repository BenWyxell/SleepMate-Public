from datetime import datetime

import pytest

from cpap.o2ring_vld import HEADER_SIZE, HEADER_STRUCT, RECORD_STRUCT, parse_vld


def make_vld(*, duration=20, records=None):
    records = records or [
        (97, 60, False, 1, 0),
        (96, 62, False, 2, 0),
        (89, 70, False, 3, 0),
        (88, 75, False, 4, 0),
        (95, 65, False, 5, 0),
    ]
    raw_records = b"".join(RECORD_STRUCT.pack(*r) for r in records)
    total_size = HEADER_SIZE + len(raw_records)
    header = HEADER_STRUCT.pack(
        3, 2026, 9, 1, 23, 10, 5,
        total_size, total_size,
        duration, duration,
        93, 88, 1, 1, 0,
        8, 1, 90,
    )
    return header + bytes(HEADER_SIZE - len(header)) + raw_records


def test_vld3_uses_duration_header_not_spo2_minimum_bytes():
    parsed = parse_vld(make_vld(duration=20))
    assert parsed.version == 3
    assert parsed.start == datetime(2026, 9, 1, 23, 10, 5)
    assert parsed.duration_seconds == 20
    assert parsed.interval_seconds == 4.0
    assert len(parsed.samples) == 5
    assert parsed.samples[2].spo2 == 89
    assert parsed.samples[3].heart_rate == 75
    assert parsed.samples[4].motion == 5


def test_vld3_invalid_flag_removes_physiological_values():
    parsed = parse_vld(make_vld(records=[
        (97, 60, False, 1, 0),
        (85, 80, True, 9, 1),
        (96, 61, False, 2, 0),
        (95, 62, False, 2, 0),
        (94, 63, False, 2, 0),
    ]))
    bad = parsed.samples[1]
    assert bad.valid is False
    assert bad.spo2 is None
    assert bad.heart_rate is None
    assert bad.motion == 9


def test_vld3_rejects_unknown_resolution():
    with pytest.raises(ValueError, match="mintavételi"):
        parse_vld(make_vld(duration=15))


def test_vld3_rejects_partial_record():
    with pytest.raises(ValueError, match="csonka"):
        parse_vld(make_vld() + b"\x00")
