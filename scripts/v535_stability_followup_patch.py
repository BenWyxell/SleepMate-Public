from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path): return (ROOT / path).read_text(encoding='utf-8')
def write(path, text): (ROOT / path).write_text(text, encoding='utf-8')
def replace_once(path, old, new):
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{path}: expected one occurrence, found {count}: {old[:180]!r}')
    write(path, text.replace(old, new, 1))

# 1) Uninstall/status race: do not mutate or re-arm polling after runtime shutdown.
replace_once(
    'web/o2ring.js',
    "async function refreshStatus(){clearTimeout(R.statusTimer);try{const x=await api('/api/o2ring/status');R.status=x;R.settings=x.settings||R.settings;applyLive(x.live||{});installSettingsConnection();window.dispatchEvent(new CustomEvent('sleepmate-o2-status',{detail:x}))}catch{}finally{const relevant=id('page-oximetry')?.classList.contains('active')||id('page-settings')?.classList.contains('active');R.statusTimer=setTimeout(refreshStatus,relevant?6000:30000)}}",
    "async function refreshStatus(){if(!R.installed)return;clearTimeout(R.statusTimer);R.statusTimer=null;try{const x=await api('/api/o2ring/status');if(!R.installed)return;R.status=x;R.settings=x.settings||R.settings;applyLive(x.live||{});installSettingsConnection();window.dispatchEvent(new CustomEvent('sleepmate-o2-status',{detail:x}))}catch{}finally{if(R.installed){const relevant=id('page-oximetry')?.classList.contains('active')||id('page-settings')?.classList.contains('active');R.statusTimer=setTimeout(refreshStatus,relevant?6000:30000)}}}",
)
replace_once(
    'web/o2ring.js',
    "function uninstall(){R.installed=false;closeLiveStream();if(R.eventSource){R.eventSource.close();R.eventSource=null}clearTimeout(R.statusTimer);qa('[data-o2ring-feature]').forEach(x=>x.remove());",
    "function uninstall(){R.installed=false;closeLiveStream();clearO2Interactions();if(R.eventSource){R.eventSource.close();R.eventSource=null}clearTimeout(R.statusTimer);R.statusTimer=null;qa('[data-o2ring-feature]').forEach(x=>x.remove());",
)

# 2) Peer-mode switching must reuse the already loaded day instead of force refetching.
replace_once(
    'web/o2ring.js',
    "ox?.classList.remove('hidden');loadDaily(true).then(drawDaily)",
    "ox?.classList.remove('hidden');loadDaily(false).then(drawDaily)",
)

# 3-4) Chart engine: explicit gap threshold + date-aware trend axis/tooltip.
replace_once(
    'web/o2ring.js',
    "const mx=t=>p.l+(t-a)/Math.max(.001,b-a)*iw,my=(v,r)=>p.t+(r[1]-v)/Math.max(.001,r[1]-r[0])*ih,gap=chartGap(rows,!!opts.trendGap);",
    "const mx=t=>p.l+(t-a)/Math.max(.001,b-a)*iw,my=(v,r)=>p.t+(r[1]-v)/Math.max(.001,r[1]-r[0])*ih,explicitGap=num(opts.gapSeconds),gap=explicitGap==null?chartGap(rows,!!opts.trendGap):Math.max(0,explicitGap);",
)
replace_once(
    'web/o2ring.js',
    "ctx.fillStyle=COLORS.text;for(let i=0;i<=4;i++){const txt=clock(a+(b-a)*i/4),tw=ctx.measureText(txt).width;ctx.fillText(txt,Math.max(p.l,Math.min(w-p.r-tw,p.l+iw*i/4-tw/2)),h-8)}",
    "const xLabel=typeof opts.xLabel==='function'?opts.xLabel:clock;ctx.fillStyle=COLORS.text;for(let i=0;i<=4;i++){const txt=xLabel(a+(b-a)*i/4),tw=ctx.measureText(txt).width;ctx.fillText(txt,Math.max(p.l,Math.min(w-p.r-tw,p.l+iw*i/4-tw/2)),h-8)}",
)
replace_once(
    'web/o2ring.js',
    "c._smO2Meta={rows,a,b,p,iw,ih,syncGroup:opts.syncGroup,series,redraw:opts.redraw}",
    "c._smO2Meta={rows,a,b,p,iw,ih,syncGroup:opts.syncGroup,series,redraw:opts.redraw,tooltipLabel:opts.tooltipLabel}",
)
replace_once(
    'web/o2ring.js',
    "if(m&&row){const parts=[`<b>${clock(row.timestamp)}</b>`];for(const s of m.series){",
    "if(m&&row){const hoverLabel=typeof m.tooltipLabel==='function'?m.tooltipLabel(row.timestamp):clock(row.timestamp),parts=[`<b>${hoverLabel}</b>`];for(const s of m.series){",
)
replace_once(
    'web/o2ring.js',
    "chartDraw(c,rows,{range,series:ss,syncGroup:'dash-o2',rightAxis:false,trendGap:true,redraw})",
    "chartDraw(c,rows,{range,series:ss,syncGroup:'dash-o2',rightAxis:false,trendGap:true,gapSeconds:36*3600,xLabel:date,tooltipLabel:ts=>`${date(ts)} ${clock(ts)}`,redraw})",
)
replace_once(
    'web/o2ring.js',
    "chartDraw(c,t,{range,series:ss,syncGroup:'trends',rightAxis:false,trendGap:true,redraw})",
    "chartDraw(c,t,{range,series:ss,syncGroup:'trends',rightAxis:false,trendGap:true,gapSeconds:36*3600,xLabel:date,tooltipLabel:ts=>`${date(ts)} ${clock(ts)}`,redraw})",
)

