import re
from pathlib import Path

from cpap.version import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


def test_windows_release_has_single_version_source():
    assert re.fullmatch(r"\d+\.\d+\.\d+", APP_VERSION)

    app_spec = (ROOT / "build" / "windows" / "SleepMate.spec").read_text(encoding="utf-8")
    updater_spec = (ROOT / "build" / "windows" / "SleepMateUpdater.spec").read_text(encoding="utf-8")
    assert "version_info.generated.txt" in app_spec
    assert "version_info.generated.txt" in updater_spec
    assert not (ROOT / "build" / "windows" / "version_info.txt").exists()

    source_build_info = (ROOT / "build_info.json").read_text(encoding="utf-8")
    if '"version": null' in source_build_info:
        assert APP_VERSION not in source_build_info

    build = (ROOT / "build" / "windows" / "build_release.ps1").read_text(encoding="utf-8")
    assert "from cpap.version import APP_VERSION" in build
    assert "version_info.generated.txt" in build
    assert "sleepmate-$AppVersion-windows" in build
    assert "SleepMateUpdater.exe ProductVersion mismatch" in build
    assert "Update manifest version mismatch" in build
    assert "Update manifest asset mismatch" in build
    assert "Expected update ZIP missing" in build
    assert "Program-tree release contract OK" in build
    assert "ISCC.exe" not in build
    assert "SLEEPMATE_SIGN_PFX" not in build

    generator = (ROOT / "scripts" / "generate_msi_wxs.py").read_text(encoding="utf-8")
    assert 'ap.add_argument("--version", required=True)' in generator
    assert '"Version": version' in generator
    assert 'f"SleepMate:{version}"' in generator
    assert "PRODUCT_NAMESPACE" in generator
    assert "PACKAGE_NAMESPACE" in generator

    workflow = (ROOT / ".github" / "workflows" / "windows-release.yml").read_text(encoding="utf-8")
    assert "from cpap.version import APP_VERSION; print(APP_VERSION)" in workflow
    assert 'SleepMate_Setup_v${VERSION}.msi' in workflow
    assert "wixl -v -a x64" in workflow
    assert "msiexec.exe" in workflow


def test_release_pwa_shell_cannot_lose_sleep_feature_after_update():
    sleep_feature_version = "5.2.6"
    chart_feature_version = "5.2.14"
    refresh_feature_version = "5.2.12"
    base = (ROOT / "web" / "service-worker-v508-base.js").read_text(encoding="utf-8")
    live = (ROOT / "web" / "service-worker.js").read_text(encoding="utf-8")
    shell_patch = (ROOT / "cpap" / "sleep_analysis_v522.py").read_text(encoding="utf-8")

    assert "sleepmate-shell-v5.2.14" in base
    assert "sleepmate-shell-v5.2.14-ss131" in live
    for asset_name in (
        "sleepmate-sleep.js",
        "sleepmate-sleep-v523.js",
        "sleepmate-sleep-v524.js",
    ):
        asset = f"{asset_name}?v={sleep_feature_version}"
        assert asset in base
        assert asset in live
        assert asset in shell_patch

    chart_asset = f"sleepmate-chart-v523.js?v={chart_feature_version}"
    assert chart_asset in base
    assert chart_asset in live
    assert chart_asset in shell_patch

    refresh_asset = f"sleepmate-sleep-refresh-v5212.js?v={refresh_feature_version}"
    assert refresh_asset in base
    assert refresh_asset in live
    assert refresh_asset in shell_patch

    for worker in (base, live):
        assert "sleep-analysis" in worker
        assert "const stale=keys.filter" in worker
        assert "self.clients.matchAll({type:'window',includeUncontrolled:true})" in worker
        assert "await client.navigate(client.url)" in worker
        assert "/sleepmate-chart-v523.js" in worker

    spec = (ROOT / "build" / "windows" / "SleepMate.spec").read_text(encoding="utf-8")
    assert "'/sleepmate-chart-v523.js'" in spec
    assert "'/sleepmate-sleep-v523.js'" in spec
    assert "'/sleepmate-sleep-refresh-v5212.js'" in spec


def test_v529_sleepsync_settings_are_hydrated_before_schedule_save():
    app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    hydration = (ROOT / "web" / "sleepsync-hydration-v529.js").read_text(encoding="utf-8")
    integration = (ROOT / "cpap" / "sleepsync_integration.py").read_text(encoding="utf-8")

    assert "sleepsync-hydration-v529.js" in app
    assert "setSaveReady(false)" in hydration
    assert "nativeFetch('/api/sleepsync/settings'" in hydration
    assert "nativeFetch('/api/sleepsync/wifi'" in hydration
    assert "if(therapy)therapy.value=cfg.therapy_data_dir||''" in hydration
    assert "if(backup)backup.value=cfg.backup_root||''" in hydration
    assert "setSaveReady(true)" in hydration
    assert 'payload["auto_sync_mode"] = "scheduled"' in integration
    assert 'if "backup_root" in payload and not str(payload.get("backup_root") or "").strip()' in integration
    assert 'self._default_settings().get("backup_root")' in integration


