import pytest

from cpap.o2ring_device_config import _device_update


def test_device_config_maps_supported_fields_to_protocol_json_keys():
    update = _device_update({
        "oxi_threshold": 90,
        "hr_low": 50,
        "hr_high": 120,
        "motor": 60,
        "lighting_mode": 2,
        "brightness": 1,
    })
    assert update == {
        "SetOxiSwitch": "1",
        "SetOxiThr": "90",
        "SetHRSwitch": "1",
        "SetHRLowThr": "50",
        "SetHRHighThr": "120",
        "SetMotor": "60",
        "SetLightingMode": "2",
        "SetLightStr": "1",
    }


def test_device_config_rejects_reversed_hr_limits():
    with pytest.raises(ValueError, match="alsó határa"):
        _device_update({"hr_low": 130, "hr_high": 80})


def test_device_config_rejects_unsafe_spo2_threshold():
    with pytest.raises(ValueError, match="70–95"):
        _device_update({"oxi_threshold": 99})
