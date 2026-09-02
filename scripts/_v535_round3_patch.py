from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path): return (ROOT / path).read_text(encoding='utf-8')
def write(path, text): (ROOT / path).write_text(text, encoding='utf-8')
def replace_once(path, old, new):
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{path}: expected one occurrence, found {count}: {old[:140]!r}')
    write(path, text.replace(old, new, 1))
def replace_between(path, start, end, replacement):
    text = read(path)
    i = text.find(start)
    j = text.find(end, i + len(start)) if i >= 0 else -1
    if i < 0 or j < 0:
        raise SystemExit(f'{path}: replacement markers missing: {start!r} / {end!r}')
    write(path, text[:i] + replacement.rstrip() + '\n' + text[j:])

# ---------------------------------------------------------------------------
# Requirements 12-13: one unified Oximetria action/tab row, compact state below it.
# ---------------------------------------------------------------------------
replace_once(
    'web/o2ring.js',
    '<div class="o2r-hero-actions"><button id="o2rDash" type="button">← Dashboard</button><button id="o2rConnectNow" type="button">＋ Kapcsolódás</button><button id="o2rSyncNowTop" type="button">↻ Szinkron</button></div></section><div class="o2r-tabs"><button data-o2r-tab="live" class="active">Élő O₂ monitor</button><button data-o2r-tab="recordings">Felvételek</button><button data-o2r-tab="trends">Trendek</button></div><section class="o2r-view active"',
    '<div class="o2r-hero-actions"><button id="o2rDash" type="button">← Dashboard</button><button id="o2rConnectNow" type="button">＋ Kapcsolódás</button><button id="o2rSyncNowTop" type="button">↻ Szinkron</button><button data-o2r-tab="live" class="active">Élő O₂ monitor</button><button data-o2r-tab="recordings">Felvételek</button><button data-o2r-tab="trends">Trendek</button></div><div id="o2rSearchState" class="o2r-search-state"><span>Állapot</span><strong id="o2rLiveState">–</strong><small id="o2rLiveSignal">jel –</small></div></section><section class="o2r-view active"',
)
replace_once(
    'web/o2ring.js',
    '<article class="panel o2r-live-card state"><label>Állapot</label><strong id="o2rLiveState">–</strong><small id="o2rLiveSignal">jel –</small></article>',
    '',
)
replace_once(
    'web/o2ring-v534.css',
    '.o2r-live-cards{grid-template-columns:repeat(4,minmax(0,1fr))!important;',
    '.o2r-live-cards{grid-template-columns:repeat(3,minmax(0,1fr))!important;',
)
css = read('web/o2ring-v534.css')
css += '''

/* v5.3.5 Oximetria unified navigation + compact connection state */
.o2r-hero-actions{display:flex;align-items:center;gap:6px;flex-wrap:wrap}.o2r-hero-actions [data-o2r-tab]{flex:0 0 auto}.o2r-search-state{display:flex;align-items:center;gap:8px;margin-top:7px;padding:6px 9px;border:1px solid rgba(96,175,211,.18);border-radius:10px;background:rgba(5,14,24,.38);min-height:31px}.o2r-search-state>span{font-size:9px;color:#8fa8bc;text-transform:uppercase;letter-spacing:.05em}.o2r-search-state>strong{font-size:11px;color:#e6f5ff}.o2r-search-state>small{font-size:9px;color:#91a8bb;margin-left:auto}
@media(max-width:600px){.o2r-hero-actions{overflow-x:auto;flex-wrap:nowrap;padding-bottom:2px}.o2r-hero-actions>button{white-space:nowrap}.o2r-search-state{width:100%}}
'''
write('web/o2ring-v534.css', css)

