from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path): return (ROOT/path).read_text(encoding='utf-8')
def write(path,text): (ROOT/path).write_text(text,encoding='utf-8')
def replace_once(path,old,new):
    text=read(path); n=text.count(old)
    if n!=1: raise SystemExit(f'{path}: expected 1 occurrence, got {n}: {old[:120]!r}')
    write(path,text.replace(old,new,1))
def replace_between(path,start,end,new):
    text=read(path); i=text.find(start); j=text.find(end,i+len(start)) if i>=0 else -1
    if i<0 or j<0: raise SystemExit(f'{path}: markers missing: {start} / {end}')
    write(path,text[:i]+new.rstrip()+'\n'+text[j:])

# 3 + 5 + 9: normal line weight, visible drag selection, single-point trend visibility.
replace_once(
    'web/o2ring.js',
    "function drawLine(ctx,segments,mapX,mapY,color,width=2){ctx.strokeStyle=color;ctx.lineWidth=width;ctx.lineJoin='round';ctx.lineCap='round';for(const seg of segments){if(!seg.length)continue;ctx.beginPath();seg.forEach((r,i)=>{const x=mapX(r.timestamp),y=mapY(r.value);i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.stroke()}",
    "function drawLine(ctx,segments,mapX,mapY,color,width=1.15){ctx.strokeStyle=color;ctx.lineWidth=width;ctx.lineJoin='round';ctx.lineCap='round';for(const seg of segments){if(!seg.length)continue;if(seg.length===1){const r=seg[0];ctx.fillStyle=color;ctx.beginPath();ctx.arc(mapX(r.timestamp),mapY(r.value),Math.max(1.7,width+0.7),0,Math.PI*2);ctx.fill();continue}ctx.beginPath();seg.forEach((r,i)=>{const x=mapX(r.timestamp),y=mapY(r.value);i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.stroke()}",
)
replace_once(
    'web/o2ring.js',
    "for(const s of series){const r=s.axis==='right'?rr:lr;drawLine(ctx,makeSegments(rows,s.key,a,b,gap),mx,v=>my(v,r),s.color,2)}ctx.fillStyle=COLORS.text;",
    "for(const s of series){const r=s.axis==='right'?rr:lr;drawLine(ctx,makeSegments(rows,s.key,a,b,gap),mx,v=>my(v,r),s.color,opts.lineWidth??1.15)}const ctl=R.chartControllers.get(c),drag=ctl?.drag;if(drag?.mode==='zoom'&&num(drag.start)!=null&&num(drag.end)!=null){const x1=mx(Math.min(drag.start,drag.end)),x2=mx(Math.max(drag.start,drag.end));ctx.fillStyle='rgba(85,183,255,.16)';ctx.fillRect(x1,p.t,x2-x1,ih);ctx.strokeStyle='#55b7ff';ctx.lineWidth=1;ctx.strokeRect(x1,p.t,x2-x1,ih)}ctx.fillStyle=COLORS.text;",
)

