from pathlib import Path

path = Path('scripts/v534_browser_acceptance.py')
text = path.read_text(encoding='utf-8')


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected exactly one target, found {count}')
    text = text.replace(old, new, 1)


fixture_anchor = "          window.__smAcceptanceO2 = {\n"
fixture_prelude = """          const dayCodeFor = ts => {
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
"""
replace_once(fixture_anchor, fixture_prelude + fixture_anchor, 'daily fixture prelude')

replace_once(
    "            liveRows,\n            bufferCalls:0,\n",
    "            liveRows,\n            bufferCalls:0,\n            dailyDay,daily,batchRows,dayCalls:0,invalidationHandlers:[],canvasText:[],\n",
    'fixture state fields',
)

native_fetch_anchor = "          const nativeFetch = window.fetch.bind(window);\n"
browser_instrumentation = """          const nativeEventAdd=window.EventSource?.prototype?.addEventListener;
          if(nativeEventAdd){
            window.EventSource.prototype.addEventListener=function(type,listener,options){
              if(type==='invalidation'&&String(this.url||'').includes('/api/o2ring/events')){
                window.__smAcceptanceO2.invalidationHandlers.push(listener);
              }
              return nativeEventAdd.call(this,type,listener,options);
            };
          }
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
"""
replace_once(native_fetch_anchor, browser_instrumentation + native_fetch_anchor, 'EventSource/canvas instrumentation')

trend_fetch_anchor = "            if (url.pathname === '/api/o2ring/trends') return jsonResponse({rows:f.trendRows});\n"
daily_fetch = """            if (url.pathname === '/api/o2ring/day') {
              f.dayCalls++;
              return jsonResponse({...f.daily,day:url.searchParams.get('day')||f.dailyDay});
            }
            if (url.pathname === '/api/o2ring/day-batch') {
              const wanted=(url.searchParams.get('days')||'').split(',').filter(Boolean);
              return jsonResponse({rows:f.batchRows.filter(r=>wanted.includes(r.day))});
            }
"""
replace_once(trend_fetch_anchor, daily_fetch + trend_fetch_anchor, 'daily/batch fetch fixtures')

main_anchor = "\n\ndef main() -> int:\n"
zoom_helper = r'''

def zoom_canvas(page: Page, canvas_id: str) -> tuple[list[float], list[float]]:
    canvas = page.locator(f"#{canvas_id}")
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
'''
replace_once(main_anchor, zoom_helper + main_anchor, 'zoom helper')

mode_anchor = '        progress("Focus/All charts/Oximetria repeated mode switching")\n'
daily_test = r'''        progress("data-backed Dashboard Oximetria/Focus/All charts and SleepSync invalidation")
        page.evaluate(
            """() => {
              const f=window.__smAcceptanceO2,d=document.getElementById('day');
              if(![...d.options].some(o=>o.value===f.dailyDay))d.add(new Option('Acceptance O2',f.dailyDay));
              d.value=f.dailyDay;
              const a=f.daily.samples[0].timestamp*1000,b=f.daily.samples.at(-1).timestamp*1000;
              state.days=[f.dailyDay];state.currentDay=f.dailyDay;state.full=[a,b];state.view=[a,b];state.summary=null;
              document.getElementById('dashboardOverviewView')?.classList.add('hidden');
              document.getElementById('dashboardDailyView')?.classList.remove('hidden');
            }"""
        )
        page.locator("#o2rDailyBtn").click()
        page.wait_for_function("() => window.__smAcceptanceO2.dayCalls > 0")
        page.wait_for_function("() => document.getElementById('o2rDayDual')?._smO2Meta?.rows?.length >= 5")
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
              const f=window.__smAcceptanceO2;f.canvasText=[];
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

'''
replace_once(mode_anchor, daily_test + mode_anchor, 'data-backed dashboard acceptance block')

path.write_text(text, encoding='utf-8')
