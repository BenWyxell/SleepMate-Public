from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FACADE_PATH = ROOT / "cpap" / "sleepsync_integration.py"
ENGINE_PATH = ROOT / "cpap" / "sleepsync_engine_v2.py"
LEGACY_PATH = ROOT / "cpap" / "sleepsync_legacy.py"
WIFI_PATH = ROOT / "cpap" / "sleepsync_wifi_v5215.py"
AUTOGRACE_PATH = ROOT / "cpap" / "sleepsync_wifi_autograce_v5215.py"
PRESENCE_PATH = ROOT / "cpap" / "sleepsync_wifi_presence_v5216.py"
VERSION_PATH = ROOT / "cpap" / "version.py"
UI_PATH = ROOT / "web" / "app.js"
ARCHIVE_UI_PATH = ROOT / "web" / "app-engine119.js"
UI_POLISH_PATH = ROOT / "web" / "sleepsync-polish.js"
HYDRATION_PATH = ROOT / "web" / "sleepsync-hydration-v529.js"
SLEEPSYNC_CSS_PATH = ROOT / "web" / "sleepsync.css"
MOBILE_CSS_PATH = ROOT / "web" / "sleepsync-mobile-v5213.css"
POLISH_CSS_PATH = ROOT / "web" / "sleepsync-polish.css"
NOTICE_CSS_PATH = ROOT / "web" / "sleepsync-notice.css"
STABILITY_PATH = ROOT / "web" / "sleepsync-stability.css"
SERVICE_WORKER_PATH = ROOT / "web" / "service-worker.js"
BASE_WORKER_PATH = ROOT / "web" / "service-worker-v508-base.js"
AURORA_PATH = ROOT / "web" / "sleepmate-aurora.css"
CHART_PATH = ROOT / "web" / "sleepmate-chart-v523.js"
TRAY_PATH = ROOT / "sleepmate_tray.pyw"
UPDATER_PATH = ROOT / "update_worker.py"
SPEC_PATH = ROOT / "build" / "windows" / "SleepMate.spec"

FACADE = FACADE_PATH.read_text(encoding="utf-8")
ENGINE = ENGINE_PATH.read_text(encoding="utf-8")
LEGACY = LEGACY_PATH.read_text(encoding="utf-8")
WIFI = WIFI_PATH.read_text(encoding="utf-8")
AUTOGRACE = AUTOGRACE_PATH.read_text(encoding="utf-8")
PRESENCE = PRESENCE_PATH.read_text(encoding="utf-8")
VERSION = VERSION_PATH.read_text(encoding="utf-8")
UI = UI_PATH.read_text(encoding="utf-8")
ARCHIVE_UI = ARCHIVE_UI_PATH.read_text(encoding="utf-8")
UI_POLISH = UI_POLISH_PATH.read_text(encoding="utf-8")
HYDRATION = HYDRATION_PATH.read_text(encoding="utf-8")
SLEEPSYNC_CSS = SLEEPSYNC_CSS_PATH.read_text(encoding="utf-8")
MOBILE_CSS = MOBILE_CSS_PATH.read_text(encoding="utf-8")
POLISH_CSS = POLISH_CSS_PATH.read_text(encoding="utf-8")
NOTICE_CSS = NOTICE_CSS_PATH.read_text(encoding="utf-8")
STABILITY = STABILITY_PATH.read_text(encoding="utf-8")
SERVICE_WORKER = SERVICE_WORKER_PATH.read_text(encoding="utf-8")
BASE_WORKER = BASE_WORKER_PATH.read_text(encoding="utf-8")
AURORA = AURORA_PATH.read_text(encoding="utf-8")
CHART = CHART_PATH.read_text(encoding="utf-8")
TRAY = TRAY_PATH.read_text(encoding="utf-8")
UPDATER = UPDATER_PATH.read_text(encoding="utf-8")
SPEC = SPEC_PATH.read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"SleepSync integration contract FAILED: {message}")


