from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_dashboard_trend_axis_keeps_last_label_without_overlap() -> None:
    frontend = read("web/frontend-v534.js")

    assert "installAdaptiveDashboardTrendAxis" in frontend
    assert "adaptiveTrendDaySet" in frontend
    assert "b.left<previous+8" in frontend
    assert "b.right>lastBox.left-8" in frontend
    assert "keep.add(String(rows[last]?.day??''))" in frontend


def test_all_dashboard_trend_renderers_share_the_adaptive_axis_guard() -> None:
    frontend = read("web/frontend-v534.js")

    assert "wrap('drawTrendLine','line')" in frontend
    assert "wrap('drawUsageBars','bar')" in frontend
    assert "wrap('drawEventBars','bar')" in frontend
    assert "window.trendDateLabel=function(row)" in frontend


def test_trend_axis_fix_does_not_change_chart_data_or_series_logic() -> None:
    frontend = read("web/frontend-v534.js")

    assert "const n=rows.length,step=Math.max(1,Math.ceil(n/6))" in frontend
    assert "adaptiveTrendAxisDays=adaptiveTrendDaySet(canvas,rows,kind)" in frontend
    assert "return original.call(this,canvas,rows,...rest)" in frontend
