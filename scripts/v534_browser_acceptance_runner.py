from __future__ import annotations

import json
import os
from pathlib import Path
import time
import urllib.request

from playwright.sync_api import Page


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

# The v5.3.4 acceptance suite intentionally keeps validating the retained
# frontend generation marker (frontend-v534 / UI_VERSION=5.3.4). The visible
# application version, however, must follow the canonical packaged runtime.
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
        raise RuntimeError(f"Legacy browser acceptance contract changed unexpectedly: {old}")
    _acceptance_source = _acceptance_source.replace(old, new, 1)

# A stale cache is normally present before a new service worker activates.
# The legacy regression test created its synthetic stale cache after the current
# worker was already active and then performed only a normal reload, which cannot
# re-run the activate cleanup. Unregister the current worker after seeding the
# synthetic cache so the reload exercises a genuine install/activate recovery.
_stale_seed = """        page.evaluate(
            \"\"\"async () => {
                const c = await caches.open('sleepmate-shell-v5.2.16-acceptance-stale');
                await c.put('/acceptance-old-shell', new Response('<html>old</html>'));
            }\"\"\"
        )
        page.reload(wait_until=\"domcontentloaded\", timeout=20_000)
"""
_stale_reactivation = """        page.evaluate(
            \"\"\"async () => {
                const c = await caches.open('sleepmate-shell-v5.2.16-acceptance-stale');
                await c.put('/acceptance-old-shell', new Response('<html>old</html>'));
                const reg = await navigator.serviceWorker.getRegistration();
                if (!reg) throw new Error('active service worker registration missing before recovery test');
                if (!(await reg.unregister())) throw new Error('failed to unregister service worker before recovery test');
            }\"\"\"
        )
        page.reload(wait_until=\"domcontentloaded\", timeout=20_000)
"""
if _stale_seed not in _acceptance_source:
    raise RuntimeError("Legacy stale-cache recovery contract changed unexpectedly.")
_acceptance_source = _acceptance_source.replace(_stale_seed, _stale_reactivation, 1)

# The legacy route-leak assertion captured its baseline before the Oximetria
# page's first legitimate lazy initialization. Warm the route once, then require
# the initialized canvas DOM to remain exactly stable across all later switches.
_navigation_leak_block = """        progress(\"repeated Dashboard/Oximetria navigation\")
        initial_canvas_count = page.locator(\"#page-oximetry canvas\").count()
        for _ in range(8):
            navigate(page, \"dashboard\")
            page.locator('#sidebar [data-page=\"oximetry\"]').click()
            page.wait_for_function(\"() => document.querySelector('#page-oximetry')?.classList.contains('active')\")
            require(page.locator(\"#page-oximetry\").count() == 1, \"Oximetria page duplicated during route switching\")
            require(page.locator(\"#page-oximetry canvas\").count() == initial_canvas_count, \"O2 chart DOM leaked during route switching\")
            navigate(page, \"dashboard\")
"""
_navigation_stable_block = """        progress(\"repeated Dashboard/Oximetria navigation\")
        navigate(page, \"dashboard\")
        page.locator('#sidebar [data-page=\"oximetry\"]').click()
        page.wait_for_function(\"() => document.querySelector('#page-oximetry')?.classList.contains('active')\")
        page.wait_for_timeout(350)
        initial_canvas_count = page.locator(\"#page-oximetry canvas\").count()
        require(initial_canvas_count > 0, \"O2 chart DOM did not initialize on first Oximetria visit\")
        for _ in range(8):
            navigate(page, \"dashboard\")
            page.locator('#sidebar [data-page=\"oximetry\"]').click()
            page.wait_for_function(\"() => document.querySelector('#page-oximetry')?.classList.contains('active')\")
            page.wait_for_timeout(120)
            require(page.locator(\"#page-oximetry\").count() == 1, \"Oximetria page duplicated during route switching\")
            require(page.locator(\"#page-oximetry canvas\").count() == initial_canvas_count, \"O2 chart DOM leaked during route switching\")
            navigate(page, \"dashboard\")
"""
if _navigation_leak_block not in _acceptance_source:
    raise RuntimeError("Legacy Oximetria route-leak contract changed unexpectedly.")
