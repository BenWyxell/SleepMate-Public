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


def install_o2_acceptance_fixtures(page: Page) -> None:
    """Inject deterministic O2 data while keeping the packaged frontend and real SSE lifecycle."""
    page.add_init_script(
        """
        (() => {
          const now = Math.floor(Date.now()/1000);
          const summary = (avg,min,hr,t90=0,odi3=1.2,odi4=.6) => ({
            spo2_average:avg, spo2_minimum:min, heart_rate_average:hr,
            t90_seconds:t90, odi3, odi4, coverage_percent:100
          });
          const liveRows = [
            {timestamp:now-60,spo2:97,heart_rate:62,motion:0},
            {timestamp:now-40,spo2:96,heart_rate:64,motion:0},
            {timestamp:now-20,spo2:95,heart_rate:66,motion:1},
          ];
          const recSamples = [
            {timestamp:now-3600,spo2:97,heart_rate:61,motion:0},
            {timestamp:now-3540,spo2:96,heart_rate:63,motion:0},
            {timestamp:now-3480,spo2:94,heart_rate:67,motion:1},
            {timestamp:now-3420,spo2:95,heart_rate:65,motion:0},
          ];
          window.__smAcceptanceO2 = {
            liveRows,
            bufferCalls:0,
            trendRows:[0,1,2,3,4].map(i => ({
              start_ts:now-(4-i)*86400,
              summary:summary(96.2+i*.15,91+i%2,63+i,30+i*8,1.0+i*.2,.5+i*.1)
            })),
            recordings:[{
              recording_id:'acceptance-recording', source_name:'acceptance.vld',
              start_ts:now-3600, end_ts:now-3420,
              summary:summary(95.5,94,64,0,1.1,.4)
            }],
            recording:{
              recording_id:'acceptance-recording', source_name:'acceptance.vld',
              start_ts:now-3600, end_ts:now-3420,
              summary:summary(95.5,94,64,0,1.1,.4), samples:recSamples
            }
          };
          const nativeFetch = window.fetch.bind(window);
          const jsonResponse = value => Promise.resolve(new Response(JSON.stringify(value), {
            status:200, headers:{'Content-Type':'application/json'}
          }));
          window.fetch = function(input, init) {
            let url;
            try {
              const raw = typeof input === 'string' ? input : input?.url;
              url = new URL(raw, location.href);
            } catch (_) {
              return nativeFetch(input, init);
            }
            const f = window.__smAcceptanceO2;
            if (url.pathname === '/api/o2ring/live-buffer') {
              f.bufferCalls++;
              const since = Number(url.searchParams.get('since') || 0);
              const rows = f.liveRows.filter(r => r.timestamp > since);
              return jsonResponse({rows,count:rows.length,points:f.liveRows.length,last_timestamp:f.liveRows.at(-1)?.timestamp||null});
            }
            if (url.pathname === '/api/o2ring/trends') return jsonResponse({rows:f.trendRows});
            if (url.pathname === '/api/o2ring/recordings') return jsonResponse({rows:f.recordings});
            if (url.pathname === '/api/o2ring/recording') return jsonResponse(f.recording);
            return nativeFetch(input, init);
          };
        })();
        """
    )


