from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from cpap.o2ring_runtime_v534 import _EventHub, _daily_v534, _extract_day_codes, _recent_day_codes
from cpap.version import API_VERSION, APP_VERSION, BUILD_CHANNEL

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def sample(ts: float, spo2: int = 96, hr: int = 65):
    return {"timestamp": ts, "spo2": spo2, "heart_rate": hr, "valid": True}


def recording(rid: str, start: datetime, end: datetime, samples: list[dict]):
    return {
        "recording_id": rid,
        "source_name": f"{rid}.vld",
        "start_ts": start.timestamp(),
        "end_ts": end.timestamp(),
        "samples": samples,
    }


def fake_service(recordings: list[dict], start: datetime, end: datetime, *, auto_match: bool = True):
    session = SimpleNamespace(start=start, end=end)
    dataset = SimpleNamespace(sessions=lambda _day: [session])
    handler = SimpleNamespace(dataset=dataset)
    return SimpleNamespace(
        app=SimpleNamespace(Handler=handler),
        store=SimpleNamespace(list_recordings=lambda: recordings),
        settings=lambda: {"o2ring_clock_offset_seconds": 0.0, "o2ring_auto_match": auto_match},
    )


def test_v534_release_identity_and_single_active_frontend_owner():
    shell = read("cpap/v530_features.py")
    assert APP_VERSION == "5.3.4"
    assert API_VERSION == 19
    assert BUILD_CHANNEL == "stable"
    assert 'UI_VERSION = "5.3.4"' in shell
    assert 'frontend-v534.js' in shell
    assert 'o2ring-v534.css' in shell
    assert 'o2ring-v532.js' not in shell
    assert 'frontend-v533.js' not in shell
    assert 'install_o2ring_runtime_v534' in shell


def test_v534_live_chart_is_visibility_scoped_and_batch_restored():
    js = read("web/o2ring.js")
    stream = read("cpap/o2ring_stream.py")
    for marker in (
        "document.visibilityState==='visible'",
        "function updateLiveLifecycle()",
        "function closeLiveStream()",
        "/api/o2ring/live-buffer?since=",
        "async function refillLive(since=null)",
        "R.liveResumePromise",
        "await refillLive(since)",
        "if(o2PageVisible())openLiveStream()",
    ):
        assert marker in js
    assert "class _LiveBuffer" in stream
    assert 'path == "/api/o2ring/live-buffer"' in stream
    assert "service.manager.add_listener(BUFFER.append_snapshot)" in stream
    assert "setInterval(" not in js


def test_v534_sleepsync_is_event_driven_not_frontend_polled():
    backend = read("cpap/o2ring_runtime_v534.py")
    js = read("web/o2ring.js")
    for marker in (
        '"sleepsync-completed"',
        "sync._sync_job = types.MethodType(wrapped, sync)",
        'parsed.path == "/api/o2ring/events"',
        "EventSource(`/api/o2ring/events?after=${R.eventSeq}`)",
        "invalidateDays(x.days||[])",
    ):
        assert marker in backend or marker in js
    assert "setInterval(" not in backend
    assert "setInterval(" not in js


def test_v534_invalidation_hub_replays_every_missed_event_in_order():
    hub = _EventHub(max_events=32)
    first = hub.publish("recording-added", days=["20260901"], source="o2ring")
    second = hub.publish("sleepsync-completed", days=["20260902"], source="sleepsync")
    third = hub.publish("therapy-invalidated", days=["20260903"], source="runtime")

    assert hub.wait(0, timeout=0.01)["seq"] == first["seq"]
    assert hub.wait(first["seq"], timeout=0.01)["seq"] == second["seq"]
    assert hub.wait(second["seq"], timeout=0.01)["seq"] == third["seq"]
    assert [x["seq"] for x in hub.events_after(0)] == [first["seq"], second["seq"], third["seq"]]
    assert hub.snapshot()["seq"] == third["seq"]


def test_v534_dashboard_modes_focus_charts_and_night_card_are_present():
    js = read("web/o2ring.js")
    for marker in (
        "#focusViewBtn,#stackViewBtn,#o2rDailyBtn",
        "if(o)o.textContent='Oximetria'",
        "O2_FOCUS_DEFS",
        "o2_spo2",
        "o2_hr",
        "card.className='overview-card sm-o2-focus-mini'",
        "card.onclick=()=>selectSignal(d.key)",
        "smStackO2Spo2",
        "smStackO2Hr",
        "smStackO2Dual",
        "smNightO2Card",
        "smDashboardO2V534",
    ):
        assert marker in js
    focus = js[js.index("const O2_FOCUS_DEFS"):js.index("function ensureStackO2")]
    assert "smO2FocusSpo2" not in focus
    assert "smO2FocusHr" not in focus
    assert "smO2FocusDual" not in focus
    assert "Vissza" not in js


