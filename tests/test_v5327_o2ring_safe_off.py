from __future__ import annotations

from cpap.o2ring_lifecycle import stop_and_wait


class _PendingManager:
    def __init__(self, pending: bool):
        self.pending = pending
        self.requested = 0
        self.stopped = 0
        self._thread = None

    def snapshot(self):
        return {"post_recording_sync_pending": self.pending}

    def request_sync(self):
        self.requested += 1
        # Simulate the existing BLE worker completing the final FileList pass.
        self.pending = False

    def stop(self):
        self.stopped += 1


def test_ble_off_drains_pending_post_recording_sync_before_stop() -> None:
    manager = _PendingManager(True)
    stop_and_wait(manager)
    assert manager.requested == 1
    assert manager.stopped == 1


def test_ordinary_ble_off_does_not_add_sync_when_nothing_is_pending() -> None:
    manager = _PendingManager(False)
    stop_and_wait(manager)
    assert manager.requested == 0
    assert manager.stopped == 1
