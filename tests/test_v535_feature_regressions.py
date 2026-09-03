from __future__ import annotations

from pathlib import Path

import pytest

import app as app_module
from cpap.ui_preferences_v530 import (
    PWA_NAV_DEFAULT_LABELS,
    PWA_NAV_LABEL_MAX_LENGTH,
    _normalize_bool,
    _normalize_labels,
)


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_custom_pwa_labels_are_normalized_bounded_and_resettable():
    assert _normalize_labels(None) == {}
    assert _normalize_labels({"dashboard": PWA_NAV_DEFAULT_LABELS["dashboard"]}) == {}
    assert _normalize_labels({"dashboard": "  Főoldal   ma  "}) == {"dashboard": "Főoldal ma"}
    with pytest.raises(ValueError):
        _normalize_labels({"dashboard": "x" * (PWA_NAV_LABEL_MAX_LENGTH + 1)})
    with pytest.raises(ValueError):
        _normalize_labels({"unknown": "Ismeretlen"})


def test_ai_feature_flags_require_real_booleans():
    assert _normalize_bool(True, "ai_luna_visible") is True
    assert _normalize_bool(False, "ai_milo_visible") is False
    assert _normalize_bool(False, "ai_prompting_enabled") is False
    with pytest.raises(ValueError):
        _normalize_bool("false", "ai_prompting_enabled")


