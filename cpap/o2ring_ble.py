"""Direct Windows BLE runtime for Wellue/Viatom O2Ring devices.

The implementation speaks the documented Viatom/Lepu framing directly through
Bleak.  No ViHealth/Wellue desktop application and no interactive CLI process is
required.  Unknown or malformed packets are ignored rather than converted into
invented physiological values.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import threading
import time
from typing import Any, Callable


SERVICE_UUID = "14839ac4-7d7e-415c-9a42-167340cf2339"
NOTIFY_UUID = "0734594a-a8e7-4b1a-a6b1-cd5243059a57"
WRITE_UUID = "8b00ace7-eb0b-49b0-bbe9-9aee0a26e1a3"
CMD_INFO = 0x14
CMD_READ_SENSORS = 0x17
CMD_FILE_OPEN = 0x03
CMD_FILE_READ = 0x04
CMD_FILE_CLOSE = 0x05


@dataclass
class LiveO2State:
    connected: bool = False
    scanning: bool = False
    device_name: str | None = None
    device_address: str | None = None
    device_model: str | None = None
    serial_number: str | None = None
    spo2: int | None = None
    heart_rate: int | None = None
    perfusion_index: float | None = None
    motion: int | None = None
    battery_percent: int | None = None
    worn: bool | None = None
    calibrating: bool = False
    measuring: bool = False
    last_sample_ts: float | None = None
    last_sync_ts: float | None = None
    stored_file_count: int = 0
    last_error: str | None = None


def crc8(data: bytes) -> int:
    crc = 0
    for byte in data:
        chk = crc ^ byte
        crc = 0
        if chk & 0x01: crc = 0x07
        if chk & 0x02: crc ^= 0x0E
        if chk & 0x04: crc ^= 0x1C
        if chk & 0x08: crc ^= 0x38
        if chk & 0x10: crc ^= 0x70
        if chk & 0x20: crc ^= 0xE0
        if chk & 0x40: crc ^= 0xC7
        if chk & 0x80: crc ^= 0x89
    return crc


def build_packet(command: int, data: bytes = b"", block: int = 0) -> bytes:
    body = bytearray((0xAA, command & 0xFF, (command ^ 0xFF) & 0xFF))
    body.extend(int(block).to_bytes(2, "little", signed=False))
    body.extend(len(data).to_bytes(2, "little", signed=False))
    body.extend(data)
    body.append(crc8(bytes(body)))
    return bytes(body)


def parse_live_packet(data: bytes) -> dict[str, Any]:
    """Parse the live READ_SENSORS response used by PO1/PO2/PO3-family rings."""
    if len(data) < 19 or data[0] != 0xAA or data[1] != CMD_READ_SENSORS:
        return {}
    if data[2] != (CMD_READ_SENSORS ^ 0xFF):
        return {}
    spo2_raw = int(data[7])
    hr_raw = int(data[8])
    worn = int(data[18]) == 0
    calibrating = worn and (spo2_raw == 0 or hr_raw == 0)
    spo2 = spo2_raw if worn and 50 <= spo2_raw <= 100 else None
    heart_rate = hr_raw if worn and 20 <= hr_raw <= 250 else None
    return {
        "spo2": spo2,
        "heart_rate": heart_rate,
        "battery_percent": int(data[14]) if int(data[14]) <= 100 else None,
        "motion": int(data[16]),
        "perfusion_index": float(data[17]),
        "worn": worn,
        "calibrating": calibrating,
        "measuring": bool(worn and not calibrating and spo2 is not None and heart_rate is not None),
    }


class _FrameAssembler:
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, chunk: bytes) -> list[bytes]:
        self.buffer.extend(chunk)
        frames: list[bytes] = []
        while True:
            while self.buffer and self.buffer[0] != 0xAA:
                del self.buffer[0]
            if len(self.buffer) < 8:
                break
            payload_len = int.from_bytes(self.buffer[5:7], "little")
            total = 7 + payload_len + 1
            if total <= 0 or total > 2_000_000:
                del self.buffer[0]
                continue
            if len(self.buffer) < total:
                break
            frame = bytes(self.buffer[:total])
            del self.buffer[:total]
            if frame[2] == (frame[1] ^ 0xFF) and crc8(frame[:-1]) == frame[-1]:
                frames.append(frame)
        return frames


class O2RingBLEManager:
    """Autonomous O2Ring connection, live polling and stored-file downloader."""

    DEVICE_HINTS = ("O2Ring", "O2 Ring", "Viatom", "Wellue", "Checkme", "O2")

    def __init__(self, *, known_file: Callable[[str], bool] | None = None,
                 on_file: Callable[[str, bytes, dict[str, Any]], None] | None = None):
        self._state = LiveO2State()
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._sync_requested = threading.Event()
        self._preferred_address: str | None = None
        self._listeners: list[Callable[[dict[str, Any]], None]] = []
        self._known_file = known_file or (lambda _name: False)
        self._on_file = on_file
        self._assembler = _FrameAssembler()
        self._responses: asyncio.Queue[bytes] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            payload = asdict(self._state)
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        payload["ble_service_uuid"] = SERVICE_UUID
        return payload

    def add_listener(self, callback: Callable[[dict[str, Any]], None]) -> None:
        self._listeners.append(callback)

    def set_preferred_device(self, address: str | None) -> None:
        self._preferred_address = str(address or "").strip() or None

    def request_sync(self) -> None:
        self._sync_requested.set()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._sync_requested.set()
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
        self._loop = asyncio.get_running_loop()
        self._responses = asyncio.Queue()
        while not self._stop.is_set():
            device = None
            try:
                with self._lock:
                    self._state.scanning = True
                    self._state.last_error = None
                devices = await BleakScanner.discover(timeout=5.0, service_uuids=[SERVICE_UUID])
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
                async with BleakClient(device, timeout=10.0) as client:
                    await client.start_notify(NOTIFY_UUID, self._on_notification)
                    with self._lock:
                        self._state.connected = True
                    await self._refresh_info(client)
                    last_info = time.monotonic()
                    while client.is_connected and not self._stop.is_set():
                        await self._send(client, build_packet(CMD_READ_SENSORS))
                        try:
                            await self._wait_command(CMD_READ_SENSORS, timeout=2.0)
                        except asyncio.TimeoutError:
                            pass
                        if self._sync_requested.is_set() or time.monotonic() - last_info > 60.0:
                            await self._refresh_info(client)
                            last_info = time.monotonic()
                        await asyncio.sleep(1.0)
            except Exception as exc:
                self._set_error(exc)
            finally:
                with self._lock:
                    self._state.connected = False
                    self._state.measuring = False
                    self._state.scanning = False
            await asyncio.sleep(3.0)

    async def _send(self, client: Any, packet: bytes) -> None:
        for offset in range(0, len(packet), 20):
            await client.write_gatt_char(WRITE_UUID, packet[offset:offset + 20], response=False)
            if len(packet) > 20:
                await asyncio.sleep(0.02)

    async def _wait_command(self, command: int, timeout: float = 5.0) -> bytes:
        if self._responses is None:
            raise asyncio.TimeoutError()
        deadline = self._loop.time() + timeout if self._loop else time.monotonic() + timeout
        while True:
            remaining = deadline - (self._loop.time() if self._loop else time.monotonic())
            if remaining <= 0:
                raise asyncio.TimeoutError()
            frame = await asyncio.wait_for(self._responses.get(), remaining)
            if len(frame) >= 2 and frame[1] == command:
                return frame

    async def _refresh_info(self, client: Any) -> None:
        try:
            await self._send(client, build_packet(CMD_INFO))
            frame = await self._wait_command(CMD_INFO, timeout=4.0)
            payload = frame[7:-1]
            info = json.loads(payload.rstrip(b"\x00").decode("utf-8", errors="replace"))
            files = [x.strip() for x in str(info.get("FileList") or "").split(",") if x.strip()]
            battery_text = str(info.get("CurBAT") or "").replace("%", "").strip()
            with self._lock:
                self._state.device_model = str(info.get("Model") or self._state.device_name or "") or None
                self._state.serial_number = str(info.get("SN") or "") or None
                self._state.stored_file_count = len(files)
                try:
                    self._state.battery_percent = int(battery_text)
                except Exception:
                    pass
            if self._sync_requested.is_set():
                await self._download_new_files(client, files, info)
                self._sync_requested.clear()
        except Exception as exc:
            self._set_error(exc)

    async def _download_new_files(self, client: Any, files: list[str], info: dict[str, Any]) -> None:
        for name in files:
            if self._stop.is_set() or self._known_file(name):
                continue
            raw = await self._download_file(client, name)
            if raw and self._on_file:
                self._on_file(name, raw, info)
        with self._lock:
            self._state.last_sync_ts = time.time()

    async def _download_file(self, client: Any, name: str) -> bytes:
        await self._send(client, build_packet(CMD_FILE_OPEN, name.encode("ascii", errors="ignore") + b"\x00"))
        opened = await self._wait_command(CMD_FILE_OPEN, timeout=5.0)
        if len(opened) < 12:
            raise RuntimeError(f"O2Ring fájlmegnyitási válasz túl rövid: {name}")
        data = opened[7:-1]
        status = int(data[0]) if data else 0
        if status != 0:
            raise RuntimeError(f"O2Ring fájlmegnyitási hiba ({status}): {name}")
        size_candidates = []
        if len(data) >= 11:
            size_candidates.append(int.from_bytes(data[7:11], "little"))
        if len(data) >= 5:
            size_candidates.append(int.from_bytes(data[-4:], "little"))
        file_size = next((v for v in size_candidates if 0 < v < 50_000_000), 0)
        if not file_size:
            raise RuntimeError(f"O2Ring fájlméret nem olvasható: {name}")
        output = bytearray()
        block = 0
        try:
            while len(output) < file_size:
                await self._send(client, build_packet(CMD_FILE_READ, block=block))
                frame = await self._wait_command(CMD_FILE_READ, timeout=6.0)
                chunk = frame[7:-1]
                if not chunk:
                    break
                output.extend(chunk)
                block += 1
            return bytes(output[:file_size])
        finally:
            try:
                await self._send(client, build_packet(CMD_FILE_CLOSE))
                await self._wait_command(CMD_FILE_CLOSE, timeout=2.0)
            except Exception:
                pass

    def _on_notification(self, _sender: Any, data: bytearray) -> None:
        for frame in self._assembler.feed(bytes(data)):
            if frame[1] == CMD_READ_SENSORS:
                update = parse_live_packet(frame)
                if update:
                    now = time.time()
                    with self._lock:
                        for key, value in update.items():
                            setattr(self._state, key, value)
                        self._state.last_sample_ts = now
                        self._state.last_error = None
                        payload = asdict(self._state)
                    for listener in tuple(self._listeners):
                        try:
                            listener(payload)
                        except Exception:
                            continue
            if self._responses is not None and self._loop is not None:
                try:
                    self._loop.call_soon_threadsafe(self._responses.put_nowait, frame)
                except Exception:
                    pass

    def _set_error(self, exc: Exception) -> None:
        with self._lock:
            self._state.last_error = str(exc)
            self._state.scanning = False


__all__ = [
    "O2RingBLEManager", "LiveO2State", "SERVICE_UUID", "NOTIFY_UUID", "WRITE_UUID",
    "build_packet", "crc8", "parse_live_packet",
]
