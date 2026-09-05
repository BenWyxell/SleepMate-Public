from pathlib import Path


def text(path):
    return Path(path).read_text(encoding="utf-8")


def test_packaged_dashboard_pwa_css_is_build_versioned():
    spec = text("build/windows/SleepMate.spec")
    assert "dashboard_pwa_link = f'<link rel=\"stylesheet\" href=\"/dashboard-pwa-v5312.css?v={FRONTEND_ID}\">'" in spec
    assert "dashboard-pwa-v5312.css" in spec
    assert "asset + f'?v={FRONTEND_ID}'" in spec
    assert "/dashboard-pwa-v5312.css?v=2" in text("web/service-worker-v508-base.js")
    assert "/dashboard-pwa-v5312.css?v=2" in text("web/service-worker.js")


def test_daily_o2_has_runtime_independent_api_fallback():
    spec = text("build/windows/SleepMate.spec")
    assert "window.SleepMateO2Ring?.getDailySummary" in spec
    assert "/api/o2ring/day?day=${encodeURIComponent(code)}&max_points=1" in spec
    assert "for(let attempt=0;attempt<3;attempt++)" in spec


def test_daily_bento_css_is_still_present_and_phone_scoped():
    css = text("web/dashboard-pwa-v5312.css")
    assert "/* Phone PWA daily detail bento extension */" in css
    assert "html.sm-phone-pwa #page-dashboard #dashboardDailyView .daily-core-grid" in css
    assert "grid-template-columns:repeat(2,minmax(0,1fr))!important" in css
