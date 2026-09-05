from __future__ import annotations

from pathlib import Path

from cpap.v530_features import _patch_o2ring


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_o2_cards_use_dashboard_trend_layout() -> None:
    source = (ROOT / "web" / "o2ring.js").read_text(encoding="utf-8")
    patched = _patch_o2ring(source)

    start = patched.index("function ensureDashboardO2Section()")
    end = patched.index("function dayTrendTs", start)
    body = patched[start:end]

    assert 'class="trend-grid sm-dashboard-o2-trends"' in body
    assert body.count('class="panel trend-card"') == 2
    assert '<canvas id="smDashO2Trend"></canvas>' in body
    assert '<canvas id="smDashHrTrend"></canvas>' in body
    assert 'sm-o2-chart-wrap' not in body
    assert 'sm-dashboard-o2-mini' not in body
