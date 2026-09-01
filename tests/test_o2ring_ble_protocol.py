from cpap.o2ring_ble import (
    CMD_READ_SENSORS,
    build_packet,
    crc8,
    parse_live_packet,
    parse_response,
)


def response_frame(payload: bytes, *, status: int = 0, block: int = 0) -> bytes:
    body = bytearray((0x55, status & 0xFF, (status ^ 0xFF) & 0xFF))
    body.extend(int(block).to_bytes(2, "little"))
    body.extend(len(payload).to_bytes(2, "little"))
    body.extend(payload)
    body.append(crc8(bytes(body)))
    return bytes(body)


def test_request_frame_uses_aa_command_and_crc():
    frame = build_packet(CMD_READ_SENSORS)
    assert frame[0] == 0xAA
    assert frame[1] == CMD_READ_SENSORS
    assert frame[2] == (CMD_READ_SENSORS ^ 0xFF)
    assert frame[3:7] == b"\x00\x00\x00\x00"
    assert crc8(frame[:-1]) == frame[-1]


def test_response_frame_uses_55_status_not_command_id():
    payload = bytes.fromhex("624200000000006100920a0100")
    frame = response_frame(payload)
    status, block, decoded = parse_response(frame)
    assert status == 0
    assert block == 0
    assert decoded == payload


def test_live_sensor_payload_matches_reference_layout():
    # Reference sample from the working O2Ring implementation:
    # SpO2 98, HR 66, battery 97, motion 146, PI/signal 10, finger present.
    payload = bytes.fromhex("624200000000006100920a0100")
    live = parse_live_packet(response_frame(payload))
    assert live["spo2"] == 98
    assert live["heart_rate"] == 66
    assert live["battery_percent"] == 97
    assert live["motion"] == 146
    assert live["perfusion_index"] == 10.0
    assert live["worn"] is True
    assert live["measuring"] is True


def test_live_sensor_payload_with_no_finger_does_not_publish_values():
    payload = bytes.fromhex("ffff0000000000620100000000")
    live = parse_live_packet(response_frame(payload))
    assert live["spo2"] is None
    assert live["heart_rate"] is None
    assert live["worn"] is False
    assert live["measuring"] is False
