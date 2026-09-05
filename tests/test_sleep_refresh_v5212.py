from pathlib import Path


def test_sleepsync_success_invalidates_sleep_analysis_cache():
    root = Path(__file__).resolve().parents[1]
    patch = (root / "cpap" / "sleep_refresh_v5212.py").read_text(encoding="utf-8")

    assert "service._cache_key = None" in patch
    assert "service._cache_payload = None" in patch
    assert "SleepSyncService._sync_connected = sync_connected" in patch
    assert "SleepSyncService._backup_connected = backup_connected" in patch
    assert "original_sync_connected(self, jid)" in patch
    assert "original_backup_connected(self, jid)" in patch


def test_open_sleep_view_refreshes_after_new_successful_sleepsync_run():
    root = Path(__file__).resolve().parents[1]
    js = (root / "web" / "sleepmate-sleep-refresh-v5212.js").read_text(encoding="utf-8")

    assert "/api/sleepsync/status?_sleep_refresh=" in js
    assert "status.last_run" in js
    assert "!status.running&&!status.last_error" in js
    assert "document.getElementById('v523Period')" in js
    assert "dispatchEvent(new Event('change',{bubbles:true}))" in js
    assert "document.hidden" in js


def test_sleep_refresh_bridge_is_installed_before_runtime_sleepsync_service_creation():
    root = Path(__file__).resolve().parents[1]
    installer = (root / "cpap" / "sleep_analysis_v522.py").read_text(encoding="utf-8")

    assert "from .sleep_refresh_v5212 import install_sleep_refresh_v5212" in installer
    assert "install_sleep_refresh_v5212(app_module)" in installer
    assert "sleepmate-sleep-refresh-v5212.js?v=5.2.12" in installer
