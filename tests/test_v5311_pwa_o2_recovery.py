from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_pwa_o2_runtime_has_one_deterministic_boot_path() -> None:
    source = read("web/sleepmate-v530.js")

    assert "scheduleO2Recovery" not in source
    assert "bindO2HydrationRecovery" not in source
    assert "await ensureO2Modules()" in source
    assert "await Promise.resolve(window.SleepMateO2Ring.install())" in source
    assert "installO2MasterPanel();hydrateO2Master()" in source


def test_pwa_frontend_never_deletes_release_cache_from_frozen_ui_version() -> None:
    source = read("web/frontend-v534.js")
    assert "enforceFrontendGeneration" not in source
    assert "caches.keys()" not in source
    assert "caches.delete" not in source
    assert "location.reload()" not in source
    assert "reg?.update?.()" not in source


def test_dashboard_oximetry_uses_same_day_trend_renderer_as_ahi() -> None:
    source = read("web/o2ring.js")
    draw_start = source.index("function drawDashboardO2Mini()")
    draw_end = source.index("function ensureDashboardO2Section()", draw_start)
    draw_body = source[draw_start:draw_end]
    refresh_start = source.index("async function refreshDashboardO2")
    refresh_end = source.index("async function loadRecordings", refresh_start)
    refresh_body = source[refresh_start:refresh_end]

    assert "drawTrendLine" in draw_body
    assert "chartDraw(" not in draw_body
    assert "bindChart(" not in draw_body
    assert "R.dashboardTrendRows=rows.map" in refresh_body
    assert "byDay=new Map" in refresh_body
    assert "spo2:s?(num(s.spo2_median)??num(s.spo2_average)):null" in refresh_body
    assert "heart_rate:s?(num(s.heart_rate_median)??num(s.heart_rate_average)):null" in refresh_body
