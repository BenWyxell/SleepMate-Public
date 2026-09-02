from __future__ import annotations

import json
import os
from pathlib import Path
import time
import urllib.request

from playwright.sync_api import sync_playwright


def _runtime_app_version() -> str:
    base_url = os.environ["SLEEPMATE_ACCEPTANCE_URL"].rstrip("/")
    req = urllib.request.Request(
        f"{base_url}/api/version",
        headers={"Accept": "application/json", "Cache-Control": "no-store"},
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        payload = json.load(response)
    version = str(payload.get("version") or "").strip()
    if not version:
        raise RuntimeError("Packaged runtime did not report a canonical application version.")
    return version


APP_VERSION = _runtime_app_version()
BASE_URL = os.environ["SLEEPMATE_ACCEPTANCE_URL"].rstrip("/")
EDGE_PATH = Path(os.environ["SLEEPMATE_EDGE_PATH"])
STALE_CACHE = "sleepmate-shell-v5.2.16-acceptance-stale"
CURRENT_SHELL_CACHE = "sleepmate-shell-v5.3.5-refactor"


def _progress(message: str) -> None:
    print(f"[v5.3.5 Edge acceptance runner] {message}", flush=True)


def _verify_service_worker_recovery() -> None:
    """Exercise real stale-cache cleanup without racing the full SleepMate UI.

    The production worker intentionally navigates controlled windows after deleting
    stale caches. Running that recovery inside the long UI acceptance makes the
    browser test race its own reload/navigation. A minimal same-origin document in
    an isolated browser context verifies the real install/activate/cache cleanup,
    then the UI suite starts from a completely clean context.
    """
    _progress("service-worker stale-cache recovery preflight")
    token = str(int(time.time() * 1000))
    last_names: list[str] = []
    last_error = ""

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=str(EDGE_PATH),
            headless=True,
            args=["--no-first-run", "--disable-gpu", "--disable-background-networking"],
        )
        context = browser.new_context(service_workers="allow")
        page = context.new_page()
        page.set_default_timeout(5_000)
        page.goto(f"{BASE_URL}/manifest.webmanifest", wait_until="domcontentloaded", timeout=20_000)

        page.evaluate(
            """async stale => {
                const registrations = await navigator.serviceWorker.getRegistrations();
                await Promise.all(registrations.map(reg => reg.unregister()));
                for (const key of await caches.keys()) await caches.delete(key);
                const cache = await caches.open(stale);
                await cache.put('/acceptance-old-shell', new Response('<html>old</html>'));
            }""",
            STALE_CACHE,
        )
        seeded = page.evaluate("() => caches.keys()")
        if STALE_CACHE not in seeded:
            raise AssertionError(f"failed to seed stale PWA cache: {seeded}")

        # Do not await activation in this renderer: the production activate handler
        # is allowed to navigate controlled clients after cleanup. Fire registration
        # and observe the resulting cache state from the minimal document instead.
        page.evaluate(
            """token => {
                window.__smAcceptanceSwError = '';
                navigator.serviceWorker.register(
                    `/service-worker.js?acceptance-recovery=${encodeURIComponent(token)}`,
                    {scope:'/', updateViaCache:'none'}
                ).catch(err => { window.__smAcceptanceSwError = String(err); });
            }""",
            token,
        )

        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            try:
                last_names = list(page.evaluate("() => caches.keys()") or [])
                last_error = str(page.evaluate("() => window.__smAcceptanceSwError || ''") or "")
                if STALE_CACHE not in last_names and CURRENT_SHELL_CACHE in last_names:
                    break
            except Exception as exc:
                # One renderer replacement is expected when activate() calls
                # client.navigate(client.url). Any persistent failure is caught by
                # the bounded deadline and diagnostics below.
                last_error = repr(exc)
            time.sleep(0.15)
        else:
            raise AssertionError(
                "service-worker recovery did not settle within 20s; "
                f"caches={last_names!r}; error={last_error!r}"
            )

        if STALE_CACHE in last_names:
            raise AssertionError(f"stale PWA shell survived service-worker activation: {last_names}")
        if CURRENT_SHELL_CACHE not in last_names:
            raise AssertionError(f"current PWA shell cache was not created: {last_names}")

        # Let any worker-triggered client navigation settle, then prove there is an
        # active registration. This is deliberately independent from the UI suite.
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5_000)
        except Exception:
            pass
        active_url = ""
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            try:
                active_url = str(
                    page.evaluate(
                        """async () => {
                            const reg = await navigator.serviceWorker.getRegistration('/');
                            return reg?.active?.scriptURL || '';
                        }"""
                    )
                    or ""
                )
                if active_url:
                    break
            except Exception:
                pass
            time.sleep(0.15)
        if not active_url:
            raise AssertionError("service-worker recovery finished without an active registration")

        context.close()
        browser.close()

    _progress(f"service-worker recovery PASS ({last_names})")


