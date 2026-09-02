from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"missing source marker for {label}")
    return text.replace(old, new, 1)


def sub_once(text: str, pattern: str, repl: str, label: str) -> str:
    out, n = re.subn(pattern, repl, text, count=1, flags=re.S)
    if n != 1:
        raise RuntimeError(f"expected exactly one regex replacement for {label}, got {n}")
    return out


# ---------------------------------------------------------------------------
# Authoritative O2 runtime: route ownership, lifecycle, touch zoom/pan,
# synchronized trend/dashboard interaction, and per-signal overlay persistence.
# ---------------------------------------------------------------------------
path = "web/o2ring.js"
js = read(path)
js = replace_once(
    js,
    "statusTimer:null};",
    "statusTimer:null,trendZoom:null,trendRows:[],dashboardTrendZoom:null,dashboardTrendRows:[],liveResumePromise:null};",
    "O2 runtime state extensions",
)

js = sub_once(
    js,
    r"function bindChart\(c,\{setRange,resetRange,redraw,syncGroup\}\)\{.*?\}\nfunction coreView",
    r'''function clampChartRange(rows,a,b,minSpan=4){const f=bounds(rows);if(!f)return null;if(a>b)[a,b]=[b,a];const total=Math.max(.001,f[1]-f[0]),span=Math.min(total,Math.max(minSpan,b-a));let x=a,y=a+span;if(x<f[0]){x=f[0];y=x+span}if(y>f[1]){y=f[1];x=y-span}return[x,y]}
function clearO2Interactions(){for(const c of qa('canvas')){const ctl=R.chartControllers.get(c);if(!ctl)continue;for(const pid of ctl.pointers?.keys?.()||[]){try{c.releasePointerCapture(pid)}catch{}}ctl.pointers?.clear?.();ctl.drag=null;ctl.pinch=null;ctl.pendingRange=null;if(ctl.raf){cancelAnimationFrame(ctl.raf);ctl.raf=0}hideTooltip(c)}R.hover={}}
function bindChart(c,{setRange,resetRange,redraw,syncGroup}){if(!c)return;const existing=R.chartControllers.get(c);if(existing){existing.setRange=setRange;existing.resetRange=resetRange;existing.redraw=redraw;existing.syncGroup=syncGroup;return}const ctl={setRange,resetRange,redraw,syncGroup,drag:null,pinch:null,pointers:new Map(),pendingRange:null,raf:0};R.chartControllers.set(c,ctl);c.style.touchAction='pan-y';c.style.cursor='crosshair';const meta=()=>c._smO2Meta;const timeAtX=x=>{const m=meta(),r=c.getBoundingClientRect();if(!m)return null;const px=Math.max(m.p.l,Math.min(r.width-m.p.r,x-r.left));return m.a+(px-m.p.l)/Math.max(1,m.iw)*(m.b-m.a)};const scheduleRange=range=>{if(!range)return;ctl.pendingRange=range;if(ctl.raf)return;ctl.raf=requestAnimationFrame(()=>{ctl.raf=0;const next=ctl.pendingRange;ctl.pendingRange=null;if(next){ctl.setRange?.(next);ctl.redraw?.()}})};const showPoint=e=>{const t=timeAtX(e.clientX);if(t!=null)setHover(ctl.syncGroup,t);const m=meta(),row=m&&t!=null?nearest(m.rows,t):null;if(m&&row){const parts=[`<b>${clock(row.timestamp)}</b>`];for(const s of m.series){const v=num(row[s.key]);if(v!=null)parts.push(`<span style="--dot:${s.color}"><i></i>${esc(s.label||s.key)}: <b>${fmt(v,s.digits??0)}${s.unit||''}</b></span>`)}tooltip(c,parts.join(''),e.clientX-c.getBoundingClientRect().left,e.clientY-c.getBoundingClientRect().top)}return t};const startPinch=()=>{if(ctl.pointers.size<2)return;const pts=[...ctl.pointers.values()].slice(0,2),m=meta();if(!m)return;const dist=Math.hypot(pts[1].x-pts[0].x,pts[1].y-pts[0].y)||1,centerX=(pts[0].x+pts[1].x)/2,center=timeAtX(centerX);ctl.pinch={dist,range:[m.a,m.b],center,ratio:(center-m.a)/Math.max(.001,m.b-m.a)};ctl.drag=null};c.addEventListener('pointerdown',e=>{if(e.button!=null&&e.button!==0)return;const t=showPoint(e);if(t==null)return;try{c.setPointerCapture(e.pointerId)}catch{}if(e.pointerType==='touch'){ctl.pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});if(ctl.pointers.size>=2){startPinch();if(e.cancelable)e.preventDefault();return}}const m=meta();ctl.drag={id:e.pointerId,start:t,end:t,startX:e.clientX,startY:e.clientY,lastX:e.clientX,lastY:e.clientY,mode:e.pointerType==='touch'||e.shiftKey?'pan':'zoom',range:m?[m.a,m.b]:null}});c.addEventListener('pointermove',e=>{const t=showPoint(e);if(e.pointerType==='touch'&&ctl.pointers.has(e.pointerId))ctl.pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});if(ctl.pinch&&ctl.pointers.size>=2){const pts=[...ctl.pointers.values()].slice(0,2),dist=Math.hypot(pts[1].x-pts[0].x,pts[1].y-pts[0].y)||1,base=ctl.pinch.range,span=(base[1]-base[0])*(ctl.pinch.dist/dist),a=ctl.pinch.center-span*ctl.pinch.ratio,b=a+span,m=meta();scheduleRange(clampChartRange(m?.rows||[],a,b));if(e.cancelable)e.preventDefault();return}const d=ctl.drag;if(!d||d.id!==e.pointerId)return;d.end=t??d.end;const dx=e.clientX-d.startX,dy=e.clientY-d.startY;if(d.mode==='pan'&&d.range&&Math.abs(dx)>4&&Math.abs(dx)>Math.abs(dy)*.85){const m=meta(),delta=-dx/Math.max(1,m?.iw||1)*(d.range[1]-d.range[0]);scheduleRange(clampChartRange(m?.rows||[],d.range[0]+delta,d.range[1]+delta));if(e.pointerType==='touch'&&e.cancelable)e.preventDefault()}d.lastX=e.clientX;d.lastY=e.clientY});const end=e=>{if(e.pointerType==='touch')ctl.pointers.delete(e.pointerId);if(ctl.pointers.size<2)ctl.pinch=null;const d=ctl.drag;if(d&&d.id===e.pointerId){ctl.drag=null;if(d.mode==='zoom'){const dx=Math.abs(e.clientX-d.startX),dy=Math.abs(e.clientY-d.startY),a=Math.min(d.start,d.end),b=Math.max(d.start,d.end),m=meta();if(dx>18&&dx>dy*1.15&&b-a>4)scheduleRange(clampChartRange(m?.rows||[],a,b))}}try{c.releasePointerCapture(e.pointerId)}catch{}};c.addEventListener('pointerup',end);c.addEventListener('pointercancel',e=>{ctl.pointers.delete(e.pointerId);ctl.drag=null;ctl.pinch=null;try{c.releasePointerCapture(e.pointerId)}catch{}});c.addEventListener('pointerleave',e=>{if(e.pointerType!=='touch'&&!ctl.drag&&!ctl.pinch){delete R.hover[ctl.syncGroup];hideTooltip(c);requestAnimationFrame(()=>redrawGroup(ctl.syncGroup))}});c.addEventListener('dblclick',()=>{ctl.resetRange?.();ctl.redraw?.()});c.addEventListener('wheel',e=>{if(!e.ctrlKey&&!e.shiftKey)return;const m=meta();if(!m)return;e.preventDefault();const center=timeAtX(e.clientX)??(m.a+m.b)/2,span=(m.b-m.a)*(e.deltaY>0?1.22:.82),ratio=(center-m.a)/Math.max(.001,m.b-m.a),a=center-span*ratio,b=a+span;scheduleRange(clampChartRange(m.rows,a,b))},{passive:false})}
function coreView''',
    "shared O2 chart lifecycle",
)

