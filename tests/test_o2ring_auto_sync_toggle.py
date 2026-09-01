from cpap.o2ring_ble import O2RingBLEManager


def test_ring_removal_respects_auto_sync_toggle():
    enabled = False
    manager = O2RingBLEManager(auto_sync_enabled=lambda: enabled)

    manager._state.worn = True
    manager._apply_live({"worn": False})
    assert not manager._sync_requested.is_set()

    enabled = True
    manager._state.worn = True
    manager._apply_live({"worn": False})
    assert manager._sync_requested.is_set()


def test_manual_sync_still_works_when_auto_sync_is_off():
    manager = O2RingBLEManager(auto_sync_enabled=lambda: False)
    assert not manager._sync_requested.is_set()

    manager.request_sync()
    assert manager._sync_requested.is_set()