for path, source in (
    (FACADE_PATH, FACADE),
    (ENGINE_PATH, ENGINE),
    (LEGACY_PATH, LEGACY),
    (WIFI_PATH, WIFI),
    (AUTOGRACE_PATH, AUTOGRACE),
    (PRESENCE_PATH, PRESENCE),
    (TRAY_PATH, TRAY),
    (UPDATER_PATH, UPDATER),
):
    compile(source, str(path), "exec")

require("sleepsync_engine_v2" in FACADE, "canonical facade does not use v2 engine")
require("install_sleepsync_wifi_v5215" in FACADE, "v5.2.15 recovery layer is not installed")
require("install_sleepsync_wifi_autograce_v5215" in FACADE, "auto-association grace layer is not installed")
require("install_sleepsync_wifi_presence_v5216" in FACADE, "v5.2.16 AP-presence gate is not installed")
require('EZSHARE_ROOT = "A:"' in ENGINE, "ez Share root must be exactly A:")
require('sd_directory: str = EZSHARE_ROOT' in ENGINE, "root scan does not use A:")
require("_parse_directory(EZSHARE_ROOT)" in ENGINE, "HTTP readiness does not verify the real A: directory listing")
require('MANDATORY_SENTINEL = "STR.EDF"' in LEGACY, "STR.EDF mandatory sentinel is missing")
require("ALWAYS_REFRESH_FILES" in LEGACY, "always-refresh ResMed file contract is missing")
require("0 fájlt sikerült felismerni" in LEGACY, "zero-file scan is not rejected")
require("Sikeres állapot tiltva" in LEGACY, "0-file/error success guard is missing")
require("missing_mandatory" in LEGACY and "mandatory_refreshed" in LEGACY, "mandatory-file refresh verification is missing")
require("authoritative=True" not in LEGACY, "SleepSync must never authoritative-delete SleepMate data")
require(LEGACY.count("authoritative=False") >= 2, "sync and SD backup must both use non-destructive SleepMate import")

require("def _run_netsh_native" in WIFI, "native Windows console decoding is missing")
require("GetOEMCP" in WIFI, "localized netsh output is not decoded with the Windows OEM code page")
require("def _resilient_connect_wifi" in WIFI, "adaptive ez Share recovery is missing")
require("ASSOCIATION_WINDOWS = (20, 25, 30, 45)" in WIFI, "adaptive association windows changed unexpectedly")
require("DIAGNOSTIC_INTERVAL_SECONDS = 5" in WIFI, "passive WLAN diagnostic cadence is missing")
require("MANUAL_MIN_SYNC_ATTEMPTS = 8" in WIFI, "manual recovery floor is below eight cycles")
require("AUTO_MIN_SYNC_ATTEMPTS = 12" in WIFI, "automatic recovery floor is below twelve cycles")
require("MANUAL_RECOVERY_WINDOW_SECONDS = 25 * 60" in WIFI, "manual recovery window is missing")
require("AUTO_RECOVERY_WINDOW_SECONDS = 45 * 60" in WIFI, "automatic recovery window is missing")
require("SleepSyncService._connect_wifi = _resilient_connect_wifi" in WIFI, "adaptive Wi-Fi override is not installed")
require("SleepSyncService._wait_http_ready = _wait_http_ready_resilient" in WIFI, "resilient HTTP readiness override is not installed")
require("SleepSyncService._sync_job = _persistent_sync_job" in WIFI, "persistent sync retry loop is not installed")
require("EZSHARE_DIRECT_BASE" in WIFI and "_route_gateway_bases" in WIFI, "direct ez Share endpoint fallback is missing")
require("_probe_ezshare_root" in WIFI and "DATALOG" in WIFI and "STR.EDF" in WIFI, "direct endpoint validation is too weak")
require("attempt % 4" not in WIFI, "old periodic disconnect loop leaked back into Wi-Fi acquisition")
require("_wait_for_wifi(profile, 3)" not in WIFI, "old three-second association restart leaked back in")