# ---------------------------------------------------------------------------
# Browser fixture: medians/min/max must be independent values and selection/line
# drawing must be observable, not inferred from source markers.
# ---------------------------------------------------------------------------
replace_between(
    'scripts/v534_browser_acceptance.py',
    '          const summary = (avg,min,hr,t90=0,odi3=1.2,odi4=.6) => ({',
    '          const liveRows = [',
    '''          const summary = (avg,min,hr,t90=0,odi3=1.2,odi4=.6,spo2Median=avg,hrMedian=hr) => ({
            spo2_average:avg, spo2_median:spo2Median, spo2_minimum:min,
            spo2_maximum:Math.min(100,Math.max(min,Math.round(avg+2))),
            heart_rate_average:hr, heart_rate_median:hrMedian,
            heart_rate_minimum:Math.max(20,Math.round(hr-9)),
            heart_rate_maximum:Math.min(240,Math.round(hr+11)),
            t90_seconds:t90, odi3, odi4, coverage_percent:100
          });
          const liveRows = [''',
)
replace_once(
    'scripts/v534_browser_acceptance.py',
    '            summary:summary(95.8,93,65.2,42,1.4,.7), samples:dailySamples',
    '            summary:summary(95.8,93,65.2,42,1.4,.7,96.4,64.0), samples:dailySamples',
)
replace_once(
    'scripts/v534_browser_acceptance.py',
    '            dailyDay,daily,batchRows,dayCalls:0,invalidationHandlers:[],canvasText:[],pathRecords:[],',
    '            dailyDay,daily,batchRows,dayCalls:0,invalidationHandlers:[],canvasText:[],pathRecords:[],rectRecords:[],',
)
replace_once(
    'scripts/v534_browser_acceptance.py',
    "              f.pathRecords.push({id:this.canvas.id,style:String(this.strokeStyle),moves:p.moves||0,lines:p.lines||0});",
    "              f.pathRecords.push({id:this.canvas.id,style:String(this.strokeStyle),width:Number(this.lineWidth)||0,moves:p.moves||0,lines:p.lines||0});",
)
replace_once(
    'scripts/v534_browser_acceptance.py',
    '          const nativeFillText=CanvasRenderingContext2D.prototype.fillText;\n',
    '''          const nativeFillRect=CanvasRenderingContext2D.prototype.fillRect;
          CanvasRenderingContext2D.prototype.fillRect=function(x,y,w,h){
            const f=window.__smAcceptanceO2;
            if(f&&this.canvas?.id&&f.rectRecords.length<4000){
              f.rectRecords.push({id:this.canvas.id,style:String(this.fillStyle),x,y,w,h});
            }
            return nativeFillRect.call(this,x,y,w,h);
          };
          const nativeFillText=CanvasRenderingContext2D.prototype.fillText;
''',
)
replace_once(
    'scripts/v534_browser_acceptance.py',
    "            if (url.pathname === '/api/o2ring/live-buffer') {",
    '''            if (url.pathname === `/api/day/${f.dailyDay}/stats`) {
              return jsonResponse({apnea_duration:'0:00',rows:[{key:'pressure',title:'Nyomás',unit:'cmH2O',min:6,median:8,p95:10,p995:11,max:12}]});
            }
            if (url.pathname === '/api/o2ring/live-buffer') {''',
)

# Helper that proves the blue drag-selection rectangle is actually painted.
insert_before = '\ndef main() -> int:\n'
text = read('scripts/v534_browser_acceptance.py')
if text.count(insert_before) != 1:
    raise SystemExit('browser main insertion marker missing')
helper = r'''
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

'''
text = text.replace(insert_before, '\n' + helper + 'def main() -> int:\n', 1)
write('scripts/v534_browser_acceptance.py', text)

# Synthetic daily route must include a valid CPAP summary so O2 mini charts can
# genuinely use the normal core hero/interaction engine.
replace_once(
    'scripts/v534_browser_acceptance.py',
    '              state.days=[f.dailyDay];state.currentDay=f.dailyDay;state.full=[a,b];state.view=[a,b];state.summary=null;\n',
    '''              state.days=[f.dailyDay];state.currentDay=f.dailyDay;state.full=[a,b];state.view=[a,b];
              state.summary={day:f.dailyDay,ahi:0,therapy_seconds:(b-a)/1000,usage:'00:11:00',counts:{OA:0,CA:0,H:0,UA:0,RERA:0},events:[],sessions:[{start:new Date(a).toISOString(),end:new Date(b).toISOString(),duration_s:(b-a)/1000}],integrity:{complete:true,edf_files:1,problems:[]}};
              buildOverviewGrid();buildStackedGrid();renderNightEvaluation(state.summary,{rows:[]},{prescriptions:[]});
''',
)

