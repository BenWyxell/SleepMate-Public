from pathlib import Path

from cpap.version import API_VERSION, APP_VERSION, BUILD_CHANNEL

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v532_release_identity():
    assert APP_VERSION == "5.3.2"
    assert API_VERSION == 19
    assert BUILD_CHANNEL == "stable"
    assert read("RELEASE_NOTES_5_3_2.md").startswith("# SleepMate 5.3.2\n")


def test_v532_packaged_pwa_keeps_all_o2_runtime_assets_network_first():
    base = read("web/service-worker-v508-base.js")
    live = read("web/service-worker.js")
    assets = (
        "/sleepmate-aurora.css",
        "/sleepmate-v530.css",
        "/sleepmate-v530.js",
        "/o2ring.css",
        "/o2ring.js",
        "/o2ring-report-ui.js",
        "/o2ring-v532.css",
        "/o2ring-v532.js",
    )
    for asset in assets:
        assert asset in base
        assert asset in live
    assert "o2ring\\/(?:day|day-batch|trends)" in base
    assert "sleepmate-shell-v5.3.2-o2" in live


def test_v532_shell_does_not_activate_legacy_interval_polish():
    shell = read("cpap/v530_features.py")
    runtime = read("web/o2ring-v532.js")
    assert "o2ring-v532.js" in shell
    assert "o2ring-v532.css" in shell
    assert "o2ring-polish-core.js" not in shell
    assert "o2ring-polish-trends.js" not in shell
    assert "o2ring-polish-daily.js" not in shell
    assert "o2ring-polish-dashboard.js" not in shell
    assert "setInterval(" not in runtime


def test_v532_user_requested_ui_surfaces_are_present():
    runtime = read("web/o2ring-v532.js")
    css = read("web/o2ring-v532.css")
    for marker in (
        "switchDailyMode",
        "smO2FocusDual",
        "smStackO2Dual",
        "smO2OverlaySelect",
        "smNightO2Card",
        "smDashboardO2V532",
        "smO2TrendV3",
        "smO2QuickBar",
        "smO2DashLink",
        "SpO₂ + pulzus – élő",
        "Élő Oxi",
    ):
        assert marker in runtime
    assert "#trendUsage,#trendEvents{filter:none!important}" in css
    assert "sm-o2-settings-panel" in css


def test_v532_reports_use_batched_cpap_overlap_data():
    runtime = read("web/o2ring-v532.js")
    backend = read("cpap/o2ring_v532.py")
    assert "/api/o2ring/day-batch?days=" in runtime
    assert 'parsed.path == "/api/o2ring/day-batch"' in backend
    assert "service.daily(day, max_points=1)" in backend
    assert "td.colSpan=13" in runtime
