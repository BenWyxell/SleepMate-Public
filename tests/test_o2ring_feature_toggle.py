from types import SimpleNamespace

from cpap.o2ring_integration import DEFAULTS, O2RingService


class _Log:
    def append(self, *args, **kwargs):
        pass


class _Handler:
    persistent_log = _Log()


class FakeApp:
    Handler = _Handler

    def __init__(self, root, config=None):
        self.STATE_BASE = root
        self._config = dict(config or {})

    def load_config(self):
        return dict(self._config)

    def save_config(self, update):
        self._config.update(update)
        return dict(self._config)


def test_o2ring_master_switch_defaults_off():
    assert DEFAULTS["o2ring_enabled"] is False
    assert DEFAULTS["o2ring_ble_enabled"] is True


def test_ble_off_preserves_remembered_ring_and_history_store(tmp_path):
    app = FakeApp(tmp_path, {
        "o2ring_enabled": True,
        "o2ring_ble_enabled": True,
        "o2ring_auto_connect": False,
        "o2ring_preferred_address": "AA:BB:CC:DD",
    })
    service = O2RingService(app)
    assert service.manager.snapshot()["remembered_address"] == "AA:BB:CC:DD"

    saved = service.save_settings({"o2ring_ble_enabled": False})
    assert saved["o2ring_ble_enabled"] is False
    assert saved["o2ring_preferred_address"] == "AA:BB:CC:DD"
    assert service.manager.snapshot()["remembered_address"] == "AA:BB:CC:DD"
    assert (tmp_path / "private" / "oximetry").exists() is False
    # Store lives directly below the provided private root and remains present.
    assert (tmp_path / "oximetry" / "recordings").is_dir()


def test_master_off_hides_runtime_but_does_not_forget_device(tmp_path):
    app = FakeApp(tmp_path, {
        "o2ring_enabled": True,
        "o2ring_ble_enabled": True,
        "o2ring_auto_connect": False,
        "o2ring_preferred_address": "RING-123",
    })
    service = O2RingService(app)
    service.save_settings({"o2ring_enabled": False})
    status = service.status()
    assert status["feature_enabled"] is False
    assert status["ble_enabled"] is False
    assert status["settings"]["o2ring_preferred_address"] == "RING-123"


def test_forget_device_is_explicit_and_does_not_delete_recordings(tmp_path):
    app = FakeApp(tmp_path, {
        "o2ring_enabled": True,
        "o2ring_ble_enabled": False,
        "o2ring_auto_connect": False,
        "o2ring_preferred_address": "RING-123",
    })
    service = O2RingService(app)
    marker = service.store.recordings_dir / "keep.json"
    marker.write_text("{}", encoding="utf-8")

    service.forget_device()

    assert app._config["o2ring_preferred_address"] == ""
    assert service.manager.snapshot()["remembered_address"] is None
    assert marker.exists()
