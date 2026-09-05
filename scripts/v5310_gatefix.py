from pathlib import Path
import re


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def replace(path: str, old: str, new: str, *, count: int | None = None) -> None:
    text = read(path)
    found = text.count(old)
    if count is not None and found != count:
        raise SystemExit(f"{path}: expected {count} occurrences, found {found}: {old!r}")
    if found == 0:
        raise SystemExit(f"{path}: missing expected text: {old!r}")
    write(path, text.replace(old, new))


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    found = text.count(old)
    if found != 1:
        raise SystemExit(f"{path}: expected one occurrence, found {found}: {old!r}")
    write(path, text.replace(old, new, 1))


def replace_block(path: str, pattern: str, replacement: str) -> None:
    text = read(path)
    updated, found = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if found != 1:
        raise SystemExit(f"{path}: expected one block for {pattern!r}, got {found}")
    write(path, updated)


# Release/cache assertions that intentionally move with the release.
replace_once("tests/test_mobile_ai_push_v417.py", "sleepmate-shell-v5.3.9-o2-hydration-1", "sleepmate-shell-v5.3.10-o2-hydration-1")
replace_once("tests/test_o2ring_v532_release_contract.py", 'APP_VERSION=="5.3.9"', 'APP_VERSION=="5.3.10"')
replace_once("tests/test_pwa_sleep_shell_v526.py", "sleepmate-shell-v5.3.9-o2-hydration-1", "sleepmate-shell-v5.3.10-o2-hydration-1")
replace_once("tests/test_pwa_sleep_shell_v526.py", 'assert "sleepmate-shell-v5.3.9" in sw', 'assert "sleepmate-shell-v5.3.10" in sw')
replace_once("tests/test_v537_targeted_fixes.py", "sleepmate-shell-v5.3.9-o2-hydration-1", "sleepmate-shell-v5.3.10-o2-hydration-1")

# v5.3.4 acceptance matrix: keep backend buffer compatibility, but frontend Live is now a fresh current-measurement session.
p = "tests/test_v534_acceptance_matrix.py"
replace_once(p, 'assert APP_VERSION == "5.3.9"', 'assert APP_VERSION == "5.3.10"')
replace_once(p, 'assert "sleepmate-shell-v5.3.9-o2-hydration-1" in worker', 'assert "sleepmate-shell-v5.3.10-o2-hydration-1" in worker')
replace_block(
    p,
    r"def test_acceptance_p0_live_o2_only_paints_when_visible_and_batch_refills_on_return\(\):\n.*?(?=\ndef test_acceptance_p1_all_o2_charts_share_exact_hover_crosshair_zoom_pan_contract)",
    '''def test_acceptance_p0_live_o2_is_visible_scoped_and_current_measurement_only():
    js = read("web/o2ring.js")
    stream = read("cpap/o2ring_stream.py")
    for marker in (
        "document.visibilityState==='visible'",
        "function o2PageVisible()",
        "function updateLiveLifecycle()",
        "function closeLiveStream()",
        "async function resumeLive()",
        "R.liveResumePromise",
        "livePageActive:false",
        "R.livePageActive=true;R.live=[];R.liveZoom=null;drawLive()",
        "x.measuring===true&&x.last_sample_ts",
        "if(!measuring&&R.live.length){R.live=[];R.liveZoom=null;drawLive()}",
        'value="instant" selected>Azonnali',
        'value="1">1 perc',
        "Jelenleg nincs mérés folyamatban.",
        "R.liveRaf=requestAnimationFrame(()=>{R.liveRaf=0;drawLive()})",
    ):
        assert marker in js
    resume = js[js.index("async function resumeLive()"):js.index("function updateLiveLifecycle()")]
    assert "await refillLive(" not in resume
    assert "function o2PageVisible(){return document.visibilityState==='visible'&&location.hash.startsWith('#oximetry')" in js
    # Backend buffer remains available for compatibility, but opening Live no longer hydrates from it.
    assert "class _LiveBuffer" in stream
    assert 'path == "/api/o2ring/live-buffer"' in stream
    assert "service.manager.add_listener(BUFFER.append_snapshot)" in stream

''',
)
replace_block(
    p,
    r"def test_acceptance_o2_trends_live_handoff_and_hover_redraw_are_gap_safe\(\):\n.*?\n    assert js\.count\(\"trendGap:true\"\) >= 2\n",
    '''def test_acceptance_o2_trends_live_handoff_and_hover_redraw_are_gap_safe():
    js = read("web/o2ring.js")
    for marker in (
        "function chartGap(rows,trendGap=false)",
        "medianDelta(rows,null)*3.2",
        "trendGap:true",
        "hoverRaf:new Map()",
        "function scheduleGroupRedraw(group)",
        "const seen=new Set()",
        "!seen.has(fn)",
        "R.hoverRaf.delete(group)",
        "livePageActive:false",
        "x.measuring===true&&x.last_sample_ts",
        "if(!measuring&&R.live.length){R.live=[];R.liveZoom=null;drawLive()}",
        "if(R.liveResumePromise===work)",
        "function closeMobileO2Drawer()",
        "smooth:true,points:true,connectGaps:true,lineWidth:2",
    ):
        assert marker in js
    resume = js[js.index("async function resumeLive()"):js.index("function updateLiveLifecycle()")]
    assert "await refillLive(" not in resume
    assert js.count("trendGap:true") >= 1
''',
)

