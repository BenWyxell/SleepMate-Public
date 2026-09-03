import asyncio
import csv
from datetime import datetime
import json
from pathlib import Path
import zipfile
from xml.etree import ElementTree

import cpap.o2ring_ble as ble_module
from cpap.o2ring_ble import CMD_INFO, O2RingBLEManager
from cpap.o2ring_export import EXPORT_COLUMNS, export_o2ring_data
from cpap.oximetry import OximetrySample, OximetryStore


ROOT = Path(__file__).resolve().parents[1]


def _manager(*, auto_sync=True, known=None, file_lists=()):
    known_names = set(known or ())
    received = []
    listed = iter(file_lists)
    manager = O2RingBLEManager(
        known_file=lambda name: name in known_names,
        auto_sync_enabled=lambda: auto_sync,
        on_file=lambda name, raw, _info: (known_names.add(name), received.append((name, raw))),
    )

    async def request(_client, command, **_kwargs):
        assert command == CMD_INFO
        names = next(listed)
        return json.dumps({"FileList": ",".join(names)}).encode("ascii")

    async def download(_client, name):
        return ("raw:" + name).encode("ascii")

    manager._request = request
    manager._download_file = download
    return manager, received


def _remove_ring(manager):
    manager._state.worn = True
    manager._apply_live({"worn": False, "measuring": False})


def test_post_recording_file_available_immediately_is_downloaded():
    manager, received = _manager(file_lists=(("fresh.vld",),))
    _remove_ring(manager)

    asyncio.run(manager._refresh_info(object()))

    assert received == [("fresh.vld", b"raw:fresh.vld")]
    assert manager.snapshot()["post_recording_sync_pending"] is False


def test_post_recording_file_appearing_later_is_downloaded_after_retry(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(ble_module.time, "monotonic", lambda: clock[0])
    manager, received = _manager(file_lists=((), ("delayed.vld",)))
    _remove_ring(manager)

    asyncio.run(manager._refresh_info(object()))
    assert received == []
    assert manager.snapshot()["post_recording_sync_pending"] is True
    assert manager._post_recording_sync_due(101.9) is False

    clock[0] = 102.0
    assert manager._post_recording_sync_due() is True
    asyncio.run(manager._refresh_info(object()))
    assert received == [("delayed.vld", b"raw:delayed.vld")]
    assert manager.snapshot()["post_recording_sync_pending"] is False


def test_post_recording_pending_survives_disconnect_and_downloads_after_reconnect(monkeypatch):
    clock = [200.0]
    monkeypatch.setattr(ble_module.time, "monotonic", lambda: clock[0])
    manager, received = _manager(file_lists=(("after-reconnect.vld",),))
    _remove_ring(manager)

    async def disconnected(_client, _command, **_kwargs):
        raise ConnectionError("BLE disconnected")

    good_request = manager._request
    manager._request = disconnected
    try:
        asyncio.run(manager._refresh_info(object()))
    except ConnectionError:
        pass
    assert manager.snapshot()["post_recording_sync_pending"] is True

    manager._request = good_request
    clock[0] = 202.0
    asyncio.run(manager._refresh_info(object()))
    assert received == [("after-reconnect.vld", b"raw:after-reconnect.vld")]


def test_known_file_is_not_downloaded_again():
    manager, received = _manager(known={"known.vld"}, file_lists=(("known.vld",),))
    _remove_ring(manager)

    asyncio.run(manager._refresh_info(object()))

    assert received == []
    assert manager.snapshot()["post_recording_sync_pending"] is True


def test_auto_sync_off_does_not_download_but_manual_sync_still_does():
    manager, received = _manager(auto_sync=False, file_lists=(("manual.vld",), ("manual.vld",)))
    _remove_ring(manager)
    assert manager._sync_requested.is_set() is False

    asyncio.run(manager._refresh_info(object()))
    assert received == []

    manager.request_sync()
    asyncio.run(manager._refresh_info(object()))
    assert received == [("manual.vld", b"raw:manual.vld")]


def test_periodic_fallback_waits_until_measurement_is_closed():
    manager, received = _manager(file_lists=(("fallback.vld",), ("fallback.vld",)))
    manager._state.measuring = True
    asyncio.run(manager._refresh_info(object()))
    assert received == []

    manager._state.measuring = False
    asyncio.run(manager._refresh_info(object()))
    assert received == [("fallback.vld", b"raw:fallback.vld")]


def test_complete_export_creates_raw_csv_xlsx_and_unique_timestamped_folders(tmp_path):
    store = OximetryStore(tmp_path / "state")
    first = store.save_recording(
        device_id="ring", start_ts=200.0, end_ts=201.0,
        source_name="night two", raw_bytes=b"\x00VLD-two\xff",
        samples=[OximetrySample(200.0, 96, 62, 2, True)],
    )
    second = store.save_recording(
        device_id="ring", start_ts=100.0, end_ts=101.0,
        source_name="night-one.vld", raw_bytes=b"VLD-one",
        samples=[OximetrySample(100.0, 97, 60, 1, True)],
    )
    fixed = lambda: datetime(2026, 9, 3, 8, 9, 10)

    export_one = export_o2ring_data(store, tmp_path / "exports", now=fixed)
    export_two = export_o2ring_data(store, tmp_path / "exports", now=fixed)

    root_one, root_two = Path(export_one["folder"]), Path(export_two["folder"])
    assert root_one != root_two
    assert {item.name for item in root_one.iterdir()} == {"OSCAR", "CSV", "Excel"}
    assert (root_one / "OSCAR" / "night-one.vld").read_bytes() == b"VLD-one"
    assert (root_one / "OSCAR" / "night two.vld").read_bytes() == b"\x00VLD-two\xff"

    csv_path = next((root_one / "CSV").glob("*.csv"))
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert tuple(rows[0]) == EXPORT_COLUMNS
    assert [float(row["timestamp"]) for row in rows] == [100.0, 200.0]
    assert [row["recording_id"] for row in rows] == [
        second["recording_id"], first["recording_id"],
    ]

    xlsx_path = next((root_one / "Excel").glob("*.xlsx"))
    with zipfile.ZipFile(xlsx_path) as archive:
        assert "xl/worksheets/sheet1.xml" in archive.namelist()
        sheet = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    assert len(sheet.findall(".//x:sheetData/x:row", ns)) == 3


def test_export_controls_use_existing_responsive_settings_patterns():
    js = (ROOT / "web" / "sleepmate-v530.js").read_text(encoding="utf-8")
    css = (ROOT / "web" / "sleepmate-v530.css").read_text(encoding="utf-8")
    for marker in (
        'class="path-picker"', 'class="settings-actions sm-o2-export-actions"',
        'id="smO2ExportDir"', 'id="smO2BrowseExport"', 'id="smO2ExportAll"',
        'id="smO2OpenExport"', '/api/o2ring/export-sync', '/api/o2ring/export',
        'O2Ring szinkronizálása…', 'O2Ring adatok exportálása…',
        'Az O2Ring adatok exportálása elkészült.',
    ):
        assert marker in js
    assert ".sm-o2-export .path-picker{grid-template-columns:1fr}" in css
    assert ".sm-o2-export-actions button{width:100%" in css
