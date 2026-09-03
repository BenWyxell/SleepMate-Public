from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path
import urllib.request
from urllib.parse import unquote, urlparse

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


BASE_URL = os.environ["SLEEPMATE_ACCEPTANCE_URL"].rstrip("/")
EDGE_PATH = Path(os.environ["SLEEPMATE_EDGE_PATH"])
WEB_ROOT = Path(__file__).resolve().parents[1] / "web"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def api_json(path: str, method: str = "GET", payload: dict | None = None) -> dict:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=body,
        method=method,
        headers={"Accept": "application/json", "Content-Type": "application/json", "Cache-Control": "no-store"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def wait_runtime(page: Page, timeout: int = 35_000) -> None:
    try:
        page.wait_for_function(
            """() => document.querySelector('.hidden-until-ready')?.classList.contains('ready')
                && window.SleepMateV530 && window.SleepMateFrontendV534 && window.SleepMateO2Ring""",
            timeout=timeout,
        )
    except PlaywrightTimeoutError as exc:
        snapshot = page.evaluate(
            """() => ({url:location.href,ready:document.querySelector('.hidden-until-ready')?.className,
              core:typeof window.navigate,features:!!window.SleepMateV530,frontend:!!window.SleepMateFrontendV534,
              o2:!!window.SleepMateO2Ring,error:document.getElementById('errorBox')?.innerText||''})"""
        )
        raise AssertionError(f"SleepMate browser runtime did not become ready: {snapshot}") from exc
    page.wait_for_timeout(250)


def open_runtime(page: Page, fragment: str = "dashboard") -> None:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            page.goto(f"{BASE_URL}/#{fragment}", wait_until="domcontentloaded", timeout=45_000)
        except PlaywrightTimeoutError:
            # The source backend can keep a navigation request pending while its
            # first data scan is busy. Runtime readiness is the authoritative gate.
            pass
        try:
            wait_runtime(page)
            return
        except AssertionError as exc:
            last_error = exc
            if attempt < 2:
                page.wait_for_timeout(250)
    raise AssertionError(f"SleepMate did not load after three browser attempts: {last_error}") from last_error


def reload_runtime(page: Page) -> None:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            page.reload(wait_until="domcontentloaded", timeout=45_000)
        except PlaywrightTimeoutError:
            pass
        try:
            wait_runtime(page)
            return
        except AssertionError as exc:
            last_error = exc
            if attempt < 2:
                page.wait_for_timeout(250)
    raise AssertionError(f"SleepMate reload failed after three attempts: {last_error}") from last_error


def navigate(page: Page, destination: str) -> None:
    page.evaluate("destination => window.navigate(destination)", destination)
    page.wait_for_timeout(180)


def select_settings(page: Page, category: str) -> None:
    navigate(page, "settings")
    if page.locator("#settingsCategorySelect").is_visible():
        page.locator("#settingsCategorySelect").select_option(category)
    else:
        page.locator(f'[data-settings-tab="{category}"]').click()
    page.wait_for_timeout(180)


def set_ai_toggle(page: Page, element_id: str, preference: str, value: bool) -> None:
    toggle = page.locator(f"#{element_id}")
    toggle.set_checked(value)
    try:
        page.wait_for_function(
            "([key,value]) => window.SleepMateV530.preferences()[key] === value",
            arg=[preference, value],
            timeout=10_000,
        )
    except PlaywrightTimeoutError as exc:
        state = page.evaluate(
            "([id,key]) => ({checked:document.getElementById(id)?.checked,pref:window.SleepMateV530.preferences()[key],status:document.getElementById('aiFeatureSettingsStatus')?.textContent})",
            [element_id, preference],
        )
        raise AssertionError(f"AI toggle {preference} did not settle to {value}: {state}") from exc


def install_prompt_route(page: Page) -> None:
    prompt = (
        "[RENDSZERINSTRUKCIÓ]\nSleepMate acceptance system instruction\n\n"
        "[FELHASZNÁLÓI PROMPT]\nIdőszak: 2026-09-02. CPAP AHI: 1.2. Oximetria: aktív."
    )

    def handler(route) -> None:
        route.fulfill(
            status=200,
            content_type="application/json; charset=utf-8",
            body=json.dumps(
                {
                    "ok": True,
                    "analysis_type": "night",
                    "analysis_key": "night",
                    "period": {"period_start": "2026-09-02", "period_end": "2026-09-02", "therapy_days": 1},
                    "prompt_version": "acceptance",
                    "prompt": prompt,
                    "filename": "SleepMate_napi_elemzes_2026-09-02_prompt.txt",
                },
                ensure_ascii=False,
            ),
        )

    page.route("**/api/ai/prompt", handler)


def install_source_asset_routes(page: Page) -> None:
    """Serve checked-out frontend assets directly; API and document requests stay real."""

    def handler(route) -> None:
        path = unquote(urlparse(route.request.url).path)
        if path == "/" or path.startswith("/api/") or path == "/equipment-image":
            route.continue_()
            return
        candidate = (WEB_ROOT / path.lstrip("/")).resolve()
        try:
            candidate.relative_to(WEB_ROOT.resolve())
        except ValueError:
            route.continue_()
            return
        if not candidate.is_file():
            route.continue_()
            return
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if candidate.suffix in {".js", ".css", ".svg", ".webmanifest"}:
            content_type += "; charset=utf-8"
        route.fulfill(status=200, content_type=content_type, body=candidate.read_bytes())

    page.route("**/*", handler)


def test_preferences_ai_prompt_and_o2(page: Page, context) -> None:
    original_prefs = api_json("/api/ui/preferences")
    original_o2 = api_json("/api/o2ring/settings")
    restore_prefs = {
        key: original_prefs[key]
        for key in ("pwa_bottom_nav", "pwa_bottom_nav_labels", "ai_luna_visible", "ai_milo_visible", "ai_prompting_enabled")
        if key in original_prefs
    }
    restore_o2 = {
        key: original_o2[key]
        for key in (
            "o2ring_enabled", "o2ring_ble_enabled", "o2ring_auto_connect", "o2ring_auto_sync", "o2ring_auto_match"
        )
        if key in original_o2
    }
    try:
        test_nav = list(original_prefs.get("pwa_bottom_nav") or [])
        if "dashboard" not in test_nav:
            test_nav = (["dashboard"] + test_nav)[:6]
        api_json(
            "/api/ui/preferences",
            "POST",
            {"pwa_bottom_nav": test_nav, "ai_luna_visible": True, "ai_milo_visible": True, "ai_prompting_enabled": False},
        )
        if not original_o2.get("o2ring_enabled"):
            api_json("/api/o2ring/settings", "POST", {**restore_o2, "o2ring_enabled": True})

        install_prompt_route(page)
        open_runtime(page)

        select_settings(page, "push")
        dashboard_label = page.locator('[data-nav-label="dashboard"]')
        require(dashboard_label.count() == 1, "Dashboard custom-label input is missing")
        require(dashboard_label.get_attribute("maxlength") == "18", "PWA label length limit is not 18")
        dashboard_label.fill("Főoldal")
        page.locator("#smPwaSaveLabels").click()
        page.wait_for_function(
            "() => window.SleepMateV530.preferences().pwa_bottom_nav_labels?.dashboard === 'Főoldal'"
        )
        require(
            page.locator('#mobileBottomNav [data-sm-nav-id="dashboard"] b').inner_text().strip() == "Főoldal",
            "custom PWA label did not update immediately",
        )
        require(
            page.locator('#mobileBottomNav [data-sm-nav-id="dashboard"]').get_attribute("data-mobile-page") == "dashboard",
            "custom label changed the navigation route identity",
        )

        reload_runtime(page)
        require(
            page.locator('#mobileBottomNav [data-sm-nav-id="dashboard"] b').inner_text().strip() == "Főoldal",
            "custom PWA label did not survive reload",
        )
        select_settings(page, "push")
        page.locator("#smPwaResetLabels").click()
        page.wait_for_function(
            "() => !Object.keys(window.SleepMateV530.preferences().pwa_bottom_nav_labels || {}).length"
        )
        require(
            page.locator('#mobileBottomNav [data-sm-nav-id="dashboard"] b').inner_text().strip() == "Dashboard",
            "PWA label reset did not restore the default",
        )

        select_settings(page, "ai")
        set_ai_toggle(page, "settingAiLunaVisible", "ai_luna_visible", False)
        navigate(page, "ai")
        require(page.locator('[data-ai-provider="gemini"]').is_hidden(), "Luna UI remained visible after Luna OFF")
        require(page.locator('[data-ai-provider="groq"]').is_visible(), "Milo UI disappeared together with Luna")
        select_settings(page, "ai")
        set_ai_toggle(page, "settingAiLunaVisible", "ai_luna_visible", True)
        set_ai_toggle(page, "settingAiMiloVisible", "ai_milo_visible", False)
        navigate(page, "ai")
        require(page.locator('[data-ai-provider="groq"]').is_hidden(), "Milo UI remained visible after Milo OFF")
        require(page.locator('[data-ai-provider="gemini"]').is_visible(), "Luna UI disappeared together with Milo")

        select_settings(page, "ai")
        set_ai_toggle(page, "settingAiLunaVisible", "ai_luna_visible", False)
        set_ai_toggle(page, "settingAiPromptingEnabled", "ai_prompting_enabled", True)
        navigate(page, "ai")
        require(page.locator(".ai-provider-grid").is_hidden(), "assistant provider UI is visible with Luna and Milo OFF")
        require(page.locator(".ai-launch-panel").is_visible(), "prompt launcher disappeared with Luna and Milo OFF")
        page.evaluate("() => { state.days=['20260902']; state.currentDay='20260902'; state.latestDay='20260902'; }")
        page.locator('[data-ai-analysis="night"]').click()
        page.wait_for_function("() => !document.getElementById('aiPromptModal').classList.contains('hidden')")
        page.wait_for_function("() => document.getElementById('aiPromptContent').textContent.includes('CPAP AHI: 1.2')")
        prompt_text = page.locator("#aiPromptContent").text_content() or ""
        require("RENDSZERINSTRUKCIÓ" in prompt_text and "Oximetria: aktív" in prompt_text, "prompt modal is incomplete")

        context.grant_permissions(["clipboard-read", "clipboard-write"], origin=BASE_URL)
        page.locator("#aiPromptCopy").click()
        page.wait_for_function("() => document.getElementById('aiPromptStatus').textContent.includes('vágólapra másolva')")
        copied = page.evaluate("() => navigator.clipboard.readText()")
        require(copied.replace("\r\n", "\n") == prompt_text.replace("\r\n", "\n"), f"clipboard did not receive the complete prompt: {copied!r} != {prompt_text!r}")

        with page.expect_download(timeout=10_000) as download_info:
            page.locator("#aiPromptDownload").click()
        download = download_info.value
        require(download.suggested_filename == "SleepMate_napi_elemzes_2026-09-02_prompt.txt", "wrong TXT filename")
        downloaded = Path(download.path()).read_text(encoding="utf-8")
        require(downloaded == prompt_text, "downloaded UTF-8 TXT does not match the complete prompt")

        page.evaluate(
            """() => { window.__smOpened=[]; window.open=(url,target,features) => {
                window.__smOpened.push({url,target,features}); return {opener:null};
            }}"""
        )
        page.locator("#aiPromptChatGpt").click()
        page.locator("#aiPromptGemini").click()
        opened = page.evaluate("() => window.__smOpened")
        require([row["url"] for row in opened] == ["https://chatgpt.com/", "https://gemini.google.com/app"], "external AI buttons opened wrong URLs")
        require(all(row["target"] == "_blank" for row in opened), "external AI buttons did not open a new tab/window")

        page.locator("#aiPromptClose").click()
        select_settings(page, "ai")
        set_ai_toggle(page, "settingAiPromptingEnabled", "ai_prompting_enabled", False)
        require(page.locator('#sidebar [data-page="ai"]').is_hidden(), "AI navigation remained visible with all three UI features OFF")
        page.evaluate("() => { location.hash='#ai'; }")
        page.wait_for_function("() => !location.hash.startsWith('#ai')")

        select_settings(page, "display")
        master = page.locator("#smO2Enabled")
        master.set_checked(False, force=True)
        page.wait_for_function("() => document.documentElement.classList.contains('sm-o2-disabled')")
        require(page.locator('#sidebar [data-page="oximetry"]').count() == 0, "Oximetria sidebar item remained after O2 OFF")
        require(page.locator("#page-oximetry").count() == 0, "Oximetria page remained mounted after O2 OFF")
        require(page.locator("#spo2Metric").is_hidden() and page.locator("#hrMetric").is_hidden(), "SpO2/Pulse cards remained visible after O2 OFF")
        visible_settings_children = page.locator('[data-settings-panel="display"] > *:visible').evaluate_all(
            "nodes => nodes.map(node => node.id || node.className)"
        )
        require(visible_settings_children == ["smO2Master"], f"O2-only settings remained visible after O2 OFF: {visible_settings_children}")
        page.evaluate("() => { location.hash='#oximetry'; }")
        page.wait_for_function("() => !location.hash.startsWith('#oximetry')")

        select_settings(page, "display")
        master.set_checked(True, force=True)
        page.wait_for_function("() => !document.documentElement.classList.contains('sm-o2-disabled')")
        page.wait_for_function("() => !!document.querySelector('#sidebar [data-page=\"oximetry\"]')")
        require(page.locator("#page-oximetry").count() == 1, "Oximetria UI did not return after O2 ON")
    finally:
        api_json("/api/ui/preferences", "POST", restore_prefs)
        api_json("/api/o2ring/settings", "POST", restore_o2)


def install_mobile_fixtures(page: Page) -> None:
    now = 1_788_300_000
    live_rows = [
        {"timestamp": now + i * 60, "spo2": 96 - (i % 3), "heart_rate": 60 + (i % 7), "motion": i % 2}
        for i in range(31)
    ]

    def live_handler(route) -> None:
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"rows": live_rows, "count": len(live_rows), "points": len(live_rows), "last_timestamp": live_rows[-1]["timestamp"]}),
        )

    page.route("**/api/o2ring/live-buffer*", live_handler)
    page.add_init_script(
        """
        Object.defineProperty(navigator,'standalone',{configurable:true,get:()=>true});
        const nativeMatchMedia=window.matchMedia.bind(window);
        window.matchMedia=query=>query.includes('display-mode: standalone')
          ? {matches:true,media:query,onchange:null,addListener(){},removeListener(){},addEventListener(){},removeEventListener(){},dispatchEvent(){return true}}
          : nativeMatchMedia(query);
        window.__smCanvasLabels=[];
        const nativeFillText=CanvasRenderingContext2D.prototype.fillText;
        CanvasRenderingContext2D.prototype.fillText=function(text,x,y,...rest){
          if(this.canvas?.id){
            window.__smCanvasLabels.push({id:this.canvas.id,text:String(text),x:Number(x),y:Number(y),width:this.measureText(String(text)).width,height:this.canvas.getBoundingClientRect().height});
          }
          return nativeFillText.call(this,text,x,y,...rest);
        };
        """
    )