# Latest sleep card: test actual requested duration semantics, not merely absence of legacy text.
marker = '''        require(
            page.evaluate("() => window.SleepMateV530.NAV.oximetry_live?.label") == "Élő O₂ monitor",
            "PWA live O2 navigation label missing",
        )
'''
addition = marker + '''        page.evaluate("""() => {
            state.dashboardOverview={latest:{summary:{therapy_seconds:27000,usage:'07:30:00',sessions:[{},{}]}}};
            window.SleepMateFrontendV534.syncLatestSessionCard();
        }""")
        require(page.locator(".latest-sleep-cards .session-status label").inner_text().strip() == "Alvásidő", "latest sleep card label is not Alvásidő")
        require(page.locator("#latestStatus").inner_text().strip() == "7:30", "latest sleep card does not show total therapy duration")
        require(page.locator("#latestSessions").inner_text().strip() == "2 szakasz", "latest sleep secondary text lost session count")
        require(page.locator("#smDashboardO2V534").count() == 1, "Dashboard Oximetriai összegzés is not stably owned on first PWA load")
'''
replace_once('scripts/v534_browser_acceptance.py', marker, addition)

# Daily O2: assert medians, night-card content/placement/size, line weight and visible drag selection.
marker = '        page.wait_for_function("() => document.getElementById(\'o2rDayDual\')?._smO2Meta?.rows?.length >= 5")\n'
addition = marker + '''        require("96" in page.locator("#spo2").inner_text(), "daily SpO2 card did not hydrate the matched O2 median")
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
'''
replace_once('scripts/v534_browser_acceptance.py', marker, addition)

# SleepSync invalidation must update the medians too.
replace_once(
    'scripts/v534_browser_acceptance.py',
    "              f.daily.summary={...f.daily.summary,spo2_average:93.4,spo2_minimum:90,heart_rate_average:68.5};",
    "              f.daily.summary={...f.daily.summary,spo2_average:93.4,spo2_median:94.6,spo2_minimum:90,spo2_maximum:98,heart_rate_average:68.5,heart_rate_median:67.0,heart_rate_minimum:58,heart_rate_maximum:77};",
)
replace_once(
    'scripts/v534_browser_acceptance.py',
    '        require("93" in page.locator("#smNightO2Card").inner_text(), "SleepSync invalidation did not refresh the night O2 summary")',
    '        require("94" in page.locator("#smNightO2Card").inner_text() and "67" in page.locator("#smNightO2Card").inner_text(), "SleepSync invalidation did not refresh the night O2 medians")',
)

# Replace obsolete custom Focus chart acceptance with the requested two stock mini cards + stock hero.
replace_between(
    'scripts/v534_browser_acceptance.py',
    '        page.locator("#focusViewBtn").click()\n        page.wait_for_function("() => document.getElementById(\'smO2FocusDual\')?._smO2Meta?.rows?.length >= 5")',
    '        page.locator("#stackViewBtn").click()\n',
    '''        page.locator("#focusViewBtn").click()
        page.wait_for_function("() => document.querySelector('.overview-card[data-key=\"o2_spo2\"]') && document.querySelector('.overview-card[data-key=\"o2_hr\"]')")
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
''',
)

# All Charts: validate Alapnézet, a real right axis strip and hover values on a normal CPAP card.
marker = '''        require(
            all(x["pointerEvents"] != "none" for x in stack_pointer_events),
            f"Stack O2 chart input was disabled by the CPAP base-canvas CSS: {stack_pointer_events}",
        )
'''
addition = marker + '''        flow_overlay = page.locator('#stackedCharts .stack-chart[data-key="flow"] .sm-o2-overlay-select')
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
'''
replace_once('scripts/v534_browser_acceptance.py', marker, addition)

# Focus restore now uses the core state.view rather than removed custom canvas metadata.
replace_once(
    'scripts/v534_browser_acceptance.py',
    '        restored_focus = page.evaluate("() => {const m=document.getElementById(\'smO2FocusDual\')?._smO2Meta;return m?[m.a,m.b]:null}")\n        require(restored_focus is not None and max(abs(restored_focus[i]-focus_zoom[i]) for i in (0,1)) < .05, f"Focus zoom was not preserved across mode switching: {focus_zoom} -> {restored_focus}")',
    '        restored_focus = page.evaluate("() => [...state.view]")\n        require(restored_focus is not None and max(abs(restored_focus[i]-focus_zoom[i]) for i in (0,1)) < 2, f"Focus zoom was not preserved across mode switching: {focus_zoom} -> {restored_focus}")',
)
replace_once(
    'scripts/v534_browser_acceptance.py',
    '            "smO2FocusSpo2","smO2FocusHr","smO2FocusDual",\n',
    '            "mini-o2_spo2","mini-o2_hr","heroOverlay",\n',
)

