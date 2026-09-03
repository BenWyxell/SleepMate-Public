from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path
import time
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
        f"{BASE_URL}{path}", data=body, method=method,
        headers={"Accept": "application/json", "Content-Type": "application/json", "Cache-Control": "no-store"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def install_source_routes(page: Page) -> None:
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


def standalone_override(page: Page) -> None:
    page.add_init_script(
        """
        Object.defineProperty(navigator,'standalone',{configurable:true,get:()=>true});
        const nativeMatchMedia=window.matchMedia.bind(window);
        window.matchMedia=query=>query.includes('display-mode: standalone')
          ? {matches:true,media:query,onchange:null,addListener(){},removeListener(){},addEventListener(){},removeEventListener(){},dispatchEvent(){return true}}
          : nativeMatchMedia(query);
        """
    )


def open_phone(page: Page, fragment: str = "dashboard") -> float:
    started = time.perf_counter()
    page.goto(f"{BASE_URL}/#{fragment}", wait_until="domcontentloaded", timeout=45_000)
    page.wait_for_function(
        "() => document.querySelector('.hidden-until-ready')?.classList.contains('ready') && window.SleepMateV530",
        timeout=35_000,
    )
    return time.perf_counter() - started


def assert_mobile_rendering(browser, standalone: bool) -> None:
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, screen={"width": 390, "height": 844},
        is_mobile=True, has_touch=True, service_workers="block",
    )
    page = context.new_page()
    page.set_default_timeout(12_000)
    if standalone:
        standalone_override(page)
    install_source_routes(page)
    elapsed = open_phone(page)
    mode = "PWA" if standalone else "web"
    require(elapsed < 12, f"phone {mode} startup exceeded 12 seconds: {elapsed:.2f}s")
    print(f"[phone {mode} startup] {elapsed:.2f}s", flush=True)
    classes = page.locator("html").get_attribute("class") or ""
    require("sm-phone-ui" in classes, f"phone {mode} missed first-paint performance mode: {classes}")
    require(("sm-phone-pwa" in classes) == standalone, f"phone {mode} standalone detection is wrong: {classes}")
    require(page.locator(".sm-aurora-flow .flow").count() > 0, f"phone {mode} lost the decorative SVG")
    require(page.locator(".sm-aurora-flow .flow").first.evaluate("n => getComputedStyle(n).animationName") == "none", f"phone {mode} SVG still animates")
    require(page.locator(".sm-aurora-flow .flow").first.evaluate("n => getComputedStyle(n).filter") == "none", f"phone {mode} SVG filter is still expensive")
    require(page.locator(".app-shell .topbar").evaluate("n => getComputedStyle(n).backdropFilter") == "none", f"phone {mode} keeps backdrop blur")
    page.evaluate(
        """() => {const shell=document.querySelector('.content-shell');
          for(let i=0;i<12;i++)shell.scrollTop=i%2?shell.scrollHeight:0;
          shell.scrollTop=shell.scrollHeight;}"""
    )
    page.wait_for_timeout(80)
    scroll = page.locator(".content-shell").evaluate("n => ({top:n.scrollTop,max:n.scrollHeight-n.clientHeight})")
    require(scroll["max"] <= 0 or scroll["top"] >= scroll["max"] - 2, f"phone {mode} rapid scroll did not catch up: {scroll}")
    context.close()


def assert_sleepsync_schedule(browser) -> None:
    original = api_json("/api/sleepsync/settings")
    restore = {key: original.get(key) for key in ("auto_sync_enabled", "auto_sync_mode", "schedule_days", "schedule_times")}
    seeded = {
        "auto_sync_enabled": True, "auto_sync_mode": "scheduled",
        "schedule_days": ["monday", "wednesday", "friday"], "schedule_times": ["06:45", "21:15"],
    }
    api_json("/api/sleepsync/settings", "POST", seeded)
    context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, service_workers="block")
    page = context.new_page()
    page.set_default_timeout(12_000)
    install_source_routes(page)
    try:
        open_phone(page, "sleepsync")
        page.locator('[data-sleepsync-tab="sync"]').click()
        page.wait_for_function("() => document.querySelectorAll('.ssScheduleTime').length === 2")
        summary = (page.locator("#ssCurrentSchedule").text_content() or "").strip()
        require("Hétfő" in summary and "Szerda" in summary and "Péntek" in summary, f"saved days are missing: {summary}")
        require("06:45" in summary and "21:15" in summary, f"saved times are missing: {summary}")
        checked = page.locator('#ssScheduleDays [data-day]:checked').evaluate_all("nodes => nodes.map(n=>n.dataset.day)")
        times = page.locator(".ssScheduleTime").evaluate_all("nodes => nodes.map(n=>n.value)")
        require(checked == seeded["schedule_days"], f"saved day controls were not hydrated: {checked}")
        require(times == seeded["schedule_times"], f"saved time controls were not hydrated: {times}")

        page.locator('.ssScheduleTime').first.fill("07:10")
        page.locator('#ssScheduleDays [data-day="tuesday"]').check()
        page.locator('[data-sleepsync-panel="sync"] [data-ss-action="save-settings"]').click()
        page.wait_for_function("() => document.getElementById('ssSettingsSaveStatus')?.textContent.includes('mentve')")
        try:
            page.reload(wait_until="domcontentloaded", timeout=45_000)
        except PlaywrightTimeoutError:
            # The source backend may keep a parallel first-data request open;
            # application readiness below is the relevant reload boundary.
            pass
        page.wait_for_function("() => window.SleepMateV530 && document.querySelector('.hidden-until-ready')?.classList.contains('ready')")
        page.locator('[data-sleepsync-tab="sync"]').click()
        page.wait_for_function("() => document.querySelector('.ssScheduleTime')?.value === '07:10'")
        summary = (page.locator("#ssCurrentSchedule").text_content() or "").strip()
        require("Kedd" in summary and "07:10" in summary and "21:15" in summary, f"edited schedule did not survive reload: {summary}")
    finally:
        context.close()
        api_json("/api/sleepsync/settings", "POST", restore)


def main() -> int:
    require(EDGE_PATH.is_file(), f"Edge executable missing: {EDGE_PATH}")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=str(EDGE_PATH), headless=True, args=["--no-first-run", "--disable-background-networking"])
        assert_mobile_rendering(browser, standalone=False)
        assert_mobile_rendering(browser, standalone=True)
        assert_sleepsync_schedule(browser)
        browser.close()
    print("[mobile performance + SleepSync acceptance] PASS", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
