from __future__ import annotations

from pathlib import Path

from cpap.v530_features import _patch_frontend_v534, _patch_o2ring, _patch_sleepmate_v530


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_pwa_o2_runtime_recovers_after_failed_dynamic_script_load() -> None:
    source = read("web/sleepmate-v530.js")
    patched = _patch_sleepmate_v530(source)

    assert "existing.remove()" in patched
    assert "s.onerror=()=>{s.remove()" in patched
    assert "function o2RuntimeMissing()" in patched
    assert "scheduleO2Recovery()" in patched
    assert "if(!resolvedO2()||o2RuntimeMissing())" in patched
    assert "installO2MasterPanel();hydrateO2Master()" in patched
    assert "installO2Master:installO2MasterPanel" in patched


def test_pwa_frontend_never_deletes_release_cache_from_frozen_ui_version() -> None:
    source = read("web/frontend-v534.js")
    patched = _patch_frontend_v534(source)

    start = patched.index("async function enforceFrontendGeneration()")
    end = patched.index("function waitForDynamicSettings()", start)
    body = patched[start:end]

    assert "caches.keys()" not in body
    assert "caches.delete" not in body
    assert "location.reload()" not in body
    assert "reg?.update?.()" in body


def test_dashboard_oximetry_uses_same_day_trend_renderer_as_ahi() -> None:
    source = read("web/o2ring.js")
    patched = _patch_o2ring(source)

    draw_start = patched.index("function drawDashboardO2Mini()")
    draw_end = patched.index("function ensureDashboardO2Section()", draw_start)
    draw_body = patched[draw_start:draw_end]
    refresh_start = patched.index("async function refreshDashboardO2")
    refresh_end = patched.index("async function loadRecordings", refresh_start)
    refresh_body = patched[refresh_start:refresh_end]

    assert "drawTrendLine" in draw_body
    assert "chartDraw(" not in draw_body
    assert "bindChart(" not in draw_body
    assert "R.dashboardTrendRows=rows.map" in refresh_body
    assert "byDay=new Map" in refresh_body
    assert "spo2:s?(num(s.spo2_median)??num(s.spo2_average)):null" in refresh_body
    assert "heart_rate:s?(num(s.heart_rate_median)??num(s.heart_rate_average)):null" in refresh_body