js = sub_once(
    js,
    r"function installNav\(\)\{.*?\}\nfunction installPage",
    """function installNav(){let b=q('#sidebar [data-page=\"oximetry\"]');if(!b){b=document.createElement('button');b.type='button';b.className='nav-item';b.dataset.page='oximetry';b.innerHTML=`${icon()}<span>Oximetria</span>`;const reports=q('#sidebar [data-page=\"reports\"]');reports?.parentNode?.insertBefore(b,reports)}b.dataset.o2ringFeature='1';const label=b.querySelector('span');if(label)label.textContent='Oximetria'}\nfunction installPage""",
    "single sidebar Oximetria owner",
)

js = replace_once(
    js,
    "function openOximetry(tab='live'){if(!R.installed)return;history.pushState({sleepmate:true,o2:true},'', '#oximetry');showOximetry(tab)}",
    "function openOximetry(tab='live'){if(!R.installed)return;if(location.hash!=='#oximetry')history.pushState({sleepmate:true,o2:true},'', '#oximetry');showOximetry(tab)}",
    "non-duplicating Oximetria route",
)
js = replace_once(
    js,
    "function selectO2Tab(name){R.pageTab=name;",
    "function selectO2Tab(name){if(R.pageTab!==name)clearO2Interactions();R.pageTab=name;",
    "O2 tab interaction cleanup",
)
js = replace_once(
    js,
    "async function resumeLive(){if(!o2PageVisible())return;await refillLive();openLiveStream()}",
    "async function resumeLive(){if(!o2PageVisible())return;if(R.liveResumePromise)return R.liveResumePromise;R.liveResumePromise=(async()=>{await refillLive();if(o2PageVisible())openLiveStream()})().finally(()=>{R.liveResumePromise=null});return R.liveResumePromise}",
    "single live resume batch",
)
js = replace_once(
    js,
    "function switchMode(mode){rememberMode();R.mode=mode;clearCoreInteractions();",
    "function switchMode(mode){rememberMode();R.mode=mode;clearCoreInteractions();clearO2Interactions();",
    "view switch lifecycle cleanup",
)
js = replace_once(
    js,
    "s.onchange=e=>saveOverlay(key,e.target.value);",
    "s.onchange=e=>saveOverlay(e.currentTarget.dataset.signal||key,e.currentTarget.value);",
    "per-signal overlay persistence",
)

