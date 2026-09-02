from __future__ import annotations

import json
import os
from pathlib import Path
import urllib.request

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


VERSION = "5.3.4"
BASE_URL = os.environ["SLEEPMATE_ACCEPTANCE_URL"].rstrip("/")
EDGE_PATH = Path(os.environ["SLEEPMATE_EDGE_PATH"])


def progress(message: str) -> None:
    print(f"[v5.3.4 Edge acceptance] {message}", flush=True)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def api_json(path: str) -> dict:
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        headers={"Accept": "application/json", "Cache-Control": "no-store"},
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.load(response)


def runtime_snapshot(
    page: Page,
    *,
    page_errors: list[str] | None = None,
    console_errors: list[str] | None = None,
    request_failures: list[str] | None = None,
    http_errors: list[str] | None = None,
) -> dict:
    """Return diagnostics without executing JS in a renderer that may already be hung."""
    try:
        current_url = page.url
    except Exception as exc:  # pragma: no cover - only used for a dead target
        current_url = f"<unavailable: {exc!r}>"
    return {
        "url": current_url,
        "rendererSnapshot": "skipped after readiness timeout to avoid deadlocking on page.evaluate",
        "pageErrors": list(page_errors or []),
        "consoleErrors": list(console_errors or []),
        "requestFailures": list(request_failures or []),
        "httpErrors": list(http_errors or []),
    }


def wait_runtime(
    page: Page,
    *,
    page_errors: list[str] | None = None,
    console_errors: list[str] | None = None,
    request_failures: list[str] | None = None,
    http_errors: list[str] | None = None,
) -> None:
    try:
        page.wait_for_function(
            """() => document.querySelector('.hidden-until-ready')?.classList.contains('ready')
                && window.SleepMateV530
                && window.SleepMateFrontendV534
                && window.SleepMateO2Ring""",
            timeout=20_000,
        )
    except PlaywrightTimeoutError as exc:
        snapshot = runtime_snapshot(
            page,
            page_errors=page_errors,
            console_errors=console_errors,
            request_failures=request_failures,
            http_errors=http_errors,
        )
        raise AssertionError(
            "SleepMate browser runtime did not become ready within the first-load acceptance window.\n"
            + json.dumps(snapshot, ensure_ascii=False, indent=2)
        ) from exc
    page.wait_for_timeout(350)


def navigate(page: Page, name: str) -> None:
    page.evaluate("name => window.navigate(name)", name)
    page.wait_for_timeout(120)


def assert_no_horizontal_overflow(page: Page, label: str) -> None:
    metrics = page.evaluate(
        """() => ({
            viewport: window.innerWidth,
            doc: document.documentElement.scrollWidth,
            body: document.body.scrollWidth
        })"""
    )
    require(
        max(metrics["doc"], metrics["body"]) <= metrics["viewport"] + 3,
        f"{label}: horizontal overflow {metrics}",
    )


