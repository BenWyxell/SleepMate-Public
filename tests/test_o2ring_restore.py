from __future__ import annotations

import json
from pathlib import Path
import threading

import pytest

from cpap.o2ring_restore import _rehydrate_service, _stop_and_wait
from cpap.oximetry import OximetrySample, OximetryStore


ROOT = Path(__file__).resolve().parents[1]


class StoppableThread:
    def __init__(self, *, stops=True):
        self.alive = True
        self.stops = stops
        self.join_timeout = None

    def is_alive(self):
        return self.alive

    def join(self, timeout):
        self.join_timeout = timeout
        if self.stops:
            self.alive = False


class StoppableManager:
    def __init__(self, *, stops=True):
        self._thread = StoppableThread(stops=stops)
        self.stop_called = False

    def stop(self):
        self.stop_called = True


def test_stop_and_wait_proves_ble_worker_has_exited():
    manager = StoppableManager(stops=True)
    _stop_and_wait(manager, timeout=4.5)
    assert manager.stop_called is True
    assert manager._thread.join_timeout == 4.5
    assert manager._thread.is_alive() is False


def test_stop_and_wait_blocks_restore_when_ble_worker_will_not_exit():
    manager = StoppableManager(stops=False)
    with pytest.raises(RuntimeError, match="biztonsági okból megszakadt"):
        _stop_and_wait(manager, timeout=0.1)
    assert manager.stop_called is True


class FreshManager:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.preferred = None
        self.listeners = []
        self.start_calls = []

    def add_listener(self, callback):
        self.listeners.append(callback)

    def set_preferred_device(self, address):
        self.preferred = address

    def start(self, *, sync_on_start=True):
        self.start_calls.append(sync_on_start)


class RehydrateService:
    def __init__(self, root: Path):
        self.store = OximetryStore(root)
        self._lock = threading.RLock()
        self._known_source_names = {"STALE-BEFORE-RESTORE.vld"}
        self._cfg = {
            "o2ring_enabled": True,
            "o2ring_ble_enabled": True,
            "o2ring_auto_connect": True,
            "o2ring_auto_sync": True,
            "o2ring_preferred_address": "AA:BB:CC:DD:EE:FF",
        }
        self.manager = object()

    def settings(self):
        return dict(self._cfg)

    @staticmethod
    def _ble_should_run(cfg):
        return bool(cfg.get("o2ring_enabled") and cfg.get("o2ring_ble_enabled") and cfg.get("o2ring_auto_connect"))

    def _known_file(self, name):
        return name in self._known_source_names

    def _on_file(self, *_args, **_kwargs):
        return None

    def _remember_connected_device(self, *_args, **_kwargs):
        return None

    def _load_known_names(self):
        known = {
            str(row.get("source_name") or "").strip()
            for row in self.store.list_recordings()
            if str(row.get("source_name") or "").strip()
        }
        tombstone = self.store.root / "oximetry" / "deleted_sources.json"
        if tombstone.is_file():
            payload = json.loads(tombstone.read_text(encoding="utf-8"))
            known.update(str(x).strip() for x in payload.get("source_names") or [] if str(x).strip())
        with self._lock:
            self._known_source_names = known


def test_rehydrate_rebuilds_store_known_files_pairing_and_fresh_ble_runtime(tmp_path, monkeypatch):
    service = RehydrateService(tmp_path)
    service.store.save_recording(
        device_id="ring",
        start_ts=1000.0,
        end_ts=1008.0,
        source_name="RESTORED-SESSION.vld",
        samples=[
            OximetrySample(timestamp=1000.0, spo2=97, heart_rate=60),
            OximetrySample(timestamp=1004.0, spo2=96, heart_rate=61),
        ],
        raw_bytes=b"restored-vld",
    )
    tombstone = tmp_path / "oximetry" / "deleted_sources.json"
    tombstone.write_text(
        json.dumps({"schema": 1, "source_names": ["DELETED-ON-RING.vld"]}),
        encoding="utf-8",
    )

    import cpap.o2ring_restore as restore_module
    monkeypatch.setattr(restore_module, "O2RingBLEManager", FreshManager)

    old_manager = service.manager
    result = _rehydrate_service(service, restart=True)

    assert service.manager is not old_manager
    assert isinstance(service.manager, FreshManager)
    assert service.manager.preferred == "AA:BB:CC:DD:EE:FF"
    assert service.manager.start_calls == [False]
    assert len(service.manager.listeners) == 1
    assert service._known_source_names == {"RESTORED-SESSION.vld", "DELETED-ON-RING.vld"}
    assert "STALE-BEFORE-RESTORE.vld" not in service._known_source_names
    assert result == {
        "recordings": 1,
        "known_sources": 2,
        "remembered_device": True,
        "ble_restarted": True,
        "sync_on_restore": False,
    }