# Reports: compact geometry + exact Daily Statistics min/median/max O2 rows.
marker = '        require(report_after != report_before, f"SleepSync invalidation did not refresh report O2 columns: {report_before} -> {report_after}")\n'
addition = marker + '''        report_geometry = page.evaluate("""() => {
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
'''
replace_once('scripts/v534_browser_acceptance.py', marker, addition)

# Oximetria page layout acceptance for requirements 12-13.
marker = '''        page.locator('#sidebar [data-page="oximetry"]').click()
        page.wait_for_function("() => document.querySelector('#page-oximetry')?.classList.contains('active')")
        for tab in ("recordings", "trends", "live"):
'''
addition = '''        page.locator('#sidebar [data-page="oximetry"]').click()
        page.wait_for_function("() => document.querySelector('#page-oximetry')?.classList.contains('active')")
        action_labels = page.evaluate("() => [...document.querySelectorAll('#page-oximetry .o2r-hero-actions > button')].map(x=>x.textContent.trim())")
        require(action_labels == ['← Dashboard','＋ Kapcsolódás','↻ Szinkron','Élő O₂ monitor','Felvételek','Trendek'], f"Oximetria top buttons are not one unified ordered row: {action_labels}")
        require(page.locator("#page-oximetry .o2r-tabs").count() == 0, "Oximetria still has a separate tab strip")
        require(page.locator("#page-oximetry .o2r-live-cards .state").count() == 0, "large separate Állapot card still exists in Live metrics")
        require(page.locator("#o2rSearchState").count() == 1 and page.evaluate("() => document.getElementById('o2rSearchState')?.parentElement?.classList.contains('o2r-hero')") is True, "compact Állapot was not moved under the Oximetria connection/search area")
        for tab in ("recordings", "trends", "live"):
'''
replace_once('scripts/v534_browser_acceptance.py', marker, addition)

# Dashboard O2 section must survive repeated refreshes and a one-night dataset.
marker = '        hover_canvas(page, "smDashHrTrend", ("Pulzus",))\n'
addition = marker + '''        require(page.locator("#smDashboardO2V534").is_visible(), "Dashboard Oximetriai összegzés is hidden despite matched data")
        page.evaluate("""() => { const f=window.__smAcceptanceO2; state.dashboardOverview={rows:[{day:f.batchRows.at(-1).day}]}; window.SleepMateO2Ring.refresh(); }""")
        page.wait_for_function("() => document.getElementById('smDashO2Trend')?._smO2Meta?.rows?.length===1")
        require(page.locator("#smDashboardO2V534").count() == 1 and page.locator("#smDashboardO2V534").is_visible(), "Dashboard O2 summary disappeared with one matched night")
        page.evaluate("""() => { const f=window.__smAcceptanceO2; state.dashboardOverview={rows:f.batchRows.map(r=>({day:r.day}))}; window.SleepMateO2Ring.refresh(); }""")
        page.wait_for_function("() => document.getElementById('smDashO2Trend')?._smO2Meta?.rows?.length>=5")
'''
replace_once('scripts/v534_browser_acceptance.py', marker, addition)