def test_v529_fresh_tray_is_never_killed_as_stale():
    launcher = (ROOT / "sleepmate_main.py").read_text(encoding="utf-8")
    assert "TRAY_HEARTBEAT_FRESH_SECONDS = 45" in launcher
    assert "if heartbeat_age <= TRAY_HEARTBEAT_FRESH_SECONDS:" in launcher
    assert "return False" in launcher
    fresh_guard = launcher.index("if heartbeat_age <= TRAY_HEARTBEAT_FRESH_SECONDS:")
    taskkill = launcher.index('["taskkill", "/PID"')
    assert fresh_guard < taskkill


def test_v5210_ezshare_association_is_not_restarted_every_few_seconds():
    wifi = (ROOT / "cpap" / "sleepsync_wifi_v5215.py").read_text(encoding="utf-8")
    autograce = (ROOT / "cpap" / "sleepsync_wifi_autograce_v5215.py").read_text(encoding="utf-8")

    assert "ASSOCIATION_WINDOWS = (20, 25, 30, 45)" in wifi
    assert "Escalate only BETWEEN association windows" in wifi
    assert "attempt % 4" not in wifi
    assert "_wait_for_wifi(profile, 3)" not in wifi

    assert "AUTO_ASSOCIATION_GRACE_SECONDS = 12" in autograce
    assert "nem küldünk connect/scant/resetet" in autograce
    assert "target_mode = self._profile_mode(profile)" in autograce
    assert "original_states[profile] = target_mode" in autograce
    assert 'self._set_profile_mode(profile, "auto")' in autograce


def test_v5211_wlan_diagnostics_are_passive_during_association():
    wifi = (ROOT / "cpap" / "sleepsync_wifi_v5215.py").read_text(encoding="utf-8")

    assert "def _wlan_interface_snapshot" in wifi
    assert '["wlan", "show", "interfaces"]' in wifi
    assert "DIAGNOSTIC_INTERVAL_SECONDS = 5" in wifi
    assert "WLAN passzív állapot" in wifi
    assert "Utolsó Windows WLAN állapot" in wifi

    observation_start = wifi.index("deadline = time.monotonic() + association_wait")
    observation_end = wifi.index("active = self.get_current_wifi_ssid()", observation_start)
    observation = wifi[observation_start:observation_end]
    assert "visible_wifi_ssids" not in observation
    assert '["wlan", "connect"' not in observation
    assert "_disconnect_wifi" not in observation


def test_v5215_auto_association_precedes_active_recovery_and_dns_fallback_is_direct():
    integration = (ROOT / "cpap" / "sleepsync_integration.py").read_text(encoding="utf-8")
    autograce = (ROOT / "cpap" / "sleepsync_wifi_autograce_v5215.py").read_text(encoding="utf-8")
    wifi = (ROOT / "cpap" / "sleepsync_wifi_v5215.py").read_text(encoding="utf-8")

    assert "install_sleepsync_wifi_v5215()" in integration
    assert "install_sleepsync_wifi_autograce_v5215()" in integration
    assert integration.index("install_sleepsync_wifi_v5215()") < integration.index(
        "install_sleepsync_wifi_autograce_v5215()"
    )

    grace_start = autograce.index(
        "deadline = time.monotonic() + AUTO_ASSOCIATION_GRACE_SECONDS"
    )
    recovery_start = autograce.index("_ACTIVE_RECOVERY_CONNECT(self, profile)", grace_start)
    grace = autograce[grace_start:recovery_start]
    assert "visible_wifi_ssids" not in grace
    assert "_run_netsh" not in grace
    assert "_disconnect_wifi" not in grace
    assert "return original_states" in autograce

    assert "MANUAL_MIN_SYNC_ATTEMPTS = 8" in wifi
    assert "AUTO_MIN_SYNC_ATTEMPTS = 12" in wifi
    assert "MANUAL_RECOVERY_WINDOW_SECONDS = 25 * 60" in wifi
    assert "AUTO_RECOVERY_WINDOW_SECONDS = 45 * 60" in wifi
    assert "def _run_netsh_native" in wifi
    assert "GetOEMCP" in wifi
    assert "EZSHARE_DIRECT_BASE" in wifi
    assert "_route_gateway_bases" in wifi
    assert "SleepSyncService._wait_http_ready = _wait_http_ready_resilient" in wifi
    assert "SleepSyncService._sync_job = _persistent_sync_job" in wifi


