from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_pwa_dashboard_stylesheet_is_loaded_from_app_bootstrap() -> None:
    app = read("web/app.js")
    assert "dashboard-pwa-v5312.css?v=1" in app
    assert "dashboardStyle.dataset.sleepmateDashboardPwa='1'" in app
    assert "link[data-sleepmate-dashboard-pwa=\"1\"]" in app


def test_pwa_dashboard_uses_compact_bento_grids_without_hiding_data() -> None:
    css = read("web/dashboard-pwa-v5312.css")

    assert "html.sm-phone-pwa #page-dashboard" in css
    assert ".latest-sleep-cards" in css
    assert ".aggregate-cards" in css
    assert ".delta-grid" in css
    assert ".sm-dashboard-o2-cards" in css
    assert "grid-template-columns:repeat(2,minmax(0,1fr))!important" in css
    assert ".sm-dashboard-o2-trends" in css
    assert "height:168px!important" in css

    # The redesign is allowed to rearrange and compact the Dashboard, but not to
    # make any of its metrics/trends disappear behind a CSS visibility shortcut.
    assert "display:none" not in css
    assert "visibility:hidden" not in css
    assert "content-visibility:hidden" not in css


def test_pwa_shell_precaches_dashboard_style() -> None:
    for path in ("web/service-worker.js", "web/service-worker-v508-base.js"):
        source = read(path)
        assert "/dashboard-pwa-v5312.css?v=1" in source
        assert "/dashboard-pwa-v5312.css" in source
