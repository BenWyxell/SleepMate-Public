"""Direct Windows BLE runtime for Wellue/Viatom O2Ring devices.

The module is intentionally dependency-light at import time.  Bleak is imported
only when the runtime starts so SleepMate remains usable on systems without
Bluetooth support and test environments can exercise the rest of the app.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import threading
import time
from typing import Any, Callable


@dataclass
class LiveO2State:
    connected: bool = False
    scanning: bool = False
    device_name: str | None = None
    device_address: str | None = None
    spo2: int | None = None
    heart_rate: int | None = None
    perfusion_index: float | None = None
    motion: int | None = None
    battery_percent: int | None = None
    worn: bool | None = None
    measuring: bool = False
    last_sample_ts: float | None = None
    last_error: str | None = None


class O2RingBLEManager:
    """Background BLE manager with an API-friendly, thread-safe live snapshot.

    Protocol parsing is isolated behind ``notification_parser`` so we can keep
    SleepMate's orchestration stable while supporting additional O2Ring firmware
    revisions later without changing the HTTP/UI contracts.
    """

    DEVICE_HINTS = ("O2Ring", "O2 Ring", "Viatom", "Wellue", "Checkme")

    def __init__(self, notification_parser: Callable[[bytes], dict[str, Any]] | None = None):
        self._state = LiveO2State()
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._preferred_address: str | None = None
        self._notification_parser = notification_parser or self._default_parser
        self._listeners: list[Callable[[dict[str, Any]], None]] = []

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            payload = asdict(self._state)
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        return payload

    def add_listener(self, callback: Callable[[dict[str, Any]], None]) -> None:
        self._listeners.append(callback)

    def set_preferred_device(self, address: str | None) -> None:
        self._preferred_address = address or None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._thread_main, name="SleepMate-O2Ring", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _thread_main(self) -> None:
        try:
            asyncio.run(self._run_forever())
        except Exception as exc:
            self._set_error(exc)

    async def _run_forever(self) -> None:
        try:
            from bleak import BleakClient, BleakScanner
        except Exception as exc:
            self._set_error(RuntimeError(f"Bleak nem érhető el: {exc}"))
            return

        while not self._stop.is_set():
            device = None
            try:
                with self._lock:
                    self._state.scanning = True
                    self._state.last_error = None
                devices = await BleakScanner.discover(timeout=5.0)
                for candidate in devices:
                    name = (getattr(candidate, "name", None) or "").strip()
                    address = getattr(candidate, "address", None)
                    if self._preferred_address and address == self._preferred_address:
                        device = candidate
                        break
                    if any(hint.lower() in name.lower() for hint in self.DEVICE_HINTS):
                        device = candidate
                        break
                with self._lock:
                    self._state.scanning = False
                if device is None:
                    await asyncio.sleep(5.0)
                    continue

                with self._lock:
                    self._state.device_name = getattr(device, "name", None)
                    self._state.device_address = getattr(device, "address", None)

                async with BleakClient(device) as client:
                    with self._lock:
                        self._state.connected = True
                    await self._subscribe_known_notify_characteristics(client)
                    while client.is_connected and not self._stop.is_set():
                        await asyncio.sleep(1.0)
            except Exception as exc:
                self._set_error(exc)
            finally:
                with self._lock:
                    self._state.connected = False
                    self._state.measuring = False
                    self._state.scanning = False
            await asyncio.sleep(3.0)

    async def _subscribe_known_notify_characteristics(self, client: Any) -> None:
        """Subscribe to notify characteristics exposed by the connected device.

        We intentionally discover rather than hard-code one UUID here; firmware
        families differ. Protocol-specific write/notify UUID selection is the
        next layer and can be narrowed once the target ring is probed.
        """
        services = client.services
        for service in services:
            for char in service.characteristics:
                props = set(getattr(char, "properties", []) or [])
                if "notify" in props or "indicate" in props:
                    try:
                        await client.start_notify(char.uuid, self._on_notification)
                    except Exception:
                        continue

    def _on_notification(self, _sender: Any, data: bytearray) -> None:
        try:
            update = self._notification_parser(bytes(data))
        except Exception as exc:
            self._set_error(exc)
            return
        if not update:
            return
        now = time.time()
        with self._lock:
            for key in ("spo2", "heart_rate", "perfusion_index", "motion", "battery_percent", "worn", "measuring"):
                if key in update:
                    setattr(self._state, key, update[key])
            self._state.last_sample_ts = now
            self._state.last_error = None
            payload = asdict(self._state)
        for listener in tuple(self._listeners):
            try:
                listener(payload)
            except Exception:
                continue

    @staticmethod
    def _default_parser(data: bytes) -> dict[str, Any]:
        """Conservative parser fallback.

        The real Wellue/Viatom packet decoder is deliberately kept separate.
        Returning no update for unknown packets is safer than inventing medical
        values from an unverified byte layout.
        """
        return {}

    def _set_error(self, exc: Exception) -> None:
        with self._lock:
            self._state.last_error = str(exc)
            self._state.scanning = False
