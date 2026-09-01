from __future__ import annotations

from pathlib import Path

import pytest

from cpap.o2ring_lifecycle import start_reliably, stop_and_wait


ROOT = Path(__file__).resolve().parents[1]


class FakeStopEvent:
    def __init__(self, value=False):
        self.value = bool(value)

    def is_set(self):
        return self.value


class FakeThread:
    def __init__(self, *, alive=True, exits_on_join=True):
        self.alive = bool(alive)
        self.exits_on_join = bool(exits_on_join)
        self.join_calls = []

    def is_alive(self):
        return self.alive

    def join(self, timeout):
        self.join_calls.append(timeout)
        if self.exits_on_join:
            self.alive = False


class FakeManager:
    def __init__(self, *, thread=None, stopping=False):
        self._thread = thread
        self._stop = FakeStopEvent(stopping)
        self.stop_calls = 0
        self.start_calls = []

    def stop(self):
        self.stop_calls += 1
        self._stop.value = True

    def start(self, *, sync_on_start=True):
        self.start_calls.append(bool(sync_on_start))
        self._stop.value = False


def test_stop_and_wait_is_a_real_quiescent_boundary():
    thread = FakeThread(alive=True, exits_on_join=True)
    manager = FakeManager(thread=thread)
    stop_and_wait(manager, timeout=3.25)
    assert manager.stop_calls == 1
    assert thread.join_calls == [3.25]
    assert thread.is_alive() is False


def test_start_reliably_waits_out_a_previous_stop_then_restarts():
    thread = FakeThread(alive=True, exits_on_join=True)
    manager = FakeManager(thread=thread, stopping=True)
    start_reliably(manager, sync_on_start=False, timeout=4.0)
    assert thread.join_calls == [4.0]
    assert manager.start_calls == [False]
    assert manager._stop.is_set() is False


def test_start_reliably_does_not_join_a_normal_running_worker():
    thread = FakeThread(alive=True, exits_on_join=False)
    manager = FakeManager(thread=thread, stopping=False)
    start_reliably(manager, sync_on_start=True, timeout=1.0)
    assert thread.join_calls == []
    assert manager.start_calls == [True]


def test_start_reliably_fails_instead_of_silently_losing_restart():
    thread = FakeThread(alive=True, exits_on_join=False)
    manager = FakeManager(thread=thread, stopping=True)
    with pytest.raises(RuntimeError, match="újraindítás biztonsági okból"):
        start_reliably(manager, sync_on_start=False, timeout=0.1)
    assert thread.join_calls == [0.1]
    assert manager.start_calls == []


def test_stop_and_wait_fails_if_worker_cannot_be_quiesced():
    thread = FakeThread(alive=True, exits_on_join=False)
    manager = FakeManager(thread=thread)
    with pytest.raises(RuntimeError, match="művelet biztonsági okból megszakadt"):
        stop_and_wait(manager, timeout=0.1)
    assert manager.stop_calls == 1
    assert manager.start_calls == []


def test_all_mutating_o2_paths_use_shared_lifecycle_gate():
    integration = (ROOT / "cpap" / "o2ring_integration.py").read_text(encoding="utf-8")
    data_management = (ROOT / "cpap" / "o2ring_data_management.py").read_text(encoding="utf-8")
    restore = (ROOT / "cpap" / "o2ring_restore.py").read_text(encoding="utf-8")
    device_config = (ROOT / "cpap" / "o2ring_device_config.py").read_text(encoding="utf-8")

    assert "from .o2ring_lifecycle import start_reliably, stop_and_wait" in integration
    assert "start_reliably(self.manager" in integration
    assert "stop_and_wait(self.manager)" in integration
    assert "start_reliably(service.manager" in integration

    assert "from .o2ring_lifecycle import start_reliably, stop_and_wait" in data_management
    assert "stop_and_wait(service.manager)" in data_management
    assert "start_reliably(service.manager" in data_management

    assert "from .o2ring_lifecycle import start_reliably, stop_and_wait as _stop_and_wait" in restore
    assert "_stop_and_wait(old_manager)" in restore
    assert "start_reliably(manager, sync_on_start=False)" in restore

    assert "from .o2ring_lifecycle import start_reliably" in device_config
    assert "start_reliably(service.manager, sync_on_start=False)" in device_config