js = sub_once(
    js,
    r"async function loadTrends\(limit=30\)\{.*?\}\nfunction ensureReportColumns",
    r'''function drawTrendCharts(){const t=R.trendRows||[],range=R.trendZoom||bounds(t),set=v=>R.trendZoom=v,reset=()=>R.trendZoom=null,redraw=drawTrendCharts,defs=[['o2rTrendSpo2',[{key:'spo2_avg',label:'Átlag SpO₂',unit:'%',color:COLORS.spo2,fixed:[70,100]},{key:'spo2_min',label:'Minimum SpO₂',unit:'%',color:COLORS.blue,fixed:[70,100]}]],['o2rTrendHr',[{key:'hr',label:'Pulzus',unit:' bpm',color:COLORS.hr}]],['o2rTrendT90',[{key:'t90',label:'T90',unit:' p',color:COLORS.teal}]],['o2rTrendOdi',[{key:'odi3',label:'ODI3',color:COLORS.spo2},{key:'odi4',label:'ODI4',color:COLORS.rose}]]];for(const[cid,ss]of defs){const c=id(cid);chartDraw(c,t,{range,series:ss,syncGroup:'trends',rightAxis:false,redraw});bindChart(c,{setRange:set,resetRange:reset,redraw,syncGroup:'trends'})}}
async function loadTrends(limit=30){if(Number(limit)!==Number(R.trendLimit))R.trendZoom=null;R.trendLimit=limit;try{const x=await api(`/api/o2ring/trends?limit=${limit}`),rows=x.rows||[],t=rows.map(r=>({timestamp:num(r.start_ts),spo2_avg:num(r.summary?.spo2_average),spo2_min:num(r.summary?.spo2_minimum),hr:num(r.summary?.heart_rate_average),t90:num(r.summary?.t90_seconds)/60,odi3:num(r.summary?.odi3),odi4:num(r.summary?.odi4)})).filter(r=>r.timestamp),av=k=>{const v=t.map(r=>num(r[k])).filter(x=>x!=null);return v.length?v.reduce((a,b)=>a+b,0)/v.length:null};R.trendRows=t;id('o2rTrendAvg').textContent=av('spo2_avg')==null?'—':`${fmt(av('spo2_avg'),1)}%`;const mins=t.map(r=>r.spo2_min).filter(x=>x!=null);id('o2rTrendMin').textContent=mins.length?`${Math.min(...mins)}%`:'—';id('o2rTrendHrAvg').textContent=av('hr')==null?'—':`${fmt(av('hr'),1)} bpm`;id('o2rTrendT90Avg').textContent=av('t90')==null?'—':`${fmt(av('t90'),0)} p`;id('o2rTrendEmpty').classList.toggle('hidden',t.length>=2);drawTrendCharts()}catch{R.trendRows=[];drawTrendCharts()}}
function ensureReportColumns''',
    "interactive synchronized trend charts",
)

