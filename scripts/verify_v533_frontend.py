from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "cpap" / "version.py").read_text(encoding="utf-8")
FEATURES = (ROOT / "cpap" / "v530_features.py").read_text(encoding="utf-8")
RECOVERY = (ROOT / "web" / "frontend-v533.js").read_text(encoding="utf-8")
RECOVERY_CSS = (ROOT / "web" / "frontend-v533.css").read_text(encoding="utf-8")
O2 = (ROOT / "web" / "o2ring-v532.js").read_text(encoding="utf-8")
SW = (ROOT / "web" / "service-worker.js").read_text(encoding="utf-8")
BASE_SW = (ROOT / "web" / "service-worker-v508-base.js").read_text(encoding="utf-8")
FIRST_RUN = (ROOT / "web" / "first-run.js").read_text(encoding="utf-8")


def require(ok: bool, message: str) -> None:
    if not ok:
        raise SystemExit(f"v5.3.3 frontend recovery contract FAILED: {message}")


require('APP_VERSION = "5.3.3"' in VERSION, "APP_VERSION is not 5.3.3")
require('API_VERSION = 19' in VERSION, "API version changed unexpectedly")
require('BUILD_CHANNEL = "stable"' in VERSION, "build channel is not stable")

require('frontend-v533.js' in FEATURES, "recovery controller is not injected")
require('frontend-v533.css' in FEATURES, "recovery stylesheet is not injected")
require('sleepmate-ui-version' in FEATURES and '5.3.3' in FEATURES, "HTML shell has no UI generation marker")
require('X-SleepMate-UI-Version' in FEATURES, "server does not expose UI generation header")
require('no-store, no-cache, must-revalidate' in FEATURES, "HTML shell can still be browser-cached")
require('/app.js?v=5.3.3' in FEATURES and '/style.css?v=5.3.3' in FEATURES, "source shell cache-busting is not current")

for marker in (
    'enforceFrontendGeneration',
    'normalizeSettings',
    'dedupeSetupWizard',
    'normalizePwaLiveChoice',
    'openOximetryLive',
    'bindOximetryNavigation',
    'bindDailyModes',
    'setDailyMode',
    'fixLatestStatusFlash',
    'hookOverviewRefresh',
):
    require(marker in RECOVERY, f"recovery controller is missing {marker}")
require("push.textContent='PWA'" in RECOVERY, "PWA/Push menu is not merged")
require("display.textContent='O2Ring'" in RECOVERY, "display settings are not renamed to O2Ring")
require("[data-settings-panel=\"system\"]" in RECOVERY, "setup wizard is not anchored to one settings panel")
require("#focusViewBtn,#stackViewBtn,#o2rDailyBtn" in RECOVERY, "dashboard three-mode ownership is missing")
require("e.stopImmediatePropagation()" in RECOVERY, "legacy duplicate click handlers are not suppressed")
require("sleepmate-ui-recovered" in RECOVERY and "caches.delete" in RECOVERY, "stale PWA recovery is missing")
require("setInterval(" not in RECOVERY, "recovery controller must not poll the DOM")

for marker in (
    'smO2FocusDual',
    'smStackO2Dual',
    'smO2OverlaySelect',
    'smDashboardO2V532',
    'smO2TrendV3',
    'smNightO2Card',
    'hydrateReportO2',
    'smO2LiveCombinedCanvas',
):
    require(marker in O2, f"O2 feature regressed: {marker}")
require("setInterval(" not in O2, "O2 runtime must remain event-driven")

require('sm-v533-o2-settings' in RECOVERY_CSS, "O2Ring responsive settings CSS missing")
require('sm-v533-o2-hero' in RECOVERY_CSS, "compact Oximetria hero CSS missing")
require('#trendUsage,#trendEvents' in RECOVERY_CSS and 'filter:none' in RECOVERY_CSS, "bar-chart glow removal missing")

for worker, name in ((SW, 'live worker'), (BASE_SW, 'packaged worker')):
    require('frontend-v533.js' in worker and 'frontend-v533.css' in worker, f"{name} does not protect recovery assets")
    require('sleepmate-shell-v5.3.3' in worker, f"{name} is not on the 5.3.3 shell generation")
    require("client.navigate(client.url)" in worker, f"{name} cannot evict stale open clients")

require('function injectReopen()' in FIRST_RUN, "setup wizard reopen entry disappeared")
print('v5.3.3 frontend recovery contract OK')
