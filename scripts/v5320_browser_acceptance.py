from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

from playwright.sync_api import BrowserContext, Page, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
RELEASE = "5.3.27"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_backend(port: int) -> None:
    deadline = time.monotonic() + 75
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/version", timeout=1) as response:
                payload = json.load(response)
            if payload.get("version") != RELEASE:
                raise AssertionError(f"backend version {payload.get('version')} != {RELEASE}")
            return
        except Exception as exc:
            last_error = exc
            time.sleep(0.2)
    raise AssertionError(f"backend {RELEASE} did not become ready: {last_error}")


def start_backend(state: Path, port: int) -> subprocess.Popen[bytes]:
    env = os.environ.copy()
    env["SLEEPMATE_STATE_DIR"] = str(state)
    env["PYTHONUNBUFFERED"] = "1"
    log_path = state / "backend.log"
    with log_path.open("ab") as log:
        process = subprocess.Popen(
            [sys.executable, "sleepmate_main.py", "--backend", "--host", "127.0.0.1", "--port", str(port), "--no-browser"],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    process.sleepmate_log = log_path  # type: ignore[attr-defined]
    try:
        wait_backend(port)
    except Exception:
        process.terminate()
        process.wait(timeout=10)
        raise
    return process


def stop_backend(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def make_state(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "config.json").write_text(
        json.dumps(
            {
                "o2ring_enabled": True,
                "o2ring_ble_enabled": False,
                "o2ring_auto_connect": False,
                "o2ring_auto_sync": False,
                "update_auto_check": False,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    private = path / "private"
    private.mkdir(parents=True, exist_ok=True)
    (private / "onboarding.json").write_text(
        json.dumps(
            {
                "version": 1,
                "completed": True,
                "completed_at": "acceptance-fixture",
                "last_step": 6,
                "choices": {},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def launch_context(playwright, profile: Path, browser_executable: Path) -> BrowserContext:
    return playwright.chromium.launch_persistent_context(
        str(profile),
        executable_path=str(browser_executable),
        headless=True,
        service_workers="allow",
        args=["--no-first-run", "--disable-features=msEdgeFirstRunExperience"],
    )


def monitor_page(page: Page) -> list[str]:
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(f"pageerror: {error}"))
    page.on("requestfailed", lambda request: errors.append(f"requestfailed: {request.url} {request.failure}"))
    page.on("console", lambda message: errors.append(f"console: {message.text}") if message.type == "error" else None)
    return errors


def assert_o2_ui(page: Page, errors: list[str], backend_log: Path) -> None:
    page.wait_for_function(
        "expected => document.querySelector('meta[name=\"sleepmate-release-version\"]')?.content === expected",
        arg=RELEASE,
        timeout=20_000,
    )
    nav = page.locator('#sidebar [data-page="oximetry"]')
    try:
        nav.wait_for(state="visible", timeout=15_000)
    except Exception as exc:
        diagnostics = page.evaluate(
            """() => ({scripts:[...document.scripts].map(s=>s.src||s.id),
              o2State:window.SleepMateV530?.o2State?.(),bootComplete:window.__sleepmateBootComplete,
              hasCore:typeof window.renderBottomNav,hasO2:!!window.SleepMateO2Ring,
              body:document.body?.innerText?.slice(0,500)})"""
        )
        server = backend_log.read_text(encoding="utf-8", errors="replace")[-6000:]
        raise AssertionError(f"Oximetria navigation missing; errors={errors}; diagnostics={diagnostics}; backend={server}") from exc
    assert nav.count() == 1, "Oximetria navigation is duplicated or missing"
    nav.click()
    page.locator("#page-oximetry").wait_for(state="visible", timeout=10_000)
    for selector in ("#o2rLiveDual", "#o2rLiveSpo2Chart", "#o2rLiveHrChart"):
        canvas = page.locator(selector)
        canvas.wait_for(state="visible", timeout=10_000)
        drawn = canvas.evaluate(
            "c => c.width > 0 && c.height > 0 && c.getContext('2d').getImageData(0,0,c.width,c.height).data.some(v => v !== 0)"
        )
        assert drawn, f"Oximetry visualization was not drawn: {selector}"

    page.locator('#sidebar [data-page="settings"]').click()
    page.locator('[data-settings-tab="display"]').click()
    for selector in ("#smO2Master", "#smO2QuickBar", "#smO2AdvancedV534"):
        page.locator(selector).wait_for(state="visible", timeout=10_000)
    content = page.locator('[data-settings-panel="display"]').inner_text().strip()
    assert "O2Ring integráció" in content and "O2Ring részletes beállítások" in content
    assert len(content) > 200, "Settings -> O2Ring rendered an empty/incomplete panel"
    assert not page.locator("#startupSplash").is_visible()
    remote_requests = page.evaluate(
        "() => performance.getEntriesByType('resource').filter(x => new URL(x.name).pathname === '/api/remote/status').length"
    )
    assert remote_requests == 0, "startup probed slow remote-access tools before the remote settings panel was opened"


def assert_current_pwa(page: Page, backend_log: Path) -> None:
    deadline = time.monotonic() + 45
    state: dict = {}
    while time.monotonic() < deadline:
        state = page.evaluate(
            """async () => {const r=await navigator.serviceWorker.getRegistration();return {
              caches:await caches.keys(),controller:navigator.serviceWorker.controller?.state||null,
              active:r?.active?.state,waiting:r?.waiting?.state,installing:r?.installing?.state,
              readyState:document.readyState,registrationStarted:typeof pwaRegistrationStarted==='undefined'?null:pwaRegistrationStarted,
              resources:performance.getEntriesByType('resource').filter(x=>x.duration>5000).map(x=>({name:x.name,duration:x.duration,transferSize:x.transferSize}))};}"""
        )
        if "sleepmate-shell-v5.3.27" in state["caches"] and state["active"] == "activated":
            break
        page.wait_for_timeout(200)
    else:
        promise_state = page.evaluate(
            """async () => Promise.race([
              Promise.resolve(window.__sleepmatePwaRegistrationPromise).then(
                r => ({settled:'resolved', scope:r?.scope||null}),
                e => ({settled:'rejected', error:String(e), name:e?.name||null})
              ),
              new Promise(resolve => setTimeout(() => resolve({settled:'pending'}), 1000))
            ])"""
        )
        diagnostics = page.evaluate(
            """async () => ({
              href:location.href,isSecureContext,serviceWorkerSupported:'serviceWorker' in navigator,
              registrations:(await navigator.serviceWorker.getRegistrations()).map(r=>({scope:r.scope,active:r.active?.state,waiting:r.waiting?.state,installing:r.installing?.state})),
              promise:window.__sleepmatePwaRegistrationPromise ? 'present' : 'missing',
              installError:window.__sleepmatePwaInstallError||null
            })"""
        )
        server = backend_log.read_text(encoding="utf-8", errors="replace")[-12000:]
        raise AssertionError(
            f"current PWA did not install cleanly: state={state}; promise={promise_state}; "
            f"diagnostics={diagnostics}; backend={server}"
        )
    assert not any("5.3.19" in key for key in state["caches"]), state


def open_and_assert(context: BrowserContext, url: str, backend_log: Path) -> None:
    page = context.pages[0] if context.pages else context.new_page()
    errors = monitor_page(page)
    page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    assert_o2_ui(page, errors, backend_log)
    assert_current_pwa(page, backend_log)
    unexpected = [item for item in errors if "/equipment-image" not in item]
    assert not unexpected, unexpected


def main() -> int:
    parser = argparse.ArgumentParser(description="SleepMate 5.3.27 browser/PWA acceptance")
    parser.add_argument("--browser", default=r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    args = parser.parse_args()
    browser_executable = Path(args.browser)
    if not browser_executable.is_file():
        raise SystemExit(f"Browser executable not found: {browser_executable}")

    with tempfile.TemporaryDirectory(prefix="sleepmate-v5320-browser-", ignore_cleanup_errors=True) as temp_name:
        temp = Path(temp_name)
        state = temp / "state"
        profile = temp / "profile"
        make_state(state)
        port = free_port()
        url = f"http://127.0.0.1:{port}/"

        with sync_playwright() as playwright:
            process = start_backend(state, port)
            try:
                context = launch_context(playwright, profile, browser_executable)
                try:
                    open_and_assert(context, url, process.sleepmate_log)  # type: ignore[attr-defined]
                finally:
                    context.close()
            finally:
                stop_backend(process)

            process = start_backend(state, port)
            try:
                context = launch_context(playwright, profile, browser_executable)
                try:
                    open_and_assert(context, url, process.sleepmate_log)  # type: ignore[attr-defined]
                finally:
                    context.close()
            finally:
                stop_backend(process)

    print("SleepMate 5.3.27 browser/PWA acceptance OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