js = sub_once(
    js,
    r"async function refreshDashboardO2\(force=false\)\{.*?\}\nasync function loadRecordings",
    r'''function drawDashboardO2Mini(){const rows=R.dashboardTrendRows||[],range=R.dashboardTrendZoom||bounds(rows),set=v=>R.dashboardTrendZoom=v,reset=()=>R.dashboardTrendZoom=null,redraw=drawDashboardO2Mini,defs=[['smDashO2Trend',[{key:'spo2',label:'SpO₂',unit:'%',color:COLORS.spo2,fixed:[75,100]}]],['smDashHrTrend',[{key:'heart_rate',label:'Pulzus',unit:' bpm',color:COLORS.hr}]]];for(const[cid,ss]of defs){const c=id(cid);chartDraw(c,rows,{range,series:ss,syncGroup:'dash-o2',rightAxis:false,redraw});bindChart(c,{setRange:set,resetRange:reset,redraw,syncGroup:'dash-o2'})}}
async function refreshDashboardO2(force=false){let rows=[];try{rows=state.dashboardOverview?.rows||[]}catch{}if(!rows.length)return;const data=await getBatch(rows.map(r=>r.day),force),avail=data.filter(x=>x.available&&x.summary),agg=q('#dashboardOverviewView .aggregate-cards');if(!agg)return;let sec=id('smDashboardO2V534');if(!sec){sec=document.createElement('section');sec.id='smDashboardO2V534';sec.className='panel sm-dashboard-o2-v534';sec.dataset.o2ringFeature='1';sec.innerHTML='<div class="panel-head"><div><h3>Oximetriai összegzés</h3><span>CPAP-idővel átfedő O2Ring-adatok.</span></div><button id="smDashO2Open">Oximetria →</button></div><div class="sm-dashboard-o2-cards"><div><span>Átlag SpO₂</span><b id="smDashO2Avg">—</b></div><div><span>Minimum SpO₂</span><b id="smDashO2Min">—</b></div><div><span>Átlag pulzus</span><b id="smDashHrAvg">—</b></div><div><span>Átlag T90</span><b id="smDashT90">—</b></div></div><div class="sm-dashboard-o2-mini"><article><header>SpO₂ trend</header><div class="sm-o2-chart-wrap"><canvas id="smDashO2Trend"></canvas></div></article><article><header>Pulzus trend</header><div class="sm-o2-chart-wrap"><canvas id="smDashHrTrend"></canvas></div></article></div><div id="smDashO2Empty" class="o2r-empty hidden">Ebben az időszakban még nincs illesztett O2Ring adat.</div>';agg.insertAdjacentElement('afterend',sec);id('smDashO2Open').onclick=()=>openOximetry('recordings')}const av=key=>{const v=avail.map(x=>num(x.summary?.[key])).filter(x=>x!=null);return v.length?v.reduce((a,b)=>a+b,0)/v.length:null},mins=avail.map(x=>num(x.summary?.spo2_minimum)).filter(x=>x!=null);id('smDashO2Avg').textContent=av('spo2_average')==null?'—':`${fmt(av('spo2_average'),1)}%`;id('smDashO2Min').textContent=mins.length?`${Math.min(...mins)}%`:'—';id('smDashHrAvg').textContent=av('heart_rate_average')==null?'—':`${fmt(av('heart_rate_average'),1)} bpm`;id('smDashT90').textContent=av('t90_seconds')==null?'—':dur(av('t90_seconds'));id('smDashO2Empty').classList.toggle('hidden',avail.length>0);R.dashboardTrendRows=avail.map((x,i)=>({timestamp:num(x.matches?.[0]?.cpap_start)||Date.now()/1000+i*86400,spo2:num(x.summary?.spo2_average),heart_rate:num(x.summary?.heart_rate_average)}));if(force)R.dashboardTrendZoom=null;drawDashboardO2Mini()}
async function loadRecordings''',
    "interactive Dashboard O2 trends",
)

