from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web" / "app-core.js").read_text(encoding="utf-8")
HTML = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "web" / "style.css").read_text(encoding="utf-8")
SW = (ROOT / "web" / "service-worker.js").read_text(encoding="utf-8")
MANIFEST = (ROOT / "web" / "manifest.webmanifest").read_text(encoding="utf-8")
BACKEND = (ROOT / "app.py").read_text(encoding="utf-8")


def test_pwa_only_bottom_navigation_and_no_duplicate_quick_view():
    assert 'id="mobileBottomNav"' in HTML
    assert 'id="mobileQuickView"' not in HTML
    assert 'id="pullRefreshIndicator"' in HTML
    assert "pwa-standalone" in CSS
    for label in ("Dashboard", "Napok", "Diagrammok", "Luna &amp; Milo", "Egyéb"):
        assert label in HTML
    assert "setupPullToRefresh()" in APP
    assert "setupDailySwipe()" in APP
    assert 'id="daySwipeCue"' in HTML


def test_daily_page_survives_optional_endpoint_failures():
    assert "Promise.allSettled" in APP
    assert "const s=await api(`/api/day/${day}`)" in APP
    assert "Napi kiegészítő adat" in APP


def test_touch_charts_support_pinch_pan_doubletap_and_scroll_cleanup():
    assert "pointerType==='touch'" in APP
    assert "handleHeroPinch" in APP
    assert "moveTouchPinch" in APP
    assert "panChartTouch" in APP
    assert "handleChartDoubleTap" in APP
    assert "shareCurrentDay" in APP
    assert "navigator.share" in APP
    compact = CSS.replace(" ", "")
    assert "touch-action:none" in compact
    assert "touch-action:pan-y" in compact
    assert "clearTrendHover()" in APP


def test_pwa_offline_and_real_web_push_present():
    assert "X-SleepMate-Offline" in APP
    assert "X-SleepMate-Offline" in SW
    assert "API_CACHE" in SW
    assert "navigationFallback" in SW
    assert "addEventListener('push'" in SW
    assert "warmOfflineRecentDays" in APP
    assert "Notification.requestPermission" in APP
    assert "pushManager.subscribe" in APP
    assert 'data-settings-tab="push"' in HTML
    assert 'id="pushEnableButton"' in HTML
    assert '"/api/push/subscribe"' in BACKEND


def test_friendly_error_ui_and_status_present():
    assert 'id="errorTitle"' in HTML
    assert 'id="errorTechnical"' in HTML
    assert "friendlyApiError" in APP
    assert 'id="pwaStatusServer"' in HTML
    assert 'id="pwaStatusOffline"' in HTML


def test_manifest_display_override_without_os_shortcuts():
    assert '"display_override"' in MANIFEST
    assert '"shortcuts"' not in MANIFEST
