from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def daily_css() -> str:
    css = read("web/dashboard-pwa-v5312.css")
    assert "/* Phone PWA daily detail bento extension */" in css
    return css.split("/* Phone PWA daily detail bento extension */", 1)[1]


def test_phone_pwa_daily_dashboard_is_compact_two_column_bento():
    css = daily_css()
    for selector in ("#dashboardDailyView .daily-core-grid", "#dashboardDailyView .therapy-vitals", "#dashboardDailyView .night-evaluation-full .night-eval-list", "#dashboardDailyView .full-width-therapy .daily-therapy-grid", "#dashboardDailyView .overview-grid"):
        assert selector in css
    assert css.count("grid-template-columns:repeat(2,minmax(0,1fr))!important") >= 5


def test_daily_bento_preserves_all_existing_data_surfaces():
    css = daily_css()
    assert "display:none" not in css
    assert "visibility:hidden" not in css
    assert "content-visibility:hidden" not in css
    for surface in ("daily-overview-panel", "night-evaluation-full", "compact-assessment", "full-width-therapy", "hero-panel", "overview-grid"):
        assert surface in css


def test_daily_bento_is_phone_pwa_scoped():
    css = daily_css()
    assert css.count("html.sm-phone-pwa #page-dashboard #dashboardDailyView") >= 35
    assert "#dashboardDailyView .daily-core-grid" in css
    assert "#dashboardDailyView .therapy-vitals" in css