js = replace_once(
    js,
    "function overrideBars(){try{",
    "function overrideBars(){try{try{Object.assign(TREND_EVENT_COLORS,EVENT_COLORS)}catch{}if(typeof syncTrendHover==='function'&&!syncTrendHover.__sm534){const origHover=syncTrendHover;syncTrendHover=function(...a){const r=origHover(...a),source=a[1],tip=id('trendTooltip');if(source?._trendMeta?.kind==='usage'){const dot=tip?.querySelector('span i');if(dot)dot.style.background=COLORS.teal}return r};syncTrendHover.__sm534=true}",
    "centralized Dashboard trend tooltip palette",
)

js = replace_once(
    js,
    "document.addEventListener('click',e=>{const live=e.target?.closest?.('[data-sm-nav-id=\"oximetry_live\"]');if(live){e.preventDefault();e.stopImmediatePropagation();openOximetry('live')}},true);",
    "document.addEventListener('click',e=>{const live=e.target?.closest?.('[data-sm-nav-id=\"oximetry_live\"]');if(live){e.preventDefault();e.stopImmediatePropagation();openOximetry('live');return}const nav=e.target?.closest?.('#sidebar [data-page=\"oximetry\"]');if(nav){e.preventDefault();e.stopImmediatePropagation();openOximetry(R.pageTab||'live')}},true);",
    "capture-owned Oximetria navigation",
)
write(path, js)


# ---------------------------------------------------------------------------
# PWA settings: create one source-level PWA category instead of creating a
# second category and cleaning it up later.
# ---------------------------------------------------------------------------
path = "web/sleepmate-v530.js"
pwa = read(path)
pwa = pwa.replace("const VERSION='5.3.0';", "const VERSION='5.3.4';", 1)
pwa = sub_once(
    pwa,
    r"  function installPwaSettingsTab\(\)\{.*?\n  \}\n  function renderPwaEditor",
    r'''  function installPwaSettingsTab(){
    const tabs=document.querySelector('.settings-inner-tabs'),sel=document.getElementById('settingsCategorySelect'),main=document.querySelector('#page-settings main, #page-settings');if(!tabs||!main)return;
    const push=tabs.querySelector('[data-settings-tab="push"]'),legacy=tabs.querySelector('[data-settings-tab="pwa"]');if(push){push.textContent='PWA';push.onclick=()=>activateSettingsTab('push')}legacy?.remove();
    if(sel){const pushOpt=[...sel.options].find(o=>o.value==='push');if(pushOpt)pushOpt.textContent='PWA';[...sel.options].filter(o=>o.value==='pwa').forEach(o=>o.remove())}
    const pushPanel=document.querySelector('[data-settings-panel="push"]');if(!pushPanel)return;
    let panel=document.getElementById('smPwaSettingsPanel');if(!panel){panel=document.createElement('section');panel.id='smPwaSettingsPanel';panel.className='panel sm-pwa-settings';panel.innerHTML=`<div class="panel-head"><div><h3>PWA alsó navigáció</h3><span>Válassz 1–6 elemet. Nincs fenntartott üres hely: a kiválasztott elemek automatikusan kitöltik a teljes alsó sávot.</span></div><span class="security-pill">max. 6</span></div><div id="smPwaNavEditor" class="sm-pwa-nav-editor"></div><div class="sm-pwa-preview-wrap"><span>Telefonos előnézet</span><div id="smPwaNavPreview" class="sm-pwa-nav-preview"></div></div><p id="smPwaNavMsg" class="muted"></p>`}panel.classList.remove('settings-tab-panel');panel.removeAttribute('data-settings-panel');if(panel.parentNode!==pushPanel)pushPanel.prepend(panel);renderPwaEditor();
  }
  function renderPwaEditor''',
    "source-level merged PWA settings",
)
write(path, pwa)