# Keep the retained v5.3.4 frontend-generation suite, but align only the pieces
# whose semantics differ in v5.3.5. The long UI test no longer performs synthetic
# service-worker replacement; that is verified above in its own browser context.
_ACCEPTANCE_PATH = Path(__file__).with_name("v534_browser_acceptance.py")
_acceptance_source = _ACCEPTANCE_PATH.read_text(encoding="utf-8")

_sidebar_expectations = (
    (
        'require(page.locator("#sidebarVersion").inner_text().strip() == f"v{VERSION}", "stale sidebar version")',
        'require(page.locator("#sidebarVersion").inner_text().strip() == f"v{APP_VERSION}", "stale sidebar version")',
    ),
    (
        'require(page.locator("#sidebarVersion").inner_text().strip() == f"v{VERSION}", "reload restored stale UI version")',
        'require(page.locator("#sidebarVersion").inner_text().strip() == f"v{APP_VERSION}", "reload restored stale UI version")',
    ),
)
for old, new in _sidebar_expectations:
    if old not in _acceptance_source:
        raise RuntimeError(f"Legacy browser acceptance version contract changed unexpectedly: {old}")
    _acceptance_source = _acceptance_source.replace(old, new, 1)

_recovery_block = '''        progress("stale cache purge and first recovery reload")
        page.evaluate(
            """async () => {
                const c = await caches.open('sleepmate-shell-v5.2.16-acceptance-stale');
                await c.put('/acceptance-old-shell', new Response('<html>old</html>'));
            }"""
        )
        page.reload(wait_until="domcontentloaded", timeout=20_000)
        wait_runtime(
            page,
            page_errors=page_errors,
            console_errors=console_errors,
            request_failures=request_failures,
            http_errors=http_errors,
        )
        stale = page.evaluate("() => caches.keys()")
        require(
            "sleepmate-shell-v5.2.16-acceptance-stale" not in stale,
            f"stale PWA shell survived first recovery reload: {stale}",
        )
'''
_clean_reload_block = '''        progress("clean UI reload after isolated service-worker recovery")
        page.reload(wait_until="domcontentloaded", timeout=20_000)
        wait_runtime(
            page,
            page_errors=page_errors,
            console_errors=console_errors,
            request_failures=request_failures,
            http_errors=http_errors,
        )
'''
if _recovery_block not in _acceptance_source:
    raise RuntimeError("Legacy stale-cache browser recovery block changed unexpectedly.")
_acceptance_source = _acceptance_source.replace(_recovery_block, _clean_reload_block, 1)

_navigation_leak_block = '''        progress("repeated Dashboard/Oximetria navigation")
        initial_canvas_count = page.locator("#page-oximetry canvas").count()
        for _ in range(8):
            navigate(page, "dashboard")
            page.locator('#sidebar [data-page="oximetry"]').click()
            page.wait_for_function("() => document.querySelector('#page-oximetry')?.classList.contains('active')")
            require(page.locator("#page-oximetry").count() == 1, "Oximetria page duplicated during route switching")
            require(page.locator("#page-oximetry canvas").count() == initial_canvas_count, "O2 chart DOM leaked during route switching")
            navigate(page, "dashboard")
'''
_navigation_stable_block = '''        progress("repeated Dashboard/Oximetria navigation")
        # The Oximetria page owns persistent canvases created by its first normal
        # route initialization. Warm that route once, then enforce exact DOM
        # stability across subsequent switches; only post-initialization growth is
        # a leak.
        navigate(page, "dashboard")
        page.locator('#sidebar [data-page="oximetry"]').click()
        page.wait_for_function("() => document.querySelector('#page-oximetry')?.classList.contains('active')")
        page.wait_for_timeout(350)
        initial_canvas_count = page.locator("#page-oximetry canvas").count()
        require(initial_canvas_count > 0, "O2 chart DOM did not initialize on first Oximetria visit")
        for _ in range(8):
            navigate(page, "dashboard")
            page.locator('#sidebar [data-page="oximetry"]').click()
            page.wait_for_function("() => document.querySelector('#page-oximetry')?.classList.contains('active')")
            page.wait_for_timeout(120)
            require(page.locator("#page-oximetry").count() == 1, "Oximetria page duplicated during route switching")
            require(page.locator("#page-oximetry canvas").count() == initial_canvas_count, "O2 chart DOM leaked during route switching")
            navigate(page, "dashboard")
'''
if _navigation_leak_block not in _acceptance_source:
    raise RuntimeError("Legacy Oximetria route-leak contract changed unexpectedly.")
_acceptance_source = _acceptance_source.replace(_navigation_leak_block, _navigation_stable_block, 1)

_acceptance_source = _acceptance_source.replace(
    'VERSION = "5.3.4"\n',
    f'VERSION = "5.3.4"\nAPP_VERSION = {APP_VERSION!r}\n',
    1,
)
_ACCEPTANCE_PATH.write_text(_acceptance_source, encoding="utf-8")

import v534_browser_acceptance as acceptance


def main() -> int:
    if not EDGE_PATH.is_file():
        raise AssertionError(f"Edge executable missing: {EDGE_PATH}")
    _verify_service_worker_recovery()
    return acceptance.main()


if __name__ == "__main__":
    raise SystemExit(main())
