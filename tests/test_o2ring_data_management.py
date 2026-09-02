from __future__ import annotations

import json
from pathlib import Path
import threading

from cpap.o2ring_data_management import (
    _apply_tombstones,
    _delete_local_oximetry,
    _load_tombstones,
)
from cpap.o2ring_integration import O2RingService
from cpap.oximetry import OximetrySample, OximetryStore


ROOT = Path(__file__).resolve().parents[1]


class FakeManager:
    def __init__(self):
        self.stop_calls = 0
        self.start_calls = []

    def stop(self):
        self.stop_calls += 1

    def start(self, *, sync_on_start=False):
        self.start_calls.append(bool(sync_on_start))


class FakeService:
    def __init__(self, root: Path):
        self.store = OximetryStore(root)
        self.manager = FakeManager()
        self._lock = threading.RLock()
        self._known_source_names = set()
        self._settings = {
            "o2ring_enabled": True,
            "o2ring_ble_enabled": True,
            "o2ring_auto_connect": True,
            "o2ring_preferred_address": "AA:BB:CC:DD:EE:FF",
        }
        self.app = type("App", (), {"Handler": type("Handler", (), {"persistent_log": None})})()

    def settings(self):
        return dict(self._settings)

    @staticmethod
    def _ble_should_run(cfg):
        return bool(
            cfg.get("o2ring_enabled")
            and cfg.get("o2ring_ble_enabled", True)
            and cfg.get("o2ring_auto_connect", True)
        )


def seed_recording(service: FakeService, source_name: str = "250901_230001.vld"):
    service.store.save_recording(
        device_id="TEST-RING",
        start_ts=1_000.0,
        end_ts=1_012.0,
        source_name=source_name,
        raw_bytes=b"O2RING-RAW",
        samples=[
            OximetrySample(timestamp=1_000.0, spo2=97, heart_rate=63),
            OximetrySample(timestamp=1_004.0, spo2=96, heart_rate=64),
            OximetrySample(timestamp=1_008.0, spo2=95, heart_rate=65),
            OximetrySample(timestamp=1_012.0, spo2=96, heart_rate=64),
        ],
    )


def test_delete_removes_health_data_but_preserves_ring_and_blocks_resync(tmp_path):
    service = FakeService(tmp_path / "private")
    seed_recording(service)
    remembered_before = service.settings()["o2ring_preferred_address"]

    result = _delete_local_oximetry(service)

    assert result["ok"] is True
    assert result["recordings_deleted"] == 1
    assert result["raw_files_deleted"] == 1
    assert result["recordings_remaining"] == 0
    assert result["remembered_device_preserved"] is True
    assert service.settings()["o2ring_preferred_address"] == remembered_before
    assert list(service.store.recordings_dir.glob("*.json")) == []
    assert list(service.store.raw_dir.glob("*.vld")) == []
    assert "250901_230001.vld" in service._known_source_names
    assert service.manager.stop_calls == 1
    assert service.manager.start_calls == [False]

    tombstone = service.store.root / "oximetry" / "deleted_sources.json"
    assert tombstone.is_file()
    payload = json.loads(tombstone.read_text(encoding="utf-8"))
    assert payload["schema"] == 1
    assert payload["source_names"] == ["250901_230001.vld"]


def test_tombstones_survive_restart_and_are_applied_as_known_files(tmp_path):
    root = tmp_path / "private"
    first = FakeService(root)
    seed_recording(first, "old-ring-session.vld")
    _delete_local_oximetry(first)

    restarted = FakeService(root)
    assert restarted._known_source_names == set()
    applied = _apply_tombstones(restarted)

    assert applied == {"old-ring-session.vld"}
    assert restarted._known_source_names == {"old-ring-session.vld"}
    assert _load_tombstones(restarted) == {"old-ring-session.vld"}


def test_real_o2ring_service_loads_tombstones_before_ble_manager_can_start(tmp_path, monkeypatch):
    state = tmp_path / "state"
    ox_dir = state / "private" / "oximetry"
    ox_dir.mkdir(parents=True)
    (ox_dir / "deleted_sources.json").write_text(
        json.dumps({"schema": 1, "source_names": ["deleted-before-restart.vld"]}),
        encoding="utf-8",
    )

    events = []

    class BootManager:
        def __init__(self, **kwargs):
            events.append(("manager_init", kwargs["known_file"]("deleted-before-restart.vld")))

        def set_preferred_device(self, value):
            events.append(("preferred", value))

        def add_listener(self, callback):
            events.append(("listener", callable(callback)))

        def start(self, *, sync_on_start=False):
            events.append(("start", bool(sync_on_start)))

    monkeypatch.setattr("cpap.o2ring_integration.O2RingBLEManager", BootManager)

    class App:
        STATE_BASE = state
        Handler = type("Handler", (), {"persistent_log": None})

        @staticmethod
        def load_config():
            return {
                "o2ring_enabled": True,
                "o2ring_ble_enabled": True,
                "o2ring_auto_connect": True,
                "o2ring_auto_sync": True,
                "o2ring_preferred_address": "REMEMBERED-RING",
            }

        @staticmethod
        def save_config(update):
            return update

    service = O2RingService(App)

    assert "deleted-before-restart.vld" in service._known_source_names
    assert events[0] == ("manager_init", True)
    assert events[-1] == ("start", True)


def test_delete_confirmation_and_settings_ui_contract_are_explicit():
    backend = (ROOT / "cpap" / "o2ring_data_management.py").read_text(encoding="utf-8")
    ui = (ROOT / "web" / "o2ring-data-management.js").read_text(encoding="utf-8")
    shell = (ROOT / "cpap" / "v530_features.py").read_text(encoding="utf-8")
    integration = (ROOT / "cpap" / "o2ring_integration.py").read_text(encoding="utf-8")

    assert '_CONFIRM_TOKEN = "DELETE_OXIMETRY"' in backend
    assert 'path == "/api/o2ring/delete-data"' in backend
    assert 'body.get("confirm")' in backend
    assert "sync_on_start=False" in backend
    assert "deleted_sources.json" in backend

    assert "Helyi O2Ring mérési adatok törlése" in ui
    assert "/api/o2ring/delete-data" in ui
    assert "DELETE_OXIMETRY" in ui
    assert "window.confirm" in ui
    assert "SleepMateO2Ring?.refresh" in ui
    assert "SleepMateO2Combined?.refresh" in ui

    assert "install_o2ring_data_management(app_module)" in shell
    assert 'data_management_path = app_module.WEB / "o2ring-data-management.js"' in shell
    assert '"sm-o2-data-management-inline" not in text' in shell
    assert "data_management_path.read_text" in shell
    assert '<script id="sm-o2-data-management-inline">' in shell
    assert "self._load_known_names()" in integration
    assert 'self.manager = O2RingBLEManager(' in integration
    assert integration.index("self._load_known_names()") < integration.index("self.manager = O2RingBLEManager(")
