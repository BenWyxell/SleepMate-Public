from pathlib import Path

P = Path('scripts/v534_browser_acceptance.py')
text = P.read_text(encoding='utf-8')

def rep(old: str, new: str) -> None:
    global text
    n = text.count(old)
    if n != 1:
        raise SystemExit(f'expected exactly one marker, got {n}: {old[:180]!r}')
    text = text.replace(old, new, 1)

# Real core flow-signal fixture: the normal Focus hero must load through the same
# /api/day/<day>/signal/flow path that production uses.
rep(
    '''          const daily = {
            day:dailyDay, available:true, auto_match:true,''',
    '''          const flowSignal = {
            key:'flow', unit:'L/min',
            series:[{
              start:new Date((now-3600)*1000).toISOString(),
              points:[[0,0],[60,11],[120,-7],[240,8],[360,-10],[480,6],[600,-5],[660,0]]
            }]
          };
          const daily = {
            day:dailyDay, available:true, auto_match:true,''',
)
rep(
    "dailyDay,daily,batchRows,dayCalls:0,invalidationHandlers:[],canvasText:[],pathRecords:[],rectRecords:[],",
    "dailyDay,daily,flowSignal,batchRows,dayCalls:0,invalidationHandlers:[],canvasText:[],pathRecords:[],rectRecords:[],",
)
rep(
    '''            if (url.pathname === `/api/day/${f.dailyDay}/stats`) {
              return jsonResponse({apnea_duration:'0:00',rows:[{key:'pressure',title:'Nyomás',unit:'cmH2O',min:6,median:8,p95:10,p995:11,max:12}]});
            }''',
    '''            if (url.pathname === `/api/day/${f.dailyDay}/signal/flow`) {
              return jsonResponse(f.flowSignal);
            }
            if (url.pathname === `/api/day/${f.dailyDay}/stats`) {
              return jsonResponse({apnea_duration:'0:00',rows:[{key:'pressure',title:'Nyomás',unit:'cmH2O',min:6,median:8,p95:10,p995:11,max:12}]});
            }''',
)

# Synthetic core summary has known original CPAP oximetry values. Matched O2Ring
# must override them, and disappearance of the match must restore these values.
rep(
    '''              state.days=[f.dailyDay];state.currentDay=f.dailyDay;state.full=[a,b];state.view=[a,b];
              state.summary={day:f.dailyDay,ahi:0,therapy_seconds:(b-a)/1000,usage:'00:11:00',counts:{OA:0,CA:0,H:0,UA:0,RERA:0},events:[],sessions:[{start:new Date(a).toISOString(),end:new Date(b).toISOString(),duration_s:(b-a)/1000}],integrity:{complete:true,edf_files:1,problems:[]}};''',
    '''              state.days=[f.dailyDay];state.currentDay=f.dailyDay;state.full=[a,b];state.view=[a,b];
              state.settings={...state.settings,show_spo2:true,show_hr:true};
              state.summary={day:f.dailyDay,ahi:0,therapy_seconds:(b-a)/1000,usage:'00:11:00',counts:{OA:0,CA:0,H:0,UA:0,RERA:0},events:[],sessions:[{start:new Date(a).toISOString(),end:new Date(b).toISOString(),duration_s:(b-a)/1000}],oximetry:{spo2_median:91,pulse_median:58},integrity:{complete:true,edf_files:1,problems:[]}};''',
)
# Keep the exact-value assertion and align only its diagnostic marker with the matrix.
rep(
    '"daily SpO2 card did not hydrate the requested median"',
    '"daily SpO2 card did not hydrate the matched O2 median"',
)

