"""Reliable lifecycle boundary for the O2Ring BLE worker.

O2RingBLEManager.stop() is intentionally non-blocking because normal process
shutdown must stay cheap. Configuration, restore, deletion and explicit device
forget operations are different: before they mutate persistent state they must
prove the old BLE worker has actually exited. Likewise a rapid OFF -> ON toggle
must not lose the restart merely because the stopping thread is still alive.
"""
from __future__ import annotations


DEFAULT_STOP_TIMEOUT_SECONDS = 20.0


def stop_and_wait(manager, timeout: float = DEFAULT_STOP_TIMEOUT_SECONDS) -> None:
    """Request BLE stop and wait until the worker can no longer mutate state."""
    manager.stop()
    thread = getattr(manager, "_thread", None)
    if thread is not None and thread.is_alive():
        thread.join(max(0.1, float(timeout)))
    if thread is not None and thread.is_alive():
        raise RuntimeError(
            "Az O2Ring Bluetooth háttérfolyamata nem állt le időben; "
            "a művelet biztonsági okból megszakadt."
        )


def start_reliably(manager, *, sync_on_start: bool = True,
                   timeout: float = DEFAULT_STOP_TIMEOUT_SECONDS) -> None:
    """Start BLE even when a previous stop is still draining.

    O2RingBLEManager.start() correctly treats an already-running worker as a
    no-op/sync request. The one exceptional state is an alive worker whose stop
    event is already set: that worker is committed to exit, so returning early
    would leave BLE stopped after a rapid OFF -> ON toggle. Wait for that worker
    first, then start a fresh one.
    """
    thread = getattr(manager, "_thread", None)
    stop_event = getattr(manager, "_stop", None)
    stopping = bool(
        thread is not None
        and thread.is_alive()
        and stop_event is not None
        and callable(getattr(stop_event, "is_set", None))
        and stop_event.is_set()
    )
    if stopping:
        thread.join(max(0.1, float(timeout)))
        if thread.is_alive():
            raise RuntimeError(
                "Az előző O2Ring Bluetooth kapcsolat még nem állt le; "
                "az újraindítás biztonsági okból nem indítható el."
            )
    manager.start(sync_on_start=bool(sync_on_start))


__all__ = [
    "DEFAULT_STOP_TIMEOUT_SECONDS",
    "stop_and_wait",
    "start_reliably",
]