# Browser fixture: count status calls, create a real missing-night gap in both dashboard and trends.
replace_once(
    'scripts/v534_browser_acceptance.py',
    "            dailyDay,daily,batchRows,dayCalls:0,invalidationHandlers:[],canvasText:[],pathRecords:[],rectRecords:[],",
    "            dailyDay,daily,batchRows,dayCalls:0,statusCalls:0,invalidationHandlers:[],canvasText:[],pathRecords:[],rectRecords:[],",
)
replace_once(
    'scripts/v534_browser_acceptance.py',
    "          const batchRows=[0,1,2,3,4].map(i => {\n            const ts=now-(4-i)*86400;",
    "          const batchOffsets=[0,1,2,4,5];\n          const batchRows=batchOffsets.map((offset,i) => {\n            const ts=now-(5-offset)*86400;",
)
replace_once(
    'scripts/v534_browser_acceptance.py',
    "            trendRows:[0,1,2,3,4].map(i => ({\n              start_ts:now-(4-i)*86400,",
    "            trendRows:[0,1,2,4,5].map((offset,i) => ({\n              start_ts:now-(5-offset)*86400,",
)
replace_once(
    'scripts/v534_browser_acceptance.py',
    "            if (url.pathname === `/api/day/${f.dailyDay}/stats`) {",
    "            if (url.pathname === '/api/o2ring/status') { f.statusCalls++; return nativeFetch(input, init); }\n            if (url.pathname === `/api/day/${f.dailyDay}/stats`) {",
)

# Plain Focus/Stack/Oximetria switching is a UI operation: no forced day API requests.
replace_once(
    'scripts/v534_browser_acceptance.py',
    "        daily_listener_before = page.evaluate(\n            \"ids => Object.fromEntries(ids.map(id => [id, window.__smO2ListenerCounts[id] || 0]))\",\n            persistent_daily_ids,\n        )\n        for _ in range(6):",
    "        daily_listener_before = page.evaluate(\n            \"ids => Object.fromEntries(ids.map(id => [id, window.__smO2ListenerCounts[id] || 0]))\",\n            persistent_daily_ids,\n        )\n        page.wait_for_timeout(180)\n        mode_day_calls_before = page.evaluate(\"() => window.__smAcceptanceO2.dayCalls\")\n        for _ in range(6):",
)
replace_once(
    'scripts/v534_browser_acceptance.py',
    "        daily_listener_after = page.evaluate(\n            \"ids => Object.fromEntries(ids.map(id => [id, window.__smO2ListenerCounts[id] || 0]))\",\n            persistent_daily_ids,\n        )\n        require(daily_listener_after == daily_listener_before,",
    "        daily_listener_after = page.evaluate(\n            \"ids => Object.fromEntries(ids.map(id => [id, window.__smO2ListenerCounts[id] || 0]))\",\n            persistent_daily_ids,\n        )\n        page.wait_for_timeout(180)\n        mode_day_calls_after = page.evaluate(\"() => window.__smAcceptanceO2.dayCalls\")\n        require(mode_day_calls_after == mode_day_calls_before, f\"peer-mode switching force-refetched daily O2 data: {mode_day_calls_before} -> {mode_day_calls_after}\")\n        require(daily_listener_after == daily_listener_before,",
)

