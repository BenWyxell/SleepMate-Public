from __future__ import annotations

from pathlib import Path

from cpap.o2ring_runtime_v534 import _extract_day_codes
from cpap.version import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_acceptance_p0_single_frontend_owner_and_stale_pwa_recovery():
    shell = read("cpap/v530_features.py")
    sw = read("web/service-worker.js")
    base = read("web/service-worker-v508-base.js")
    assert APP_VERSION == "5.3.9"
    assert 'UI_VERSION = "5.3.4"' in shell
    assert "o2ring-v532.js" not in shell
    assert "frontend-v533.js" not in shell
    assert "frontend-v534.js" in shell
    assert "o2ring-v534.css" in shell
    for worker in (sw, base):
        assert "sleepmate-shell-v5.3.9-o2-hydration-1" in worker
        assert "sleepmate-api-v5.3.9-refactor" in worker
        assert "/o2ring.js" in worker
        assert "/frontend-v534.js?v=5.3.4" in worker
        assert "/o2ring-v534.css?v=5.3.4" in worker
        assert "/o2ring-v532.js" not in worker
        assert "/frontend-v533.js" not in worker
        assert "X-SleepMate-UI-Version" in worker
        assert "SLEEPMATE_SHELL_READY" in worker
        assert "event.respondWith(navigationFallback(req))" in worker
        assert "event.respondWith(codeNetworkFirst(req))" in worker


def test_acceptance_p0_dashboard_three_modes_and_route_lifecycle_are_single_owned():
    js = read("web/o2ring.js")
    for marker in (
        "#focusViewBtn,#stackViewBtn,#o2rDailyBtn",
        "if(o)o.textContent='Oximetria'",
        "function switchMode(mode)",
        "clearCoreInteractions();clearO2Interactions();",
        "R.modeViews",
        "function clearO2Interactions()",
        "chartControllers:new WeakMap()",
        "#sidebar [data-page=\"oximetry\"]",
        "stopImmediatePropagation();openOximetry(R.pageTab||'live')",
        "if(location.hash!=='#oximetry')history.pushState",
    ):
        assert marker in js
    assert "Vissza" not in js
    assert "setInterval(" not in js


def test_acceptance_p0_live_o2_only_paints_when_visible_and_batch_refills_on_return():
    js = read("web/o2ring.js")
    stream = read("cpap/o2ring_stream.py")
    for marker in (
        "document.visibilityState==='visible'",
        "function o2PageVisible()",
        "function updateLiveLifecycle()",
        "function closeLiveStream()",
        "async function resumeLive()",
        "R.liveResumePromise",
        "await refillLive(since)",
        "if(o2PageVisible())openLiveStream()",
        "/api/o2ring/live-buffer?since=",
        "R.liveRaf=requestAnimationFrame(()=>{R.liveRaf=0;drawLive()})",
    ):
        assert marker in js
    assert "function o2PageVisible(){return document.visibilityState==='visible'&&location.hash.startsWith('#oximetry')" in js
    assert "class _LiveBuffer" in stream
    assert 'path == "/api/o2ring/live-buffer"' in stream
    assert "service.manager.add_listener(BUFFER.append_snapshot)" in stream


def test_acceptance_p1_all_o2_charts_share_exact_hover_crosshair_zoom_pan_contract():
    js = read("web/o2ring.js")
    for marker in (
        "hour:'2-digit',minute:'2-digit',second:'2-digit'",
        "function nearest(rows,t)",
        "function bindChart(c,",
        "function clampChartRange",
        "ctl.pointers",
        "ctl.pinch",
        "pointerdown",
        "pointermove",
        "pointercancel",
        "dblclick",
        "e.pointerType==='touch'||e.shiftKey?'pan':'zoom'",
        "setHover(ctl.syncGroup,t)",
        "syncGroup:'live'",
        "syncGroup:'daily-o2'",
        "syncGroup:'stack-o2'",
        "syncGroup:'recording'",
        "syncGroup:'trends'",
        "syncGroup:'dash-o2'",
    ):
        assert marker in js
    assert "medianDelta(rows)*3.2" in js
    assert "makeSegments" in js


def test_acceptance_p1_sleepsync_and_recording_invalidation_are_event_driven_and_targeted():
    backend = read("cpap/o2ring_runtime_v534.py")
    frontend = read("web/o2ring.js")
    for marker in (
        '"recording-added"',
        '"sleepsync-completed"',
        "sync._sync_job = types.MethodType(wrapped, sync)",
        'parsed.path == "/api/o2ring/events"',
        "EventSource(`/api/o2ring/events?after=${R.eventSeq}`)",
        "invalidateDays(x.days||[])",
        "R.batchCache.clear()",
    ):
        assert marker in backend or marker in frontend
    assert "setInterval(" not in backend
    changed = {
        "import": {
            "changed_days": ["20260901", "20260902"],
            "changed_files": ["DATALOG/20260902/20260902_001_PLD.edf"],
        }
    }
    assert _extract_day_codes(changed) == {"20260901", "20260902"}


