from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS_PATH = ROOT / 'web' / 'o2ring.js'
BROWSER_PATH = ROOT / 'scripts' / 'v534_browser_acceptance.py'
MATRIX_PATH = ROOT / 'tests' / 'test_v535_user_acceptance_matrix.py'

def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{path}: expected one occurrence, found {count}: {old[:160]!r}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')

# Request 01: when matched O2Ring data disappears, restore native/core oximetry state
# before conditionally applying Ring medians. This prevents stale Ring values and
# preserves genuine CPAP/SA2 oximetry if that is available.
replace_once(
    JS_PATH,
    "function hydrateDailyO2Metrics(){const s=R.day?.summary;if(!R.day?.available||!s)return;const spo2=num(s.spo2_median),hr=num(s.heart_rate_median);if(id('spo2')&&spo2!=null){id('spo2').textContent=`${fmt(spo2,1)}%`;id('spo2').classList.remove('no-data')}if(id('hr')&&hr!=null){id('hr').textContent=`${fmt(hr,1)}`;id('hr').classList.remove('no-data')}}",
    "function hydrateDailyO2Metrics(){const s=R.day?.summary,restore=()=>{try{if(typeof applyOximetryVisibility==='function')applyOximetryVisibility(state.summary)}catch{}};restore();if(!R.day?.available||!s)return;const spo2=num(s.spo2_median),hr=num(s.heart_rate_median);if(id('spo2')&&spo2!=null){id('spo2').textContent=`${fmt(spo2,1)}%`;id('spo2').classList.remove('no-data')}if(id('hr')&&hr!=null){id('hr').textContent=`${fmt(hr,1)}`;id('hr').classList.remove('no-data')}}",
)

browser = BROWSER_PATH.read_text(encoding='utf-8')

# Request 05: provide a real core CPAP signal fixture so selecting the normal Flow
# mini-card exercises loadMainSignal -> /api/day/.../signal/flow -> drawHeroBase.
old = """          const daily = {\n            day:dailyDay, available:true, auto_match:true,\n            matches:[{cpap_start:now-3600,cpap_end:now-2940,overlap_seconds:660,cpap_coverage_percent:96}],\n            summary:summary(95.8,93,65.2,42,1.4,.7,96.4,64.0), samples:dailySamples\n          };\n          const batchOffsets=[0,1,2,4,5];\n"""
new = """          const daily = {\n            day:dailyDay, available:true, auto_match:true,\n            matches:[{cpap_start:now-3600,cpap_end:now-2940,overlap_seconds:660,cpap_coverage_percent:96}],\n            summary:summary(95.8,93,65.2,42,1.4,.7,96.4,64.0), samples:dailySamples\n          };\n          const flowSignal={\n            key:'flow',unit:'L/min',\n            series:[{\n              start:new Date(dailySamples[0].timestamp*1000).toISOString(),\n              points:dailySamples.map((r,i)=>[r.timestamp-dailySamples[0].timestamp,[0.3,-0.25,0.4,-0.15,0.2][i]])\n            }]\n          };\n          const batchOffsets=[0,1,2,4,5];\n"""
if browser.count(old) != 1:
    raise SystemExit('browser fixture: daily insertion anchor mismatch')
browser = browser.replace(old, new, 1)

old = """            liveRows,\n            bufferCalls:0,\n            dailyDay,daily,batchRows,dayCalls:0,statusCalls:0,invalidationHandlers:[],canvasText:[],pathRecords:[],rectRecords:[],\n"""
new = """            liveRows,\n            bufferCalls:0,\n            dailyDay,daily,flowSignal,batchRows,dayCalls:0,statusCalls:0,invalidationHandlers:[],canvasText:[],pathRecords:[],rectRecords:[],\n"""
if browser.count(old) != 1:
    raise SystemExit('browser fixture: state insertion anchor mismatch')
browser = browser.replace(old, new, 1)

old = """            if (url.pathname === `/api/day/${f.dailyDay}/stats`) {\n              return jsonResponse({apnea_duration:'0:00',rows:[{key:'pressure',title:'Nyomás',unit:'cmH2O',min:6,median:8,p95:10,p995:11,max:12}]});\n            }\n            if (url.pathname === '/api/o2ring/live-buffer') {\n"""
new = """            if (url.pathname === `/api/day/${f.dailyDay}/stats`) {\n              return jsonResponse({apnea_duration:'0:00',rows:[{key:'pressure',title:'Nyomás',unit:'cmH2O',min:6,median:8,p95:10,p995:11,max:12}]});\n            }\n            if (url.pathname === `/api/day/${f.dailyDay}/signal/flow`) return jsonResponse(f.flowSignal);\n            if (url.pathname === '/api/o2ring/live-buffer') {\n"""
if browser.count(old) != 1:
    raise SystemExit('browser fixture: flow route anchor mismatch')
browser = browser.replace(old, new, 1)