def assert_mobile_sidebar(page: Page, width: int, height: int) -> None:
    page.set_viewport_size({"width": width, "height": height})
    page.evaluate("() => document.documentElement.classList.add('pwa-standalone','sm-phone-pwa')")
    navigate(page, "dashboard")
    if not page.locator("#sidebar").evaluate("node => node.classList.contains('mobile-open')"):
        page.locator("#mobileMenuToggle").click()
    page.wait_for_function("() => document.getElementById('sidebar').classList.contains('mobile-open')")
    layout = page.evaluate(
        """() => {
          const sidebar=document.getElementById('sidebar'),nav=sidebar.querySelector('.nav'),bottom=document.getElementById('mobileBottomNav');
          const sr=sidebar.getBoundingClientRect(),nr=nav.getBoundingClientRect(),br=bottom.getBoundingClientRect();
          const items=[...nav.querySelectorAll('.nav-item:not(.hidden)')].map(x=>{const r=x.getBoundingClientRect();return {text:x.innerText.trim(),top:r.top,bottom:r.bottom,left:r.left}});
          const style=getComputedStyle(nav),version=getComputedStyle(document.getElementById('sidebarVersion').parentElement);
          return {sidebar:{top:sr.top,bottom:sr.bottom},nav:{top:nr.top,bottom:nr.bottom,scrollHeight:nav.scrollHeight,clientHeight:nav.clientHeight,overflowY:style.overflowY,display:style.display,columns:style.gridTemplateColumns},bottomTop:br.top,items,version:version.display};
        }"""
    )
    require(layout["nav"]["overflowY"] == "hidden", f"{width}x{height}: phone PWA menu can scroll: {layout}")
    require(layout["nav"]["scrollHeight"] <= layout["nav"]["clientHeight"] + 1, f"{width}x{height}: menu content does not fit: {layout}")
    require(layout["nav"]["display"] == "flex", f"{width}x{height}: menu is not a single flex column")
    require(layout["nav"]["columns"] in ("none", ""), f"{width}x{height}: two-column menu detected: {layout['nav']['columns']}")
    require(layout["version"] == "none", f"{width}x{height}: version should be hidden to preserve phone menu room")
    require(layout["sidebar"]["bottom"] <= layout["bottomTop"] + 1, f"{width}x{height}: bottom nav overlaps sidebar")
    require(all(row["top"] >= layout["nav"]["top"] - 1 and row["bottom"] <= layout["nav"]["bottom"] + 1 for row in layout["items"]), f"{width}x{height}: a menu item is clipped")
    require(any("Beállítások" in row["text"] for row in layout["items"]), f"{width}x{height}: Settings is missing")
    require(len({round(row["left"], 1) for row in layout["items"]}) == 1, f"{width}x{height}: menu items are arranged in columns")
    page.evaluate("() => window.closeMobileSidebar?.()")