# Dashboard mini trend must split at the deliberately missing night.
replace_once(
    'scripts/v534_browser_acceptance.py',
    "        page.evaluate(\"\"\"() => { const f=window.__smAcceptanceO2; state.dashboardOverview={rows:f.batchRows.map(r=>({day:r.day}))}; window.SleepMateO2Ring.refresh(); }\"\"\")\n        page.wait_for_function(\"() => document.getElementById('smDashO2Trend')?._smO2Meta?.rows?.length>=5\")",
    "        page.evaluate(\"\"\"() => { const f=window.__smAcceptanceO2; f.pathRecords=[]; state.dashboardOverview={rows:f.batchRows.map(r=>({day:r.day}))}; window.SleepMateO2Ring.refresh(); }\"\"\")\n        page.wait_for_function(\"() => document.getElementById('smDashO2Trend')?._smO2Meta?.rows?.length>=5\")\n        page.wait_for_timeout(160)\n        dash_gap_paths = page.evaluate(\"\"\"() => window.__smAcceptanceO2.pathRecords.filter(x => x.id==='smDashO2Trend' && x.lines>0 && ['#55d8ff','rgb(85, 216, 255)'].includes(String(x.style).toLowerCase()))\"\"\")\n        require(len([x for x in dash_gap_paths if x.get('moves') == 1]) >= 2, f\"Dashboard O2 trend bridged a missing night: {dash_gap_paths}\")",
)

# Oximetry trend must split the 48h gap and render actual date labels.
old_trend_assert = '''        require(any(x.get("moves") == 1 and x.get("lines", 0) >= 4 for x in trend_paths), f"nightly SpO2 trend was incorrectly split between consecutive days: {trend_paths}")
        hover_canvas(page, "o2rTrendSpo2", ("SpO₂",))
'''
new_trend_assert = '''        trend_segments = [x for x in trend_paths if x.get("moves") == 1]
        require(len(trend_segments) >= 2 and sum(x.get("lines", 0) for x in trend_segments) >= 3, f"nightly SpO2 trend did not split at the missing night: {trend_paths}")
        expected_trend_date = page.evaluate("""() => new Date(window.__smAcceptanceO2.trendRows[0].start_ts*1000).toLocaleDateString('hu-HU',{year:'numeric',month:'2-digit',day:'2-digit'})""")
        trend_axis_text = page.evaluate("() => window.__smAcceptanceO2.canvasText.filter(x=>x.id==='o2rTrendSpo2').map(x=>x.text)")
        require(expected_trend_date in trend_axis_text, f"O2 trend X-axis did not render dates: expected={expected_trend_date!r}, labels={trend_axis_text}")
        hover_canvas(page, "o2rTrendSpo2", ("SpO₂",))
'''
replace_once('scripts/v534_browser_acceptance.py', old_trend_assert, new_trend_assert)

# At the very end, race a status refresh with uninstall and prove polling cannot restart.
replace_once(
    'scripts/v534_browser_acceptance.py',
    "        page.set_viewport_size({\"width\": 844, \"height\": 390})\n        page.wait_for_timeout(120)\n        assert_no_horizontal_overflow(page, \"O2Ring settings iPhone landscape\")\n\n        browser.close()",
    "        page.set_viewport_size({\"width\": 844, \"height\": 390})\n        page.wait_for_timeout(120)\n        assert_no_horizontal_overflow(page, \"O2Ring settings iPhone landscape\")\n\n        progress(\"O2 status polling stays stopped after uninstall race\")\n        page.evaluate(\"\"\"async () => { const p=window.SleepMateO2Ring.refreshStatus(); window.SleepMateO2Ring.uninstall(); try{await p}catch{} }\"\"\")\n        status_calls_after_uninstall = page.evaluate(\"() => window.__smAcceptanceO2.statusCalls\")\n        page.wait_for_timeout(6500)\n        require(page.evaluate(\"() => window.__smAcceptanceO2.statusCalls\") == status_calls_after_uninstall, \"O2 status polling restarted after uninstall\")\n\n        browser.close()",
)

# Permanent source-level regression guards.
matrix = 'tests/test_v535_user_acceptance_matrix.py'
t = read(matrix)
addition = '''\n\ndef test_stability_status_timer_cannot_rearm_after_uninstall():\n    assert "async function refreshStatus(){if(!R.installed)return" in JS\n    assert "if(!R.installed)return;R.status=x" in JS\n    assert "finally{if(R.installed)" in JS\n    assert "clearO2Interactions();if(R.eventSource)" in JS\n\ndef test_stability_peer_mode_switch_reuses_loaded_daily_o2():\n    assert "ox?.classList.remove('hidden');loadDaily(false).then(drawDaily)" in JS\n    assert "peer-mode switching force-refetched daily O2 data" in BROWSER\n\ndef test_stability_trends_break_missing_nights_and_use_date_axis():\n    assert JS.count("gapSeconds:36*3600") >= 2\n    assert JS.count("xLabel:date") >= 2\n    assert "tooltipLabel:ts=>`${date(ts)} ${clock(ts)}`" in JS\n    assert "Dashboard O2 trend bridged a missing night" in BROWSER\n    assert "O2 trend X-axis did not render dates" in BROWSER\n'''
if 'test_stability_status_timer_cannot_rearm_after_uninstall' not in t:
    t += addition
write(matrix, t)

print('v5.3.5 O2 stability follow-up applied')