def main() -> int:
    require(EDGE_PATH.is_file(), f"Edge executable missing: {EDGE_PATH}")
    page_errors: list[str] = []
    console_errors: list[str] = []
    request_failures: list[str] = []
    http_errors: list[str] = []
    live_stream_requests: list[str] = []

    progress(f"starting packaged Edge against {BASE_URL}")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=str(EDGE_PATH),
            headless=True,
            args=["--no-first-run", "--disable-gpu", "--disable-background-networking"],
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 920},
            service_workers="allow",
        )
        page = context.new_page()
        page.set_default_timeout(5_000)
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        page.on(
            "console",
            lambda msg: console_errors.append(msg.text)
            if msg.type == "error"
            else None,
        )
        page.on(
            "requestfailed",
            lambda req: request_failures.append(
                f"{req.method} {req.url} :: {req.failure or 'request failed'}"
            ),
        )
        page.on(
            "response",
            lambda res: http_errors.append(f"HTTP {res.status} {res.url}")
            if res.status >= 400
            else None,
        )
        page.on(
            "request",
            lambda req: live_stream_requests.append(req.url)
            if "/api/o2ring/live-stream" in req.url
            else None,
        )

        progress("first real browser boot")
        page.goto(f"{BASE_URL}/#dashboard", wait_until="domcontentloaded", timeout=20_000)
        wait_runtime(
            page,
            page_errors=page_errors,
            console_errors=console_errors,
            request_failures=request_failures,
            http_errors=http_errors,
        )
        progress("runtime ready on first load")

        meta = page.locator('meta[name="sleepmate-ui-version"]').get_attribute("content")
        require(meta == VERSION, f"wrong UI generation meta: {meta}")
        require(page.locator("#sidebarVersion").inner_text().strip() == f"v{VERSION}", "stale sidebar version")
        require(page.locator('#sidebar [data-page="oximetry"]').count() == 1, "Oximetria sidebar item missing/duplicated")
        require(page.locator("#page-oximetry").count() == 1, "Oximetria page missing/duplicated")
        require(page.locator("#o2rDailyBtn").count() == 1, "Dashboard Oximetria mode missing/duplicated")
        require(
            page.evaluate("() => window.SleepMateV530.NAV.oximetry_live?.label") == "Élő O₂ monitor",
            "PWA live O2 navigation label missing",
        )

        progress("stale cache purge and first recovery reload")
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
        require(page.locator("#sidebarVersion").inner_text().strip() == f"v{VERSION}", "reload restored stale UI version")

        progress("repeated Dashboard/Oximetria navigation")
        initial_canvas_count = page.locator("#page-oximetry canvas").count()
        for _ in range(8):
            navigate(page, "dashboard")
            page.locator('#sidebar [data-page="oximetry"]').click()
            page.wait_for_function("() => document.querySelector('#page-oximetry')?.classList.contains('active')")
            require(page.locator("#page-oximetry").count() == 1, "Oximetria page duplicated during route switching")
            require(page.locator("#page-oximetry canvas").count() == initial_canvas_count, "O2 chart DOM leaked during route switching")
            navigate(page, "dashboard")

        progress("Focus/All charts/Oximetria repeated mode switching")
        for _ in range(6):
            for control in ("focusViewBtn", "stackViewBtn", "o2rDailyBtn"):
                page.evaluate("id => document.getElementById(id)?.click()", control)
        require(page.locator("#focusViewBtn").inner_text().strip() == "Fókusz nézet", "Focus button text mutated")
        require(page.locator("#stackViewBtn").inner_text().strip() == "Összes grafikon", "All charts button text mutated")
        require(page.locator("#o2rDailyBtn").inner_text().strip() == "Oximetria", "Oximetria mode mutated into navigation/back")

        progress("Oximetria Live/Recordings/Trends repeated switching")
        page.locator('#sidebar [data-page="oximetry"]').click()
        page.wait_for_function("() => document.querySelector('#page-oximetry')?.classList.contains('active')")
        for _ in range(5):
            for tab in ("recordings", "trends", "live"):
                page.locator(f'[data-o2r-tab="{tab}"]').click()
                page.wait_for_timeout(60)
        require(page.locator("#page-oximetry").count() == 1, "Oximetria tab switching duplicated page")
        require(page.locator("#page-oximetry canvas").count() == initial_canvas_count, "Oximetria tab switching leaked charts")

        progress("hidden Live O2 lifecycle")
        page.locator('[data-o2r-tab="live"]').click()
        page.wait_for_timeout(500)
        before_leave = len(live_stream_requests)
        navigate(page, "dashboard")
        page.wait_for_timeout(900)
        require(
            len(live_stream_requests) == before_leave,
            "hidden Dashboard state spawned additional live O2 streams",
        )

        progress("settings hydration and toggle persistence")
        navigate(page, "settings")
        page.wait_for_timeout(500)
        require(page.locator('[data-settings-tab="pwa"]').count() == 0, "legacy separate PWA settings tab returned")
        require(page.locator('[data-settings-tab="push"]').inner_text().strip() == "PWA", "PWA/notification settings are not merged")
        require(page.locator('[data-settings-tab="display"]').inner_text().strip() == "O2Ring", "Megjelenés was not renamed to O2Ring")
        require(page.locator("#frSettingsReopen").count() <= 1, "First-run wizard reopen card duplicated")

        page.locator('[data-settings-tab="display"]').click()
        page.wait_for_timeout(250)
        require(page.locator("#smO2Master").count() == 1, "O2Ring master settings missing/duplicated")
        require(page.locator("#smO2AdvancedV534").count() == 1, "O2Ring advanced settings missing/duplicated")

        auto_match = page.locator("#smO2AutoMatch")
        current = auto_match.is_checked()
        auto_match.set_checked(not current)
        page.wait_for_timeout(450)
        persisted = api_json("/api/o2ring/settings").get("o2ring_auto_match")
        require(bool(persisted) is (not current), "O2 auto-match toggle did not persist on first interaction")
        auto_match.set_checked(current)
        page.wait_for_timeout(450)

        progress("iPhone portrait Oximetria geometry")
        page.set_viewport_size({"width": 390, "height": 844})
        page.locator('#sidebar [data-page="oximetry"]').click(force=True)
        page.locator('[data-o2r-tab="live"]').click()
        page.wait_for_timeout(250)
        assert_no_horizontal_overflow(page, "Oximetria iPhone portrait")
        geometry = page.evaluate(
            """() => {
                const a=document.getElementById('o2rLiveSpo2Chart')?.getBoundingClientRect();
                const b=document.getElementById('o2rLiveHrChart')?.getBoundingClientRect();
                return a&&b?{leftA:a.left,leftB:b.left,widthA:a.width,widthB:b.width}:null;
            }"""
        )
        require(geometry is not None, "mobile live O2 canvases missing")
        require(abs(geometry["leftA"] - geometry["leftB"]) <= 1.5, f"mobile O2 X origins differ: {geometry}")
        require(abs(geometry["widthA"] - geometry["widthB"]) <= 1.5, f"mobile O2 plot widths differ: {geometry}")

        progress("iPhone portrait/landscape O2Ring settings")
        navigate(page, "settings")
        page.locator('[data-settings-tab="display"]').click()
        page.wait_for_timeout(200)
        assert_no_horizontal_overflow(page, "O2Ring settings iPhone portrait")
        columns = page.evaluate(
            """() => getComputedStyle(document.querySelector('.sm-o2-advanced-grid')).gridTemplateColumns"""
        )
        require(" " not in columns.strip(), f"mobile O2 settings are not one-column: {columns}")

        page.set_viewport_size({"width": 844, "height": 390})
        page.wait_for_timeout(120)
        assert_no_horizontal_overflow(page, "O2Ring settings iPhone landscape")

        browser.close()

    require(not page_errors, "browser page errors: " + " | ".join(page_errors))
    require(not console_errors, "browser console errors: " + " | ".join(console_errors))
    require(not request_failures, "browser request failures: " + " | ".join(request_failures))
    require(not http_errors, "browser HTTP errors: " + " | ".join(http_errors))
    progress("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