# User acceptance matrix: Dashboard O2 now intentionally follows the normal smooth trend visual language.
p = "tests/test_v535_user_acceptance_matrix.py"
replace_block(
    p,
    r"def test_stability_trends_break_missing_nights_and_use_date_axis\(\):\n.*?(?=\n\ndef test_stability_live_return_opens_stream_before_bounded_refill)",
    '''def test_stability_trends_use_date_axis_and_dashboard_o2_matches_smooth_core_style():
    assert JS.count("gapSeconds:36*3600") >= 1
    assert JS.count("xLabel:date") >= 2
    assert "tooltipLabel:ts=>`${date(ts)} ${clock(ts)}`" in JS
    assert "smooth:true,points:true,connectGaps:true,lineWidth:2" in JS
    assert "Dashboard O2 trend is not smoothed like the core Dashboard trends" in BROWSER
    assert "O2 trend X-axis did not render dates" in BROWSER
''',
)
replace_block(
    p,
    r"def test_stability_live_return_opens_stream_before_bounded_refill\(\):\n.*?(?=\ndef test_request_05_edge_compares_o2_hero_to_real_core_hero_width)",
    '''def test_stability_live_view_starts_fresh_and_never_refills_historical_buffer():
    resume = JS[JS.index('async function resumeLive()'):JS.index('function updateLiveLifecycle()')]
    assert 'openLiveStream()' in resume
    assert 'await refillLive(' not in resume
    assert 'if(R.liveResumePromise)return R.liveResumePromise' in resume
    assert 'R.livePageActive=true;R.live=[];R.liveZoom=null;drawLive()' in JS
    assert 'if(!measuring&&R.live.length){R.live=[];R.liveZoom=null;drawLive()}' in JS
    assert 'Live O2 uses only the current visible measurement session' in BROWSER

''',
)
replace_once(p, "assert APP_VERSION == '5.3.9'", "assert APP_VERSION == '5.3.10'")
replace_once(p, "assert RELEASE_NOTES.startswith('# SleepMate 5.3.9\\n')", "assert RELEASE_NOTES.startswith('# SleepMate 5.3.10\\n')")
replace_once(p, "assert 'Release build: **5.3.9**.' in section", "assert 'Release build: **5.3.10**.' in section")
replace_once(p, "const CACHE='sleepmate-shell-v5.3.9-o2-hydration-1';", "const CACHE='sleepmate-shell-v5.3.10-o2-hydration-1';")