def test_v5212_successful_sleepsync_invalidates_and_refreshes_sleep_view():
    bridge = (ROOT / "cpap" / "sleep_refresh_v5212.py").read_text(encoding="utf-8")
    frontend = (ROOT / "web" / "sleepmate-sleep-refresh-v5212.js").read_text(encoding="utf-8")
    installer = (ROOT / "cpap" / "sleep_analysis_v522.py").read_text(encoding="utf-8")

    assert "service._cache_key = None" in bridge
    assert "service._cache_payload = None" in bridge
    assert "SleepSyncService._sync_connected = sync_connected" in bridge
    assert "SleepSyncService._backup_connected = backup_connected" in bridge
    assert "install_sleep_refresh_v5212(app_module)" in installer

    assert "/api/sleepsync/status?_sleep_refresh=" in frontend
    assert "status.last_run" in frontend
    assert "!status.running&&!status.last_error" in frontend
    assert "document.getElementById('v523Period')" in frontend
    assert "dispatchEvent(new Event('change',{bubbles:true}))" in frontend


def test_v5213_packaged_pwa_scheduler_always_hydrates_and_is_mobile_ready():
    polish = (ROOT / "web" / "sleepsync-polish.js").read_text(encoding="utf-8")
    hydration = (ROOT / "web" / "sleepsync-hydration-v529.js").read_text(encoding="utf-8")
    mobile = (ROOT / "web" / "sleepsync-mobile-v5213.css").read_text(encoding="utf-8")
    sleepsync_css = (ROOT / "web" / "sleepsync.css").read_text(encoding="utf-8")
    base = (ROOT / "web" / "service-worker-v508-base.js").read_text(encoding="utf-8")
    live = (ROOT / "web" / "service-worker.js").read_text(encoding="utf-8")

    assert "ensureHydrationModule" in polish
    assert "script.src='/sleepsync-hydration-v529.js?v=131'" in polish
    assert "requestHydration(false)" in polish
    assert "window.__sleepSyncHydrateSettings=hydrate" in hydration

    assert "repairScheduleIfCleared" in hydration
    assert "ss-schedule-ready" in hydration
    assert "setSaveReady(false)" in hydration
    assert "setSaveReady(true)" in hydration

    assert "sleepsync-mobile-v5213.css" in sleepsync_css
    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in mobile
    assert "font-size:16px!important" in mobile
    assert ".ss-schedule-foot>button" in mobile
    assert "height:50px!important" in mobile

    for worker in (base, live):
        assert "/sleepsync-hydration-v529.js" in worker
        assert "/sleepsync-mobile-v5213.css" in worker


def test_v5214_mobile_tooltip_stays_outside_finger_and_cannot_use_stale_overlay():
    chart = (ROOT / "web" / "sleepmate-chart-v523.js").read_text(encoding="utf-8")
    loader = (ROOT / "cpap" / "sleep_analysis_v522.py").read_text(encoding="utf-8")
    base = (ROOT / "web" / "service-worker-v508-base.js").read_text(encoding="utf-8")
    live = (ROOT / "web" / "service-worker.js").read_text(encoding="utf-8")
    spec = (ROOT / "build" / "windows" / "SleepMate.spec").read_text(encoding="utf-8")

    assert "__sleepmateChartV5214" in chart
    assert "coarse?64:30" in chart
    assert "coarse?64:28" in chart
    assert "event?.pointerType==='touch'" in chart
    assert "cy+gap" not in chart
    assert "y+gap" not in chart
    assert "sleepmate-chart-v523.js?v=5.2.14" in loader
    assert "sleepmate-chart-v523.js?v=5.2.14" in base
    assert "sleepmate-chart-v523.js?v=5.2.14" in live
    assert "'/sleepmate-chart-v523.js'" in spec


def test_v5214_updater_gracefully_removes_tray_icon_before_force_fallback():
    tray = (ROOT / "sleepmate_tray.pyw").read_text(encoding="utf-8")
    updater = (ROOT / "update_worker.py").read_text(encoding="utf-8")

    assert 'QUIT_REQUEST_FILE = STATE_BASE / "private" / "quit_tray.request"' in tray
    assert "if QUIT_REQUEST_FILE.is_file():" in tray
    assert "self.quit()" in tray
    assert "self.icon.stop()" in tray

    assert "def request_graceful_tray_exit" in updater
    assert 'request = state_dir / "private" / "quit_tray.request"' in updater
    assert "graceful = request_graceful_tray_exit(tray_pid, state_dir, log_path)" in updater
    assert "if not graceful and not stop_process_tree" in updater
    graceful_pos = updater.index("graceful = request_graceful_tray_exit")
    force_pos = updater.index("stop_process_tree(tray_pid", graceful_pos)
    image_fallback_pos = updater.index("stop_sleepmate_image_processes(launcher_exe", graceful_pos)
    assert graceful_pos < force_pos < image_fallback_pos
    assert '["taskkill", "/IM", image_name, "/T", "/F"]' in updater