# ---------------------------------------------------------------------------
# First-run settings card: one canonical System-panel instance and no polling.
# ---------------------------------------------------------------------------
path = "web/first-run.js"
first = read(path)
first = sub_once(
    first,
    r"  function injectReopen\(\)\{.*?\n  \}\n\n  window\.openSleepMateFirstRun",
    r'''  function injectReopen(){
    const page=$('#page-settings'),system=$('[data-settings-panel="system"]');if(!page||!system)return false;const all=$$('.fr-settings-reopen').filter(x=>x.textContent.includes('Első beállítás varázsló'));let box=$('#frSettingsReopen')||all[0];for(const x of all)if(x!==box)x.remove();if(!box){box=document.createElement('section');box.className='fr-settings-reopen';box.innerHTML='<b>Első beállítás varázsló</b><p>Újra végigvezet az adatforrás, SleepSync, távoli elérés, backup és AI alapbeállításain.</p><button type="button" class="fr-btn">Varázsló megnyitása</button>'}box.id='frSettingsReopen';box.querySelector('button').onclick=()=>open(true);if(box.parentNode!==system)system.appendChild(box);return true
  }

  window.openSleepMateFirstRun''',
    "single setup wizard settings card",
)
first = replace_once(
    first,
    "window.addEventListener('load',()=>{setTimeout(()=>open(false),650);let tries=0;const timer=setInterval(()=>{tries++;if(injectReopen()||tries>30)clearInterval(timer)},500)},{once:true});",
    "window.addEventListener('load',()=>{setTimeout(()=>open(false),650);if(injectReopen())return;const page=$('#page-settings');if(!page)return;const observer=new MutationObserver(()=>{if(injectReopen())observer.disconnect()});observer.observe(page,{childList:true,subtree:true});setTimeout(()=>{observer.disconnect();injectReopen()},8000)},{once:true});",
    "observer-based setup wizard mount",
)
write(path, first)


# ---------------------------------------------------------------------------
# Migrate obsolete 5.3.2/5.3.3 release-contract tests to the active 5.3.4
# semantics. Historical source files remain, but must not be required active.
# ---------------------------------------------------------------------------
path = "tests/test_mobile_ai_push_v417.py"
t = read(path)
t = sub_once(
    t,
    r"def test_mobile5_cache_bust\(\):.*\Z",
    '''def test_mobile5_cache_bust():\n    assert 'sleepmate-shell-v5.2.14-ss131' in SW\n    assert "const UI_VERSION='5.3.4'" in SW\n    assert 'sleepmate-shell-v5.3.4-refactor' in SW\n    assert 'sleepmate-api-v5.3.4-refactor' in SW\n    assert '/style.css?v=5.3.4' in SW\n    assert '/app.js?v=5.3.4' in SW\n    assert '/style.css?v=5.0.0' in HTML\n    assert '/app.js?v=5.0.0' in HTML\n    assert 'UI_VERSION = "5.3.4"' in RECOVERY\n    assert "text.replace('/style.css?v=5.0.0', f'/style.css?v={UI_VERSION}')" in RECOVERY\n    assert "text.replace('/app.js?v=5.0.0', f'/app.js?v={UI_VERSION}')" in RECOVERY\n    assert 'X-SleepMate-UI-Version' in RECOVERY\n''',
    "mobile cache contract",
)
write(path, t)

path = "tests/test_o2ring_combined_ui.py"
t = read(path)
t = sub_once(
    t,
    r"def test_combined_timeline_is_owned_by_v532_dynamic_shell_only\(\):.*?\n\ndef test_combined_timeline_is_inert_without_dynamic_o2_daily_panel",
    '''def test_combined_timeline_is_owned_by_v534_authoritative_runtime():\n    shell = (ROOT / "cpap" / "v530_features.py").read_text(encoding="utf-8")\n    runtime = (ROOT / "web" / "o2ring.js").read_text(encoding="utf-8")\n    assert 'UI_VERSION = "5.3.4"' in shell\n    assert "o2ring-v532.js" not in shell\n    assert "frontend-v533.js" not in shell\n    for marker in ("smO2FocusDual", "smStackO2Dual", "o2rLiveDual", "daily-o2"):\n        assert marker in runtime\n\n\ndef test_combined_timeline_is_inert_without_dynamic_o2_daily_panel''',
    "combined timeline active owner",
)
write(path, t)