# 2 + 4: Focus O2 becomes two normal overview mini cards using the core hero chart engine.
replace_between(
    'web/o2ring.js',
    'function renderFocus(){',
    'function ensureStackO2(){',
    """const O2_FOCUS_DEFS=[{key:'o2_spo2',source:'spo2',title:'SpO₂',unit:'%',color:COLORS.spo2},{key:'o2_hr',source:'heart_rate',title:'Pulzus',unit:'bpm',color:COLORS.hr}];
function isO2FocusKey(key){return O2_FOCUS_DEFS.some(x=>x.key===key)}
function ensureO2CoreChartDefs(){try{for(const d of O2_FOCUS_DEFS)if(CHART_BY_KEY&&!CHART_BY_KEY[d.key])CHART_BY_KEY[d.key]={key:d.key,title:d.title,color:d.color}}catch{}}
function o2CoreSignal(key){const d=O2_FOCUS_DEFS.find(x=>x.key===key);if(!d)return null;const rows=normalizeRows(R.day?.samples||[]),gap=chartGap(rows,false),segs=makeSegments(rows,d.source,-Infinity,Infinity,gap),series=segs.map(seg=>{const start=seg[0]?.timestamp||0;return{start:new Date(start*1000).toISOString(),points:seg.map(r=>[r.timestamp-start,r.value])}});return{key,unit:d.unit,series}}
function renderFocus(){const host=id('overviewGrid');if(!host)return;ensureO2CoreChartDefs();id('smO2FocusSection')?.remove();const validDay=R.dayCode===dayCode(),show=!!(validDay&&R.day?.available);for(const d of O2_FOCUS_DEFS){let card=host.querySelector(`.overview-card[data-key=\"${d.key}\"]`);if(!card){card=document.createElement('button');card.type='button';card.className='overview-card sm-o2-focus-mini';card.dataset.key=d.key;card.dataset.o2ringFeature='1';card.innerHTML=`<div class=\"mini-head\"><span>${d.title}</span><small id=\"mini-unit-${d.key}\">${d.unit}</small></div><canvas id=\"mini-${d.key}\"></canvas>`;card.onclick=()=>selectSignal(d.key);host.appendChild(card)}card.classList.toggle('hidden',!show);card.classList.toggle('selected',state.selectedSignal===d.key);if(show){const data=o2CoreSignal(d.key);state.overviewSignals.set(d.key,data);const u=id(`mini-unit-${d.key}`);if(u)u.textContent=d.unit;try{drawMini(d.key)}catch{}if(state.selectedSignal===d.key){state.mainSignal=data;try{updateHeroHeader();drawHeroBase();drawHeroOverlay()}catch{}}}}if(!show&&isO2FocusKey(state.selectedSignal)){try{selectSignal('flow')}catch{}}}
""",
)