# Request 01: matched ring data disappears -> core values return; match returns ->
# ring medians return. Verify both directions after actual invalidation refreshes.
rep(
    '''        require("94" in page.locator("#smNightO2Card").inner_text() and "67" in page.locator("#smNightO2Card").inner_text(), "SleepSync invalidation did not refresh the night O2 medians")

        page.locator("#focusViewBtn").click()''',
    '''        require("94" in page.locator("#smNightO2Card").inner_text() and "67" in page.locator("#smNightO2Card").inner_text(), "SleepSync invalidation did not refresh the night O2 medians")

        progress("matched O2 disappearance restores core oximetry and return reapplies medians")
        disappear_calls = page.evaluate("() => window.__smAcceptanceO2.dayCalls")
        page.evaluate(
            """() => {
              const f=window.__smAcceptanceO2;
              f.savedMatchedDaily=structuredClone(f.daily);
              f.daily={...f.daily,available:false,summary:null,matches:[],samples:[]};
              f.emitInvalidation('sleepsync-completed');
            }"""
        )
        page.wait_for_function("n => window.__smAcceptanceO2.dayCalls > n", arg=disappear_calls)
        page.wait_for_function("() => document.getElementById('spo2')?.textContent.trim()==='91%' && document.getElementById('hr')?.textContent.trim()==='58 bpm'")
        require(page.locator("#spo2").inner_text().strip() == "91%", "daily SpO2 card stayed stale after matched O2 data disappeared")
        require(page.locator("#hr").inner_text().strip() == "58 bpm", "daily pulse card stayed stale after matched O2 data disappeared")

        return_calls = page.evaluate("() => window.__smAcceptanceO2.dayCalls")
        page.evaluate(
            """() => {
              const f=window.__smAcceptanceO2;
              f.daily=structuredClone(f.savedMatchedDaily);
              f.emitInvalidation('sleepsync-completed');
            }"""
        )
        page.wait_for_function("n => window.__smAcceptanceO2.dayCalls > n", arg=return_calls)
        page.wait_for_function("() => document.getElementById('spo2')?.textContent.trim()==='94.6%' && document.getElementById('hr')?.textContent.trim()==='67 bpm'")
        require(page.locator("#spo2").inner_text().strip() == "94.6%", "daily SpO2 median did not return when matched O2 data returned")
        require(page.locator("#hr").inner_text().strip() == "67 bpm", "daily pulse median did not return when matched O2 data returned")

        page.locator("#focusViewBtn").click()''',
)

# Dashboard aggregate must remain visible with exactly one matched night.
rep(
    '''        page.evaluate(
            """() => {
              const f=window.__smAcceptanceO2;
              state.dashboardOverview={rows:f.batchRows.map(r=>({day:r.day}))};
              document.getElementById('dashboardDailyView')?.classList.add('hidden');
              document.getElementById('dashboardOverviewView')?.classList.remove('hidden');
            }"""
        )
        page.evaluate("() => window.SleepMateO2Ring.refresh()")''',
    '''        page.evaluate(
            """() => {
              const f=window.__smAcceptanceO2;
              state.dashboardOverview={rows:[{day:f.batchRows.at(-1).day}]};
              document.getElementById('dashboardDailyView')?.classList.add('hidden');
              document.getElementById('dashboardOverviewView')?.classList.remove('hidden');
            }"""
        )
        page.evaluate("() => window.SleepMateO2Ring.refresh()")
        page.wait_for_function("() => document.getElementById('smDashO2Trend')?._smO2Meta?.rows?.length === 1")
        require(page.locator("#smDashO2Avg").inner_text().strip() != "—", "Dashboard O2 summary disappeared with one matched night")

        page.evaluate(
            """() => {
              const f=window.__smAcceptanceO2;
              state.dashboardOverview={rows:f.batchRows.map(r=>({day:r.day}))};
            }"""
        )
        page.evaluate("() => window.SleepMateO2Ring.refresh()")''',
)

# Dashboard trend: skip one night. Two segments must be drawn and date labels must
# be present on the x axis.
rep(
    '''        hover_canvas(page, "smDashO2Trend", ("SpO₂",))
        hover_canvas(page, "smDashHrTrend", ("Pulzus",))

        page.evaluate(
            """() => {
              document.getElementById('dashboardOverviewView')?.classList.add('hidden');''',
    '''        hover_canvas(page, "smDashO2Trend", ("SpO₂",))
        hover_canvas(page, "smDashHrTrend", ("Pulzus",))

        page.evaluate(
            """() => {
              const f=window.__smAcceptanceO2;
              f.pathRecords=[];f.canvasText=[];
              state.dashboardOverview={rows:[f.batchRows[0],f.batchRows[1],f.batchRows[3],f.batchRows[4]].map(r=>({day:r.day}))};
            }"""
        )
        page.evaluate("() => window.SleepMateO2Ring.refresh()")
        page.wait_for_function("() => document.getElementById('smDashO2Trend')?._smO2Meta?.rows?.length === 4")
        missing_night_paths = page.evaluate(
            """() => window.__smAcceptanceO2.pathRecords.filter(x =>
              x.id==='smDashO2Trend' && x.lines>0 &&
              ['#55d8ff','rgb(85, 216, 255)'].includes(String(x.style).toLowerCase())
            )"""
        )
        require(len(missing_night_paths) >= 2, f"Dashboard O2 trend bridged a missing night: {missing_night_paths}")
        dashboard_date_labels = page.evaluate("() => window.__smAcceptanceO2.canvasText.filter(x=>x.id==='smDashO2Trend').map(x=>x.text)")
        require(any(x.count('.') >= 2 and ':' not in x for x in dashboard_date_labels), f"O2 trend X-axis did not render dates: {dashboard_date_labels}")

        page.evaluate(
            """() => {
              document.getElementById('dashboardOverviewView')?.classList.add('hidden');''',
)