# ---------------------------------------------------------------------------
# Explicit 15-point source acceptance matrix: each user report has its own test.
# ---------------------------------------------------------------------------
write('tests/test_v535_user_acceptance_matrix.py', r'''from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')

JS = read('web/o2ring.js')
CSS = read('web/o2ring-v534.css')
FRONT = read('web/frontend-v534.js')
HTML = read('web/index.html')
DOMAIN = read('cpap/oximetry.py')
BROWSER = read('scripts/v534_browser_acceptance.py')

def test_01_daily_spo2_and_pulse_cards_use_matched_medians():
    assert 'function hydrateDailyO2Metrics()' in JS
    assert 's.spo2_median' in JS and 's.heart_rate_median' in JS
    assert 'daily SpO2 card did not hydrate the matched O2 median' in BROWSER

def test_02_focus_contains_only_two_stock_o2_mini_cards():
    focus = JS[JS.index('const O2_FOCUS_DEFS'):JS.index('function ensureStackO2')]
    assert "title:'SpO₂'" in focus and "title:'Pulzus'" in focus
    assert 'smO2FocusDual' not in focus
    assert "card.className='overview-card sm-o2-focus-mini'" in focus

def test_03_o2_drag_selection_is_visibly_painted():
    assert "drag?.mode==='zoom'" in JS and "rgba(85,183,255,.16)" in JS
    assert 'require_drag_selection(page, "o2rDaySpo2Chart")' in BROWSER
    assert 'require_drag_selection(page, "o2rDayHrChart")' in BROWSER

def test_04_focus_o2_uses_the_normal_core_hero_chart():
    assert 'card.onclick=()=>selectSignal(d.key)' in JS
    assert 'loadMainSignal.__smO2' in JS and 'o2CoreSignal(state.selectedSignal)' in JS
    assert 'SpO2 Focus mini did not open the normal hero chart' in BROWSER

def test_05_o2_line_weight_matches_normal_charts():
    assert 'opts.lineWidth??1.15' in JS
    assert 'COLORS.spo2,1.05' in JS and 'COLORS.hr,1.05' in JS
    assert 'O2 chart line weight is thicker than normal charts' in BROWSER

def test_06_all_charts_overlay_has_right_scales_and_hover_values():
    assert 'function drawOverlayScaleLabels' in JS
    assert 'O₂ 100%' in JS and 'O₂ 75%' in JS and 'HR ${hrHi}' in JS and 'HR ${hrLo}' in JS
    assert "parts.push(`SpO₂ ${fmt(r.spo2,0)}%`)" in JS
    assert "parts.push(`Pulzus ${fmt(r.heart_rate,0)} bpm`)" in JS
    assert 'All Charts overlay lacks SpO2 right-axis labels' in BROWSER

def test_07_overlay_off_option_is_alapnezet():
    assert '<option value="off">Alapnézet</option>' in JS
    assert '+ O₂</option>' not in JS

def test_08_latest_sleep_card_shows_total_duration():
    assert '<label>Alvásidő</label>' in HTML
    assert 'latestDuration(summary)' in FRONT
    assert 'latest?.summary||latest' in FRONT
    assert 'latest sleep card does not show total therapy duration' in BROWSER

def test_09_dashboard_oximetry_summary_is_stably_owned_and_draws_data():
    assert 'function ensureDashboardO2Section()' in JS
    assert 'const sec=ensureDashboardO2Section();if(!sec)return' in JS
    assert 'seg.length===1' in JS
    assert 'Dashboard O2 summary disappeared with one matched night' in BROWSER

def test_10_report_selected_days_table_is_compact():
    assert "classList.add('sm-report-days-compact')" in JS
    assert '.sm-report-days-compact .report-days-table th' in CSS
    assert 'Reports selected-days table remains oversized' in BROWSER

def test_11_daily_statistics_contains_spo2_and_pulse_min_median_max():
    assert 'spo2_maximum: int | None' in DOMAIN
    assert "row('spo2','SpO₂ (O2Ring)'" in JS
    assert "row('hr','Pulzus (O2Ring)'" in JS
    assert 'Daily Statistics missing pulse min/median/max' in BROWSER

def test_12_oximetry_top_navigation_is_one_row_after_sync():
    install = JS[JS.index('function installPage()'):JS.index('function closeMobileO2Drawer()')]
    actions = install[install.index('<div class="o2r-hero-actions">'):install.index('</div><div id="o2rSearchState"')]
    assert actions.index('o2rSyncNowTop') < actions.index('data-o2r-tab="live"') < actions.index('data-o2r-tab="recordings"') < actions.index('data-o2r-tab="trends"')
    assert '<div class="o2r-tabs">' not in install

def test_13_large_state_card_is_moved_under_connection_search_area():
    install = JS[JS.index('function installPage()'):JS.index('function closeMobileO2Drawer()')]
    assert 'id="o2rSearchState" class="o2r-search-state"' in install
    assert 'o2r-live-card state' not in install
    assert '.o2r-search-state{' in CSS

def test_14_night_evaluation_o2_card_only_contains_spo2_and_pulse_medians():
    block = JS[JS.index('function renderNightCard()'):JS.index('function drawDashboardO2Mini()')]
    assert "list=id('nightEvalList')" in block
    assert 's.spo2_median' in block and 's.heart_rate_median' in block
    for forbidden in ('Minimum <b>', 'T90 <b>', 'ODI3 / ODI4 <b>'):
        assert forbidden not in block

def test_15_night_o2_card_is_a_normal_grid_card_not_full_width():
    assert '#nightEvalList .sm-night-o2-card' in CSS
    assert 'width:auto!important' in CSS and 'max-width:none!important' in CSS
    assert 'night O2 card still spans the full PC width' in BROWSER
''')

print('v5.3.5 round 3 patch applied')
