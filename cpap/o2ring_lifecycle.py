"""Reliable lifecycle boundary for the O2Ring BLE worker.

O2RingBLEManager.stop() is intentionally non-blocking because normal process
shutdown must stay cheap. Configuration, restore, deletion and explicit device
forget operations are different: before they mutate persistent state they must
prove the old BLE worker has actually exited. Likewise a rapid OFF -> ON toggle
must not lose the restart merely because the stopping thread is still alive.
"""
from __future__ import annotations

import time


DEFAULT_STOP_TIMEOUT_SECONDS = 20.0
POST_RECORDING_DRAIN_TIMEOUT_SECONDS = 22.0


def _drain_pending_post_recording_sync(manager, timeout: float) -> None:
    """Give a just-removed ring a short chance to finish its final VLD sync.

    The O2Ring can expose the closed VLD a few seconds after the worn->off
    transition. If the user disables BLE immediately, an unconditional stop used
    to terminate the retry loop before that newest file appeared. Only an already
    pending post-recording sync is drained here; ordinary OFF operations remain
    immediate.
    """
    snapshot = getattr(manager, "snapshot", None)
    if not callable(snapshot):
        return
    try:
        state = snapshot()
    except Exception:
        return
    if not bool((state or {}).get("post_recording_sync_pending")):
        return

    # Wake the normal FileList path immediately, then let its existing 2/5/10/20
    # second retries do the real work. No alternate download implementation is
    # introduced here.
    try:
        request_sync = getattr(manager, "request_sync", None)
        if callable(request_sync):
            request_sync()
    except Exception:
        pass

    deadline = time.monotonic() + max(0.0, min(float(timeout), POST_RECORDING_DRAIN_TIMEOUT_SECONDS))
    while time.monotonic() < deadline:
        try:
            if not bool((snapshot() or {}).get("post_recording_sync_pending")):
                return
        except Exception:
            return
        thread = getattr(manager, "_thread", None)
        if thread is not None and callable(getattr(thread, "is_alive", None)) and not thread.is_alive():
            return
        time.sleep(0.25)


def stop_and_wait(manager, timeout: float = DEFAULT_STOP_TIMEOUT_SECONDS) -> None:
    """Request BLE stop and wait until the worker can no longer mutate state.

    When the ring has just been removed, first preserve the normal post-recording
    retry window so the newest VLD is not lost merely because BLE was switched off
    immediately from the Oximetry quick toggle.
    """
    _drain_pending_post_recording_sync(manager, POST_RECORDING_DRAIN_TIMEOUT_SECONDS)
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
    "POST_RECORDING_DRAIN_TIMEOUT_SECONDS",
    "stop_and_wait",
    "start_reliably",
]