require("AUTO_ASSOCIATION_GRACE_SECONDS = 12" in AUTOGRACE, "auto-association grace window is not 12 seconds")
require("AUTO_ASSOCIATION_DIAGNOSTIC_SECONDS = 4" in AUTOGRACE, "auto-association diagnostics are not passive/frequent enough")
require('self._set_profile_mode(profile, "auto")' in AUTOGRACE, "ez Share is not made the sole automatic target first")
require("nem küldünk connect/scant/resetet" in AUTOGRACE, "clean no-connect/no-scan/no-reset grace contract is missing")
require("_ACTIVE_RECOVERY_CONNECT(self, profile)" in AUTOGRACE, "auto-association does not fall back to adaptive recovery")
require("return original_states" in AUTOGRACE, "original Wi-Fi profile modes are not preserved across nested recovery")

require("PRESENCE_CONFIRM_DELAY_SECONDS = 2" in PRESENCE, "presence confirmation delay changed unexpectedly")
require("MANUAL_PRESENCE_RECHECK_SECONDS = 30" in PRESENCE, "manual presence recheck is not 30 seconds")
require("AUTO_PRESENCE_RECHECK_SECONDS = 45" in PRESENCE, "automatic presence recheck is not 45 seconds")
require("PRESENCE_POLL_SECONDS = 30" in PRESENCE, "presence polling cadence is not 30 seconds")
require("EzShareNotBroadcastingError" in PRESENCE, "explicit AP-absent state is missing")
require("nem küldünk connect/reset/profile-helyreállítást" in PRESENCE, "AP-absent path can still hammer WLAN recovery")
require("SleepSyncService._connect_wifi = _presence_aware_active_connect" in PRESENCE, "presence-aware connect override is not installed")
require("SleepSyncService._sync_job = _presence_aware_sync_job" in PRESENCE, "presence-aware sync loop is not installed")
require("def _gateway_first_candidates" in AUTOGRACE, "gateway-first HTTP endpoint order is missing")

require("def _sync_connected" in ENGINE, "integrated sync override is missing")
require("super()._backup_connected(jid)" in ENGINE, "sync does not create the full SD mirror + ZIP in the same connection")
require('"backup_created": True' in ENGINE and '"zip_path"' in ENGINE and '"run_root"' in ENGINE, "sync result does not expose its automatic backup")
require("Terápiás adatok, SD-tükör és ZIP elkészült" in ENGINE, "integrated sync/backup completion phase is missing")

require('cfg["auto_sync_mode"] = "scheduled"' in ENGINE, "legacy card-available mode is not migrated to scheduled mode")
require("def _scheduler_loop" in ENGINE and "wifi_network_visible" not in ENGINE.split("def _scheduler_loop", 1)[1].split("def _scan_sd", 1)[0], "automatic scheduler still watches card availability")
require("def _repair_stale_tailscale_serve" in ENGINE, "portable Tailscale stale-port repair is missing")
require("tailscale_auto_serve" in ENGINE and "tailscale_enable()" in ENGINE, "Tailscale repair does not rebind Serve to the active port")

require("document.readyState==='loading'" in UI and "document.write" in UI, "parser-ordered integration boot is missing")
require("/app-engine119.js?v=130" in UI, "stable integration engine generation is not active")
require("/sleepsync-polish.js?v=130" in UI and "/sleepsync-hydration-v529.js?v=130" in UI, "source frontend does not load current SleepSync add-ons")
require("hardRescue" not in UI and "bootHealthy" not in UI, "old mobile boot rescue leaked back in")
require("getRegistrations" not in UI and "unregister" not in UI, "page startup must never unregister the PWA service worker")
require("const core=document.createElement('script')" in ARCHIVE_UI and "core.src='/app-core.js?v=5.0.8'" in ARCHIVE_UI, "frozen #119 engine no longer boots the unchanged core directly")
require("integrationRoute();" in ARCHIVE_UI and "ensureSleepSyncUi();" in ARCHIVE_UI, "frozen #119 route integration is incomplete")
require("statusRequest" in ARCHIVE_UI and "renderJobProgress" in ARCHIVE_UI, "SleepSync status/progress engine is incomplete")
require("ssSettingsSaveStatus" in ARCHIVE_UI and "settingsSaving" in ARCHIVE_UI, "settings save feedback/guard is missing")