def test_acceptance_p1_session_matching_is_timestamp_overlap_deterministic_and_deduplicated():
    backend = read("cpap/o2ring_runtime_v534.py")
    domain = read("cpap/oximetry.py")
    for marker in (
        "match_recording_to_cpap(",
        "-float(item[0].overlap_seconds)",
        "shared > 30.0",
        "selected.setdefault(key, sample)",
        "key = int(round(ts * 1000.0))",
    ):
        assert marker in backend
    assert "overlap_start = max(rec_start, cpap_start)" in domain
    assert "overlap_end = min(rec_end, cpap_end)" in domain
    assert "minimum_overlap_seconds" in domain


def test_acceptance_p2_focus_stack_daily_dashboard_night_and_report_o2_surfaces_exist():
    js = read("web/o2ring.js")
    for marker in (
        "O2_FOCUS_DEFS",
        "mini-${d.key}",
        "o2CoreSignal",
        "smStackO2Spo2",
        "smStackO2Hr",
        "smStackO2Dual",
        "o2rDaySpo2Chart",
        "o2rDayHrChart",
        "o2rDayDual",
        "smDashboardO2V534",
        "smDashO2Trend",
        "smDashHrTrend",
        "smNightO2Card",
        "SpO₂ átlag",
        "SpO₂ min.",
        "Pulzus átlag",
        "ODI3 / ODI4",
    ):
        assert marker in js


def test_acceptance_p2_overlay_is_per_chart_timestamp_aligned_gap_aware_and_secondary_scaled():
    js = read("web/o2ring.js")
    css = read("web/o2ring-v534.css")
    for marker in (
        'value="off"',
        'value="spo2"',
        'value="hr"',
        'value="both"',
        "sm-o2-overlay:${key}",
        "e.currentTarget.dataset.signal||key",
        "makeSegments(rs,'spo2'",
        "makeSegments(rs,'heart_rate'",
        "medianDelta(rs)*3.2",
        "function drawOverlayScaleLabels",
        "O₂ 100%",
        "O₂ 75%",
        "HR ${hrHi}",
        "HR ${hrLo}",
        "clock(r.timestamp)",
    ):
        assert marker in js
    assert "right:-42px!important" in css
    assert "width:calc(100% + 42px)!important" in css


def test_acceptance_p2_dashboard_bars_loading_and_palette_are_consistent():
    js = read("web/o2ring.js")
    front = read("web/frontend-v534.js")
    css = read("web/o2ring-v534.css")
    assert "shadowBlur" not in js
    assert "Object.assign(TREND_EVENT_COLORS,EVENT_COLORS)" in js
    for color in ("#55d8ff", "#a98bff", "#48dfb9", "#ef86c8"):
        assert color in js
    assert "#trendUsage,#trendEvents{filter:none!important}" in css
    assert "function fixLatestLoading()" in front
    assert "function syncLatestSessionCard()" in front
    assert "latest?.summary||latest" in front
    assert "latestDuration(summary)" in front
    assert "summary.sessions" in front
    assert "status.textContent='—'" in front
    assert "Befejezve" not in front


def test_acceptance_settings_pwa_and_setup_wizard_are_source_level_single_and_responsive():
    pwa = read("web/sleepmate-v530.js")
    front = read("web/frontend-v534.js")
    first = read("web/first-run.js")
    css = read("web/o2ring-v534.css")
    assert "push.textContent='PWA'" in pwa
    assert "legacy?.remove()" in pwa
    assert "dataset.settingsTab='pwa'" not in pwa
    assert "panel.removeAttribute('data-settings-panel')" in pwa
    assert "tab.textContent='O2Ring'" in front
    assert "o.textContent='O2Ring'" in front
    assert "saveQueued" in front and "saveBusy" in front
    assert "id('smO2AutoMatch').onchange=saveAdvancedO2Settings" in front
    assert "Élő O₂ monitor" in front
    assert "for(const x of all)if(x!==box)x.remove()" in first
    assert "system.appendChild(box)" in first
    assert "setInterval(()=>{tries++" not in first
    assert ".sm-o2-advanced-grid,.sm-o2-device-grid{display:grid" in css
    assert "@media(max-width:900px)" in css
    assert "@media(max-width:700px)" in css
    assert "@media(max-width:600px)" in css


def test_acceptance_active_frontend_avoids_aggressive_polling_and_duplicate_runtime_layers():
    o2 = read("web/o2ring.js")
    front = read("web/frontend-v534.js")
    shell = read("cpap/v530_features.py")
    assert "setInterval(" not in o2
    assert "setInterval(" not in front
    assert "frontend-v533.js" not in shell
    assert "o2ring-v532.js" not in shell
    assert "o2ring-polish-core.js" not in shell
    assert "install_o2ring_runtime_v534" in shell


def test_acceptance_o2_trends_live_handoff_and_hover_redraw_are_gap_safe():
    js = read("web/o2ring.js")
    for marker in (
        "function chartGap(rows,trendGap=false)",
        "medianDelta(rows,null)*3.2",
        "trendGap:true",
        "hoverRaf:new Map()",
        "function scheduleGroupRedraw(group)",
        "const seen=new Set()",
        "!seen.has(fn)",
        "R.hoverRaf.delete(group)",
        "const since=R.live.at(-1)?.timestamp||0",
        "openLiveStream();await refillLive(since)",
        "liveAbort:null",
        "new AbortController()",
        "signal:ctl.signal",
        "R.liveAbort.abort()",
        "if(R.liveResumePromise===work)",
        "function closeMobileO2Drawer()",
    ):
        assert marker in js
    assert js.count("trendGap:true") >= 2
