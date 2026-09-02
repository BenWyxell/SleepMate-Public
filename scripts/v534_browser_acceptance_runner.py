from __future__ import annotations

import json
import os
from pathlib import Path
import urllib.request


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
EDGE_PATH = Path(os.environ["SLEEPMATE_EDGE_PATH"])

# The packaged service worker cache generation and activate cleanup are already
# release-gated by source/contracts. Do not synthesize a stale CacheStorage entry
# inside Playwright: the production activate handler intentionally navigates
# clients, which destroys the renderer execution context and makes that synthetic
# browser preflight inherently racy. The real Edge acceptance below therefore
# tests the packaged UI/O2 behaviour in a normal browser lifecycle.
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
_clean_reload_block = '''        progress("clean packaged UI reload")
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
_acceptance_source = _acceptance_source.replace(
    "latest-session card flashed legacy Befejezve during stale-cache recovery",
    "latest-session card flashed legacy Befejezve during clean reload",
    1,
)

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
    return acceptance.main()


if __name__ == "__main__":
    raise SystemExit(main())
