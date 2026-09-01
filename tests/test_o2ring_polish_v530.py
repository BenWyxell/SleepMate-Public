from pathlib import Path

from cpap.o2ring_v532 import _normalize_days
from cpap.ui_preferences_v530 import PWA_NAV_ALLOWED

ROOT = Path(__file__).resolve().parents[1]


def text(name: str) -> str:
    return (ROOT / "web" / name).read_text(encoding="utf-8")


def test_v532_runtime_is_the_only_active_post_release_o2_polish():
    feature = (ROOT / "cpap" / "v530_features.py").read_text(encoding="utf-8")
    assert "o2ring-v532.css" in feature
    assert "o2ring-v532.js" in feature
    assert "sm-o2-v532-inline-css" in feature
    assert "sm-o2-v532-inline" in feature
    for legacy in (
        "o2ring-polish-core.js",
        "o2ring-polish-trends.js",
        "o2ring-polish-daily.js",
        "o2ring-polish-dashboard.js",
    ):
        assert legacy not in feature


def test_v532_runtime_contains_requested_dashboard_and_oximetry_contracts():
    js = text("o2ring-v532.js")
    for marker in (
        "SpO₂ + pulzus – élő",
        "smO2FocusSpo2",
        "smO2FocusHr",
        "smO2FocusDual",
        "smStackO2Spo2",
        "smStackO2Hr",
        "smStackO2Dual",
        "switchDailyMode",
        "smO2OverlaySelect",
        "Oximetriai összegzés",
        "smNightO2Card",
        "data-sm-o2-col",
        "SpO₂ átlag",
        "smO2QuickConnect",
        "smO2DashLink",
        "smO2TrendV3",
    ):
        assert marker in js
    assert "setInterval(" not in js


def test_connect_buttons_hide_when_ring_is_connected():
    js = text("o2ring-v532.js")
    assert "classList.toggle('hidden',connected)" in js
    assert "o2rConnectNow" in js
    assert "o2rConnectSettings" in js
    assert "smO2QuickConnect" in js


def test_dashboard_and_reports_use_batch_overlap_endpoint():
    js = text("o2ring-v532.js")
    backend = (ROOT / "cpap" / "o2ring_v532.py").read_text(encoding="utf-8")
    assert "/api/o2ring/day-batch?days=" in js
    assert 'parsed.path == "/api/o2ring/day-batch"' in backend
    assert "service.daily(day, max_points=1)" in backend
    assert "td.colSpan=13" in js


def test_o2ring_settings_and_pwa_contracts():
    js = text("o2ring-v532.js")
    css = text("o2ring-v532.css")
    assert "tab.textContent='O2Ring'" in js
    assert "sm-o2-settings-panel" in css
    assert "saveQueued" in js and "saveRunning" in js
    assert "oximetry_live" in PWA_NAV_ALLOWED
    assert "Élő Oxi" in js


def test_aurora_bar_palette_is_crisp_and_consistent():
    js = text("o2ring-v532.js")
    css = text("o2ring-v532.css")
    for color in ("#55c7ff", "#9a7cff", "#48e1b9", "#ef86c8"):
        assert color in js
    assert "#trendUsage,#trendEvents{filter:none!important}" in css
    assert "recolorTrendTip" in js


def test_batch_day_normalization_is_bounded_and_deduplicated():
    values = ["2026-09-01", "20260901", "bad", "20260902"]
    assert _normalize_days(",".join(values)) == ["20260901", "20260902"]
    many = ",".join(f"2026{m:02d}{d:02d}" for m in range(1, 13) for d in range(1, 29))
    assert len(_normalize_days(many)) == 120