require("def replace_literal" in SPEC, "packager has no deterministic core hotfix mechanism")
require("state.latestDay||state.currentDay||state.days[0]" in SPEC and "location.hash===next" in SPEC, "latest-night detailed dashboard routing fix is missing")
require("d.average_usage_seconds==null?null:d.average_usage_seconds/60" in SPEC, "zero usage delta is still treated as missing data")
require("setTimeout(()=>{if(state.pullRefreshing)resetPullRefreshUi()},1100)" in SPEC, "mobile pull-refresh indicator is not transient")
require("sleepsync-bootstrap.js" in SPEC and "sleepsync-integration.js" in SPEC, "packaged SleepSync bootstrap/bridge is missing")
require("'/sleepmate-chart-v523.js'" in SPEC, "packaged PWA does not treat chart overlay as network-first code")
require("'/sleepmate-sleep-v523.js'" in SPEC and "'/sleepmate-sleep-refresh-v5212.js'" in SPEC, "packaged PWA lost sleep module code-asset protection")

require("sleepmate-aurora.css" in SPEC, "core Aurora stylesheet is not packaged")
require(".page:not(#page-sleepsync)" in AURORA, "Aurora visual system is not isolated from SleepSync")
for page in ("#page-dashboard", "#page-patient", "#page-sessions", "#page-events", "#page-reports", "#page-ai", "#page-faq", "#page-equipment", "#page-upload", "#page-logs", "#page-settings"):
    require(page in AURORA, f"Aurora page pass is missing {page}")

require("new MutationObserver" not in UI_POLISH, "polish must not use a global DOM observer")
require("window.fetch=" not in UI_POLISH.replace(" ", ""), "global fetch monkey-patch must not be used by SleepSync polish")
require("bootAttempts<80" in UI_POLISH and "setTimeout(boot,100)" in UI_POLISH, "bounded polish bootstrap is missing")
require("scheduleSummary" in UI_POLISH and "persistAutoToggle" in UI_POLISH, "scheduled UI polish is incomplete")
require('id="ssScheduleDays"' in ARCHIVE_UI and 'id="ssTimeList"' in ARCHIVE_UI, "scheduled editor controls are missing")
require("enforceScheduledOnlyUi" in UI_POLISH and "mode.value='scheduled'" in UI_POLISH, "scheduled-only UI guard is missing")
require("auto_sync_mode:'scheduled'" in UI_POLISH, "automatic toggle can persist a non-scheduled mode")
require("card_available" not in UI_POLISH, "removed card-available automation mode leaked back into active polish logic")
require("ensureHydrationModule" in UI_POLISH and "script.src='/sleepsync-hydration-v529.js'" in UI_POLISH, "packaged PWA cannot self-load SleepSync hydration")
require("window.__sleepSyncHydrateSettings=hydrate" in HYDRATION, "hydration module does not expose a packaged fallback entry point")
require("repairScheduleIfCleared" in HYDRATION, "late PWA schedule rerender recovery is missing")
require("ss-schedule-ready" in HYDRATION and "setSaveReady(false)" in HYDRATION and "setSaveReady(true)" in HYDRATION, "schedule saving is not hydration-gated")
require("sleepsync-mobile-v5213.css" in SLEEPSYNC_CSS, "mobile scheduler stylesheet is not loaded")
require("grid-template-columns:repeat(2,minmax(0,1fr))" in MOBILE_CSS, "mobile schedule grid is not compact")
require("font-size:16px!important" in MOBILE_CSS, "iOS time input zoom guard is missing")
require("height:50px!important" in MOBILE_CSS, "mobile schedule save target is too small")
require(".sleepsync-page #ssTimedSchedule{display:block!important}" in POLISH_CSS, "scheduled editor CSS is not permanently visible")
require("position:fixed!important" in STABILITY, "SleepSync notifications are not fixed overlays")
require("border-radius:6px!important" in NOTICE_CSS and "border-radius:0!important" in NOTICE_CSS, "notification/accent-line geometry cleanup is missing")