# 6-7: default wording and All Charts overlay visibility/hover integration.
replace_once(
    'web/o2ring.js',
    "s.innerHTML='<option value=\"off\">+ O₂</option><option value=\"spo2\">SpO₂</option><option value=\"hr\">Pulzus</option><option value=\"both\">SpO₂ + Pulzus</option>';",
    "s.innerHTML='<option value=\"off\">Alapnézet</option><option value=\"spo2\">SpO₂</option><option value=\"hr\">Pulzus</option><option value=\"both\">SpO₂ + Pulzus</option>';",
)
replace_once(
    'web/o2ring.js',
    "function savedOverlay(key){if(R.overlay.has(key))return R.overlay.get(key);let v='off';try{v=localStorage.getItem(`sm-o2-overlay:${key}`)||'off'}catch{}R.overlay.set(key,v);return v}function saveOverlay(key,v){R.overlay.set(key,v);try{localStorage.setItem(`sm-o2-overlay:${key}`,v)}catch{}drawOverlays()}",
    "function savedOverlay(key){if(R.overlay.has(key))return R.overlay.get(key);let v='off';try{v=localStorage.getItem(`sm-o2-overlay:${key}`)||'off'}catch{}R.overlay.set(key,v);return v}function syncStackOverlayClass(key,mode){for(const card of qa('#stackedCharts .stack-chart:not(.sm-o2-stack)'))if(stackKey(card)===key)card.classList.toggle('sm-has-o2-overlay',mode!=='off')}function saveOverlay(key,v){R.overlay.set(key,v);try{localStorage.setItem(`sm-o2-overlay:${key}`,v)}catch{}syncStackOverlayClass(key,v);drawOverlays()}",
)
replace_once(
    'web/o2ring.js',
    "function updateFocusOverlayControl(){const s=id('smO2OverlayFocusSelect');if(!s)return;let key='flow';try{key=state.selectedSignal||'flow'}catch{}s.dataset.signal=key;s.value=savedOverlay(key);s.disabled=!R.day?.available}",
    "function updateFocusOverlayControl(){const s=id('smO2OverlayFocusSelect');if(!s)return;let key='flow';try{key=state.selectedSignal||'flow'}catch{}const virtual=isO2FocusKey(key);id('smO2OverlayFocus')?.classList.toggle('hidden',virtual);s.dataset.signal=key;s.value=savedOverlay(key);s.disabled=!R.day?.available||virtual}",
)
replace_once(
    'web/o2ring.js',
    "s.dataset.signal=key;s.value=savedOverlay(key);s.disabled=!R.day?.available;ensureStackOverlayCanvas(card,key)",
    "s.dataset.signal=key;s.value=savedOverlay(key);s.disabled=!R.day?.available;card.classList.toggle('sm-has-o2-overlay',s.value!=='off');ensureStackOverlayCanvas(card,key)",
)
replace_between(
    'web/o2ring.js',
    'function drawOverlayCanvas(c,key,mode){',
    'function drawOverlays(){',
    """function drawOverlayCanvas(c,key,mode){if(!c||!visible(c))return;const {ctx,w,h}=chartSize(c,190);ctx.clearRect(0,0,w,h);if(!R.day?.available||mode==='off')return;const rs=normalizeRows(R.day.samples||[]),range=dailyRange();if(!range)return;const[a,b]=range,p={l:54,r:54,t:18,b:32},iw=w-p.l-p.r,ih=h-p.t-p.b,mx=t=>p.l+(t-a)/Math.max(.001,b-a)*iw,gap=Math.max(4,medianDelta(rs)*3.2),hrs=rs.map(r=>num(r.heart_rate)).filter(v=>v!=null),hrLo=hrs.length?Math.max(30,Math.floor(Math.min(...hrs)-6)):40,hrHi=hrs.length?Math.min(220,Math.ceil(Math.max(...hrs)+6)):140,my=(v,lo,hi)=>p.t+(hi-v)/Math.max(.001,hi-lo)*ih;if(mode==='spo2'||mode==='both')drawLine(ctx,makeSegments(rs,'spo2',a,b,gap),mx,v=>my(v,75,100),COLORS.spo2,1.05);if(mode==='hr'||mode==='both')drawLine(ctx,makeSegments(rs,'heart_rate',a,b,gap),mx,v=>my(v,hrLo,hrHi),COLORS.hr,1.05);drawOverlayScaleLabels(ctx,w,h,p,mode,hrLo,hrHi);let ht=null;try{ht=num(state.hoverTime);if(ht&&ht>1e12)ht/=1000}catch{}if(ht&&ht>=a&&ht<=b){const x=mx(ht),r=nearest(rs,ht);ctx.strokeStyle='rgba(235,248,255,.66)';ctx.setLineDash([4,4]);ctx.beginPath();ctx.moveTo(x,p.t);ctx.lineTo(x,p.t+ih);ctx.stroke();ctx.setLineDash([]);if(r){const parts=[clock(r.timestamp)];if((mode==='spo2'||mode==='both')&&num(r.spo2)!=null)parts.push(`SpO₂ ${fmt(r.spo2,0)}%`);if((mode==='hr'||mode==='both')&&num(r.heart_rate)!=null)parts.push(`Pulzus ${fmt(r.heart_rate,0)} bpm`);const txt=parts.join('  •  ');ctx.font='10px system-ui';const tw=ctx.measureText(txt).width,tx=Math.max(p.l,Math.min(w-p.r-tw-10,x+8));ctx.fillStyle='rgba(6,15,25,.9)';ctx.fillRect(tx,p.t+4,tw+8,18);ctx.fillStyle='#dff5ff';ctx.fillText(txt,tx+4,p.t+17)}}}
""",
)

