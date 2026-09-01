"""Direct Windows BLE runtime for Wellue/Viatom O2Ring devices.

Bluetooth/GATT connection state is deliberately separate from remembered device
identity. Stopping BLE never forgets the selected ring; forgetting a device is
an explicit higher-level action.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import threading
import time
from typing import Any, Callable

MATCH_UUID = "00001801-0000-1000-8000-00805f9b34fb"
SERVICE_UUID = "14839ac4-7d7e-415c-9a42-167340cf2339"
NOTIFY_UUID = "0734594a-a8e7-4b1a-a6b1-cd5243059a57"
WRITE_UUID = "8b00ace7-eb0b-49b0-bbe9-9aee0a26e1a3"
CMD_FILE_OPEN, CMD_FILE_READ, CMD_FILE_CLOSE = 0x03, 0x04, 0x05
CMD_INFO, CMD_CONFIG, CMD_READ_SENSORS = 0x14, 0x16, 0x17


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
    signal_strength: int | None = None
    motion: int | None = None
    battery_percent: int | None = None
    worn: bool | None = None
    calibrating: bool = False
    measuring: bool = False
    last_sample_ts: float | None = None
    last_sync_ts: float | None = None
    stored_file_count: int = 0
    device_config: dict[str, Any] | None = None
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
    body.extend(int(block).to_bytes(2, "little"))
    body.extend(len(data).to_bytes(2, "little"))
    body.extend(data)
    body.append(crc8(bytes(body)))
    return bytes(body)


def parse_response(frame: bytes) -> tuple[int, int, bytes]:
    if len(frame) < 8 or frame[0] != 0x55 or frame[2] != (frame[1] ^ 0xFF):
        raise ValueError("Érvénytelen O2Ring válaszkeret.")
    if crc8(frame[:-1]) != frame[-1]:
        raise ValueError("Hibás O2Ring CRC.")
    length = int.from_bytes(frame[5:7], "little")
    if len(frame) != 8 + length:
        raise ValueError("Csonka O2Ring válaszkeret.")
    return int(frame[1]), int.from_bytes(frame[3:5], "little"), frame[7:-1]


def parse_live_packet(frame: bytes) -> dict[str, Any]:
    try:
        status, _block, payload = parse_response(frame)
    except ValueError:
        return {}
    if status != 0 or len(payload) < 12:
        return {}
    spo2_raw, hr_raw = int(payload[0]), int(payload[1])
    worn = bool(payload[11])
    calibrating = worn and (spo2_raw in {0, 255} or hr_raw in {0, 255})
    spo2 = spo2_raw if worn and 50 <= spo2_raw <= 100 else None
    heart_rate = hr_raw if worn and 20 <= hr_raw <= 250 else None
    return {
        "spo2": spo2,
        "heart_rate": heart_rate,
        "battery_percent": int(payload[7]) if int(payload[7]) <= 100 else None,
        "motion": int(payload[9]),
        "signal_strength": int(payload[10]),
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
            while self.buffer and self.buffer[0] != 0x55:
                del self.buffer[0]
            if len(self.buffer) < 8:
                break
            total = 8 + int.from_bytes(self.buffer[5:7], "little")
            if total > 2_000_000:
                del self.buffer[0]
                continue
            if len(self.buffer) < total:
                break
            frame = bytes(self.buffer[:total])
            del self.buffer[:total]
            try:
                parse_response(frame)
                frames.append(frame)
            except ValueError:
                continue
        return frames


class O2RingBLEManager:
    DEVICE_HINTS = (
        "Checkme_O2", "CheckO2", "SleepU", "SleepO2", "O2Ring",
        "O2 Ring", "WearO2", "KidsO2", "BabyO2", "Oxylink",
    )

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
        self._pending_config: dict[str, Any] | None = None

    @classmethod
    def looks_like_supported_device(cls, name: str, service_uuids: set[str]) -> bool:
        lname = str(name or "").lower()
        if SERVICE_UUID.lower() in {str(x).lower() for x in service_uuids}:
            return True
        return any(hint.lower() in lname for hint in cls.DEVICE_HINTS)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            payload = asdict(self._state)
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        payload["ble_service_uuid"] = SERVICE_UUID
        payload["remembered_address"] = self._preferred_address
        return payload

    def add_listener(self, callback):
        self._listeners.append(callback)

    def set_preferred_device(self, address):
        self._preferred_address = str(address or "").strip() or None

    def request_sync(self):
        self._sync_requested.set()

    def queue_device_config(self, update: dict[str, Any]):
        self._pending_config = dict(update or {})

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._sync_requested.set()
        self._thread = threading.Thread(target=self._thread_main, name="SleepMate-O2Ring", daemon=True)
        self._thread.start()

    def stop(self):
        """Stop active BLE work but retain the remembered ring address."""
        self._stop.set()

    def _thread_main(self):
        try:
            asyncio.run(self._run_forever())
        except Exception as exc:
            self._set_error(exc)

    async def _run_forever(self):
        try:
            from bleak import BleakClient, BleakScanner
        except Exception as exc:
            self._set_error(RuntimeError(f"Bleak nem érhető el: {exc}"))
            return
        self._loop = asyncio.get_running_loop()
        self._responses = asyncio.Queue()
        while not self._stop.is_set():
            try:
                with self._lock:
                    self._state.scanning = True
                    self._state.last_error = None

                discovered = await BleakScanner.discover(timeout=5.0, return_adv=True)
                device = None
                for candidate, adv in discovered.values():
                    address = str(getattr(candidate, "address", None) or "")
                    name = str(
                        getattr(candidate, "name", None)
                        or getattr(adv, "local_name", None)
                        or ""
                    ).strip()
                    service_uuids = set(getattr(adv, "service_uuids", None) or [])
                    if self._preferred_address and address == self._preferred_address:
                        device = candidate
                        break
                    if self.looks_like_supported_device(name, service_uuids):
                        device = candidate
                        break

                with self._lock:
                    self._state.scanning = False
                if device is None:
                    await asyncio.sleep(4)
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
                        if self._pending_config:
                            update = self._pending_config
                            self._pending_config = None
                            await self._write_config(client, update)
                            await self._refresh_info(client)
                        await self._request(client, CMD_READ_SENSORS, timeout=2.0, live=True)
                        if self._sync_requested.is_set() or time.monotonic() - last_info > 60:
                            await self._refresh_info(client)
                            last_info = time.monotonic()
                        await asyncio.sleep(1)
            except Exception as exc:
                if not self._stop.is_set():
                    self._set_error(exc)
            finally:
                with self._lock:
                    self._state.connected = False
                    self._state.measuring = False
                    self._state.scanning = False
            if not self._stop.is_set():
                await asyncio.sleep(3)

    async def _send(self, client, packet: bytes):
        for offset in range(0, len(packet), 20):
            await client.write_gatt_char(WRITE_UUID, packet[offset:offset + 20], response=False)
            if len(packet) > 20:
                await asyncio.sleep(.02)

    async def _next_response(self, timeout=5.0) -> bytes:
        if self._responses is None:
            raise asyncio.TimeoutError()
        return await asyncio.wait_for(self._responses.get(), timeout)

    async def _request(self, client, command: int, data: bytes = b"", block: int = 0,
                       timeout=5.0, live=False) -> bytes:
        await self._send(client, build_packet(command, data, block))
        frame = await self._next_response(timeout)
        status, _rb, payload = parse_response(frame)
        if status != 0:
            raise RuntimeError(f"O2Ring parancshiba: {command:#04x}, státusz {status}")
        if live:
            update = parse_live_packet(frame)
            if update:
                self._apply_live(update)
        return payload

    async def _refresh_info(self, client):
        payload = await self._request(client, CMD_INFO, timeout=4)
        info = json.loads(payload.rstrip(b"\x00 \t\r\n").decode("ascii", errors="replace"))
        files = [x.strip() for x in str(info.get("FileList") or "").split(",") if x.strip()]
        with self._lock:
            self._state.device_model = str(info.get("Model") or self._state.device_name or "") or None
            self._state.serial_number = str(info.get("SN") or "") or None
            self._state.stored_file_count = len(files)
            self._state.device_config = info
            try:
                self._state.battery_percent = int(str(info.get("CurBAT") or "").replace("%", ""))
            except Exception:
                pass
        if self._sync_requested.is_set() and not self._state.measuring:
            await self._download_new_files(client, files, info)
            self._sync_requested.clear()

    async def _write_config(self, client, update: dict[str, Any]):
        allowed = {
            "SetOxiSwitch", "SetOxiThr", "SetHRSwitch", "SetHRHighThr",
            "SetHRLowThr", "SetMotor", "SetLightingMode", "SetLightStr", "SetTIME",
        }
        clean = {k: str(v) for k, v in update.items() if k in allowed}
        if not clean:
            return
        data = json.dumps(clean, separators=(",", ":")).encode("ascii")
        await self._request(client, CMD_CONFIG, data=data, timeout=4)

    async def _download_new_files(self, client, files, info):
        for name in files:
            if self._stop.is_set() or self._known_file(name):
                continue
            raw = await self._download_file(client, name)
            if raw and self._on_file:
                self._on_file(name, raw, info)
        with self._lock:
            self._state.last_sync_ts = time.time()

    async def _download_file(self, client, name: str) -> bytes:
        payload = await self._request(
            client, CMD_FILE_OPEN,
            name.encode("ascii", errors="ignore") + b"\x00",
            timeout=5,
        )
        if len(payload) < 4:
            raise RuntimeError(f"O2Ring fájlméret nem olvasható: {name}")
        file_size = int.from_bytes(payload[:4], "little")
        if not 0 < file_size < 50_000_000:
            raise RuntimeError(f"Érvénytelen O2Ring fájlméret: {file_size}")
        output = bytearray()
        block = 0
        try:
            while len(output) < file_size:
                chunk = await self._request(client, CMD_FILE_READ, block=block, timeout=6)
                if not chunk:
                    break
                output.extend(chunk)
                block += 1
            if len(output) < file_size:
                raise RuntimeError(f"Csonka O2Ring fájlletöltés: {name}")
            return bytes(output[:file_size])
        finally:
            try:
                await self._request(client, CMD_FILE_CLOSE, timeout=2)
            except Exception:
                pass

    def _apply_live(self, update):
        now = time.time()
        with self._lock:
            previous_worn = self._state.worn
            for key, value in update.items():
                setattr(self._state, key, value)
            self._state.last_sample_ts = now
            self._state.last_error = None
            payload = asdict(self._state)
        if previous_worn is True and update.get("worn") is False:
            self._sync_requested.set()
        for listener in tuple(self._listeners):
            try:
                listener(payload)
            except Exception:
                pass

    def _on_notification(self, _sender, data: bytearray):
        for frame in self._assembler.feed(bytes(data)):
            if self._responses is not None and self._loop is not None:
                self._loop.call_soon_threadsafe(self._responses.put_nowait, frame)

    def _set_error(self, exc):
        with self._lock:
            self._state.last_error = str(exc)
            self._state.scanning = False


__all__ = [
    "O2RingBLEManager", "LiveO2State", "MATCH_UUID", "SERVICE_UUID", "NOTIFY_UUID",
    "WRITE_UUID", "CMD_READ_SENSORS", "build_packet", "crc8", "parse_response",
    "parse_live_packet",
]
