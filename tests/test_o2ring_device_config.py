import pytest

from cpap.o2ring_device_config import _device_update


def test_device_config_maps_alert_switches_thresholds_and_display():
    mapped = _device_update({
        "oxi_alert_enabled": True,
        "oxi_threshold": 88,
        "hr_alert_enabled": False,
        "hr_low": 45,
        "hr_high": 130,
        "motor": 60,
        "lighting_mode": 1,
        "brightness": 2,
    })
    assert mapped == {
        "SetOxiSwitch": "1",
        "SetHRSwitch": "0",
        "SetOxiThr": "88",
        "SetHRLowThr": "45",
        "SetHRHighThr": "130",
        "SetMotor": "60",
        "SetLightingMode": "1",
        "SetLightStr": "2",
    }


def test_device_config_rejects_inverted_hr_range():
    with pytest.raises(ValueError):
        _device_update({"hr_low": 150, "hr_high": 60})


def test_device_config_rejects_out_of_range_oxygen_threshold():
    with pytest.raises(ValueError):
        _device_update({"oxi_threshold": 99})
