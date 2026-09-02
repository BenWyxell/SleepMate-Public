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
          window.__smLatestStatusHistory=[];
          const attachLatestStatusWatch=()=>{
            const el=document.getElementById('latestStatus');
            if(!el||el.__smAcceptanceWatched)return !!el;
            el.__smAcceptanceWatched=true;
            const record=()=>window.__smLatestStatusHistory.push(String(el.textContent||'').trim());
            record();
            new MutationObserver(record).observe(el,{childList:true,subtree:true,characterData:true});
            return true;
          };
          if(!attachLatestStatusWatch()){
            const rootObserver=new MutationObserver(()=>{if(attachLatestStatusWatch())rootObserver.disconnect()});
            rootObserver.observe(document,{childList:true,subtree:true});
          }
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
          const dayCodeFor = ts => {
            const d=new Date(ts*1000), p=n=>String(n).padStart(2,'0');
            return `${d.getFullYear()}${p(d.getMonth()+1)}${p(d.getDate())}`;
          };
          const dailyDay = dayCodeFor(now);
          const dailySamples = [
            {timestamp:now-3600,t:0,spo2:97,heart_rate:61,motion:0,valid:true},
            {timestamp:now-3540,t:60,spo2:96,heart_rate:63,motion:0,valid:true},
            {timestamp:now-3480,t:120,spo2:94,heart_rate:67,motion:1,valid:true},
            {timestamp:now-3000,t:600,spo2:93,heart_rate:70,motion:1,valid:true},
            {timestamp:now-2940,t:660,spo2:95,heart_rate:65,motion:0,valid:true},
          ];
          const daily = {
            day:dailyDay, available:true, auto_match:true,
            matches:[{cpap_start:now-3600,cpap_end:now-2940,overlap_seconds:660,cpap_coverage_percent:96}],
            summary:summary(95.8,93,65.2,42,1.4,.7), samples:dailySamples
          };
          const batchRows=[0,1,2,3,4].map(i => {
            const ts=now-(4-i)*86400;
            return {
              day:dayCodeFor(ts), available:true, auto_match:true,
              matches:[{cpap_start:ts,cpap_end:ts+21600,cpap_coverage_percent:94+i}],
              summary:summary(95.6+i*.2,91+i%2,62+i,24+i*9,.9+i*.2,.4+i*.1), samples:[]
            };
          });
          window.__smAcceptanceO2 = {
            liveRows,
            bufferCalls:0,
            dailyDay,daily,batchRows,dayCalls:0,invalidationHandlers:[],canvasText:[],pathRecords:[],
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
          const nativeEventAdd=window.EventSource?.prototype?.addEventListener;
          if(nativeEventAdd){
            window.EventSource.prototype.addEventListener=function(type,listener,options){
              if(type==='invalidation'&&String(this.url||'').includes('/api/o2ring/events')){
                window.__smAcceptanceO2.invalidationHandlers.push(listener);
              }
              return nativeEventAdd.call(this,type,listener,options);
            };
          }
          const nativeBeginPath=CanvasRenderingContext2D.prototype.beginPath;
          const nativeMoveTo=CanvasRenderingContext2D.prototype.moveTo;
          const nativeLineTo=CanvasRenderingContext2D.prototype.lineTo;
          const nativeStroke=CanvasRenderingContext2D.prototype.stroke;
          CanvasRenderingContext2D.prototype.beginPath=function(...args){
            this.__smAcceptancePath={moves:0,lines:0};
            return nativeBeginPath.apply(this,args);
          };
          CanvasRenderingContext2D.prototype.moveTo=function(...args){
            if(this.__smAcceptancePath)this.__smAcceptancePath.moves++;
            return nativeMoveTo.apply(this,args);
          };
          CanvasRenderingContext2D.prototype.lineTo=function(...args){
            if(this.__smAcceptancePath)this.__smAcceptancePath.lines++;
            return nativeLineTo.apply(this,args);
          };
          CanvasRenderingContext2D.prototype.stroke=function(...args){
            const f=window.__smAcceptanceO2,p=this.__smAcceptancePath||{};
            if(f&&this.canvas?.id&&f.pathRecords.length<6000){
              f.pathRecords.push({id:this.canvas.id,style:String(this.strokeStyle),moves:p.moves||0,lines:p.lines||0});
            }
            return nativeStroke.apply(this,args);
          };
          const nativeFillText=CanvasRenderingContext2D.prototype.fillText;
          CanvasRenderingContext2D.prototype.fillText=function(value,...args){
            const f=window.__smAcceptanceO2;
            if(f&&this.canvas?.id&&f.canvasText.length<3000)f.canvasText.push({id:this.canvas.id,text:String(value)});
            return nativeFillText.call(this,value,...args);
          };
          window.__smAcceptanceO2.emitInvalidation=function(type='sleepsync-completed'){
            const f=window.__smAcceptanceO2;
            const event={data:JSON.stringify({seq:Date.now(),type,days:[f.dailyDay],source:'sleepsync',details:{trigger:'acceptance'}})};
            for(const listener of [...f.invalidationHandlers])if(typeof listener==='function')listener.call(null,event);
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
            if (url.pathname === '/api/o2ring/day') {
              f.dayCalls++;
              return jsonResponse({...f.daily,day:url.searchParams.get('day')||f.dailyDay});
            }
            if (url.pathname === '/api/o2ring/day-batch') {
              const wanted=(url.searchParams.get('days')||'').split(',').filter(Boolean);
              return jsonResponse({rows:f.batchRows.filter(r=>wanted.includes(r.day))});
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
    canvas.scroll_into_view_if_needed()
    page.wait_for_timeout(60)
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


def zoom_canvas(page: Page, canvas_id: str) -> tuple[list[float], list[float]]:
    canvas = page.locator(f"#{canvas_id}")
    canvas.scroll_into_view_if_needed()
    page.wait_for_timeout(60)
    box = canvas.bounding_box()
    require(box is not None and box["width"] > 40, f"{canvas_id}: zoom target is not visible")
    before = page.evaluate(
        "id => {const m=document.getElementById(id)?._smO2Meta;return m?[m.a,m.b]:null}",
        canvas_id,
    )
    require(before is not None and before[1] > before[0], f"{canvas_id}: missing pre-zoom range")
    page.mouse.move(box["x"] + box["width"] * .55, box["y"] + box["height"] * .5)
    page.keyboard.down("Shift")
    try:
        page.mouse.wheel(0, -600)
    finally:
        page.keyboard.up("Shift")
    page.wait_for_timeout(220)
    after = page.evaluate(
        "id => {const m=document.getElementById(id)?._smO2Meta;return m?[m.a,m.b]:null}",
        canvas_id,
    )
    require(after is not None and after[1]-after[0] < before[1]-before[0], f"{canvas_id}: zoom did not shrink range: {before} -> {after}")
    return before, after


def pinch_canvas(page: Page, canvas_id: str) -> tuple[list[float], list[float]]:
    canvas = page.locator(f"#{canvas_id}")
    canvas.scroll_into_view_if_needed()
    page.wait_for_timeout(60)
    before = page.evaluate(
        "id => {const m=document.getElementById(id)?._smO2Meta;return m?[m.a,m.b]:null}",
        canvas_id,
    )
    require(before is not None and before[1] > before[0], f"{canvas_id}: missing pre-pinch range")
    page.evaluate(
        """id => {
          const c=document.getElementById(id),r=c.getBoundingClientRect(),y=r.top+r.height*.5,cx=r.left+r.width*.55;
          const fire=(type,pointerId,x)=>c.dispatchEvent(new PointerEvent(type,{
            bubbles:true,cancelable:true,pointerId,pointerType:'touch',button:0,buttons:type==='pointerup'?0:1,
            clientX:x,clientY:y,width:12,height:12,pressure:type==='pointerup'?0:.5,isPrimary:pointerId===701
          }));
          fire('pointerdown',701,cx-45);
          fire('pointerdown',702,cx+45);
          fire('pointermove',701,cx-90);
          fire('pointermove',702,cx+90);
          fire('pointerup',701,cx-90);
          fire('pointerup',702,cx+90);
        }""",
        canvas_id,
    )
    page.wait_for_timeout(240)
    after = page.evaluate(
        "id => {const m=document.getElementById(id)?._smO2Meta;return m?[m.a,m.b]:null}",
        canvas_id,
    )
    require(after is not None and after[1]-after[0] < before[1]-before[0], f"{canvas_id}: two-finger pinch did not zoom: {before} -> {after}")
    return before, after


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
        first_status_history = page.evaluate("() => window.__smLatestStatusHistory || []")
        require(
            not any("Befejezve" in value for value in first_status_history),
            f"latest-session card flashed legacy Befejezve during first boot: {first_status_history}",
        )

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
        reload_status_history = page.evaluate("() => window.__smLatestStatusHistory || []")
        require(
            not any("Befejezve" in value for value in reload_status_history),
            f"latest-session card flashed legacy Befejezve during stale-cache recovery: {reload_status_history}",
        )

        progress("repeated Dashboard/Oximetria navigation")
        initial_canvas_count = page.locator("#page-oximetry canvas").count()
        for _ in range(8):
            navigate(page, "dashboard")
            page.locator('#sidebar [data-page="oximetry"]').click()
            page.wait_for_function("() => document.querySelector('#page-oximetry')?.classList.contains('active')")
            require(page.locator("#page-oximetry").count() == 1, "Oximetria page duplicated during route switching")
            require(page.locator("#page-oximetry canvas").count() == initial_canvas_count, "O2 chart DOM leaked during route switching")
            navigate(page, "dashboard")

        navigation_status_history = page.evaluate("() => window.__smLatestStatusHistory || []")
        require(
            not any("Befejezve" in value for value in navigation_status_history),
            f"latest-session card flashed legacy Befejezve during repeated navigation: {navigation_status_history}",
        )

        progress("data-backed Dashboard Oximetria/Focus/All charts and SleepSync invalidation")
        page.evaluate(
            """() => {
              const f=window.__smAcceptanceO2,d=document.getElementById('day');
              document.querySelectorAll('.page').forEach(x=>x.classList.toggle('active',x.id==='page-dashboard'));
              const dash=document.getElementById('page-dashboard');
              dash?.classList.remove('measurement-empty-mode');
              dash?.querySelectorAll('.measurement-empty-state').forEach(x=>x.remove());
              if(![...d.options].some(o=>o.value===f.dailyDay))d.add(new Option('Acceptance O2',f.dailyDay));
              d.value=f.dailyDay;
              const a=f.daily.samples[0].timestamp*1000,b=f.daily.samples.at(-1).timestamp*1000;
              state.days=[f.dailyDay];state.currentDay=f.dailyDay;state.full=[a,b];state.view=[a,b];state.summary=null;
              document.getElementById('dashboardOverviewView')?.classList.add('hidden');
              document.getElementById('dashboardDailyView')?.classList.remove('hidden');
              document.querySelector('#dashboardDailyView .hero-panel')?.classList.remove('hidden');
              document.getElementById('overviewBlock')?.classList.remove('hidden');
              document.getElementById('stackedBlock')?.classList.add('hidden');
              document.getElementById('o2rDailyPanel')?.classList.add('hidden');
              f.pathRecords=[];
            }"""
        )
        require(page.locator("#o2rDailyBtn").is_visible(), "daily Oximetria mode is not visible in the synthetic daily route")
        page.locator("#o2rDailyBtn").click()
        require(
            page.locator("#focusViewBtn").is_visible()
            and page.locator("#stackViewBtn").is_visible()
            and page.locator("#o2rDailyBtn").is_visible(),
            "daily peer-mode controls disappeared after entering Oximetria",
        )
        require(page.locator("#smDailyModeSwitchHost").count() == 1, "daily peer-mode switch host missing/duplicated")
        page.wait_for_function("() => window.__smAcceptanceO2.dayCalls > 0")
        page.wait_for_function("() => document.getElementById('o2rDayDual')?._smO2Meta?.rows?.length >= 5")
        gap_paths = page.evaluate(
            """() => window.__smAcceptanceO2.pathRecords.filter(x =>
              x.id==='o2rDaySpo2Chart' && x.lines>0 &&
              ['#55d8ff','rgb(85, 216, 255)'].includes(String(x.style).toLowerCase())
            )"""
        )
        require(len(gap_paths) >= 2, f"daily SpO2 line crossed a long no-data gap instead of splitting into segments: {gap_paths}")
        hover_canvas(page, "o2rDayDual", ("SpO₂", "Pulzus"))
        hover_canvas(page, "o2rDaySpo2Chart", ("SpO₂",))
        hover_canvas(page, "o2rDayHrChart", ("Pulzus",))
        _, daily_zoom = zoom_canvas(page, "o2rDayDual")
        daily_ranges = page.evaluate(
            """() => ['o2rDayDual','o2rDaySpo2Chart','o2rDayHrChart'].map(id=>{const m=document.getElementById(id)?._smO2Meta;return m?[m.a,m.b]:null})"""
        )
        require(all(r is not None for r in daily_ranges), f"daily synchronized ranges missing: {daily_ranges}")
        require(max(abs(r[0]-daily_zoom[0])+abs(r[1]-daily_zoom[1]) for r in daily_ranges) < .05, f"daily O2 zoom is not synchronized: {daily_ranges}")
        page.locator("#o2rDayDual").dblclick()
        page.wait_for_timeout(120)
        _, daily_pinch = pinch_canvas(page, "o2rDayDual")
        pinch_ranges = page.evaluate(
            """() => ['o2rDayDual','o2rDaySpo2Chart','o2rDayHrChart'].map(id=>{const m=document.getElementById(id)?._smO2Meta;return m?[m.a,m.b]:null})"""
        )
        require(all(r is not None for r in pinch_ranges), f"daily pinch synchronized ranges missing: {pinch_ranges}")
        require(max(abs(r[0]-daily_pinch[0])+abs(r[1]-daily_pinch[1]) for r in pinch_ranges) < .05, f"daily two-finger pinch is not synchronized: {pinch_ranges}")
        page.locator("#o2rDayDual").dblclick()
        page.wait_for_timeout(120)

        page.wait_for_function("() => window.__smAcceptanceO2.invalidationHandlers.length > 0")
        day_calls_before = page.evaluate("() => window.__smAcceptanceO2.dayCalls")
        page.evaluate(
            """() => {
              const f=window.__smAcceptanceO2;
              f.daily.summary={...f.daily.summary,spo2_average:93.4,spo2_minimum:90,heart_rate_average:68.5};
              f.daily.samples=f.daily.samples.map((r,i)=>i===2?{...r,spo2:90,heart_rate:72}:r);
              f.emitInvalidation('sleepsync-completed');
            }"""
        )
        page.wait_for_function("n => window.__smAcceptanceO2.dayCalls > n", arg=day_calls_before)
        page.wait_for_function("() => document.getElementById('o2rDayAvg')?.textContent.includes('93')")
        require("93" in page.locator("#smNightO2Card").inner_text(), "SleepSync invalidation did not refresh the night O2 summary")

        page.locator("#focusViewBtn").click()
        page.wait_for_function("() => document.getElementById('smO2FocusDual')?._smO2Meta?.rows?.length >= 5")
        hover_canvas(page, "smO2FocusSpo2", ("SpO₂",))
        hover_canvas(page, "smO2FocusHr", ("Pulzus",))
        hover_canvas(page, "smO2FocusDual", ("SpO₂", "Pulzus"))

        page.locator("#smO2OverlayFocusSelect").select_option("both")
        page.evaluate(
            """() => {
              const f=window.__smAcceptanceO2;f.canvasText=[];f.pathRecords=[];
              state.hoverTime=f.daily.samples[1].timestamp*1000;
              window.dispatchEvent(new Event('resize'));
            }"""
        )
        page.wait_for_timeout(220)
        overlay_text = page.evaluate("() => window.__smAcceptanceO2.canvasText.filter(x=>x.id==='smO2HeroCanvas').map(x=>x.text)")
        require("O₂ 100%" in overlay_text and "O₂ 75%" in overlay_text, f"focus CPAP overlay is missing separate SpO2 scale labels: {overlay_text}")
        require(any(x.startswith("HR ") for x in overlay_text), f"focus CPAP overlay is missing HR secondary scale: {overlay_text}")
        require(any(x.count(':') >= 2 and 'O₂' in x and 'HR' in x for x in overlay_text), f"focus CPAP overlay is missing exact-time hover label: {overlay_text}")
        require(page.evaluate("() => localStorage.getItem('sm-o2-overlay:flow')") == "both", "per-chart O2 overlay selection was not persisted")
        overlay_paths = page.evaluate(
            """() => window.__smAcceptanceO2.pathRecords.filter(x => x.id==='smO2HeroCanvas' && x.lines>0)"""
        )
        overlay_spo2 = [x for x in overlay_paths if str(x.get("style", "")).lower() in ("#55d8ff", "rgb(85, 216, 255)")]
        overlay_hr = [x for x in overlay_paths if str(x.get("style", "")).lower() in ("#a98bff", "rgb(169, 139, 255)")]
        require(len(overlay_spo2) >= 2 and len(overlay_hr) >= 2, f"CPAP O2 overlay bridged a long no-data gap: {overlay_paths}")

        _, focus_zoom = zoom_canvas(page, "smO2FocusDual")
        page.locator("#stackViewBtn").click()
        page.wait_for_function("() => document.getElementById('smStackO2DualCanvas')?._smO2Meta?.rows?.length >= 5")
        hover_canvas(page, "smStackO2Spo2Canvas", ("SpO₂",))
        hover_canvas(page, "smStackO2HrCanvas", ("Pulzus",))
        hover_canvas(page, "smStackO2DualCanvas", ("SpO₂", "Pulzus"))
        _, stack_zoom = zoom_canvas(page, "smStackO2DualCanvas")

        page.locator("#focusViewBtn").click()
        page.wait_for_timeout(160)
        restored_focus = page.evaluate("() => {const m=document.getElementById('smO2FocusDual')?._smO2Meta;return m?[m.a,m.b]:null}")
        require(restored_focus is not None and max(abs(restored_focus[i]-focus_zoom[i]) for i in (0,1)) < .05, f"Focus zoom was not preserved across mode switching: {focus_zoom} -> {restored_focus}")
        page.locator("#stackViewBtn").click()
        page.wait_for_timeout(160)
        restored_stack = page.evaluate("() => {const m=document.getElementById('smStackO2DualCanvas')?._smO2Meta;return m?[m.a,m.b]:null}")
        require(restored_stack is not None and max(abs(restored_stack[i]-stack_zoom[i]) for i in (0,1)) < .05, f"All charts zoom was not preserved across mode switching: {stack_zoom} -> {restored_stack}")

        page.evaluate(
            """() => {
              const f=window.__smAcceptanceO2;
              state.dashboardOverview={rows:f.batchRows.map(r=>({day:r.day}))};
              document.getElementById('dashboardDailyView')?.classList.add('hidden');
              document.getElementById('dashboardOverviewView')?.classList.remove('hidden');
            }"""
        )
        page.evaluate("() => window.SleepMateO2Ring.refresh()")
        page.wait_for_function("() => document.getElementById('smDashO2Trend')?._smO2Meta?.rows?.length >= 5")
        require(page.locator("#smDashO2Avg").inner_text().strip() != "—", "Dashboard O2 aggregate did not hydrate from matched nights")
        hover_canvas(page, "smDashO2Trend", ("SpO₂",))
        hover_canvas(page, "smDashHrTrend", ("Pulzus",))

        page.evaluate(
            """() => {
              document.getElementById('dashboardOverviewView')?.classList.add('hidden');
              document.getElementById('dashboardDailyView')?.classList.remove('hidden');
            }"""
        )
        page.locator("#focusViewBtn").click()
        page.wait_for_timeout(120)

        progress("Focus/All charts/Oximetria repeated mode switching")
        for _ in range(6):
            for control in ("focusViewBtn", "stackViewBtn", "o2rDailyBtn"):
                page.evaluate("id => document.getElementById(id)?.click()", control)
        require(page.locator("#focusViewBtn").inner_text().strip() == "Fókusz nézet", "Focus button text mutated")
        require(page.locator("#stackViewBtn").inner_text().strip() == "Összes grafikon", "All charts button text mutated")
        require(page.locator("#o2rDailyBtn").inner_text().strip() == "Oximetria", "Oximetria mode mutated into navigation/back")

        progress("Reports O2 columns hydrate and refresh after SleepSync invalidation")
        navigate(page, "reports")
        page.wait_for_function("() => document.getElementById('page-reports')?.classList.contains('active')")
        page.evaluate(
            """() => {
              const f=window.__smAcceptanceO2,body=document.getElementById('reportDaysBody');
              body.innerHTML=f.batchRows.slice(-2).map(r=>`<tr class="click-row report-row" data-day="${r.day}"><td>${r.day}</td><td>7 ó</td><td>1.20</td><td>2</td><td>1</td><td>0</td><td>1</td><td>0</td></tr>`).join('');
              f.emitInvalidation('sleepsync-completed');
            }"""
        )
        page.wait_for_function("""() => document.querySelectorAll('#reportDaysBody [data-sm-o2-cell="spo2avg"]').length === 2""")
        page.wait_for_function("""() => [...document.querySelectorAll('#reportDaysBody [data-sm-o2-cell="spo2avg"]')].every(x=>x.textContent.trim()!=='—')""")
        report_day = page.evaluate("() => window.__smAcceptanceO2.batchRows.at(-1).day")
        report_before = page.locator(f'#reportDaysBody tr[data-day="{report_day}"] [data-sm-o2-cell="spo2avg"]').inner_text().strip()
        page.evaluate(
            """() => {
              const f=window.__smAcceptanceO2,row=f.batchRows.at(-1);
              row.summary={...row.summary,spo2_average:92.7,spo2_minimum:89,heart_rate_average:71.4};
              f.emitInvalidation('sleepsync-completed');
            }"""
        )
        page.wait_for_function(
            """day => {
              const row=[...document.querySelectorAll('#reportDaysBody tr.report-row')].find(x=>x.dataset.day===day);
              const text=row?.querySelector('[data-sm-o2-cell="spo2avg"]')?.textContent || '';
              return text.includes('92,7') || text.includes('92.7');
            }""",
            arg=report_day,
        )
        report_after = page.locator(f'#reportDaysBody tr[data-day="{report_day}"] [data-sm-o2-cell="spo2avg"]').inner_text().strip()
        require(report_after != report_before, f"SleepSync invalidation did not refresh report O2 columns: {report_before} -> {report_after}")

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
        page.wait_for_function("n => window.__smAcceptanceO2.bufferCalls > n", arg=before_buffers)
        page.wait_for_function(
            "t => document.getElementById('o2rLiveDual')?._smO2Meta?.rows?.some(r => r.timestamp > t)",
            arg=latest_before,
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
        page.evaluate("() => { window.__smAcceptanceO2.pathRecords=[]; }")
        page.locator('[data-o2r-tab="trends"]').click()
        page.wait_for_function("() => document.getElementById('o2rTrendSpo2')?._smO2Meta?.rows?.length >= 5")
        trend_paths = page.evaluate(
            """() => window.__smAcceptanceO2.pathRecords.filter(x =>
              x.id==='o2rTrendSpo2' && x.lines>0 &&
              ['#55d8ff','rgb(85, 216, 255)'].includes(String(x.style).toLowerCase())
            )"""
        )
        require(any(x.get("moves") == 1 and x.get("lines", 0) >= 4 for x in trend_paths), f"nightly SpO2 trend was incorrectly split between consecutive days: {trend_paths}")
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
        page.wait_for_function("() => !document.getElementById('sidebar')?.classList.contains('mobile-open')")
        require(page.locator("#sidebarScrim.active").count() == 0, "mobile Oximetria navigation did not close the drawer/scrim automatically")
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
