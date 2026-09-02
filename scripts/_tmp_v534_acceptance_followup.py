from pathlib import Path

path = Path('scripts/v534_browser_acceptance.py')
text = path.read_text(encoding='utf-8')


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected one target, found {count}')
    text = text.replace(old, new, 1)


replace_once(
    '            dailyDay,daily,batchRows,dayCalls:0,invalidationHandlers:[],canvasText:[],\n',
    '            dailyDay,daily,batchRows,dayCalls:0,invalidationHandlers:[],canvasText:[],pathRecords:[],\n',
    'fixture instrumentation state',
)

anchor = '          const nativeFillText=CanvasRenderingContext2D.prototype.fillText;\n'
instrumentation = '''          const nativeBeginPath=CanvasRenderingContext2D.prototype.beginPath;
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
'''
replace_once(anchor, instrumentation + anchor, 'canvas path instrumentation')

old_setup = '''        page.evaluate(
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
'''
new_setup = '''        page.evaluate(
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
'''
replace_once(old_setup, new_setup, 'synthetic daily route setup')

anchor_gap = '''        page.wait_for_function("() => document.getElementById('o2rDayDual')?._smO2Meta?.rows?.length >= 5")
        hover_canvas(page, "o2rDayDual", ("SpO₂", "Pulzus"))
'''
gap_test = '''        page.wait_for_function("() => document.getElementById('o2rDayDual')?._smO2Meta?.rows?.length >= 5")
        gap_paths = page.evaluate(
            """() => window.__smAcceptanceO2.pathRecords.filter(x =>
              x.id==='o2rDaySpo2Chart' && x.lines>0 &&
              ['#55d8ff','rgb(85, 216, 255)'].includes(String(x.style).toLowerCase())
            )"""
        )
        require(len(gap_paths) >= 2, f"daily SpO2 line crossed a long no-data gap instead of splitting into segments: {gap_paths}")
        hover_canvas(page, "o2rDayDual", ("SpO₂", "Pulzus"))
'''
replace_once(anchor_gap, gap_test, 'daily long-gap behavior')

report_anchor = '''        require(page.locator("#o2rDailyBtn").inner_text().strip() == "Oximetria", "Oximetria mode mutated into navigation/back")

        progress("Oximetria Live/Recordings/Trends repeated switching")
'''
report_test = '''        require(page.locator("#o2rDailyBtn").inner_text().strip() == "Oximetria", "Oximetria mode mutated into navigation/back")

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
'''
replace_once(report_anchor, report_test, 'report O2 SleepSync acceptance')

path.write_text(text, encoding='utf-8')