# Packaged browser acceptance: intercept sample callbacks so the test can drive a real fresh live session
# without relying on historical live-buffer hydration.
p = "scripts/v534_browser_acceptance.py"
replace_once(
    p,
    "dailyDay,daily,flowSignal,batchRows,dayCalls:0,invalidationHandlers:[],canvasText:[],pathRecords:[],rectRecords:[],",
    "dailyDay,daily,flowSignal,batchRows,dayCalls:0,invalidationHandlers:[],liveSampleHandlers:[],canvasText:[],pathRecords:[],rectRecords:[],",
)
old_event = '''          const nativeEventAdd=window.EventSource?.prototype?.addEventListener;
          if(nativeEventAdd){
            window.EventSource.prototype.addEventListener=function(type,listener,options){
              if(type==='invalidation'&&String(this.url||'').includes('/api/o2ring/events')){
                window.__smAcceptanceO2.invalidationHandlers.push(listener);
              }
              return nativeEventAdd.call(this,type,listener,options);
            };
          }
'''
new_event = '''          const nativeEventAdd=window.EventSource?.prototype?.addEventListener;
          if(nativeEventAdd){
            window.EventSource.prototype.addEventListener=function(type,listener,options){
              if(type==='invalidation'&&String(this.url||'').includes('/api/o2ring/events')){
                window.__smAcceptanceO2.invalidationHandlers.push(listener);
              }
              if(type==='sample'&&String(this.url||'').includes('/api/o2ring/live-stream')){
                window.__smAcceptanceO2.liveSampleHandlers.push(listener);
                return;
              }
              return nativeEventAdd.call(this,type,listener,options);
            };
          }
          window.__smAcceptanceO2.emitLive=function(row){
            const f=window.__smAcceptanceO2;
            const measuring=row.measuring!==false;
            const payload={connected:true,scanning:false,device_name:'O2Ring Acceptance',device_model:'O2Ring',remembered_address:'ACCEPTANCE',spo2:measuring?row.spo2:null,heart_rate:measuring?row.heart_rate:null,battery_percent:96,motion:row.motion||0,signal_strength:9,worn:measuring,calibrating:false,measuring,last_sample_ts:row.timestamp,last_error:null};
            const event={data:JSON.stringify(payload)};
            for(const listener of [...f.liveSampleHandlers])if(typeof listener==='function')listener.call(null,event);
          };
'''
replace_once(p, old_event, new_event)
replace_once(
    p,
    "const nativeLineTo=CanvasRenderingContext2D.prototype.lineTo;\n          const nativeStroke=CanvasRenderingContext2D.prototype.stroke;",
    "const nativeLineTo=CanvasRenderingContext2D.prototype.lineTo;\n          const nativeQuadraticCurveTo=CanvasRenderingContext2D.prototype.quadraticCurveTo;\n          const nativeStroke=CanvasRenderingContext2D.prototype.stroke;",
)
replace_once(p, "this.__smAcceptancePath={moves:0,lines:0};", "this.__smAcceptancePath={moves:0,lines:0,curves:0};")
replace_once(
    p,
    '''          CanvasRenderingContext2D.prototype.lineTo=function(...args){
            if(this.__smAcceptancePath)this.__smAcceptancePath.lines++;
            return nativeLineTo.apply(this,args);
          };
''',
    '''          CanvasRenderingContext2D.prototype.lineTo=function(...args){
            if(this.__smAcceptancePath)this.__smAcceptancePath.lines++;
            return nativeLineTo.apply(this,args);
          };
          CanvasRenderingContext2D.prototype.quadraticCurveTo=function(...args){
            if(this.__smAcceptancePath)this.__smAcceptancePath.curves++;
            return nativeQuadraticCurveTo.apply(this,args);
          };
''',
)
replace_once(
    p,
    "f.pathRecords.push({id:this.canvas.id,style:String(this.strokeStyle),width:Number(this.lineWidth)||0,moves:p.moves||0,lines:p.lines||0});",
    "f.pathRecords.push({id:this.canvas.id,style:String(this.strokeStyle),width:Number(this.lineWidth)||0,moves:p.moves||0,lines:p.lines||0,curves:p.curves||0});",
)
replace_block(
    p,
    r"        missing_night_paths = page\.evaluate\(\n.*?        require\(len\(missing_night_paths\) >= 2, f\"Dashboard O2 trend bridged a missing night: \{missing_night_paths\}\"\)\n",
    '''        smooth_dashboard_paths = page.evaluate(
            """() => window.__smAcceptanceO2.pathRecords.filter(x =>
              x.id==='smDashO2Trend' && x.curves>0 &&
              ['#55d8ff','rgb(85, 216, 255)'].includes(String(x.style).toLowerCase())
            )"""
        )
        require(any(x.get("curves",0) >= 2 for x in smooth_dashboard_paths), f"Dashboard O2 trend is not smoothed like the core Dashboard trends: {smooth_dashboard_paths}")
''',
)
replace_block(
    p,
    r"        progress\(\"Live O2 only runs while visible and batch-refills on return\"\)\n.*?(?=        progress\(\"exact O2 crosshair tooltips and live zoom\"\))",
    '''        progress("Live O2 uses only the current visible measurement session")
        page.locator('[data-o2r-tab="live"]').click()
        page.wait_for_function("() => window.__smAcceptanceO2.liveSampleHandlers.length > 0")
        require(page.evaluate("() => window.__smAcceptanceO2.bufferCalls") == 0, "opening Live unexpectedly hydrated historical live-buffer data")
        live_window_values = page.evaluate("() => [...document.getElementById('o2rLiveWindow').options].map(o=>o.value)")
        require(live_window_values[:2] == ['instant','1'], f"Live O2 fast windows are missing or misordered: {live_window_values}")
        require(page.locator('#o2rLiveWindow').input_value() == 'instant', "Azonnali is not the default Live O2 window")
        page.evaluate(
            """() => {
              const f=window.__smAcceptanceO2, now=Math.floor(Date.now()/1000);
              f.emitLive({timestamp:now-18,spo2:97,heart_rate:62,motion:0});
              f.emitLive({timestamp:now-9,spo2:96,heart_rate:64,motion:0});
              f.emitLive({timestamp:now-1,spo2:95,heart_rate:66,motion:1});
              f.latestAcceptanceLive=now-1;
            }"""
        )
        page.wait_for_function("() => document.getElementById('o2rLiveDual')?._smO2Meta?.rows?.length >= 3")
        page.wait_for_timeout(200)
        require(len(live_stream_requests) >= 1, "visible Oximetria Live did not open a real SSE stream")
        instant_span = page.evaluate("() => {const m=document.getElementById('o2rLiveDual')._smO2Meta;return m.b-m.a}")
        require(5 <= instant_span <= 31, f"Azonnali Live O2 window did not fit the immediate measurement: {instant_span}")
        before_streams = len(live_stream_requests)
        latest_before = page.evaluate("() => window.__smAcceptanceO2.latestAcceptanceLive")

        navigate(page, "dashboard")
        page.wait_for_timeout(500)
        require(len(live_stream_requests) == before_streams, "hidden Dashboard state spawned additional live O2 streams")
        require(page.evaluate("() => window.__smAcceptanceO2.bufferCalls") == 0, "hidden Dashboard state performed historical live-buffer hydration")

        page.locator('#sidebar [data-page="oximetry"]').click()
        page.wait_for_function("() => document.querySelector('#page-oximetry')?.classList.contains('active')")
        page.wait_for_timeout(120)
        require(page.evaluate("() => !document.getElementById('o2rLiveDual')?._smO2Meta"), "returning to Live restored an old measurement buffer")
        require(len(live_stream_requests) > before_streams, "returning to Oximetria Live did not reopen the SSE stream")
        page.evaluate(
            """t => {
              const f=window.__smAcceptanceO2;
              f.emitLive({timestamp:t+5,spo2:94,heart_rate:68,motion:0});
            }""",
            latest_before,
        )
        page.wait_for_function("t => {const rows=document.getElementById('o2rLiveDual')?._smO2Meta?.rows||[];return rows.length===1&&rows.every(r=>r.timestamp>t)}", arg=latest_before)

        page.evaluate(
            """() => {
              const f=window.__smAcceptanceO2, t=Math.floor(Date.now()/1000);
              f.emitLive({timestamp:t,spo2:null,heart_rate:null,motion:0,measuring:false});
            }"""
        )
        page.wait_for_function("() => document.getElementById('o2rLiveSpo2')?.textContent.trim()==='–' && document.getElementById('o2rLiveHr')?.textContent.trim()==='–'")
        require(page.locator('#o2rLiveIdle').is_visible(), "Live O2 idle state is not visible after measurement stops")
        require(page.evaluate("() => !document.getElementById('o2rLiveDual')?._smO2Meta"), "stopped measurement left stale samples in the Live chart")

        page.evaluate(
            """() => {
              const f=window.__smAcceptanceO2, now=Math.floor(Date.now()/1000);
              f.emitLive({timestamp:now-16,spo2:97,heart_rate:63,motion:0});
              f.emitLive({timestamp:now-8,spo2:96,heart_rate:64,motion:0});
              f.emitLive({timestamp:now-1,spo2:95,heart_rate:66,motion:1});
            }"""
        )
        page.wait_for_function("() => document.getElementById('o2rLiveDual')?._smO2Meta?.rows?.length >= 3")
        require(page.locator('#o2rLiveIdle').is_hidden(), "Live O2 idle state stayed visible during a real measurement")

''',
)

print("SleepMate 5.3.10 release gates aligned with the intentional new contracts.")