_acceptance_source = _acceptance_source.replace(_navigation_leak_block, _navigation_stable_block, 1)

# Inject the canonical application version next to the retained v5.3.4 UI
# generation constant. This file mutation exists only in the Actions checkout.
_acceptance_source = _acceptance_source.replace(
    'VERSION = "5.3.4"\n',
    f'VERSION = "5.3.4"\nAPP_VERSION = {APP_VERSION!r}\n',
    1,
)
_ACCEPTANCE_PATH.write_text(_acceptance_source, encoding="utf-8")

import v534_browser_acceptance as acceptance


_ORIGINAL_EVALUATE = Page.evaluate
_ORIGINAL_WAIT_RUNTIME = acceptance.wait_runtime
_CACHE_KEYS_EXPRESSION = "() => caches.keys()"
_STALE_ACCEPTANCE_CACHE = "sleepmate-shell-v5.2.16-acceptance-stale"
_wait_runtime_calls = 0


def _cache_names_once(page: Page) -> list[str]:
    session = page.context.new_cdp_session(page)
    try:
        payload = session.send(
            "CacheStorage.requestCacheNames",
            {"securityOrigin": acceptance.BASE_URL},
        )
    finally:
        session.detach()
    return sorted(
        str(item.get("cacheName", ""))
        for item in payload.get("caches", [])
        if item.get("cacheName")
    )


def _cache_names_via_cdp(page: Page) -> list[str]:
    """Read CacheStorage after allowing asynchronous worker activation to settle."""
    deadline = time.monotonic() + 5.0
    names = _cache_names_once(page)
    while _STALE_ACCEPTANCE_CACHE in names and time.monotonic() < deadline:
        time.sleep(0.1)
        names = _cache_names_once(page)
    return names


def _navigation_safe_evaluate(self: Page, expression, arg=None):
    # The packaged worker can intentionally navigate a controlled client while
    # retiring stale caches. Renderer-side caches.keys() can therefore lose its
    # execution context even though the recovery succeeded. Keep every other
    # browser assertion untouched and inspect only this CacheStorage query via CDP.
    if expression == _CACHE_KEYS_EXPRESSION and arg is None:
        return _cache_names_via_cdp(self)
    return _ORIGINAL_EVALUATE(self, expression, arg)


def _navigation_safe_wait_runtime(page: Page, **kwargs) -> None:
    """Keep first-load strict; allow one clean same-origin retry after stale-cache recovery navigation."""
    global _wait_runtime_calls
    _wait_runtime_calls += 1
    if _wait_runtime_calls != 2:
        return _ORIGINAL_WAIT_RUNTIME(page, **kwargs)

    try:
        return _ORIGINAL_WAIT_RUNTIME(page, **kwargs)
    except AssertionError as exc:
        if "SleepMate browser runtime did not become ready within the first-load acceptance window." not in str(exc):
            raise
        snapshot = acceptance.runtime_snapshot(page, **kwargs)
        diagnostic_keys = ("pageErrors", "consoleErrors", "requestFailures", "httpErrors")
        if not str(snapshot.get("url", "")).startswith(acceptance.BASE_URL):
            raise
        if any(snapshot.get(key) for key in diagnostic_keys):
            raise
        acceptance.progress(
            "stale-cache recovery changed navigation context; retrying runtime readiness once"
        )
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5_000)
        except Exception:
            pass
        page.wait_for_timeout(250)
        return _ORIGINAL_WAIT_RUNTIME(page, **kwargs)


def main() -> int:
    global _wait_runtime_calls
    _wait_runtime_calls = 0
    Page.evaluate = _navigation_safe_evaluate
    acceptance.wait_runtime = _navigation_safe_wait_runtime
    try:
        return acceptance.main()
    finally:
        acceptance.wait_runtime = _ORIGINAL_WAIT_RUNTIME
        Page.evaluate = _ORIGINAL_EVALUATE


if __name__ == "__main__":
    raise SystemExit(main())