# 9: always own the dashboard section, use medians, stable dates, and draw even one matched night.
replace_between(
    'web/o2ring.js',
    'async function refreshDashboardO2(force=false){',
    'async function loadRecordings(){',
    """function ensureDashboardO2Section(){const agg=q('#dashboardOverviewView .aggregate-cards');if(!agg)return null;let sec=id('smDashboardO2V534');if(!sec){sec=document.createElement('section');sec.id='smDashboardO2V534';sec.className='panel sm-dashboard-o2-v534';sec.dataset.o2ringFeature='1';sec.innerHTML='<div class=\"panel-head\"><div><h3>Oximetriai összegzés</h3><span>CPAP-idővel átfedő O2Ring-adatok.</span></div><button id=\"smDashO2Open\">Oximetria →</button></div><div class=\"sm-dashboard-o2-cards\"><div><span>Medián SpO₂</span><b id=\"smDashO2Avg\">—</b></div><div><span>Minimum SpO₂</span><b id=\"smDashO2Min\">—</b></div><div><span>Medián pulzus</span><b id=\"smDashHrAvg\">—</b></div><div><span>Átlag T90</span><b id=\"smDashT90\">—</b></div></div><div class=\"sm-dashboard-o2-mini\"><article><header>SpO₂ trend</header><div class=\"sm-o2-chart-wrap\"><canvas id=\"smDashO2Trend\"></canvas></div></article><article><header>Pulzus trend</header><div class=\"sm-o2-chart-wrap\"><canvas id=\"smDashHrTrend\"></canvas></div></article></div><div id=\"smDashO2Empty\" class=\"o2r-empty hidden\">Ebben az időszakban még nincs illesztett O2Ring adat.</div>';agg.insertAdjacentElement('afterend',sec);id('smDashO2Open').onclick=()=>openOximetry('recordings')}return sec}
function dayTrendTs(code){const s=String(code||'');if(!/^\\d{8}$/.test(s))return null;return Date.UTC(Number(s.slice(0,4)),Number(s.slice(4,6))-1,Number(s.slice(6,8)),12)/1000}
async function refreshDashboardO2(force=false){const sec=ensureDashboardO2Section();if(!sec)return;let rows=[];try{rows=state.dashboardOverview?.rows||[]}catch{}if(!rows.length){R.dashboardTrendRows=[];id('smDashO2Empty')?.classList.remove('hidden');drawDashboardO2Mini();return}const data=await getBatch(rows.map(r=>r.day),force),avail=data.filter(x=>x.available&&x.summary).sort((a,b)=>String(a.day).localeCompare(String(b.day))),av=key=>{const v=avail.map(x=>num(x.summary?.[key])).filter(x=>x!=null);return v.length?v.reduce((a,b)=>a+b,0)/v.length:null},mins=avail.map(x=>num(x.summary?.spo2_minimum)).filter(x=>x!=null),spo2Med=av('spo2_median')??av('spo2_average'),hrMed=av('heart_rate_median')??av('heart_rate_average');id('smDashO2Avg').textContent=spo2Med==null?'—':`${fmt(spo2Med,1)}%`;id('smDashO2Min').textContent=mins.length?`${Math.min(...mins)}%`:'—';id('smDashHrAvg').textContent=hrMed==null?'—':`${fmt(hrMed,1)} bpm`;id('smDashT90').textContent=av('t90_seconds')==null?'—':dur(av('t90_seconds'));id('smDashO2Empty').classList.toggle('hidden',avail.length>0);R.dashboardTrendRows=avail.map((x,i)=>({timestamp:num(x.matches?.[0]?.cpap_start)||dayTrendTs(x.day)||Date.now()/1000+i*86400,spo2:num(x.summary?.spo2_median)??num(x.summary?.spo2_average),heart_rate:num(x.summary?.heart_rate_median)??num(x.summary?.heart_rate_average)}));if(force)R.dashboardTrendZoom=null;drawDashboardO2Mini()}
""",
)