def assert_x_axis_labels(page: Page, width: int, height: int) -> None:
    page.set_viewport_size({"width": width, "height": height})
    page.evaluate("() => { document.documentElement.classList.add('pwa-standalone','sm-phone-pwa'); window.__smCanvasLabels=[]; }")
    page.evaluate("() => window.SleepMateO2Ring.refresh()")
    page.wait_for_timeout(450)
    results = page.evaluate(
        r"""() => ['o2rLiveDual','o2rLiveSpo2Chart','o2rLiveHrChart'].map(id=>{
          const canvas=document.getElementById(id),meta=canvas?._smO2Meta,count=meta?.xTickCount||0;
          const all=window.__smCanvasLabels.filter(row=>row.id===id && /^\d{1,2}:\d{2}$/.test(row.text) && row.y>=row.height-18);
          const labels=all.slice(-count).sort((a,b)=>a.x-b.x);
          return {id,count,canvasWidth:canvas?.getBoundingClientRect().width||0,labels};
        })"""
    )
    expected_max = 2 if width <= 320 else 3 if width < 430 else 4
    for result in results:
        require(2 <= result["count"] <= expected_max, f"{width}x{height} {result['id']}: unreasonable tick count {result}")
        require(len(result["labels"]) == result["count"], f"{width}x{height} {result['id']}: tick labels were not rendered")
        for label in result["labels"]:
            require(label["x"] >= 1 and label["x"] + label["width"] <= result["canvasWidth"] - 1, f"{width}x{height} {result['id']}: clipped X label {label}")
        for left, right in zip(result["labels"], result["labels"][1:]):
            require(left["x"] + left["width"] + 2 <= right["x"], f"{width}x{height} {result['id']}: overlapping X labels {left} / {right}")