require("__sleepmateChartV5214" in CHART, "v5.2.14 chart overlay guard is missing")
require("coarse?64:30" in CHART and "coarse?64:28" in CHART, "touch finger exclusion zone is missing")
require("event?.pointerType==='touch'" in CHART, "touch pointer path is not detected")
require("cy+gap" not in CHART and "y+gap" not in CHART, "tooltip may still fall back below the finger")

require('QUIT_REQUEST_FILE = STATE_BASE / "private" / "quit_tray.request"' in TRAY, "graceful tray quit request path is missing")
require("if QUIT_REQUEST_FILE.is_file():" in TRAY and "self.quit()" in TRAY and "self.icon.stop()" in TRAY, "tray cannot gracefully remove its notification icon")
require("def request_graceful_tray_exit" in UPDATER, "updater has no graceful tray shutdown")
require("graceful = request_graceful_tray_exit(tray_pid, state_dir, log_path)" in UPDATER, "update flow does not request graceful tray exit")
gr = UPDATER.index("graceful = request_graceful_tray_exit")
force = UPDATER.index("stop_process_tree(tray_pid", gr)
image_fallback = UPDATER.index("stop_sleepmate_image_processes(launcher_exe", gr)
require(gr < force < image_fallback, "force-kill can run before graceful tray icon cleanup")

# Release/PWA shell. The 5.2.18 patch changes the desktop first-run wizard,
# while the existing core PWA shell cache generation remains 5.2.14-ss131.
require('APP_VERSION = "5.2.18"' in VERSION, "release version is not 5.2.18")
require("sleepmate-shell-v5.2.14-ss131" in SERVICE_WORKER, "live PWA shell cache is not 5.2.14-ss131")
require("sleepmate-api-v5.2.14-ss131" in SERVICE_WORKER, "live PWA API cache is not 5.2.14-ss131")
for asset in (
    "/sleepsync-hydration-v529.js",
    "/sleepsync-mobile-v5213.css",
    "/sleepmate-sleep.js?v=5.2.6",
    "/sleepmate-sleep-v523.js?v=5.2.6",
    "/sleepmate-chart-v523.js?v=5.2.14",
    "/sleepmate-sleep-v524.js?v=5.2.6",
    "/sleepmate-sleep-refresh-v5212.js?v=5.2.12",
):
    require(asset in SERVICE_WORKER, f"live PWA shell is missing {asset}")
    require(asset in BASE_WORKER, f"release PWA shell base is missing {asset}")
require("const stale=keys.filter" in SERVICE_WORKER and "client.navigate(client.url)" in SERVICE_WORKER, "PWA update cannot evict stale shell and reload an open client")
require("getRegistrations" not in SERVICE_WORKER and "unregister" not in SERVICE_WORKER, "service worker must not unregister itself")
require("'/sleepmate-chart-v523.js'" in SERVICE_WORKER, "live PWA chart overlay is not network-first")
require("'/sleepmate-chart-v523.js'" in BASE_WORKER, "release base chart overlay is not network-first")

require(len(re.findall(r"sleepmate-shell-v\d+\.\d+\.\d+", BASE_WORKER)) == 2, "release packager expects exactly two shell-cache semver markers in base worker")
require(len(re.findall(r"sleepmate-api-v\d+\.\d+\.\d+", BASE_WORKER)) == 1, "release packager expects exactly one API-cache semver marker in base worker")
require(len(re.findall(r"/style\.css\?v=\d+\.\d+\.\d+", BASE_WORKER)) == 1, "release packager expects exactly one versioned style.css literal")
require(len(re.findall(r"/app\.js\?v=\d+\.\d+\.\d+", BASE_WORKER)) == 1, "release packager expects exactly one versioned app.js literal")

print("SleepSync integration safety contract OK")