def test_v534_o2_chart_interaction_has_zoom_exact_crosshair_and_sync_groups():
    js = read("web/o2ring.js")
    for marker in (
        "hour:'2-digit',minute:'2-digit',second:'2-digit'",
        "function nearest(rows,t)",
        "function bindChart(c,",
        "pointerdown",
        "pointermove",
        "dblclick",
        "syncGroup:'live'",
        "syncGroup:'daily-o2'",
        "syncGroup:'recording'",
        "setHover(ctl.syncGroup,t)",
        "function o2CoreSignal(key)",
        "loadMainSignal.__smO2",
        "o2CoreSignal(state.selectedSignal)",
        "card.onclick=()=>selectSignal(d.key)",
    ):
        assert marker in js


def test_v534_overlay_is_per_signal_timestamp_aligned_and_gap_aware():
    js = read("web/o2ring.js")
    css = read("web/o2ring-v534.css")
    for option in ('value="off"', 'value="spo2"', 'value="hr"', 'value="both"'):
        assert option in js
    for marker in (
        "localStorage.setItem(`sm-o2-overlay:${key}`",
        "makeSegments(rs,'spo2'",
        "makeSegments(rs,'heart_rate'",
        "medianDelta(rs)*3.2",
        "sm-o2-overlay-select",
        "installPerStackOverlayControls",
    ):
        assert marker in js
    assert "right:-42px!important" in css
    assert "width:calc(100% + 42px)!important" in css


def test_v534_pwa_settings_are_merged_and_o2ring_named_consistently():
    js = read("web/frontend-v534.js")
    css = read("web/o2ring-v534.css")
    for marker in (
        "function normalizePwaSettings()",
        "push.textContent='PWA'",
        "pwa?.remove()",
        "pwaPanel.removeAttribute('data-settings-panel')",
        "function normalizeO2Settings()",
        "tab.textContent='O2Ring'",
        "o.textContent='O2Ring'",
        "Élő O₂ monitor",
        "function normalizeSetupWizard()",
        "x!==keep)x.remove()",
        "system.appendChild(keep)",
        "function saveO2Toggles()",
        "e.stopImmediatePropagation()",
    ):
        assert marker in js
    assert '[data-settings-tab="pwa"]' in css
    assert ".sm-o2-settings-panel" in css
    assert "@media(max-width:600px)" in css


def test_v534_pwa_live_nav_is_not_rerendered_on_unchanged_status_ticks():
    js = read("web/frontend-v534.js")
    assert "lastLiveNavEnabled" in js
    assert "const needsChange=wanted?!currentCorrect:!!current" in js
    assert "if(!needsChange)return" in js
    status_handler = js.split("window.addEventListener('sleepmate-o2-status'", 1)[1].split("});", 1)[0]
    assert "normalizeAll()" not in status_handler


def test_v534_reports_dashboard_palette_and_loading_regressions_are_guarded():
    js = read("web/o2ring.js")
    bootstrap = read("web/frontend-v534.js")
    for marker in (
        "SpO₂ átlag",
        "SpO₂ min.",
        "Pulzus átlag",
        "ODI3 / ODI4",
        "EVENT_COLORS",
        "COLORS.teal:COLORS.blue",
    ):
        assert marker in js
    assert "shadowBlur" not in js
    assert "function fixLatestLoading()" in bootstrap
    assert "function syncLatestSessionCard()" in bootstrap
    assert "latest?.summary||latest" in bootstrap
    assert "latestDuration(summary)" in bootstrap
    assert "summary.sessions" in bootstrap
    assert "status.textContent='—'" in bootstrap
    assert "Befejezve" not in bootstrap


def test_v534_service_workers_only_activate_current_o2_frontend_generation():
    for path in ("web/service-worker.js", "web/service-worker-v508-base.js"):
        sw = read(path)
        assert "sleepmate-shell-v5.3.4-refactor" in sw
        assert "/o2ring-v534.css?v=5.3.4" in sw
        assert "/frontend-v534.js?v=5.3.4" in sw
        assert "'/o2ring.js'" in sw
        assert "o2ring-v532.js?v=5.3.3" not in sw
        assert "frontend-v533.js?v=5.3.3" not in sw
        assert "X-SleepMate-UI-Version" in sw


def test_v534_extracts_affected_sleepsync_days_without_full_rescan_contract():
    value = {
        "files": ["DATALOG/2026-09-01/file.edf", "20260902"],
        "nested": {"day": "2026_09_03"},
    }
    assert _extract_day_codes(value) == {"20260901", "20260902", "20260903"}


def test_v534_recent_day_fallback_is_chronological_not_collection_order():
    values = ["20260904", "20260901", "2026-09-06", "20260903", "20260905", "20260902"]
    assert _recent_day_codes(values, 4) == ["20260903", "20260904", "20260905", "20260906"]


