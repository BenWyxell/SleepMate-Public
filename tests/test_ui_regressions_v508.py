from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

def test_faq_search_panel_stays_in_document_flow():
    css = text("web/style.css")
    assert ".faq-search-panel{position:relative;top:auto" in css
    assert ".faq-search-panel{position:sticky" not in css

def test_dashboard_comparison_has_real_delete_action():
    html = text("web/index.html")
    js = text("web/app.js")
    assert 'id="clearComparison"' in html
    assert "$('#clearComparison').onclick=clearComparison" in js
    assert "state.comparison=null" in js
    assert "panel?.classList.add('hidden')" in js

def test_dashboard_bar_charts_are_the_last_pair():
    html = text("web/index.html")
    ids = ["trendAhi", "trendResp", "trendPressure", "trendLeak", "trendUsage", "trendEvents"]
    positions = [html.index(f'id="{item}"') for item in ids]
    assert positions == sorted(positions)
    assert html.count('class="panel trend-card trend-bar-card"') == 2

def test_windows_notifications_use_sleepmate_identity_and_icon():
    tray = text("sleepmate_tray.pyw")
    assert 'APP_USER_MODEL_ID = "SleepMate.Desktop"' in tray
    assert "SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)" in tray
    assert 'ICON_PATH = BASE / "SleepMate.ico"' in tray
    assert 'self.pystray.Icon("SleepMate", image, "SleepMate", menu)' in tray

def test_startup_has_one_web_loader_and_second_launch_signals_existing_tray():
    html = text("web/index.html")
    js = text("web/app.js")
    tray = text("sleepmate_tray.pyw")
    main = text("sleepmate_main.py")
    assert html.count('id="startupSplash"') == 1
    assert "window.__sleepmateBootStarted" in js
    assert "OPEN_REQUEST_FILE" in tray
    assert "monitor_open_requests" in tray
    assert "OPEN_REQUEST_FILE.write_text" in tray
    assert "--startup-splash" not in main