def test_new_preferences_have_safe_defaults_for_legacy_or_malformed_config(tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    monkeypatch.setattr(app_module, "config_path", lambda _base: config_file)

    config_file.write_text('{"ai_luna_visible":"false","ai_milo_visible":null,"ai_prompting_enabled":1,"pwa_bottom_nav_labels":[]}', encoding="utf-8")
    loaded = app_module.load_config()

    assert loaded["ai_luna_visible"] is True
    assert loaded["ai_milo_visible"] is True
    assert loaded["ai_prompting_enabled"] is False
    assert loaded["pwa_bottom_nav_labels"] == {}


def test_prompt_export_uses_the_same_canonical_builder_as_live_analysis(monkeypatch):
    safe_payload = {
        "schema": "cpap-ai-safe-payload-v1",
        "analysis_type": "night",
        "days": [{"date": "2026-09-02", "ahi": 1.2}],
    }
    meta = {"period_start": "2026-09-02", "period_end": "2026-09-02", "therapy_days": 1}
    monkeypatch.setattr(app_module, "build_safe_payload", lambda *_: (safe_payload, meta))
    monkeypatch.setattr(app_module, "analysis_prompts", lambda kind, payload: ("SYSTEM " + kind, "USER " + str(payload["days"][0]["ahi"])))
    external_calls = []
    monkeypatch.setattr(app_module, "external_analysis_prompt", lambda kind, payload: external_calls.append((kind, payload)) or "HUMAN PROMPT 1.2")
    handler = object.__new__(app_module.Handler)
    handler.dataset = object()
    handler.patient_store = object()

    prepared = handler._prepare_analysis_prompt({"analysis_type": "night", "provider": "gemini"})
    exported = handler._analysis_prompt_export({"analysis_type": "night", "provider": "gemini"})

    assert prepared["safe_payload"] is safe_payload
    assert exported["prompt"] == "HUMAN PROMPT 1.2"
    assert external_calls == [("night", safe_payload)]
    assert exported["filename"] == "SleepMate_napi_elemzes_2026-09-02_prompt.txt"
    source = read("app.py")
    assert "prepared = self._prepare_analysis_prompt(data)" in source
    assert 'if path == "/api/ai/prompt"' in source


def test_o2_master_toggle_has_authoritative_ui_and_route_cleanup_contract():
    html = read("web/index.html")
    js = read("web/sleepmate-v530.js")
    o2 = read("web/o2ring.js")
    css = read("web/sleepmate-v530.css")
    assert 'class="sm-o2-disabled"' in html
    assert "setO2FeatureState()" in js
    assert "window.SleepMateO2Ring?.uninstall?.()" in js
    assert "const featureActive=()=>R.installed&&!!R.settings.o2ring_enabled" in o2
    assert "loadDaily=async function(...args){if(!featureActive())" in o2
    assert "[data-sm-nav-id=\"oximetry\"]" in o2
    assert "if(location.hash.startsWith('#oximetry'))window.navigate?.('dashboard')" in o2
    assert "if(!activeO2()&&location.hash.startsWith('#oximetry'))window.navigate?.('dashboard')" in js
    for marker in ("#spo2Metric", "#hrMetric", "#smO2QuickBar", ".sm-o2-stack", ".sm-o2-focus-mini"):
        assert marker in css
    assert 'html.sm-o2-disabled [data-settings-panel="display"]>:not(#smO2Master)' in css


def test_all_oximetry_line_charts_share_responsive_x_axis_contract():
    js = read("web/o2ring.js")
    assert "function drawResponsiveXAxis" in js
    assert "iw/(compact?76:92)" in js
    assert "Math.ceil(a/step)*step" in js
    assert "mobileClock" in js and "mobileDate" in js
    assert "w-tw-2" in js
    assert js.count("drawResponsiveXAxis(ctx,") == 2  # definition + the common chartDraw call
    for group in ("live", "daily-o2", "stack-o2", "recording", "trends", "dash-o2"):
        assert f"syncGroup:'{group}'" in js


def test_mobile_sidebar_and_prompt_modal_honor_bottom_nav_and_safe_area():
    css = read("web/sleepmate-v530.css")
    for marker in (
        "min-height:calc(100dvh - 66px - env(safe-area-inset-bottom))",
        "overflow-y:auto!important",
        "#sidebar .sidebar-version{flex:0 0 auto",
        "max-height:calc(100dvh - env(safe-area-inset-top) - env(safe-area-inset-bottom) - 16px)",
        ".ai-prompt-actions{display:grid",
        "html.pwa-standalone #sidebar .sidebar-version{display:none!important}",
        "html.pwa-standalone #sidebar .nav{flex:1 1 0!important;min-height:0!important;overflow:hidden!important",
        "html.pwa-standalone #sidebar .nav{display:flex!important;flex-direction:column!important",
        "html.pwa-standalone #sidebar .nav-item{max-height:22px!important",
    ):
        assert marker in css
    pwa_drawer = css[css.index("/* Phone PWA drawer:"):css.index("/* Phone rendering:")]
    assert "grid-template-columns" not in pwa_drawer


def test_luna_milo_and_prompting_have_three_independent_conditions_and_actions():
    js = read("web/app-core.js")
    shell = read("web/sleepmate-v530.js")
    html = read("web/index.html")
    assert "function availableAIAnalysisModes()" in js
    assert "Luna értékelje" in js and "Milo értékelje" in js and "Prompt külső AI-hoz" in js
    assert "if(modes.length===1)return runAIAnalysisMode" in js
    assert "showAIAnalysisModeMenu(modes,type,button)" in js
    assert "btn.textContent='Elemzés indítása'" in js
    assert "prefs.ai_luna_visible!==false||prefs.ai_milo_visible!==false||prefs.ai_prompting_enabled===true" in shell
    assert "settingAiLunaVisible" in html and "settingAiMiloVisible" in html
    assert "sm-ai-luna-off" in shell and "sm-ai-milo-off" in shell
    assert "if(o2State===O2_STATE.DISABLED&&location.hash.startsWith('#oximetry'))window.navigate?.('dashboard')" in shell
    assert "filter(r=>r.provider==='groq'?features.miloVisible:features.lunaVisible)" in js
    for marker in ("aiPromptCopy", "aiPromptDownload", "aiPromptChatGpt", "aiPromptGemini"):
        assert marker in html
    assert "apiWrite('/api/ai/prompt','POST',selection)" in js


def test_phone_web_pwa_and_reduced_motion_keep_aurora_static_without_js_loop():
    js = read("web/sleepmate-v530.js")
    css = read("web/sleepmate-v530.css")
    assert "mobileUa||(coarse&&shortSide<=600)" in js
    assert "html.sm-phone-ui .sm-starfield" in css
    assert "html.sm-phone-ui .sm-aurora-flow .flow{animation:none!important" in css
    assert "@media(prefers-reduced-motion:reduce)" in css
    aurora = js[js.index("function installAuroraScene"):js.index("function activeO2")]
    assert "requestAnimationFrame" not in aurora
    assert "setInterval" not in aurora


def test_latest_session_card_never_renders_the_legacy_completion_label():
    core = read("web/app-core.js")
    assert "$('#latestStatus').textContent='Befejezve'" not in core
    assert "$('#latestStatus').textContent=secondsToHM(latest.therapy_seconds||0)" in core


def test_phone_web_and_pwa_use_first_paint_mobile_performance_mode():
    html = read("web/index.html")
    shell = read("web/sleepmate-v530.js")
    css = read("web/sleepmate-v530.css")
    core = read("web/app-core.js")
    diagnostics = read("web/mobile-boot-diagnostics.js")
    for worker_name in ("web/service-worker.js", "web/service-worker-v508-base.js"):
        worker = read(worker_name)
        assert "function navigationFastCache" not in worker
        assert "function codeFastCache" not in worker
        assert "event.respondWith(navigationFallback(req))" in worker
        assert "event.respondWith(codeNetworkFirst(req))" in worker
    assert "document.documentElement.classList.toggle('sm-phone-ui',phone)" in html
    assert "document.documentElement.classList.toggle('sm-phone-ui',phone)" in shell
    assert '<link rel="preload" as="script" href="/app-engine119.js?v=130">' in html
    assert '<link rel="preload" as="script" href="/app-core.js?v=5.0.8">' in html
    assert "html.sm-phone-ui .sm-starfield" in css
    assert "backdrop-filter:none!important" in css
    assert "html.sm-phone-ui .sm-aurora-flow .flow{stroke-dashoffset:0!important}" in css
    assert "const [ver]=await Promise.all([api('/api/version'),loadDays(),loadConfig()]);" in core
    assert "phoneUi&&!verboseDiagnostics" in diagnostics
    assert "if(phoneUi&&!verboseDiagnostics&&label!=='startup-slow')return" in diagnostics
    assert "if(!phoneUi||verboseDiagnostics){snapshot('dom-content-loaded')" in diagnostics
    assert "if(!phoneUi||verboseDiagnostics){snapshot('window-load');swSnapshot()}" in diagnostics
    assert "if(!shell?.classList.contains('ready')){snapshot('startup-slow')" in diagnostics
    assert "html.sm-phone-ui *,html.sm-phone-ui *::before,html.sm-phone-ui *::after{backdrop-filter:none!important" in css
    assert "html.sm-phone-ui :is(.sidebar,#dashboardDailyView){will-change:auto!important}" in css


def test_sleepsync_saved_schedule_is_always_visible_and_sync_tab_hydrates_it():
    engine = read("web/app-engine119.js")
    polish = read("web/sleepsync-polish.js")
    hydration = read("web/sleepsync-hydration-v529.js")
    css = read("web/sleepsync-polish.css")
    assert 'id="ssCurrentSchedule"' in engine
    assert "setText('ssCurrentSchedule',scheduleSummaryText(settings))" in engine
    assert "if(tab==='settings'||tab==='sync')loadSettings()" in engine
    assert "current.textContent=scheduleSummary(settings)" in polish
    assert "if(location.hash.startsWith('#sleepsync'))" in polish
    assert "if(location.hash.startsWith('#sleepsync'))hydrate(false)" in hydration
    assert "if(dirty&&!force)return true" in hydration
    assert ".sleepsync-page .ss-current-schedule" in css