# Core hooks: rebuild O2 mini cards with the normal overview grid, serve virtual O2 signals in the normal hero,
# and redraw O2 overlays on every core hover RAF.
hook_start = "function hookCore(){if(window.__smO2CoreV534)return;window.__smO2CoreV534=true;try{"
text=read('web/o2ring.js')
if hook_start not in text: raise SystemExit('hookCore start missing')
extra = "if(typeof buildOverviewGrid==='function'&&!buildOverviewGrid.__smO2){const origBuildOverview=buildOverviewGrid;buildOverviewGrid=function(...a){const r=origBuildOverview(...a);renderFocus();return r};buildOverviewGrid.__smO2=true}if(typeof loadMainSignal==='function'&&!loadMainSignal.__smO2){const origMainSignal=loadMainSignal;loadMainSignal=async function(...a){if(isO2FocusKey(state.selectedSignal)){const data=o2CoreSignal(state.selectedSignal);state.mainSignal=data;try{updateHeroHeader();drawHeroBase();drawHeroOverlay()}catch{}return data}return origMainSignal(...a)};loadMainSignal.__smO2=true}if(typeof scheduleOverlayRender==='function'&&!scheduleOverlayRender.__smO2){const origScheduleOverlay=scheduleOverlayRender;scheduleOverlayRender=function(...a){const r=origScheduleOverlay(...a);if(!R.overlayRaf)R.overlayRaf=requestAnimationFrame(()=>{R.overlayRaf=0;drawOverlays()});return r};scheduleOverlayRender.__smO2=true}"
text=text.replace(hook_start,hook_start+extra,1)
write('web/o2ring.js',text)
replace_once(
    'web/o2ring.js',
    "liveRaf:0,resizeRaf:0,liveZoom:null",
    "liveRaf:0,resizeRaf:0,overlayRaf:0,liveZoom:null",
)

# CSS: Focus O2 cards inherit stock overview geometry; active All Charts overlays reserve exactly their right axis strip.
css=read('web/o2ring-v534.css')
css += """

/* v5.3.5 chart integration */
.overview-card.sm-o2-focus-mini{background:#171b30;border-color:#242b45}.overview-card.sm-o2-focus-mini.selected{outline:1px solid #64bdfb;border-color:#64bdfb}.overview-card.sm-o2-focus-mini canvas{display:block;width:100%;height:72px;background:#101722;border-radius:4px}
#stackedCharts .stack-chart.sm-has-o2-overlay{padding-right:52px}#stackedCharts .stack-chart.sm-has-o2-overlay .stack-canvas{overflow:visible!important}.o2r-hero-actions [data-o2r-tab].active{background:#203449;color:#77ceff;border-color:#4b7795}
"""
write('web/o2ring-v534.css',css)

# Update source-level contracts from legacy custom Focus section to normal core mini/hero integration.
p='tests/test_v534_acceptance_matrix.py'; text=read(p)
old='''        "smO2FocusSpo2",\n        "smO2FocusHr",\n        "smO2FocusDual",\n'''
new='''        "O2_FOCUS_DEFS",\n        "mini-${d.key}",\n        "o2CoreSignal",\n'''
if text.count(old)!=1: raise SystemExit('focus acceptance marker block missing')
text=text.replace(old,new,1)
text=text.replace('        "syncGroup:\'focus-o2\'",\n','',1)
write(p,text)

# Extend v5.3.5 requirements contract.
p='tests/test_v535_polish_contract.py'; text=read(p)
text += '''\n\ndef test_v535_focus_uses_normal_mini_and_hero_chart_engine():\n    js=read("web/o2ring.js")\n    assert "O2_FOCUS_DEFS" in js\n    assert "card.className='overview-card sm-o2-focus-mini'" in js\n    assert "card.onclick=()=>selectSignal(d.key)" in js\n    assert "function o2CoreSignal(key)" in js\n    focus=js[js.index("const O2_FOCUS_DEFS"):js.index("function ensureStackO2")]\n    assert "smO2FocusDual" not in focus\n\ndef test_v535_o2_selection_line_weight_overlay_and_dashboard_contract():\n    js=read("web/o2ring.js"); css=read("web/o2ring-v534.css")\n    assert "drag?.mode==='zoom'" in js and "ctx.fillStyle='rgba(85,183,255,.16)'" in js\n    assert "opts.lineWidth??1.15" in js\n    assert "COLORS.spo2,1.05" in js and "COLORS.hr,1.05" in js\n    assert '<option value="off">Alapnézet</option>' in js\n    assert "scheduleOverlayRender.__smO2" in js\n    assert "sm-has-o2-overlay" in js and "sm-has-o2-overlay" in css\n    assert "function ensureDashboardO2Section()" in js\n    assert "seg.length===1" in js\n'''
write(p,text)
print('v5.3.5 round 2 patch applied')
