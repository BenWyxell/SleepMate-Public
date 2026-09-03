from pathlib import Path

from cpap.oximetry import OximetrySample, summarize_samples

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT / path).read_text(encoding="utf-8")

def test_v535_o2_summary_exposes_requested_median_min_max():
    rows = [
        OximetrySample(timestamp=0, spo2=95, heart_rate=55),
        OximetrySample(timestamp=1, spo2=97, heart_rate=65),
        OximetrySample(timestamp=2, spo2=99, heart_rate=75),
    ]
    s = summarize_samples(rows, start_ts=0, end_ts=3)
    assert s.spo2_median == 97
    assert s.spo2_minimum == 95
    assert s.spo2_maximum == 99
    assert s.heart_rate_median == 65
    assert s.heart_rate_minimum == 55
    assert s.heart_rate_maximum == 75

def test_v535_daily_cards_use_matched_o2ring_medians():
    js = read("web/o2ring.js")
    assert "function hydrateDailyO2Metrics()" in js
    assert "s.spo2_median" in js
    assert "s.heart_rate_median" in js

def test_v535_latest_sleep_card_is_duration_not_session_status():
    front = read("web/frontend-v534.js")
    html = read("web/index.html")
    core = read("web/app-core.js")
    spec = read("build/windows/SleepMate.spec")
    assert "latest?.summary||latest" in front
    assert "latestDuration(summary)" in front
    assert "<label>Alvásidő</label>" in html
    assert "$('#latestStatus').textContent=secondsToHM(latest.therapy_seconds||0)" in core
    assert "$('#latestStatus').textContent='Befejezve'" not in core
    assert "$('#latestStatus').textContent='Befejezve'" not in spec

def test_v535_reports_and_night_card_contract():
    js = read("web/o2ring.js")
    css = read("web/o2ring-v534.css")
    assert "function hydrateReportDailyStats(day)" in js
    assert "s.spo2_maximum" in js
    assert "s.heart_rate_maximum" in js
    assert "list=id('nightEvalList')" in js
    assert "Medián • CPAP-idővel átfedő O2Ring adat" in js
    for forbidden in ("Minimum <b>", "T90 <b>", "ODI3 / ODI4 <b>"):
        assert forbidden not in js[js.index("function renderNightCard"):js.index("function drawDashboardO2Mini")]
    assert ".sm-report-days-compact" in css


def test_v535_focus_uses_normal_mini_and_hero_chart_engine():
    js=read("web/o2ring.js")
    assert "O2_FOCUS_DEFS" in js
    assert "card.className='overview-card sm-o2-focus-mini'" in js
    assert "card.onclick=()=>selectSignal(d.key)" in js
    assert "function o2CoreSignal(key)" in js
    focus=js[js.index("const O2_FOCUS_DEFS"):js.index("function ensureStackO2")]
    assert "smO2FocusDual" not in focus

def test_v535_o2_selection_line_weight_overlay_and_dashboard_contract():
    js=read("web/o2ring.js"); css=read("web/o2ring-v534.css")
    assert "drag?.mode==='zoom'" in js and "ctx.fillStyle='rgba(85,183,255,.16)'" in js
    assert "opts.lineWidth??1.15" in js
    assert "COLORS.spo2,1.05" in js and "COLORS.hr,1.05" in js
    assert '<option value="off">Alapnézet</option>' in js
    assert "scheduleOverlayRender.__smO2" in js
    assert "sm-has-o2-overlay" in js and "sm-has-o2-overlay" in css
    assert "function ensureDashboardO2Section()" in js
    assert "seg.length===1" in js


def test_v535_oximetry_navigation_is_one_toolbar_and_state_is_not_a_card():
    js=read("web/o2ring.js"); css=read("web/o2ring-v534.css")
    page=js[js.index("function installPage"):js.index("function closeMobileO2Drawer")]
    assert 'id="o2rSyncNowTop"' in page
    assert page.index('id="o2rSyncNowTop"') < page.index('data-o2r-tab="live"') < page.index('data-o2r-tab="recordings"') < page.index('data-o2r-tab="trends"')
    assert 'class="o2r-tabs"' not in page
    assert 'class="panel o2r-live-card state"' not in page
    assert 'class="o2r-search-state"' in page
    assert 'id="o2rLiveState"' in page and 'id="o2rLiveSignal"' in page
    assert '.o2r-search-state' in css
