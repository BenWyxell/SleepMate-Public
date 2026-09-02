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
    spec = read("build/windows/SleepMate.spec")
    assert "latest?.summary||latest" in front
    assert "latestDuration(summary)" in front
    assert "<label>Alvásidő</label>" in html
    assert "secondsToHM(latest.therapy_seconds||0)" in spec

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