def test_v534_matching_prefers_largest_overlap_deterministically():
    start = datetime(2026, 9, 1, 23, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=8)
    long_a = recording(
        "long",
        start + timedelta(minutes=5),
        end - timedelta(minutes=5),
        [sample((start + timedelta(hours=i)).timestamp()) for i in range(1, 8)],
    )
    shorter = recording(
        "short",
        start + timedelta(minutes=35),
        end - timedelta(minutes=35),
        [sample((start + timedelta(hours=i, minutes=1)).timestamp(), 95, 66) for i in range(1, 7)],
    )
    service = fake_service([shorter, long_a], start, end)
    result = _daily_v534(service, "20260901", max_points=1000)
    assert result["available"] is True
    assert [m["recording_id"] for m in result["matches"]] == ["long"]


def test_v534_auto_match_off_really_disables_cpap_pairing():
    start = datetime(2026, 9, 1, 23, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=8)
    rec = recording(
        "night",
        start + timedelta(minutes=5),
        end - timedelta(minutes=5),
        [sample((start + timedelta(hours=i)).timestamp()) for i in range(1, 8)],
    )
    service = fake_service([rec], start, end, auto_match=False)
    result = _daily_v534(service, "20260901", max_points=1000)
    assert result["auto_match"] is False
    assert result["available"] is False
    assert result["matches"] == []
    assert result["samples"] == []


def test_v534_matching_keeps_split_segments_and_deduplicates_timestamp_points():
    start = datetime(2026, 9, 1, 23, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=8)
    seam = start + timedelta(hours=3)
    duplicate_ts = (seam + timedelta(seconds=5)).timestamp()
    first = recording(
        "part-a",
        start + timedelta(minutes=5),
        seam + timedelta(seconds=10),
        [sample((start + timedelta(hours=1)).timestamp()), sample(duplicate_ts, 94, 67)],
    )
    second = recording(
        "part-b",
        seam,
        end - timedelta(minutes=5),
        [sample(duplicate_ts, 93, 70), sample((start + timedelta(hours=6)).timestamp(), 96, 64)],
    )
    service = fake_service([first, second], start, end)
    result = _daily_v534(service, "20260901", max_points=1000)
    assert {m["recording_id"] for m in result["matches"]} == {"part-a", "part-b"}
    timestamps = [round(row["timestamp"] * 1000) for row in result["samples"]]
    assert len(timestamps) == len(set(timestamps))


def test_v534_sidebar_route_is_capture_owned_and_history_is_not_duplicated():
    js=read("web/o2ring.js")
    assert "#sidebar [data-page=\"oximetry\"]" in js
    assert "stopImmediatePropagation();openOximetry(R.pageTab||'live')" in js
    assert "if(location.hash!=='#oximetry')history.pushState" in js


def test_v534_overlay_focus_selector_persists_the_current_signal_not_flow_only():
    js=read("web/o2ring.js")
    assert "e.currentTarget.dataset.signal||key" in js
    assert "sm-o2-overlay:${key}" in js


def test_v534_all_o2_charts_have_touch_pinch_pan_and_synchronized_trend_zoom():
    js=read("web/o2ring.js")
    for marker in ("function clampChartRange", "ctl.pinch", "ctl.pointers", "mode:e.pointerType==='touch'||e.shiftKey?'pan':'zoom'", "R.trendZoom", "syncGroup:'trends'", "R.dashboardTrendZoom", "syncGroup:'dash-o2'"):
        assert marker in js


def test_v534_source_settings_are_single_pwa_category_and_single_setup_wizard_card():
    pwa=read("web/sleepmate-v530.js")
    first=read("web/first-run.js")
    assert "push.textContent='PWA'" in pwa
    assert "legacy?.remove()" in pwa
    assert "panel.removeAttribute('data-settings-panel')" in pwa
    assert "dataset.settingsTab='pwa'" not in pwa
    assert "system.appendChild(box)" in first
    assert "for(const x of all)if(x!==box)x.remove()" in first
    assert "setInterval(()=>{tries++" not in first


def test_v534_overlay_has_compact_secondary_o2_hr_scale_labels():
    js=read('web/o2ring.js')
    assert 'function drawOverlayScaleLabels' in js
    assert "O₂ 100%" in js and "O₂ 75%" in js
    assert 'HR ${hrHi}' in js and 'HR ${hrLo}' in js


def test_v534_auto_match_toggle_saves_on_first_change_and_settings_grid_is_responsive():
    js=read('web/frontend-v534.js');css=read('web/o2ring-v534.css')
    assert "id('smO2AutoMatch').onchange=saveAdvancedO2Settings" in js
    assert '.sm-o2-advanced-grid,.sm-o2-device-grid{display:grid' in css
    assert '@media(max-width:700px)' in css


def test_v534_sleepsync_nested_import_changed_days_are_targeted():
    value={'import':{'changed_days':['20260901','20260902'],'changed_files':['DATALOG/20260902/x.edf']}}
    assert _extract_day_codes(value)=={'20260901','20260902'}
