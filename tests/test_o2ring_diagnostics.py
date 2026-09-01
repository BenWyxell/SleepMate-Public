from __future__ import annotations

import json
import threading
from pathlib import Path

from cpap.o2ring_diagnostics import (
    _diag_level,
    _redact_support_value,
    safe_o2ring_diagnostics,
)
from cpap.oximetry import OximetrySample, OximetryStore


ROOT = Path(__file__).resolve().parents[1]


class FakeThread:
    @staticmethod
    def is_alive():
        return True


class FakeManager:
    _thread = FakeThread()

    @staticmethod
    def snapshot():
        return {
            "connected": True,
            "scanning": False,
            "measuring": True,
            "calibrating": False,
            "last_sample_ts": 1_777_777_777.0,
            "last_sync_ts": 1_777_777_700.0,
            "last_error": None,
            "spo2": 91,
            "heart_rate": 133,
            "motion": 7,
            "signal_strength": 4,
            "device_name": "SECRET O2Ring",
            "device_address": "AA:BB:CC:DD:EE:FF",
            "remembered_address": "AA:BB:CC:DD:EE:FF",
            "serial_number": "SERIAL-SECRET",
            "device_model": "SECRET-MODEL",
        }


class FakeService:
    def __init__(self, root: Path, *, enabled=True, ble=True, remembered=True):
        self.store = OximetryStore(root)
        self.manager = FakeManager()
        self._lock = threading.RLock()
        self._settings = {
            "o2ring_enabled": enabled,
            "o2ring_ble_enabled": ble,
            "o2ring_auto_connect": True,
            "o2ring_auto_sync": True,
            "o2ring_auto_match": True,
            "o2ring_preferred_address": "AA:BB:CC:DD:EE:FF" if remembered else "",
        }

    def settings(self):
        return dict(self._settings)


def seed(service: FakeService):
    service.store.save_recording(
        device_id="PRIVATE-RING-ID",
        source_name="private-night.vld",
        start_ts=1_000,
        end_ts=1_008,
        raw_bytes=b"PRIVATE VLD",
        samples=[
            OximetrySample(timestamp=1_000, spo2=91, heart_rate=133),
            OximetrySample(timestamp=1_004, spo2=92, heart_rate=130),
            OximetrySample(timestamp=1_008, spo2=93, heart_rate=127),
        ],
    )
    tombstone = service.store.root / "oximetry" / "deleted_sources.json"
    tombstone.write_text(
        json.dumps({"schema": 1, "source_names": ["deleted-private-night.vld"]}),
        encoding="utf-8",
    )


def test_diagnostics_expose_only_technical_boolean_and_counts(tmp_path):
    service = FakeService(tmp_path / "private")
    seed(service)
    diag = safe_o2ring_diagnostics(service)

    assert diag["feature_enabled"] is True
    assert diag["ble_enabled"] is True
    assert diag["remembered_device"] is True
    assert diag["connected"] is True
    assert diag["measuring"] is True
    assert diag["has_last_sample"] is True
    assert diag["has_completed_sync"] is True
    assert diag["recordings_count"] == 1
    assert diag["raw_recordings_count"] == 1
    assert diag["deleted_source_tombstones_count"] == 1

    blob = json.dumps(diag, ensure_ascii=False).lower()
    for forbidden in (
        "91", "133", "secret", "private-night", ".vld", "aa:bb:cc:dd:ee:ff",
        "device_address", "remembered_address", "serial_number", "device_name",
        "device_model", "source_name", "recording_id", "spo2", "heart_rate",
    ):
        assert forbidden not in blob


def test_disconnected_remembered_ring_is_not_reported_as_failure(tmp_path):
    service = FakeService(tmp_path / "private")
    service.manager.snapshot = lambda: {
        "connected": False, "scanning": False, "measuring": False,
        "calibrating": False, "last_error": None,
    }
    diag = safe_o2ring_diagnostics(service)
    level, message = _diag_level(diag)
    assert level == "OK"
    assert "jelenleg nincs kapcsolatban" in message


def test_missing_remembered_ring_is_warning_not_global_error(tmp_path):
    service = FakeService(tmp_path / "private", remembered=False)
    service.manager.snapshot = lambda: {"connected": False, "last_error": None}
    diag = safe_o2ring_diagnostics(service)
    level, _ = _diag_level(diag)
    assert level == "WARN"


def test_support_redaction_removes_historical_o2_identifiers_and_measurements():
    poisoned = {
        "source": "o2ring",
        "message": "Ring AA:BB:CC:DD:EE:FF downloaded",
        "details": {
            "source_name": "250901_230001.vld",
            "recording_id": "recording-secret-123",
            "device_id": "device-secret-456",
            "device_address": "AA:BB:CC:DD:EE:FF",
            "remembered_address": "11:22:33:44:55:66",
            "serial_number": "SERIAL-SECRET",
            "spo2": 84,
            "heart_rate": 155,
            "samples": 7000,
            "safe_counter": 4,
        },
    }
    clean = _redact_support_value(poisoned)
    blob = json.dumps(clean, ensure_ascii=False).lower()

    assert clean["details"]["safe_counter"] == 4
    assert "<redacted" in blob
    for forbidden in (
        "250901_230001.vld", "recording-secret", "device-secret", "serial-secret",
        "aa:bb:cc:dd:ee:ff", "11:22:33:44:55:66", '"spo2": 84',
        '"heart_rate": 155', '"samples": 7000',
    ):
        assert forbidden not in blob


def test_support_config_redaction_contract_covers_remembered_ring_address():
    clean = _redact_support_value({
        "o2ring_enabled": True,
        "o2ring_preferred_address": "AA:BB:CC:DD:EE:FF",
        "o2ring_auto_sync": True,
    })
    assert clean["o2ring_enabled"] is True
    assert clean["o2ring_auto_sync"] is True
    assert clean["o2ring_preferred_address"] == "<REDACTED>"


def test_v53_shell_installs_o2_diagnostics_layer():
    shell = (ROOT / "cpap" / "v530_features.py").read_text(encoding="utf-8")
    addon = (ROOT / "cpap" / "o2ring_diagnostics.py").read_text(encoding="utf-8")

    assert "from .o2ring_diagnostics import install_o2ring_diagnostics" in shell
    assert "install_o2ring_diagnostics(app_module)" in shell
    assert '"/api/o2ring/diagnostics"' in addon
    assert "SupportBundleService._mask_remote" in addon
    assert "SupportBundleService._sanitize_config" in addon
    assert "o2ring_preferred_address" in addon
