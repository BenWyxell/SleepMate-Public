from __future__ import annotations

from pathlib import Path

from cpap.oximetry import OximetryStore
from cpap.o2ring_stability_v5319 import install_o2ring_stability_v5319


ROOT = Path(__file__).resolve().parents[1]
STABLE_UPDATER_SHA256 = "f1ae4577887315b50c4c31f563d7d6c56da8a4ccfe2827f19a40dda7e8aa66e4"
STABLE_UPDATER_SOURCE_BLOB = "473938fe42d561a31243326793d7894681996eb7"


def test_status_count_never_parses_historical_recordings():
    from cpap import o2ring_integration as integration

    install_o2ring_stability_v5319()
    service = integration.O2RingService.__new__(integration.O2RingService)
    service.settings = lambda: {
        "o2ring_enabled": True,
        "o2ring_ble_enabled": True,
    }

    class Manager:
        def snapshot(self):
            return {"connected": False, "last_error": None}

    class Store:
        def count_recordings(self):
            return 7

        def list_recordings(self):
            raise AssertionError("status must never parse historical recording JSON")

    service.manager = Manager()
    service.store = Store()
    payload = service.status()
    assert payload["feature_enabled"] is True
    assert payload["recordings"] == 7
    assert payload["live"]["connected"] is False


def test_pretty_printed_large_recording_metadata_is_prefix_only(tmp_path: Path):
    store = OximetryStore(tmp_path)
    path = store.recordings_dir / "legacy-pretty.json"
    # Legacy/pretty formatting deliberately puts whitespace around the samples key.
    # The large array must never trigger a full json.loads of the entire file.
    sample = '{"timestamp":1,"spo2":97,"heart_rate":65,"motion":0,"valid":true}'
    samples = ",".join([sample] * 30000)
    path.write_text(
        '{\n  "schema": 1,\n  "recording_id": "legacy-pretty",\n'
        '  "device_id": "ring",\n  "source_name": "legacy.vld",\n'
        '  "start_ts": 1,\n  "end_ts": 2,\n  "summary": {"sample_count":30000},\n'
        '  "samples" : [' + samples + ']\n}',
        encoding="utf-8",
    )
    assert path.stat().st_size > 1_000_000

    metadata = store._recording_metadata(path)
    assert metadata["recording_id"] == "legacy-pretty"
    assert metadata["source_name"] == "legacy.vld"
    assert "samples" not in metadata

    rows = store.list_recordings()
    assert len(rows) == 1
    assert getattr(rows[0], "_samples_loaded") is False


def test_o2_recovery_keeps_visible_placeholder_when_status_fails():
    js = (ROOT / "web/o2ring-recovery-v5318.js").read_text(encoding="utf-8")
    assert "const BUILD='5.3.19-recovery'" in js
    assert "data-o2-recovery-placeholder" in js
    assert "function installPlaceholder(message)" in js
    assert "ensureSidebarButton()" in js
    assert "Az O2Ring háttérszolgáltatás most nem válaszol" in js
    assert "Újrapróbálás" in js
    assert "api('/api/o2ring/status')" in js
    assert "showRecoveryError(error?.message||String(error))" in js


def test_windows_release_reuses_exact_stable_updater_component():
    build = (ROOT / "build/windows/build_release.ps1").read_text(encoding="utf-8")
    assert "$StableUpdaterVersion = '5.3.17'" in build
    assert STABLE_UPDATER_SHA256 in build
    assert STABLE_UPDATER_SOURCE_BLOB in build
    assert "git rev-parse HEAD:update_worker.py" in build
    assert "Invoke-WebRequest -Uri $StableUpdaterZipUrl" in build
    assert "Pinned updater hash mismatch" in build
    assert "Packaged updater changed during copy" in build
    assert "SleepMateUpdater PyInstaller build" not in build
    assert "build\\windows\\SleepMateUpdater.spec" not in build