# Request 01 behavioral regression: remove matched Ring data without reloading core,
# ensure native/core cards are restored, then restore Ring data and medians.
old = """        require(\"96\" in page.locator(\"#spo2\").inner_text(), \"daily SpO2 card did not hydrate the matched O2 median\")\n        require(\"64\" in page.locator(\"#hr\").inner_text(), \"daily pulse card did not hydrate the matched O2 median\")\n        night_text = page.locator(\"#smNightO2Card\").inner_text()\n"""
new = """        require(\"96\" in page.locator(\"#spo2\").inner_text(), \"daily SpO2 card did not hydrate the matched O2 median\")\n        require(\"64\" in page.locator(\"#hr\").inner_text(), \"daily pulse card did not hydrate the matched O2 median\")\n        page.evaluate(\"\"\"async () => {\n          const f=window.__smAcceptanceO2;\n          f._matchedDaily=f.daily;\n          f.daily={day:f.dailyDay,available:false,auto_match:true,matches:[],summary:null,samples:[]};\n          await window.SleepMateO2Ring.refresh();\n        }\"\"\")\n        require(page.locator(\"#spo2\").inner_text().strip() == \"Nincs adat\", \"daily SpO2 card stayed stale after matched O2 data disappeared\")\n        require(page.locator(\"#hr\").inner_text().strip() == \"Nincs adat\", \"daily pulse card stayed stale after matched O2 data disappeared\")\n        page.evaluate(\"\"\"async () => {\n          const f=window.__smAcceptanceO2;\n          f.daily=f._matchedDaily;\n          await window.SleepMateO2Ring.refresh();\n        }\"\"\")\n        require(\"96\" in page.locator(\"#spo2\").inner_text(), \"daily SpO2 median did not return when matched O2 data returned\")\n        require(\"64\" in page.locator(\"#hr\").inner_text(), \"daily pulse median did not return when matched O2 data returned\")\n        night_text = page.locator(\"#smNightO2Card\").inner_text()\n"""
if browser.count(old) != 1:
    raise SystemExit('browser request-01 insertion anchor mismatch')
browser = browser.replace(old, new, 1)

# Mobile/PWA landscape acceptance for the Oximetry page itself.
old = """        require(abs(geometry[\"leftA\"] - geometry[\"leftB\"]) <= 1.5, f\"mobile O2 X origins differ: {geometry}\")\n        require(abs(geometry[\"widthA\"] - geometry[\"widthB\"]) <= 1.5, f\"mobile O2 plot widths differ: {geometry}\")\n\n        progress(\"iPhone portrait/landscape O2Ring settings through the mobile category selector\")\n        navigate(page, \"settings\")\n"""
new = """        require(abs(geometry[\"leftA\"] - geometry[\"leftB\"]) <= 1.5, f\"mobile O2 X origins differ: {geometry}\")\n        require(abs(geometry[\"widthA\"] - geometry[\"widthB\"]) <= 1.5, f\"mobile O2 plot widths differ: {geometry}\")\n\n        progress(\"iPhone landscape Oximetria geometry\")\n        page.set_viewport_size({\"width\": 844, \"height\": 390})\n        page.wait_for_timeout(180)\n        assert_no_horizontal_overflow(page, \"Oximetria iPhone landscape\")\n        landscape_geometry = page.evaluate(\n            \"\"\"() => {\n                const a=document.getElementById('o2rLiveSpo2Chart')?.getBoundingClientRect();\n                const b=document.getElementById('o2rLiveHrChart')?.getBoundingClientRect();\n                return a&&b?{leftA:a.left,leftB:b.left,widthA:a.width,widthB:b.width}:null;\n            }\"\"\"\n        )\n        require(landscape_geometry is not None, \"landscape live O2 canvases missing\")\n        require(abs(landscape_geometry[\"leftA\"] - landscape_geometry[\"leftB\"]) <= 1.5, f\"landscape O2 X origins differ: {landscape_geometry}\")\n        require(abs(landscape_geometry[\"widthA\"] - landscape_geometry[\"widthB\"]) <= 1.5, f\"landscape O2 plot widths differ: {landscape_geometry}\")\n\n        progress(\"iPhone portrait/landscape O2Ring settings through the mobile category selector\")\n        page.set_viewport_size({\"width\": 390, \"height\": 844})\n        navigate(page, \"settings\")\n"""
if browser.count(old) != 1:
    raise SystemExit('browser landscape insertion anchor mismatch')
browser = browser.replace(old, new, 1)
BROWSER_PATH.write_text(browser, encoding='utf-8')

matrix = MATRIX_PATH.read_text(encoding='utf-8').rstrip()
addition = '''


def test_request_01_restores_core_oximetry_when_ring_match_disappears():
    assert "applyOximetryVisibility(state.summary)" in JS
    assert "daily SpO2 card stayed stale after matched O2 data disappeared" in BROWSER
    assert "daily pulse card stayed stale after matched O2 data disappeared" in BROWSER
    assert "daily SpO2 median did not return when matched O2 data returned" in BROWSER


def test_request_05_edge_fixture_loads_real_core_flow_signal_path():
    assert "flowSignal" in BROWSER
    assert "/signal/flow" in BROWSER
    assert "state.selectedSignal==='flow' && state.mainSignal?.series?.length" in BROWSER


def test_mobile_oximetry_landscape_is_behaviorally_covered():
    assert "iPhone landscape Oximetria geometry" in BROWSER
    assert "Oximetria iPhone landscape" in BROWSER
    assert "landscape O2 X origins differ" in BROWSER
    assert "landscape O2 plot widths differ" in BROWSER
'''
for name in (
    'test_request_01_restores_core_oximetry_when_ring_match_disappears',
    'test_request_05_edge_fixture_loads_real_core_flow_signal_path',
    'test_mobile_oximetry_landscape_is_behaviorally_covered',
):
    if name in matrix:
        raise SystemExit(f'{name} already exists')
MATRIX_PATH.write_text(matrix + addition, encoding='utf-8')
