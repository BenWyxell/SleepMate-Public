from __future__ import annotations

from pathlib import Path

from cpap.ai_payload import external_analysis_prompt


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_external_prompt_is_human_facing_but_keeps_canonical_payload():
    payload = {"schema": "cpap-ai-safe-payload-v1", "days": [{"ahi": 1.2, "spo2": 95}]}
    prompt = external_analysis_prompt("night", payload)
    assert '"ahi":1.2' in prompt and '"spo2":95' in prompt
    for marker in (
        "magyar nyelvű", "rövid összefoglalót", "fő megállapításokat",
        "pozitívumokat", "figyelmet érdemlő", "ne állíts fel diagnózist",
        "Ne válaszolj JSON-ban", "ne másold vissza nyersen",
    ):
        assert marker in prompt
    assert "A válaszod KIZÁRÓLAG érvényes JSON" not in prompt


def test_ai_selector_exposes_each_enabled_mode_without_automatic_parallel_start():
    js = read("web/app-core.js")
    assert "function availableAIAnalysisModes()" in js
    assert "f.lunaVisible&&aiProviderMeta('gemini').configured" in js
    assert "f.miloVisible&&aiProviderMeta('groq').configured" in js
    assert "if(f.promptingEnabled)modes.push" in js
    assert "if(mode.id==='external')" in js
    assert "promptTask=features.promptingEnabled" not in js


def test_cold_pwa_boot_loads_one_coherent_shell_and_authoritative_o2_master():
    app = read("web/app.js")
    engine = read("web/app-engine119.js")
    shell = read("cpap/v530_features.py")
    o2 = read("web/sleepmate-v530.js")
    assert "window.addEventListener('load',()=>" not in app
    assert "script.async=false" in app
    assert "sleepmate:sleepsync-ready" in engine
    assert "<svg viewBox=" in engine
    assert 'name="sleepmate-o2ring-enabled"' in shell
    assert 'name="sleepmate-o2ring-enabled" content="unknown"' in shell
    assert "UNKNOWN:'unknown',ENABLED:'enabled',DISABLED:'disabled'" in o2
    assert "function activeO2(){return o2State===O2_STATE.ENABLED}" in o2
    for worker_name in ("web/service-worker.js", "web/service-worker-v508-base.js"):
        worker = read(worker_name)
        assert "event.respondWith(navigationFallback(req))" in worker
        assert "event.respondWith(codeNetworkFirst(req))" in worker
        assert "await client.navigate(client.url)" not in worker


def test_oximetry_touch_zoom_and_dynamic_axis_contract():
    js = read("web/o2ring.js")
    assert "steps=[1,2,5,10,15,30,60" in js
    assert "Math.ceil(a/step)*step" in js
    assert "pointer:coarse" in js and "y-t.offsetHeight-22" in js
    assert "now-lastTouchTap.time<360" in js
    assert "ctl?.resetRange?.();ctl?.redraw?.()" in js


def test_daily_o2_summary_is_prefetched_shared_and_never_false_empty_while_loading():
    core = read("web/app-core.js")
    o2 = read("web/o2ring.js")
    assert "getDailySummary:async day=>" in o2
    assert "const o2Promise=window.SleepMateO2Ring?.getDailySummary?.(day)" in core
    assert "state.o2DailyLoading=!!o2Promise" in core
    assert "loading?'Betöltés…':'Nincs adat'" in core
    assert "function dailyO2ShareValues()" in core
    assert "SpO₂:" in core and "Pulzus:" in core and "T90:" in core
    assert "hydrateReportDailyStats" in o2
    assert "window.SleepMateO2Ring?.hydrateDayRows" in core
    assert "hydrateDayRows:async(rows,force=false)" in o2


def test_ios_pwa_label_input_uses_non_zooming_font_size_without_viewport_hack():
    css = read("web/sleepmate-v530.css")
    html = read("web/index.html")
    assert ".sm-pwa-label-field input{min-height:40px;font-size:16px!important}" in css
    assert "user-scalable=no" not in html


def test_sleepsync_cold_start_keeps_bounded_bootstrap_fallback():
    polish = read("web/sleepsync-polish.js")
    assert "bootAttempts<80" in polish
    assert "setTimeout(boot,100)" in polish
    assert "sleepmate:sleepsync-ready" in polish
