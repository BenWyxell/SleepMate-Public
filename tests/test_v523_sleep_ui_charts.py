from __future__ import annotations

from datetime import date
from pathlib import Path

from cpap.sleep_analysis_v522 import _range_from_period


ROOT = Path(__file__).resolve().parents[1]
SLEEP_JS = ROOT / "web" / "sleepmate-sleep-v523.js"
CHART_JS = ROOT / "web" / "sleepmate-chart-v523.js"
SHELL = ROOT / "cpap" / "sleep_analysis_v522.py"


def test_sleep_defaults_to_full_history_everywhere():
    sleep = SLEEP_JS.read_text(encoding="utf-8")
    shell = SHELL.read_text(encoding="utf-8")
    assert "period:'all'" in sleep
    assert '<option value="all" selected>Teljes időszak</option>' in sleep
    assert "period: str = \"all\"" in shell
    assert 'str(period or "all")' in shell


def test_sleep_period_order_and_two_level_view_contract():
    text = SLEEP_JS.read_text(encoding="utf-8")
    labels = ["Utolsó 7 nap", "Utolsó 30 nap", "Teljes időszak", "Egyedi időszak", "Előző 7 nap", "Előző 30 nap"]
    positions = [text.index(label) for label in labels]
    assert positions == sorted(positions)
    assert "Egyszerű nézet" in text
    assert "Részletes napló" in text
    assert "mode:'simple'" in text
    assert "data-simple-day" in text
    assert "data-journal-day" in text


def test_multiple_naps_show_total_and_count_in_daily_table():
    text = SLEEP_JS.read_text(encoding="utf-8")
    assert "fmt(r.nap_seconds)" in text
    assert "r.nap_count" in text
    assert "${r.nap_count}×" in text
    assert "(r.blocks||[]).length" in text


def test_rolling_previous_periods_stay_relative_to_latest_sleep_day():
    rows = [{"date": "2026-08-01"}, {"date": "2026-08-28"}]
    start, end, label = _range_from_period(rows, "prev7")
    assert (start, end, label) == (date(2026, 8, 15), date(2026, 8, 21), "Előző 7 nap")
    start, end, label = _range_from_period(rows, "prev30")
    assert (start, end, label) == (date(2026, 6, 30), date(2026, 7, 29), "Előző 30 nap")


def test_chart_curve_interpolates_through_markers_and_tooltips_are_above_touch():
    text = CHART_JS.read_text(encoding="utf-8")
    assert "ctx.bezierCurveTo(cp1x,cp1y,cp2x,cp2y,p2.x,p2.y)" in text
    assert "top=cy-tip.offsetHeight-gap" in text
    assert "by=y-height-gap" in text
    sleep = SLEEP_JS.read_text(encoding="utf-8")
    assert "top=e.clientY-tip.offsetHeight-gap" in sleep


def test_shell_loads_only_current_sleep_and_chart_patches():
    worker = (ROOT / "web" / "service-worker.js").read_text(encoding="utf-8")
    assert "sleepmate-sleep-v523.js?v=5.2.6" in worker
    assert "sleepmate-chart-v523.js?v=5.2.14" in worker
    assert "sleepmate-sleep-v522.js" not in worker