def hover_canvas(page: Page, canvas_id: str, expected_labels: tuple[str, ...]) -> str:
    canvas = page.locator(f"#{canvas_id}")
    box = canvas.bounding_box()
    require(box is not None and box["width"] > 40 and box["height"] > 40, f"{canvas_id}: canvas is not visible")
    page.mouse.move(box["x"] + box["width"] * 0.68, box["y"] + box["height"] * 0.46)
    page.wait_for_timeout(120)
    text = page.evaluate(
        """id => document.getElementById(id)?.parentElement?.querySelector('.sm-o2-tooltip.show')?.innerText || ''""",
        canvas_id,
    )
    require(bool(text.strip()), f"{canvas_id}: hover tooltip/crosshair did not appear")
    first = text.splitlines()[0] if text.splitlines() else ""
    require(first.count(":") >= 2, f"{canvas_id}: tooltip does not contain exact HH:MM:SS time: {text!r}")
    for label in expected_labels:
        require(label in text, f"{canvas_id}: tooltip is missing {label}: {text!r}")
    return text


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
        install_o2_acceptance_fixtures(page)
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

        progress("Live O2 only runs while visible and batch-refills on return")
        page.locator('[data-o2r-tab="live"]').click()
        page.wait_for_function("() => window.__smAcceptanceO2.bufferCalls > 0")
        page.wait_for_function("() => document.getElementById('o2rLiveDual')?._smO2Meta?.rows?.length >= 3")
        page.wait_for_timeout(300)
        require(len(live_stream_requests) >= 1, "visible Oximetria Live did not open a real SSE stream")
        before_streams = len(live_stream_requests)
        before_buffers = page.evaluate("() => window.__smAcceptanceO2.bufferCalls")
        latest_before = page.evaluate("() => window.__smAcceptanceO2.liveRows.at(-1).timestamp")

        navigate(page, "dashboard")
        page.evaluate(
            """() => {
              const f=window.__smAcceptanceO2, t=f.liveRows.at(-1).timestamp;
              f.liveRows.push(
                {timestamp:t+5,spo2:94,heart_rate:68,motion:0},
                {timestamp:t+10,spo2:96,heart_rate:65,motion:0}
              );
            }"""
        )
        page.wait_for_timeout(900)
        require(len(live_stream_requests) == before_streams, "hidden Dashboard state spawned additional live O2 streams")
        require(
            page.evaluate("() => window.__smAcceptanceO2.bufferCalls") == before_buffers,
            "hidden Dashboard state performed live-buffer refills/repaints",
        )

        page.locator('#sidebar [data-page="oximetry"]').click()
        page.wait_for_function("() => document.querySelector('#page-oximetry')?.classList.contains('active')")
        page.wait_for_function("n => window.__smAcceptanceO2.bufferCalls > n", before_buffers)
        page.wait_for_function(
            "t => document.getElementById('o2rLiveDual')?._smO2Meta?.rows?.some(r => r.timestamp > t)",
            latest_before,
        )
        page.wait_for_timeout(300)
        require(len(live_stream_requests) > before_streams, "returning to Oximetria Live did not reopen the SSE stream")

        progress("exact O2 crosshair tooltips and live zoom")
        hover_canvas(page, "o2rLiveDual", ("SpO₂", "Pulzus"))
        hover_canvas(page, "o2rLiveSpo2Chart", ("SpO₂",))
        hover_canvas(page, "o2rLiveHrChart", ("Pulzus",))
        live_span = page.evaluate("() => {const m=document.getElementById('o2rLiveDual')._smO2Meta;return m.b-m.a}")
        live_box = page.locator("#o2rLiveDual").bounding_box()
        require(live_box is not None, "live dual canvas disappeared before zoom")
        page.mouse.move(live_box["x"] + live_box["width"] * .55, live_box["y"] + live_box["height"] * .5)
        page.keyboard.down("Shift")
        page.mouse.wheel(0, -600)
        page.keyboard.up("Shift")
        page.wait_for_timeout(220)
        zoomed_span = page.evaluate("() => {const m=document.getElementById('o2rLiveDual')._smO2Meta;return m.b-m.a}")
        require(zoomed_span < live_span, f"live O2 wheel zoom did not shrink the time range: {live_span} -> {zoomed_span}")
        page.locator("#o2rLiveDual").dblclick(position={"x": int(live_box["width"]*.5), "y": int(live_box["height"]*.5)})
        page.wait_for_timeout(120)

        progress("closed recording crosshair tooltips")
        page.locator('[data-o2r-tab="recordings"]').click()
        page.wait_for_function("() => document.querySelectorAll('#o2rRecordingList [data-rid]').length > 0")
        page.locator('#o2rRecordingList [data-rid="acceptance-recording"]').click()
        page.wait_for_function("() => document.getElementById('o2rRecDual')?._smO2Meta?.rows?.length >= 4")
        hover_canvas(page, "o2rRecDual", ("SpO₂", "Pulzus"))
        hover_canvas(page, "o2rRecSpo2", ("SpO₂",))
        hover_canvas(page, "o2rRecHr", ("Pulzus",))

        progress("O2 trend crosshair tooltips")
        page.locator('[data-o2r-tab="trends"]').click()
        page.wait_for_function("() => document.getElementById('o2rTrendSpo2')?._smO2Meta?.rows?.length >= 5")
        hover_canvas(page, "o2rTrendSpo2", ("SpO₂",))
        hover_canvas(page, "o2rTrendHr", ("Pulzus",))
        hover_canvas(page, "o2rTrendT90", ("T90",))
        hover_canvas(page, "o2rTrendOdi", ("ODI3", "ODI4"))

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

        progress("iPhone portrait Oximetria geometry through the real mobile drawer")
        page.set_viewport_size({"width": 390, "height": 844})
        navigate(page, "dashboard")
        page.locator("#mobileMenuToggle").click()
        page.wait_for_function("() => document.getElementById('sidebar')?.classList.contains('mobile-open')")
        page.locator('#sidebar [data-page="oximetry"]').click()
        page.wait_for_function("() => document.querySelector('#page-oximetry')?.classList.contains('active')")
        if page.locator("#sidebarScrim.active").count():
            page.locator("#sidebarScrim.active").click()
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

        progress("iPhone portrait/landscape O2Ring settings through the mobile category selector")
        navigate(page, "settings")
        page.wait_for_timeout(250)
        page.locator("#settingsCategorySelect").select_option("display")
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
