from datetime import datetime
import struct

from cpap.o2ring_vld import HEADER_SIZE, HEADER_STRUCT, parse_vld


def build_vld(samples, *, interval=4, start=datetime(2026, 9, 1, 23, 4, 5)):
    duration = len(samples) * interval
    total_size = HEADER_SIZE + len(samples) * 5
    header = HEADER_STRUCT.pack(
        3, start.year, start.month, start.day, start.hour, start.minute, start.second,
        total_size, total_size, duration, duration,
        95, 88, 2, 1, 0, 8, 2, 93,
    )
    header += bytes(HEADER_SIZE - len(header))
    body = b"".join(struct.pack("<BB?BB", spo2, hr, invalid, motion, vibration) for spo2, hr, invalid, motion, vibration in samples)
    return header + body


def test_vld3_header_duration_and_records_are_parsed_from_correct_offsets():
    raw = build_vld([
        (97, 61, False, 2, 0),
        (93, 65, False, 3, 0),
        (89, 70, False, 4, 1),
    ])
    parsed = parse_vld(raw)
    assert parsed.version == 3
    assert parsed.duration_seconds == 12
    assert parsed.interval_seconds == 4.0
    assert parsed.start == datetime(2026, 9, 1, 23, 4, 5)
    assert [s.spo2 for s in parsed.samples] == [97, 93, 89]
    assert [s.heart_rate for s in parsed.samples] == [61, 65, 70]
    assert parsed.samples[-1].motion == 4


def test_invalid_vld_sample_is_not_published_as_health_value():
    raw = build_vld([(255, 255, True, 1, 0)])
    parsed = parse_vld(raw)
    assert parsed.samples[0].valid is False
    assert parsed.samples[0].spo2 is None
    assert parsed.samples[0].heart_rate is None
