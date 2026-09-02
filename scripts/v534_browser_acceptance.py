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
          window.__smO2ListenerCounts={};
          const __smTrackedCanvasEvents=new Set(['pointerdown','pointermove','pointerup','pointercancel','pointerleave','dblclick','wheel']);
          const __smNativeTargetAdd=EventTarget.prototype.addEventListener;
          EventTarget.prototype.addEventListener=function(type,listener,options){
            if(this instanceof HTMLCanvasElement && this.id && __smTrackedCanvasEvents.has(type)){
              window.__smO2ListenerCounts[this.id]=(window.__smO2ListenerCounts[this.id]||0)+1;
            }
            return __smNativeTargetAdd.call(this,type,listener,options);
          };
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
          const summary = (avg,min,hr,t90=0,odi3=1.2,odi4=.6,spo2Median=avg,hrMedian=hr) => ({
            spo2_average:avg, spo2_median:spo2Median, spo2_minimum:min,
            spo2_maximum:Math.min(100,Math.max(min,Math.round(avg+2))),
            heart_rate_average:hr, heart_rate_median:hrMedian,
            heart_rate_minimum:Math.max(20,Math.round(hr-9)),
            heart_rate_maximum:Math.min(240,Math.round(hr+11)),
            t90_seconds:t90, odi3, odi4, coverage_percent:100
          });
          const liveRows = [
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
            summary:summary(95.8,93,65.2,42,1.4,.7,96.4,64.0), samples:dailySamples
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
            dailyDay,daily,batchRows,dayCalls:0,invalidationHandlers:[],canvasText:[],pathRecords:[],rectRecords:[],
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
              f.pathRecords.push({id:this.canvas.id,style:String(this.strokeStyle),width:Number(this.lineWidth)||0,moves:p.moves||0,lines:p.lines||0});
            }
            return nativeStroke.apply(this,args);
          };
          const nativeFillRect=CanvasRenderingContext2D.prototype.fillRect;
          CanvasRenderingContext2D.prototype.fillRect=function(x,y,w,h){
            const f=window.__smAcceptanceO2;
            if(f&&this.canvas?.id&&f.rectRecords.length<4000){
              f.rectRecords.push({id:this.canvas.id,style:String(this.fillStyle),x,y,w,h});
            }
            return nativeFillRect.call(this,x,y,w,h);
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
            if (url.pathname === `/api/day/${f.dailyDay}/stats`) {
              return jsonResponse({apnea_duration:'0:00',rows:[{key:'pressure',title:'Nyomás',unit:'cmH2O',min:6,median:8,p95:10,p995:11,max:12}]});
            }
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


def pan_canvas(page: Page, canvas_id: str) -> tuple[list[float], list[float]]:
    canvas = page.locator(f"#{canvas_id}")
    canvas.scroll_into_view_if_needed()
    page.wait_for_timeout(60)
    before = page.evaluate(
        "id => {const m=document.getElementById(id)?._smO2Meta;return m?[m.a,m.b]:null}",
        canvas_id,
    )
    require(before is not None and before[1] > before[0], f"{canvas_id}: missing pre-pan range")
    touch_action = page.evaluate("id => getComputedStyle(document.getElementById(id)).touchAction", canvas_id)
    require("pan-y" in str(touch_action), f"{canvas_id}: vertical page-scroll touch contract was lost: {touch_action}")
    page.evaluate(
        """id => {
          const c=document.getElementById(id),r=c.getBoundingClientRect(),y=r.top+r.height*.5,cx=r.left+r.width*.52;
          const fire=(type,x)=>c.dispatchEvent(new PointerEvent(type,{
            bubbles:true,cancelable:true,pointerId:703,pointerType:'touch',button:0,buttons:type==='pointerup'?0:1,
            clientX:x,clientY:y,width:12,height:12,pressure:type==='pointerup'?0:.5,isPrimary:true
          }));
          fire('pointerdown',cx);
          fire('pointermove',cx+70);
          fire('pointerup',cx+70);
        }""",
        canvas_id,
    )
    page.wait_for_timeout(260)
    after = page.evaluate(
        "id => {const m=document.getElementById(id)?._smO2Meta;return m?[m.a,m.b]:null}",
        canvas_id,
    )
    require(after is not None, f"{canvas_id}: missing post-pan range")
    before_span, after_span = before[1]-before[0], after[1]-after[0]
    before_mid, after_mid = (before[0]+before[1])/2, (after[0]+after[1])/2
    require(abs(after_span-before_span) < .05, f"{canvas_id}: one-finger touch pan changed zoom span: {before} -> {after}")
    require(abs(after_mid-before_mid) > .5, f"{canvas_id}: one-finger touch pan did not move the time window: {before} -> {after}")
    return before, after



def require_drag_selection(page: Page, canvas_id: str) -> None:
    canvas = page.locator(f"#{canvas_id}")
    canvas.scroll_into_view_if_needed()
    page.wait_for_timeout(60)
    box = canvas.bounding_box()
    require(box is not None and box["width"] > 80 and box["height"] > 40, f"{canvas_id}: drag target missing")
    page.evaluate("() => { window.__smAcceptanceO2.rectRecords=[]; }")
    y = box["y"] + box["height"] * .48
    page.mouse.move(box["x"] + box["width"] * .30, y)
    page.mouse.down()
    try:
        page.mouse.move(box["x"] + box["width"] * .68, y, steps=5)
        page.wait_for_timeout(160)
        records = page.evaluate(
            """id => window.__smAcceptanceO2.rectRecords.filter(x => x.id===id && x.w>4 && x.h>10 && String(x.style).includes('85, 183, 255'))""",
            canvas_id,
        )
        require(bool(records), f"{canvas_id}: visible drag-selection rectangle was not painted: {records}")
    finally:
        page.mouse.up()
    page.wait_for_timeout(100)

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
            lambda req: None
            if (
                "/api/o2ring/live-stream" in req.url
                and "ERR_ABORTED" in str(req.failure or "")
            )
            else request_failures.append(
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
        page.evaluate("""() => {
            state.dashboardOverview={latest:{summary:{therapy_seconds:27000,usage:'07:30:00',sessions:[{},{}]}}};
            window.SleepMateFrontendV534.syncLatestSessionCard();
        }""")
        require(page.locator(".latest-sleep-cards .session-status label").inner_text().strip() == "Alvásidő", "latest sleep card label is not Alvásidő")
        require(page.locator("#latestStatus").inner_text().strip() == "7:30", "latest sleep card does not show total therapy duration")
        require(page.locator("#latestSessions").inner_text().strip() == "2 szakasz", "latest sleep secondary text lost session count")
        require(page.locator("#smDashboardO2V534").count() == 1, "Dashboard Oximetriai összegzés is not stably owned on first PWA load")

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
              state.days=[f.dailyDay];state.currentDay=f.dailyDay;state.full=[a,b];state.view=[a,b];
              state.summary={day:f.dailyDay,ahi:0,therapy_seconds:(b-a)/1000,usage:'00:11:00',counts:{OA:0,CA:0,H:0,UA:0,RERA:0},events:[],sessions:[{start:new Date(a).toISOString(),end:new Date(b).toISOString(),duration_s:(b-a)/1000}],integrity:{complete:true,edf_files:1,problems:[]}};
              buildOverviewGrid();buildStackedGrid();renderNightEvaluation(state.summary,{rows:[]},{prescriptions:[]});
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
        require("96" in page.locator("#spo2").inner_text(), "daily SpO2 card did not hydrate the matched O2 median")
        require("64" in page.locator("#hr").inner_text(), "daily pulse card did not hydrate the matched O2 median")
        night_text = page.locator("#smNightO2Card").inner_text()
        require("SpO₂" in night_text and "Pulzus" in night_text and "Medián" in night_text, f"night O2 card is missing requested median summary: {night_text!r}")
        require(all(word not in night_text for word in ("Minimum", "T90", "ODI3", "ODI4")), f"night O2 card still contains detailed metrics: {night_text!r}")
        require(page.evaluate("() => document.getElementById('smNightO2Card')?.parentElement?.id") == "nightEvalList", "night O2 card is not part of the normal Night Evaluation grid")
        night_geometry = page.evaluate("""() => {
          const c=document.getElementById('smNightO2Card'),s=document.querySelector('#nightEvalList .night-fact:not(#smNightO2Card)'),l=document.getElementById('nightEvalList');
          if(!c||!s||!l)return null;const a=c.getBoundingClientRect(),b=s.getBoundingClientRect(),g=l.getBoundingClientRect();
          return {card:a.width,sibling:b.width,list:g.width};
        }""")
        require(night_geometry is not None and abs(night_geometry["card"]-night_geometry["sibling"]) <= 3, f"night O2 card is not normal card width: {night_geometry}")
        require(night_geometry["card"] < night_geometry["list"]*.6, f"night O2 card still spans the full PC width: {night_geometry}")
        require_drag_selection(page, "o2rDaySpo2Chart")
        page.locator("#o2rDaySpo2Chart").dblclick()
        require_drag_selection(page, "o2rDayHrChart")
        page.locator("#o2rDayHrChart").dblclick()
        o2_widths = page.evaluate("""() => window.__smAcceptanceO2.pathRecords.filter(x => ['#55d8ff','#a98bff','rgb(85, 216, 255)','rgb(169, 139, 255)'].includes(String(x.style).toLowerCase()) && x.lines>0).map(x=>x.width)""")
        require(bool(o2_widths) and max(o2_widths) <= 1.2, f"O2 chart line weight is thicker than normal charts: {o2_widths}")
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
        _, daily_pan = pan_canvas(page, "o2rDayDual")
        pan_ranges = page.evaluate(
            """() => ['o2rDayDual','o2rDaySpo2Chart','o2rDayHrChart'].map(id=>{const m=document.getElementById(id)?._smO2Meta;return m?[m.a,m.b]:null})"""
        )
        require(all(r is not None for r in pan_ranges), f"daily touch-pan synchronized ranges missing: {pan_ranges}")
        require(max(abs(r[0]-daily_pan[0])+abs(r[1]-daily_pan[1]) for r in pan_ranges) < .05, f"daily one-finger touch pan is not synchronized: {pan_ranges}")
        page.locator("#o2rDayDual").dblclick()
        page.wait_for_timeout(120)

        page.wait_for_function("() => window.__smAcceptanceO2.invalidationHandlers.length > 0")
        day_calls_before = page.evaluate("() => window.__smAcceptanceO2.dayCalls")
        page.evaluate(
            """() => {
              const f=window.__smAcceptanceO2;
              f.daily.summary={...f.daily.summary,spo2_average:93.4,spo2_median:94.6,spo2_minimum:90,spo2_maximum:98,heart_rate_average:68.5,heart_rate_median:67.0,heart_rate_minimum:58,heart_rate_maximum:77};
              f.daily.samples=f.daily.samples.map((r,i)=>i===2?{...r,spo2:90,heart_rate:72}:r);
              f.emitInvalidation('sleepsync-completed');
            }"""
        )
        page.wait_for_function("n => window.__smAcceptanceO2.dayCalls > n", arg=day_calls_before)
        page.wait_for_function("() => document.getElementById('o2rDayAvg')?.textContent.includes('93')")
        require("94" in page.locator("#smNightO2Card").inner_text() and "67" in page.locator("#smNightO2Card").inner_text(), "SleepSync invalidation did not refresh the night O2 medians")

        page.locator("#focusViewBtn").click()
        page.wait_for_function("""() => document.querySelector('.overview-card[data-key="o2_spo2"]') && document.querySelector('.overview-card[data-key="o2_hr"]')""")
        require(page.locator("#smO2FocusSection").count() == 0 and page.locator("#smO2FocusDual").count() == 0, "legacy separate Focus O2 graph section still exists")
        require(page.locator('.overview-card[data-key="o2_spo2"]').count() == 1 and page.locator('.overview-card[data-key="o2_hr"]').count() == 1, "Focus does not contain exactly one SpO2 and one Pulse mini card")
        mini_geometry = page.evaluate("""() => {
          const f=document.querySelector('.overview-card[data-key="flow"] canvas')?.getBoundingClientRect(),
                s=document.querySelector('.overview-card[data-key="o2_spo2"] canvas')?.getBoundingClientRect(),
                h=document.querySelector('.overview-card[data-key="o2_hr"] canvas')?.getBoundingClientRect();
          return f&&s&&h?{fw:f.width,fh:f.height,sw:s.width,sh:s.height,hw:h.width,hh:h.height}:null;
        }""")
        require(mini_geometry is not None and max(abs(mini_geometry["fw"]-mini_geometry["sw"]),abs(mini_geometry["fw"]-mini_geometry["hw"]),abs(mini_geometry["fh"]-mini_geometry["sh"]),abs(mini_geometry["fh"]-mini_geometry["hh"])) <= 2, f"Focus O2 mini charts do not match normal mini-chart geometry: {mini_geometry}")

        page.locator('.overview-card[data-key="o2_spo2"]').click()
        page.wait_for_function("() => state.selectedSignal==='o2_spo2' && state.mainSignal?.series?.length")
        require(page.locator("#heroTitle").inner_text().strip() == "SpO₂", "SpO2 Focus mini did not open the normal hero chart")
        page.evaluate("() => { window.__smAcceptanceO2.pathRecords=[]; drawHeroBase(); }")
        hero_spo2_widths = page.evaluate("""() => window.__smAcceptanceO2.pathRecords.filter(x=>x.id==='heroBase' && ['#55d8ff','rgb(85, 216, 255)'].includes(String(x.style).toLowerCase()) && x.lines>0).map(x=>x.width)""")
        require(bool(hero_spo2_widths) and max(hero_spo2_widths) <= 1.2, f"Focus SpO2 hero line is thicker than normal: {hero_spo2_widths}")
        require_drag_selection(page, "heroOverlay")
        page.evaluate("() => setView(state.full[0],state.full[1],false)")

        page.locator('.overview-card[data-key="o2_hr"]').click()
        page.wait_for_function("() => state.selectedSignal==='o2_hr' && state.mainSignal?.series?.length")
        require(page.locator("#heroTitle").inner_text().strip() == "Pulzus", "Pulse Focus mini did not open the normal hero chart")
        require_drag_selection(page, "heroOverlay")
        page.evaluate("() => setView(state.full[0]+60000,state.full[1]-60000,false)")
        focus_zoom = page.evaluate("() => [...state.view]")

        page.locator('.overview-card[data-key="flow"]').click()
        page.locator("#smO2OverlayFocusSelect").select_option("both")
        page.evaluate("""() => {
          const f=window.__smAcceptanceO2;f.canvasText=[];f.pathRecords=[];
          state.hoverTime=f.daily.samples[1].timestamp*1000;drawOverlays();
        }""")
        page.wait_for_timeout(160)
        overlay_text = page.evaluate("() => window.__smAcceptanceO2.canvasText.filter(x=>x.id==='smO2HeroCanvas').map(x=>x.text)")
        require("O₂ 100%" in overlay_text and "O₂ 75%" in overlay_text, f"focus CPAP overlay lost SpO2 scale labels: {overlay_text}")
        require(any(x.startswith("HR ") for x in overlay_text), f"focus CPAP overlay lost HR scale labels: {overlay_text}")
        require(any(x.count(':') >= 2 and 'O₂' in x and 'HR' in x for x in overlay_text), f"focus CPAP overlay lost hover values: {overlay_text}")
        page.locator("#stackViewBtn").click()
        page.wait_for_function("() => document.getElementById('smStackO2DualCanvas')?._smO2Meta?.rows?.length >= 5")
        stack_pointer_events = page.evaluate(
            """() => ['smStackO2Spo2Canvas','smStackO2HrCanvas','smStackO2DualCanvas'].map(id => ({
              id, pointerEvents:getComputedStyle(document.getElementById(id)).pointerEvents
            }))"""
        )
        require(
            all(x["pointerEvents"] != "none" for x in stack_pointer_events),
            f"Stack O2 chart input was disabled by the CPAP base-canvas CSS: {stack_pointer_events}",
        )
        flow_overlay = page.locator('#stackedCharts .stack-chart[data-key="flow"] .sm-o2-overlay-select')
        require(flow_overlay.locator('option[value="off"]').inner_text().strip() == "Alapnézet", "All Charts default overlay label is not Alapnézet")
        flow_overlay.select_option("both")
        page.evaluate("""() => {
          const card=document.querySelector('#stackedCharts .stack-chart[data-key="flow"]'),c=card?.querySelector('.sm-o2-overlay-canvas');
          if(c)c.id='acceptanceStackFlowO2';
          const f=window.__smAcceptanceO2;f.canvasText=[];f.pathRecords=[];state.hoverTime=f.daily.samples[1].timestamp*1000;drawOverlays();
        }""")
        page.wait_for_timeout(160)
        stack_overlay_text = page.evaluate("() => window.__smAcceptanceO2.canvasText.filter(x=>x.id==='acceptanceStackFlowO2').map(x=>x.text)")
        require("O₂ 100%" in stack_overlay_text and "O₂ 75%" in stack_overlay_text, f"All Charts overlay lacks SpO2 right-axis labels: {stack_overlay_text}")
        require(any(x.startswith("HR ") for x in stack_overlay_text), f"All Charts overlay lacks HR right-axis labels: {stack_overlay_text}")
        require(any(x.count(':') >= 2 and 'SpO₂' in x and 'Pulzus' in x for x in stack_overlay_text), f"All Charts hover label lacks overlaid SpO2/Pulse values: {stack_overlay_text}")
        overlay_geometry = page.evaluate("""() => {
          const card=document.querySelector('#stackedCharts .stack-chart[data-key="flow"]')?.getBoundingClientRect(),c=document.getElementById('acceptanceStackFlowO2')?.getBoundingClientRect();
          return card&&c?{cardRight:card.right,canvasRight:c.right,cardWidth:card.width,canvasWidth:c.width}:null;
        }""")
        require(overlay_geometry is not None and overlay_geometry["canvasRight"] <= overlay_geometry["cardRight"] + 2, f"All Charts O2 right axis is clipped/outside its card: {overlay_geometry}")
        hover_canvas(page, "smStackO2Spo2Canvas", ("SpO₂",))
        hover_canvas(page, "smStackO2HrCanvas", ("Pulzus",))
        hover_canvas(page, "smStackO2DualCanvas", ("SpO₂", "Pulzus"))
        _, stack_zoom = zoom_canvas(page, "smStackO2DualCanvas")

        page.locator("#focusViewBtn").click()
        page.wait_for_timeout(160)
        restored_focus = page.evaluate("() => [...state.view]")
        require(restored_focus is not None and max(abs(restored_focus[i]-focus_zoom[i]) for i in (0,1)) < 2, f"Focus zoom was not preserved across mode switching: {focus_zoom} -> {restored_focus}")
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
        require(page.locator("#smDashboardO2V534").is_visible(), "Dashboard Oximetriai összegzés is hidden despite matched data")
        page.evaluate("""() => { const f=window.__smAcceptanceO2; state.dashboardOverview={rows:[{day:f.batchRows.at(-1).day}]}; window.SleepMateO2Ring.refresh(); }""")
        page.wait_for_function("() => document.getElementById('smDashO2Trend')?._smO2Meta?.rows?.length===1")
        require(page.locator("#smDashboardO2V534").count() == 1 and page.locator("#smDashboardO2V534").is_visible(), "Dashboard O2 summary disappeared with one matched night")
        page.evaluate("""() => { const f=window.__smAcceptanceO2; state.dashboardOverview={rows:f.batchRows.map(r=>({day:r.day}))}; window.SleepMateO2Ring.refresh(); }""")
        page.wait_for_function("() => document.getElementById('smDashO2Trend')?._smO2Meta?.rows?.length>=5")

        page.evaluate(
            """() => {
              document.getElementById('dashboardOverviewView')?.classList.add('hidden');
              document.getElementById('dashboardDailyView')?.classList.remove('hidden');
            }"""
        )
        page.locator("#focusViewBtn").click()
        page.wait_for_timeout(120)

        progress("Focus/All charts/Oximetria repeated mode switching")
        persistent_daily_ids = [
            "o2rDayDual","o2rDaySpo2Chart","o2rDayHrChart",
            "mini-o2_spo2","mini-o2_hr","heroOverlay",
            "smStackO2Spo2Canvas","smStackO2HrCanvas","smStackO2DualCanvas",
        ]
        daily_listener_before = page.evaluate(
            "ids => Object.fromEntries(ids.map(id => [id, window.__smO2ListenerCounts[id] || 0]))",
            persistent_daily_ids,
        )
        for _ in range(6):
            for control in ("focusViewBtn", "stackViewBtn", "o2rDailyBtn"):
                page.evaluate("id => document.getElementById(id)?.click()", control)
        daily_listener_after = page.evaluate(
            "ids => Object.fromEntries(ids.map(id => [id, window.__smO2ListenerCounts[id] || 0]))",
            persistent_daily_ids,
        )
        require(daily_listener_after == daily_listener_before, f"daily O2 chart listeners leaked across peer-mode switching: {daily_listener_before} -> {daily_listener_after}")
        require(page.locator("#smDailyModeSwitchHost").count() == 1, "daily peer-mode host duplicated during repeated switching")
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
        report_geometry = page.evaluate("""() => {
          const p=document.querySelector('.sm-report-days-compact'),h=p?.querySelector('.panel-head')?.getBoundingClientRect(),th=p?.querySelector('th')?.getBoundingClientRect(),tr=p?.querySelector('tbody tr')?.getBoundingClientRect();
          return p&&h&&th&&tr?{panelHead:h.height,header:th.height,row:tr.height}:null;
        }""")
        require(report_geometry is not None and report_geometry["panelHead"] < 55 and report_geometry["header"] < 42 and report_geometry["row"] < 40, f"Reports selected-days table remains oversized: {report_geometry}")
        page.evaluate("() => loadReportStats(window.__smAcceptanceO2.dailyDay)")
        page.wait_for_function("() => document.querySelectorAll('#statsBody tr[data-sm-o2-stat]').length===2")
        o2_stats = page.evaluate("""() => Object.fromEntries([...document.querySelectorAll('#statsBody tr[data-sm-o2-stat]')].map(tr=>[tr.dataset.smO2Stat,[...tr.cells].map(td=>td.textContent.trim())]))""")
        require('spo2' in o2_stats and 'hr' in o2_stats, f"Daily Statistics missing O2 rows: {o2_stats}")
        require('93,0%' in o2_stats['spo2'][1] or '93.0%' in o2_stats['spo2'][1], f"Daily Statistics missing minimum SpO2: {o2_stats}")
        require('96,4%' in o2_stats['spo2'][2] or '96.4%' in o2_stats['spo2'][2], f"Daily Statistics missing median SpO2: {o2_stats}")
        require(o2_stats['spo2'][5] != '–', f"Daily Statistics missing maximum SpO2: {o2_stats}")
        require(o2_stats['hr'][1] != '–' and ('64,0 bpm' in o2_stats['hr'][2] or '64.0 bpm' in o2_stats['hr'][2]) and o2_stats['hr'][5] != '–', f"Daily Statistics missing pulse min/median/max: {o2_stats}")

        progress("Oximetria Live/Recordings/Trends repeated switching")
        page.locator('#sidebar [data-page="oximetry"]').click()
        page.wait_for_function("() => document.querySelector('#page-oximetry')?.classList.contains('active')")
        action_labels = page.evaluate("() => [...document.querySelectorAll('#page-oximetry .o2r-hero-actions > button')].map(x=>x.textContent.trim())")
        require(action_labels == ['← Dashboard','＋ Kapcsolódás','↻ Szinkron','Élő O₂ monitor','Felvételek','Trendek'], f"Oximetria top buttons are not one unified ordered row: {action_labels}")
        require(page.locator("#page-oximetry .o2r-tabs").count() == 0, "Oximetria still has a separate tab strip")
        require(page.locator("#page-oximetry .o2r-live-cards .state").count() == 0, "large separate Állapot card still exists in Live metrics")
        require(page.locator("#o2rSearchState").count() == 1 and page.evaluate("() => document.getElementById('o2rSearchState')?.parentElement?.classList.contains('o2r-hero')") is True, "compact Állapot was not moved under the Oximetria connection/search area")
        for tab in ("recordings", "trends", "live"):
            page.locator(f'[data-o2r-tab="{tab}"]').click()
            page.wait_for_timeout(90)
        persistent_page_ids = [
            "o2rLiveDual","o2rLiveSpo2Chart","o2rLiveHrChart",
            "o2rTrendSpo2","o2rTrendHr","o2rTrendT90","o2rTrendOdi",
        ]
        page_listener_before = page.evaluate(
            "ids => Object.fromEntries(ids.map(id => [id, window.__smO2ListenerCounts[id] || 0]))",
            persistent_page_ids,
        )
        for _ in range(5):
            for tab in ("recordings", "trends", "live"):
                page.locator(f'[data-o2r-tab="{tab}"]').click()
                page.wait_for_timeout(60)
        page_listener_after = page.evaluate(
            "ids => Object.fromEntries(ids.map(id => [id, window.__smO2ListenerCounts[id] || 0]))",
            persistent_page_ids,
        )
        require(page_listener_after == page_listener_before, f"Oximetria page chart listeners leaked across tab switching: {page_listener_before} -> {page_listener_after}")
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
        page.wait_for_function("() => window.__smAcceptanceO2.pathRecords.some(x => x.id==='o2rTrendSpo2' && x.lines>0)")
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
