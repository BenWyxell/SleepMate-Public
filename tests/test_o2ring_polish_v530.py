from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(name: str) -> str:
    return (ROOT / "web" / name).read_text(encoding="utf-8")


def test_polish_assets_are_wired_into_v530_shell():
    feature = (ROOT / "cpap" / "v530_features.py").read_text(encoding="utf-8")
    assert "o2ring-polish.css" in feature
    assert "sm-o2-polish-inline-css" in feature
    for name in (
        "o2ring-polish-core.js",
        "o2ring-polish-trends.js",
        "o2ring-polish-daily.js",
        "o2ring-polish-dashboard.js",
    ):
        assert name in feature


def test_o2ring_polish_contains_requested_ui_contracts():
    core = text("o2ring-polish-core.js")
    trends = text("o2ring-polish-trends.js")
    daily = text("o2ring-polish-daily.js")
    dash = text("o2ring-polish-dashboard.js")
    assert "SpO₂ + pulzus – élő" in core
    assert "o2rTrendV2" in trends
    assert "Vissza a grafikonokhoz" in daily
    assert all(x in daily for x in ("smStackSpo2", "smStackHr", "smStackMixed"))
    assert "Oximetriai összegzés" in dash
    assert "sm-report-o2-table" in dash
    assert "SpO₂ átlag" in dash
    assert "smO2DeviceQuick" in core
    assert "o2rGoDashboard" in core
    assert "PWA" in core


def test_connect_buttons_hide_after_successful_connection():
    core = text("o2ring-polish-core.js")
    assert "classList.toggle('hidden',on)" in core
    assert "o2rConnectNow" in core
    assert "o2rConnectSettings" in core
    assert "smO2QuickConnect" in core


def test_dashboard_and_report_use_cpap_overlap_endpoint():
    core = text("o2ring-polish-core.js")
    dash = text("o2ring-polish-dashboard.js")
    assert "/api/o2ring/day?day=${day}&max_points=${full?12000:1}" in core
    assert "CPAP-használattal ténylegesen átfedő O2Ring-adatok" in dash
    assert "td.colSpan=13" in dash


def test_aurora_bar_palette_replaces_legacy_dashboard_colors():
    dash = text("o2ring-polish-dashboard.js")
    for color in ("#7b8cff", "#a06bff", "#43e7c6", "#6fd6ff", "#49e3bd"):
        assert color in dash