def test_mobile_and_motion(browser) -> None:
    original_prefs = api_json("/api/ui/preferences")
    original_o2 = api_json("/api/o2ring/settings")
    restore_o2 = {
        key: original_o2[key]
        for key in ("o2ring_enabled", "o2ring_ble_enabled", "o2ring_auto_connect", "o2ring_auto_sync", "o2ring_auto_match")
        if key in original_o2
    }
    if not original_o2.get("o2ring_enabled"):
        api_json("/api/o2ring/settings", "POST", {**restore_o2, "o2ring_enabled": True})
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        screen={"width": 390, "height": 844},
        is_mobile=True,
        has_touch=True,
        service_workers="block",
    )
    page = context.new_page()
    page.set_default_timeout(12_000)
    install_source_asset_routes(page)
    install_mobile_fixtures(page)
    try:
        open_runtime(page)
        require(page.locator("html").evaluate("node => node.classList.contains('sm-phone-pwa')"), "phone PWA was not detected on first render")
        require(page.locator("html").evaluate("node => node.classList.contains('sm-phone-ui')"), "phone performance mode was not active on first render")
        require(page.locator(".sm-aurora-flow .flow").count() > 0, "decorative SVG line is missing on phone PWA")
        require(page.locator(".sm-aurora-flow .flow").first.evaluate("node => getComputedStyle(node).animationName") == "none", "decorative SVG still animates on phone PWA")
        require(page.locator(".sm-aurora-flow .flow").first.evaluate("node => getComputedStyle(node).filter") == "none", "expensive SVG blur is still active on phone PWA")

        for width, height in ((320, 568), (375, 667), (390, 844), (430, 932), (844, 390)):
            assert_mobile_sidebar(page, width, height)

        page.evaluate("() => document.querySelector('#sidebar [data-page=\"oximetry\"]')?.click()")
        page.wait_for_function("() => document.getElementById('o2rLiveDual')?._smO2Meta?.rows?.length >= 20")
        for width in (320, 375, 390, 430):
            assert_x_axis_labels(page, width, 844)

        page.set_viewport_size({"width": 390, "height": 844})
        page.evaluate("() => { document.documentElement.classList.add('pwa-standalone','sm-phone-pwa'); location.hash='#ai'; }")
        api_json("/api/ui/preferences", "POST", {"ai_luna_visible": False, "ai_milo_visible": False, "ai_prompting_enabled": True})
        reload_runtime(page)
        navigate(page, "ai")
        page.evaluate("() => { state.days=['20260902']; }")
        install_prompt_route(page)
        if page.locator("#aiAnalysisPickerButton").is_visible():
            page.locator("#aiAnalysisPickerButton").click()
            page.locator('[data-ai-mobile-choice="night"]').click()
        else:
            page.locator('[data-ai-analysis="night"]').click()
        page.wait_for_function("() => !document.getElementById('aiPromptModal').classList.contains('hidden')")
        modal = page.locator(".ai-prompt-card").evaluate(
            "node => {const r=node.getBoundingClientRect(),p=node.querySelector('.ai-prompt-content'),buttons=[...node.querySelectorAll('.ai-prompt-actions button')].map(x=>x.getBoundingClientRect().width);return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,viewport:[innerWidth,innerHeight],promptOverflow:getComputedStyle(p).overflowY,buttons}}"
        )
        require(modal["top"] >= 0 and modal["bottom"] <= modal["viewport"][1] and modal["left"] >= 0 and modal["right"] <= modal["viewport"][0], f"prompt modal overflows phone viewport: {modal}")
        require(modal["promptOverflow"] in ("auto", "scroll"), "prompt content is not independently scrollable")
        require(min(modal["buttons"]) >= 100, f"prompt actions are too narrow on phone: {modal['buttons']}")
    finally:
        context.close()
        api_json("/api/o2ring/settings", "POST", restore_o2)
        api_json(
            "/api/ui/preferences",
            "POST",
            {
                "pwa_bottom_nav": original_prefs.get("pwa_bottom_nav") or ["dashboard", "sessions", "charts", "ai", "more"],
                "pwa_bottom_nav_labels": original_prefs.get("pwa_bottom_nav_labels") or {},
                "ai_luna_visible": original_prefs.get("ai_luna_visible", True),
                "ai_milo_visible": original_prefs.get("ai_milo_visible", True),
                "ai_prompting_enabled": original_prefs.get("ai_prompting_enabled", False),
            },
        )

    phone_web = browser.new_context(
        viewport={"width": 390, "height": 844},
        screen={"width": 390, "height": 844},
        is_mobile=True,
        has_touch=True,
        service_workers="block",
    )
    phone_web_page = phone_web.new_page()
    install_source_asset_routes(phone_web_page)
    open_runtime(phone_web_page)
    require(phone_web_page.locator("html").evaluate("node => node.classList.contains('sm-phone-ui')"), "phone web performance mode was not detected")
    require(not phone_web_page.locator("html").evaluate("node => node.classList.contains('sm-phone-pwa')"), "normal phone web was misdetected as installed PWA")
    require(phone_web_page.locator(".sm-aurora-flow .flow").first.evaluate("node => getComputedStyle(node).animationName") == "none", "decorative SVG still animates on phone web")
    require(phone_web_page.locator(".app-shell .topbar").evaluate("node => getComputedStyle(node).backdropFilter") == "none", "mobile topbar still uses a live backdrop blur")
    phone_web_page.evaluate("() => { const shell=document.querySelector('.content-shell'); shell.scrollTop=shell.scrollHeight; shell.scrollTop=0; shell.scrollTop=shell.scrollHeight; }")
    phone_web_page.wait_for_timeout(80)
    require(phone_web_page.locator(".content-shell").evaluate("node => node.scrollTop > 0 || node.scrollHeight <= node.clientHeight"), "fast phone scrolling did not reach rendered content")
    phone_web.close()

    desktop = browser.new_context(viewport={"width": 1440, "height": 900}, service_workers="block")
    desktop_page = desktop.new_page()
    install_source_asset_routes(desktop_page)
    open_runtime(desktop_page)
    desktop_page.wait_for_selector(".sm-aurora-flow .flow", timeout=60_000)
    require(desktop_page.locator(".sm-aurora-flow .flow").first.evaluate("node => getComputedStyle(node).animationName") != "none", "desktop background animation was disabled")
    desktop.close()

    reduced = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce", service_workers="block")
    reduced_page = reduced.new_page()
    install_source_asset_routes(reduced_page)
    open_runtime(reduced_page)
    reduced_page.wait_for_selector(".sm-aurora-flow .flow", timeout=60_000)
    require(reduced_page.locator(".sm-aurora-flow .flow").first.evaluate("node => getComputedStyle(node).animationName") == "none", "prefers-reduced-motion did not stop the background animation")
    reduced.close()


def main() -> int:
    require(EDGE_PATH.is_file(), f"Edge executable missing: {EDGE_PATH}")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=str(EDGE_PATH),
            headless=True,
            args=["--no-first-run", "--disable-background-networking"],
        )
        desktop = browser.new_context(viewport={"width": 1440, "height": 920}, service_workers="block")
        page = desktop.new_page()
        page.set_default_timeout(12_000)
        install_source_asset_routes(page)
        page.on("pageerror", lambda exc: print(f"[v5.3.5 pageerror] {exc}", flush=True))
        page.on("console", lambda msg: print(f"[v5.3.5 console error] {msg.text}", flush=True) if msg.type == "error" else None)
        test_preferences_ai_prompt_and_o2(page, desktop)
        desktop.close()
        test_mobile_and_motion(browser)
        browser.close()
    print("[v5.3.5 feature Edge acceptance] PASS", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
