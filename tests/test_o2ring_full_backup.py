from __future__ import annotations

import json
import zipfile

from cpap.services import create_full_backup, restore_full_backup


def test_full_backup_carries_exact_o2ring_snapshot_and_manifest_config(tmp_path):
    src = tmp_path / "src"
    measurement = src / "private" / "measurement"
    (measurement / "DATALOG").mkdir(parents=True)
    (measurement / "DATALOG" / "night.edf").write_bytes(b"CPAP")

    o2 = src / "private" / "oximetry"
    recordings = o2 / "recordings"
    raw = o2 / "raw"
    recordings.mkdir(parents=True)
    raw.mkdir(parents=True)
    (recordings / "rec-a.json").write_text(
        json.dumps({"schema": 1, "recording_id": "rec-a", "source_name": "A.vld", "samples": []}),
        encoding="utf-8",
    )
    (raw / "rec-a.vld").write_bytes(b"VLD-A")
    (o2 / "deleted_sources.json").write_text(
        json.dumps({"schema": 1, "source_names": ["DELETED.vld"]}),
        encoding="utf-8",
    )

    cfg = {
        "o2ring_enabled": True,
        "o2ring_ble_enabled": True,
        "o2ring_auto_connect": True,
        "o2ring_auto_sync": False,
        "o2ring_auto_match": True,
        "o2ring_preferred_address": "AA:BB:CC:DD:EE:FF",
        "o2ring_clock_offset_seconds": -8.5,
        "o2ring_show_motion": False,
        "o2ring_spo2_reference": 90,
        "o2ring_spo2_secondary_reference": 88,
        "ai_luna_visible": False,
        "ai_milo_visible": True,
        "ai_prompting_enabled": True,
        "pwa_bottom_nav": ["dashboard", "sessions", "more"],
        "pwa_bottom_nav_labels": {"dashboard": "Főoldal"},
    }

    archive = tmp_path / "full.zip"
    create_full_backup(src, measurement, cfg, archive)

    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        assert "private/oximetry/recordings/rec-a.json" in names
        assert "private/oximetry/raw/rec-a.vld" in names
        assert "private/oximetry/deleted_sources.json" in names
        assert zf.read("private/oximetry/raw/rec-a.vld") == b"VLD-A"
        for key, value in cfg.items():
            assert manifest["config"][key] == value

    dst = tmp_path / "dst"
    dst_measurement = dst / "private" / "measurement"
    (dst_measurement / "DATALOG").mkdir(parents=True)
    dst_o2 = dst / "private" / "oximetry"
    (dst_o2 / "recordings").mkdir(parents=True)
    (dst_o2 / "raw").mkdir(parents=True)
    (dst_o2 / "recordings" / "stale.json").write_text("{}", encoding="utf-8")
    (dst_o2 / "raw" / "stale.vld").write_bytes(b"STALE")
    (dst_o2 / "deleted_sources.json").write_text(
        json.dumps({"schema": 1, "source_names": ["STALE.vld"]}),
        encoding="utf-8",
    )

    result = restore_full_backup(dst, archive, dst_measurement)
    assert result["measurement_replaced"] is True
    assert (dst_o2 / "recordings" / "rec-a.json").is_file()
    assert (dst_o2 / "raw" / "rec-a.vld").read_bytes() == b"VLD-A"
    restored_tombstones = json.loads((dst_o2 / "deleted_sources.json").read_text(encoding="utf-8"))
    assert restored_tombstones["source_names"] == ["DELETED.vld"]
    assert not (dst_o2 / "recordings" / "stale.json").exists()
    assert not (dst_o2 / "raw" / "stale.vld").exists()