def test_rehydrate_does_not_restart_ble_when_restored_master_switch_is_off(tmp_path, monkeypatch):
    service = RehydrateService(tmp_path)
    service._cfg["o2ring_enabled"] = False

    import cpap.o2ring_restore as restore_module
    monkeypatch.setattr(restore_module, "O2RingBLEManager", FreshManager)

    result = _rehydrate_service(service, restart=True)
    assert result["ble_restarted"] is False
    assert service.manager.start_calls == []
    assert service.manager.preferred == "AA:BB:CC:DD:EE:FF"


def test_restore_wrapper_orders_quiesce_before_base_restore_then_rehydrates(monkeypatch):
    import cpap.o2ring_restore as restore_module

    events = []

    class Service:
        manager = object()

    service = Service()

    class Log:
        def append(self, *_args, **_kwargs):
            events.append("log")

    class Handler:
        persistent_log = Log()

        def _progress(self, *_args, **_kwargs):
            pass

        def _restore_backup_job(self, jid, uploaded):
            events.append("base_restore")
            return {"restored": 7}

    class App:
        pass

    App.Handler = Handler

    monkeypatch.setattr(restore_module, "_installed", False)
    monkeypatch.setattr(restore_module, "get_service", lambda _app: service)
    monkeypatch.setattr(restore_module, "_stop_and_wait", lambda manager: events.append("quiesce"))

    def fake_rehydrate(_service, *, restart=True):
        events.append("rehydrate")
        return {
            "recordings": 3,
            "known_sources": 4,
            "remembered_device": True,
            "ble_restarted": bool(restart),
        }

    monkeypatch.setattr(restore_module, "_rehydrate_service", fake_rehydrate)
    restore_module.install_o2ring_restore(App)

    result = Handler()._restore_backup_job("job", "backup.zip")
    assert events[:3] == ["quiesce", "base_restore", "rehydrate"]
    assert result["restored"] == 7
    assert result["o2ring_rehydrated"] is True
    assert result["o2ring_recordings"] == 3
    assert result["o2ring_ble_restarted"] is True


def test_restore_wrapper_recovers_o2_runtime_but_preserves_original_restore_error(monkeypatch):
    import cpap.o2ring_restore as restore_module

    events = []

    class Service:
        manager = object()

    service = Service()

    class Log:
        def append(self, *_args, **_kwargs):
            events.append("log")

    class Handler:
        persistent_log = Log()

        def _progress(self, *_args, **_kwargs):
            pass

        def _restore_backup_job(self, jid, uploaded):
            events.append("base_restore")
            raise ValueError("restore exploded")

    class App:
        pass

    App.Handler = Handler

    monkeypatch.setattr(restore_module, "_installed", False)
    monkeypatch.setattr(restore_module, "get_service", lambda _app: service)
    monkeypatch.setattr(restore_module, "_stop_and_wait", lambda manager: events.append("quiesce"))
    monkeypatch.setattr(
        restore_module,
        "_rehydrate_service",
        lambda _service, restart=True: events.append("rehydrate") or {"ble_restarted": True},
    )
    restore_module.install_o2ring_restore(App)

    with pytest.raises(ValueError, match="restore exploded"):
        Handler()._restore_backup_job("job", "broken.zip")
    assert events[:3] == ["quiesce", "base_restore", "rehydrate"]


def test_v53_shell_installs_restore_lifecycle_without_modifying_base_restore():
    shell = (ROOT / "cpap" / "v530_features.py").read_text(encoding="utf-8")
    addon = (ROOT / "cpap" / "o2ring_restore.py").read_text(encoding="utf-8")
    base = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "from .o2ring_restore import install_o2ring_restore" in shell
    assert "install_o2ring_restore(app_module)" in shell
    assert "original_restore = handler_cls._restore_backup_job" in addon
    assert "_stop_and_wait(old_manager)" in addon
    assert "sync_on_start=False" in addon
    assert "o2ring_rehydrated" in addon
    assert "o2ring_rehydrated" not in base


def test_oximetry_delete_uses_same_quiescent_ble_gate():
    text = (ROOT / "cpap" / "o2ring_data_management.py").read_text(encoding="utf-8")
    assert "from .o2ring_restore import _stop_and_wait" in text
    assert "_stop_and_wait(service.manager)" in text