path = "tests/test_o2ring_polish_v530.py"
write(path, '''from pathlib import Path\n\nfrom cpap.o2ring_v532 import _normalize_days\nfrom cpap.ui_preferences_v530 import PWA_NAV_ALLOWED\n\nROOT = Path(__file__).resolve().parents[1]\n\ndef text(name: str) -> str:\n    return (ROOT / "web" / name).read_text(encoding="utf-8")\n\ndef test_v534_runtime_is_the_only_active_post_release_o2_owner():\n    feature=(ROOT/"cpap"/"v530_features.py").read_text(encoding="utf-8")\n    assert 'UI_VERSION = "5.3.4"' in feature\n    assert "o2ring-v532.js" not in feature and "frontend-v533.js" not in feature\n    assert "install_o2ring_runtime_v534" in feature\n\ndef test_v534_runtime_contains_requested_dashboard_and_oximetry_contracts():\n    js=text("o2ring.js")\n    for marker in ("SpO₂ + pulzus – élő","smO2FocusSpo2","smO2FocusHr","smO2FocusDual","smStackO2Spo2","smStackO2Hr","smStackO2Dual","switchMode","sm-o2-overlay-select","Oximetriai összegzés","smNightO2Card","SpO₂ átlag","smO2QuickConnect","o2rTrendSpo2"):\n        assert marker in js\n    assert "setInterval(" not in js\n\ndef test_connect_buttons_hide_when_ring_is_connected():\n    js=text("o2ring.js")\n    assert "o2rConnectNow" in js and "smO2QuickConnect" in js\n    assert "classList.toggle('hidden',!!l.connected)" in js\n\ndef test_dashboard_and_reports_use_batch_overlap_endpoint():\n    js=text("o2ring.js");backend=(ROOT/"cpap"/"o2ring_v532.py").read_text(encoding="utf-8")\n    assert "/api/o2ring/day-batch?days=" in js\n    assert 'parsed.path == "/api/o2ring/day-batch"' in backend\n    assert "service.daily(day, max_points=1)" in backend\n\ndef test_o2ring_settings_and_pwa_contracts():\n    js=text("frontend-v534.js");css=text("o2ring-v534.css")\n    assert "tab.textContent='O2Ring'" in js\n    assert "sm-o2-settings-panel" in css\n    assert "saveQueued" in js and "saveBusy" in js\n    assert "oximetry_live" in PWA_NAV_ALLOWED\n    assert "Élő O₂ monitor" in js\n\ndef test_aurora_bar_palette_is_crisp_and_consistent():\n    js=text("o2ring.js");css=text("o2ring-v534.css")\n    for color in ("#55d8ff","#a98bff","#48dfb9","#ef86c8"): assert color in js\n    assert "#trendUsage,#trendEvents{filter:none!important}" in css\n    assert "Object.assign(TREND_EVENT_COLORS,EVENT_COLORS)" in js\n\ndef test_batch_day_normalization_is_bounded_and_deduplicated():\n    values=["2026-09-01","20260901","bad","20260902"]\n    assert _normalize_days(",".join(values))==["20260901","20260902"]\n    many=",".join(f"2026{m:02d}{d:02d}" for m in range(1,13) for d in range(1,29))\n    assert len(_normalize_days(many))==120\n''')