# Peer modes must not invalidate/refetch the already loaded O2 day.
rep(
    '''        daily_listener_before = page.evaluate(
            "ids => Object.fromEntries(ids.map(id => [id, window.__smO2ListenerCounts[id] || 0]))",
            persistent_daily_ids,
        )
        for _ in range(6):''',
    '''        daily_listener_before = page.evaluate(
            "ids => Object.fromEntries(ids.map(id => [id, window.__smO2ListenerCounts[id] || 0]))",
            persistent_daily_ids,
        )
        mode_day_calls_before = page.evaluate("() => window.__smAcceptanceO2.dayCalls")
        for _ in range(6):''',
)
rep(
    '''        require(daily_listener_after == daily_listener_before, f"daily O2 chart listeners leaked across peer-mode switching: {daily_listener_before} -> {daily_listener_after}")
        require(page.locator("#smDailyModeSwitchHost").count() == 1, "daily peer-mode host duplicated during repeated switching")''',
    '''        require(daily_listener_after == daily_listener_before, f"daily O2 chart listeners leaked across peer-mode switching: {daily_listener_before} -> {daily_listener_after}")
        mode_day_calls_after = page.evaluate("() => window.__smAcceptanceO2.dayCalls")
        require(mode_day_calls_after == mode_day_calls_before, f"peer-mode switching force-refetched daily O2 data: {mode_day_calls_before} -> {mode_day_calls_after}")
        require(page.locator("#smDailyModeSwitchHost").count() == 1, "daily peer-mode host duplicated during repeated switching")''',
)

# Landscape must preserve aligned graph geometry, not only avoid toolbar overflow.
rep(
    '''        page.set_viewport_size({"width": 844, "height": 390})
        page.wait_for_timeout(160)
        assert_no_horizontal_overflow(page, "Oximetria iPhone landscape")
        landscape_tabs = page.evaluate("() => [...document.querySelectorAll('#page-oximetry .o2r-hero-actions > button')].map(b=>({text:b.textContent.trim(),left:b.getBoundingClientRect().left,right:b.getBoundingClientRect().right,top:b.getBoundingClientRect().top}))")
        require(len(landscape_tabs) == 6 and max(x["right"] for x in landscape_tabs) <= 844 + 2, f"Oximetria landscape top controls overflow: {landscape_tabs}")''',
    '''        page.set_viewport_size({"width": 844, "height": 390})
        page.wait_for_timeout(160)
        progress("iPhone landscape Oximetria geometry")
        assert_no_horizontal_overflow(page, "Oximetria iPhone landscape")
        landscape_tabs = page.evaluate("() => [...document.querySelectorAll('#page-oximetry .o2r-hero-actions > button')].map(b=>({text:b.textContent.trim(),left:b.getBoundingClientRect().left,right:b.getBoundingClientRect().right,top:b.getBoundingClientRect().top}))")
        require(len(landscape_tabs) == 6 and max(x["right"] for x in landscape_tabs) <= 844 + 2, f"Oximetria landscape top controls overflow: {landscape_tabs}")
        landscape_geometry = page.evaluate(
            """() => {
                const a=document.getElementById('o2rLiveSpo2Chart')?.getBoundingClientRect();
                const b=document.getElementById('o2rLiveHrChart')?.getBoundingClientRect();
                return a&&b?{leftA:a.left,leftB:b.left,widthA:a.width,widthB:b.width}:null;
            }"""
        )
        require(landscape_geometry is not None, "landscape O2 canvases missing")
        require(abs(landscape_geometry["leftA"] - landscape_geometry["leftB"]) <= 1.5, f"landscape O2 X origins differ: {landscape_geometry}")
        require(abs(landscape_geometry["widthA"] - landscape_geometry["widthB"]) <= 1.5, f"landscape O2 plot widths differ: {landscape_geometry}")''',
)

P.write_text(text, encoding='utf-8')
print('behavioral acceptance coverage patch applied')