path = "tests/test_o2ring_v532_release_contract.py"
write(path, '''from pathlib import Path\nfrom cpap.version import API_VERSION, APP_VERSION, BUILD_CHANNEL\nROOT=Path(__file__).resolve().parents[1]\ndef read(path:str)->str:return (ROOT/path).read_text(encoding="utf-8")\ndef test_current_release_identity_supersedes_historical_v532_contract():\n    assert APP_VERSION=="5.3.4" and API_VERSION==19 and BUILD_CHANNEL=="stable"\n    assert read("RELEASE_NOTES_5_3_4.md").startswith("# SleepMate 5.3.4\\n")\ndef test_current_packaged_pwa_keeps_authoritative_o2_assets_network_first():\n    for path in ("web/service-worker.js","web/service-worker-v508-base.js"):\n        sw=read(path)\n        for asset in ("/sleepmate-aurora.css","/sleepmate-v530.css","/sleepmate-v530.js","/o2ring.css","/o2ring.js","/o2ring-report-ui.js","/o2ring-v534.css","/frontend-v534.js"):\n            assert asset in sw\n        assert "/o2ring-v532.js" not in sw and "/frontend-v533.js" not in sw\ndef test_current_shell_activates_only_v534_post_release_owner():\n    shell=read("cpap/v530_features.py")\n    assert "install_o2ring_runtime_v534" in shell\n    assert "o2ring-v534.css" in shell and "frontend-v534.js" in shell\n    assert "o2ring-v532.js" not in shell and "frontend-v533.js" not in shell\ndef test_current_user_requested_surfaces_are_present():\n    runtime=read("web/o2ring.js")\n    for marker in ("switchMode","smO2FocusDual","smStackO2Dual","sm-o2-overlay-select","smNightO2Card","smDashboardO2V534","o2rTrendSpo2","smO2QuickBar","SpO₂ + pulzus – élő"):\n        assert marker in runtime\ndef test_reports_keep_batched_cpap_overlap_data():\n    runtime=read("web/o2ring.js");backend=read("cpap/o2ring_v532.py")\n    assert "/api/o2ring/day-batch?days=" in runtime\n    assert 'parsed.path == "/api/o2ring/day-batch"' in backend\n''')

path = "tests/test_pwa_sleep_shell_v526.py"
t = read(path)
t = sub_once(t, r"O2_CODE_ASSETS = \(.*?\)\n", '''O2_CODE_ASSETS = (\n    "/sleepmate-aurora.css",\n    "/sleepmate-v530.css",\n    "/sleepmate-v530.js",\n    "/o2ring.css",\n    "/o2ring.js",\n    "/o2ring-report-ui.js",\n    "/o2ring-v534.css",\n    "/frontend-v534.js",\n)\n''', "current O2 PWA assets")
t = t.replace("rotated to the v5.3.3 recovery generation.", "rotated to the v5.3.4 refactor generation.")
t = t.replace('"sleepmate-shell-v5.3.3-recovery"', '"sleepmate-shell-v5.3.4-refactor"')
t = t.replace('"sleepmate-api-v5.3.3-recovery"', '"sleepmate-api-v5.3.4-refactor"')
t = t.replace('"sleepmate-shell-v5.3.3"', '"sleepmate-shell-v5.3.4"')
t = t.replace('"sleepmate-api-v5.3.3"', '"sleepmate-api-v5.3.4"')
write(path, t)

# Strengthen the active acceptance-contract suite with the newly fixed root causes.
path = "tests/test_o2ring_v534_release_contract.py"
t = read(path)
extra = r'''

def test_v534_sidebar_route_is_capture_owned_and_history_is_not_duplicated():
    js=read("web/o2ring.js")
    assert "#sidebar [data-page=\"oximetry\"]" in js
    assert "stopImmediatePropagation();openOximetry(R.pageTab||'live')" in js
    assert "if(location.hash!=='#oximetry')history.pushState" in js


def test_v534_overlay_focus_selector_persists_the_current_signal_not_flow_only():
    js=read("web/o2ring.js")
    assert "e.currentTarget.dataset.signal||key" in js
    assert "sm-o2-overlay:${key}" in js


def test_v534_all_o2_charts_have_touch_pinch_pan_and_synchronized_trend_zoom():
    js=read("web/o2ring.js")
    for marker in ("function clampChartRange", "ctl.pinch", "ctl.pointers", "mode:e.pointerType==='touch'||e.shiftKey?'pan':'zoom'", "R.trendZoom", "syncGroup:'trends'", "R.dashboardTrendZoom", "syncGroup:'dash-o2'"):
        assert marker in js


def test_v534_source_settings_are_single_pwa_category_and_single_setup_wizard_card():
    pwa=read("web/sleepmate-v530.js")
    first=read("web/first-run.js")
    assert "push.textContent='PWA'" in pwa
    assert "legacy?.remove()" in pwa
    assert "panel.removeAttribute('data-settings-panel')" in pwa
    assert "dataset.settingsTab='pwa'" not in pwa
    assert "system.appendChild(box)" in first
    assert "for(const x of all)if(x!==box)x.remove()" in first
    assert "setInterval(()=>{tries++" not in first
'''
if "test_v534_sidebar_route_is_capture_owned" not in t:
    t += extra
write(path, t)

print("v5.3.4 acceptance refactor source migration applied")
