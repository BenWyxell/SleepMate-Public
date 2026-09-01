(()=>{
'use strict';
if(window.__sleepmateO2V532)return;
window.__sleepmateO2V532=true;

const VERSION='5.3.2';
const COLORS={
  cyan:'#55d8ff', cyan2:'#39c5f3', teal:'#48e1b9', violet:'#9a7cff', blue:'#6e8dff', rose:'#ef86c8',
  grid:'rgba(132,181,216,.14)', text:'#8fa8bc', bg:'#0d1621'
};
const EVENT_COLORS={OA:'#55c7ff',CA:'#9a7cff',H:'#48e1b9',RERA:'#ef86c8'};
const OVERLAY_SUPPORTED=new Set(['pressure','leak','flow_lim','snore']);
const q=s=>document.querySelector(s);
const qa=s=>[...document.querySelectorAll(s)];
const id=x=>document.getElementById(x);
const num=v=>v==null||v===''||!Number.isFinite(Number(v))?null:Number(v);
const fmt=(v,d=1)=>num(v)==null?'–':Number(v).toLocaleString('hu-HU',{minimumFractionDigits:d,maximumFractionDigits:d});
const dayCode=()=>String(id('day')?.value||'').replace(/-/g,'').slice(0,8);
const fmtClock=s=>num(s)==null?'–':new Date(Number(s)*1000).toLocaleTimeString('hu-HU',{hour:'2-digit',minute:'2-digit'});
const fmtDate=s=>num(s)==null?'–':new Date(Number(s)*1000).toLocaleDateString('hu-HU',{month:'2-digit',day:'2-digit'});
const fmtT90=s=>{s=Math.max(0,Number(s)||0);return s<3600?`${Math.round(s/60)} p`:`${Math.floor(s/3600)} ó ${String(Math.round((s%3600)/60)).padStart(2,'0')} p`};
const api=async(path,opts={})=>{
  const r=await fetch(path,{cache:'no-store',...opts,headers:{'Content-Type':'application/json',...(opts.headers||{})}});
  const x=await r.json().catch(()=>({}));
  if(!r.ok)throw new Error(x.error||`HTTP ${r.status}`);
  return x;
};
const status={data:null,timer:null,busy:false};
const cache={day:new Map(),summary:new Map(),batch:new Map()};
const ui={mode:'focus',views:{focus:null,stack:null},daily:null,dailyCode:'',overlay:new Map(),live:[],liveSource:null,liveZoom:null,liveFollow:true,recordingObserver:null,domObserver:null,raf:0};
const o2SettingsIds=new Set(['smO2Enabled','smO2Ble','smO2AutoConnect','smO2AutoSync']);

function schedule(fn){
  cancelAnimationFrame(ui.raf);
  ui.raf=requestAnimationFrame(()=>{ui.raf=0;fn()});
}
function canvasSize(c,minH=150){
  const dpr=window.devicePixelRatio||1,r=c.getBoundingClientRect(),w=Math.max(240,r.width||300),h=Math.max(minH,r.height||minH);
  const pw=Math.round(w*dpr),ph=Math.round(h*dpr);
  if(c.width!==pw||c.height!==ph){c.width=pw;c.height=ph}
  const ctx=c.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);return{ctx,w,h};
}
function line(ctx,pts){if(!pts.length)return;ctx.beginPath();ctx.moveTo(pts[0].x,pts[0].y);for(let i=1;i<pts.length;i++)ctx.lineTo(pts[i].x,pts[i].y);ctx.stroke()}
function sampleBounds(rows){
  const t=(rows||[]).map(r=>num(r.timestamp)).filter(v=>v!=null);
  return t.length?[Math.min(...t),Math.max(...t)]:null;
}
async function getDay(code,full=true){
  code=String(code||'').replace(/-/g,'').slice(0,8);
  if(!/^\d{8}$/.test(code))return null;
  const map=full?cache.day:cache.summary,key=`${code}:${full?1:0}`;
  if(map.has(key))return map.get(key);
  const promise=api(`/api/o2ring/day?day=${code}&max_points=${full?14000:1}`).catch(()=>null);
  map.set(key,promise);return promise;
}
async function getBatch(days){
  const clean=[...new Set((days||[]).map(x=>String(x||'').replace(/-/g,'').slice(0,8)).filter(x=>/^\d{8}$/.test(x)))];
  if(!clean.length)return [];
  const all=[];
  for(let i=0;i<clean.length;i+=90){
    const part=clean.slice(i,i+90),key=part.join(',');
    let promise=cache.batch.get(key);
    if(!promise){
      promise=api(`/api/o2ring/day-batch?days=${encodeURIComponent(key)}`).catch(()=>({rows:[]}));
      cache.batch.set(key,promise);
    }
    const x=await promise;all.push(...(x.rows||[]));
  }
  return all;
}
function clearO2Cache(){cache.day.clear();cache.summary.clear();cache.batch.clear();ui.daily=null;ui.dailyCode='';}

function drawDual(c,rows,{bounds=null,selection=null,empty='Még nincs megjeleníthető SpO₂ / pulzus adat.'}={}){
  if(!c)return;
  const {ctx,w,h}=canvasSize(c,190);ctx.clearRect(0,0,w,h);ctx.fillStyle=COLORS.bg;ctx.fillRect(0,0,w,h);
  const data=(rows||[]).filter(r=>num(r.spo2)!=null||num(r.heart_rate)!=null);
  if(!data.length){ctx.fillStyle='#8fa8bc';ctx.font='12px system-ui';ctx.fillText(empty,16,28);return}
  const full=sampleBounds(data);if(!full)return;
  let a=bounds?.[0]??full[0],b=bounds?.[1]??full[1];if(!(b>a)){a=full[0];b=full[1]+1}
  const hrs=data.map(r=>num(r.heart_rate)).filter(v=>v!=null),hrLo=hrs.length?Math.max(30,Math.floor(Math.min(...hrs)-8)):40,hrHi=hrs.length?Math.min(220,Math.ceil(Math.max(...hrs)+8)):140;
  const p={l:50,r:54,t:24,b:32},iw=w-p.l-p.r,ih=h-p.t-p.b;
  ctx.font='10px system-ui';
  for(let i=0;i<=4;i++){
    const y=p.t+ih*i/4;ctx.strokeStyle=COLORS.grid;ctx.beginPath();ctx.moveTo(p.l,y);ctx.lineTo(w-p.r,y);ctx.stroke();
    ctx.fillStyle='#7fa6ba';ctx.fillText(String(Math.round(100-25*i/4)),6,y+3);
    ctx.fillStyle='#b19dff';const hv=Math.round(hrHi-(hrHi-hrLo)*i/4);ctx.fillText(String(hv),w-p.r+8,y+3);
  }
  ctx.fillStyle=COLORS.cyan;ctx.fillText('SpO₂ %',6,12);
  ctx.fillStyle=COLORS.violet;const tw=ctx.measureText('Pulzus bpm').width;ctx.fillText('Pulzus bpm',w-tw-7,12);
  const make=(key,lo,hi)=>data.map(r=>{const t=num(r.timestamp),v=num(r[key]);if(t==null||v==null||t<a||t>b)return null;return{x:p.l+(t-a)/(b-a)*iw,y:p.t+(hi-v)/(hi-lo)*ih}}).filter(Boolean);
  ctx.lineWidth=2;ctx.lineJoin='round';ctx.lineCap='round';
  ctx.strokeStyle=COLORS.cyan;line(ctx,make('spo2',75,100));
  ctx.strokeStyle=COLORS.violet;line(ctx,make('heart_rate',hrLo,hrHi));
  ctx.fillStyle='#7f9caf';
  for(let i=0;i<=4;i++){const t=a+(b-a)*i/4,txt=fmtClock(t),x=p.l+iw*i/4-ctx.measureText(txt).width/2;ctx.fillText(txt,Math.max(p.l,Math.min(w-p.r-ctx.measureText(txt).width,x)),h-8)}
  if(selection){
    const x1=p.l+(selection[0]-a)/(b-a)*iw,x2=p.l+(selection[1]-a)/(b-a)*iw;
    ctx.fillStyle='rgba(85,216,255,.10)';ctx.fillRect(Math.min(x1,x2),p.t,Math.abs(x2-x1),ih);ctx.strokeStyle=COLORS.cyan;ctx.strokeRect(Math.min(x1,x2),p.t,Math.abs(x2-x1),ih);
  }
  c._smO2Meta={a,b,p,iw,ih,hrLo,hrHi,data};
}
function drawSingle(c,rows,key,{bounds=null,range=null,color=COLORS.cyan,label=''}={}){
  if(!c)return;const {ctx,w,h}=canvasSize(c,160);ctx.clearRect(0,0,w,h);ctx.fillStyle=COLORS.bg;ctx.fillRect(0,0,w,h);
  const data=(rows||[]).filter(r=>num(r[key])!=null);if(!data.length){ctx.fillStyle='#8fa8bc';ctx.fillText('Nincs O2Ring adat',16,28);return}
  const full=sampleBounds(data);let a=bounds?.[0]??full[0],b=bounds?.[1]??full[1];if(!(b>a))b=a+1;
  const vals=data.map(r=>num(r[key])),lo=range?.[0]??Math.floor(Math.min(...vals)-3),hi=range?.[1]??Math.ceil(Math.max(...vals)+3),p={l:48,r:15,t:18,b:30},iw=w-p.l-p.r,ih=h-p.t-p.b;
  ctx.font='10px system-ui';for(let i=0;i<=4;i++){const y=p.t+ih*i/4;ctx.strokeStyle=COLORS.grid;ctx.beginPath();ctx.moveTo(p.l,y);ctx.lineTo(w-p.r,y);ctx.stroke();ctx.fillStyle='#7f9caf';ctx.fillText(String(Math.round(hi-(hi-lo)*i/4)),5,y+3)}
  const pts=data.map(r=>{const t=num(r.timestamp),v=num(r[key]);if(t<a||t>b)return null;return{x:p.l+(t-a)/(b-a)*iw,y:p.t+(hi-v)/(hi-lo)*ih}}).filter(Boolean);
  ctx.strokeStyle=color;ctx.lineWidth=2;line(ctx,pts);ctx.fillStyle='#7f9caf';if(label)ctx.fillText(label,p.l,11);
  for(let i=0;i<=4;i++){const txt=fmtClock(a+(b-a)*i/4),tw=ctx.measureText(txt).width;ctx.fillText(txt,Math.max(p.l,Math.min(w-p.r-tw,p.l+iw*i/4-tw/2)),h-7)}
  c._smO2Meta={a,b,p,iw,ih,data};
}
function bindZoom(c,getRows,getBounds,setBounds,redraw){
  if(!c||c.dataset.smO2Zoom==='1')return;c.dataset.smO2Zoom='1';c.style.touchAction='pan-y pinch-zoom';c.style.cursor='crosshair';
  let drag=null;
  const toTime=(clientX)=>{const m=c._smO2Meta,r=c.getBoundingClientRect();if(!m)return null;const x=Math.max(m.p.l,Math.min(r.width-m.p.r,clientX-r.left));return m.a+(x-m.p.l)/Math.max(1,m.iw)*(m.b-m.a)};
  c.addEventListener('pointerdown',e=>{if(e.button!=null&&e.button!==0)return;const t=toTime(e.clientX);if(t==null)return;drag={id:e.pointerId,start:t,end:t,x:e.clientX};c.classList.add('sm-o2-zooming');try{c.setPointerCapture(e.pointerId)}catch{}});
  c.addEventListener('pointermove',e=>{if(!drag||drag.id!==e.pointerId)return;drag.end=toTime(e.clientX)??drag.end});
  const finish=e=>{if(!drag||drag.id!==e.pointerId)return;const d=drag;drag=null;c.classList.remove('sm-o2-zooming');const a=Math.min(d.start,d.end),b=Math.max(d.start,d.end);if(Math.abs(e.clientX-d.x)>5&&b-a>8){setBounds([a,b]);redraw()}};
  c.addEventListener('pointerup',finish);c.addEventListener('pointercancel',e=>{if(drag&&drag.id===e.pointerId){drag=null;c.classList.remove('sm-o2-zooming')}});
  c.addEventListener('dblclick',()=>{setBounds(null);redraw()});
}

function addResetButton(card,reset){
  const head=card?.querySelector('.o2r-chart-head,header,.stack-head');if(!head||head.querySelector('.sm-o2-reset'))return;
  const b=document.createElement('button');b.type='button';b.className='sm-o2-reset';b.textContent='Teljes idő';b.onclick=reset;head.appendChild(b);
}

function compactOximetry(){
  const page=id('page-oximetry');if(!page)return;
  const hero=page.querySelector('.o2r-hero');if(hero)hero.classList.add('sm-o2-hero-v532');
  const liveCards=page.querySelector('.o2r-live-cards');if(liveCards)liveCards.classList.add('sm-o2-live-chips');
  const actions=hero?.querySelector('.o2r-hero-actions');
  if(actions&&!id('smO2DashLink')){const b=document.createElement('button');b.id='smO2DashLink';b.type='button';b.className='sm-o2-dashboard-link';b.textContent='← Dashboard';b.onclick=()=>window.navigate?.('dashboard');actions.prepend(b)}
  const st=id('o2rStatus');if(st)st.classList.add('sm-o2-status-compact');
  ensureLiveCombined();
}
function ensureLiveCombined(){
  const view=q('#page-oximetry [data-o2r-view="live"]'),grid=view?.querySelector('.o2r-chart-grid');if(!view||!grid)return;
  let card=id('smO2LiveCombined');
  if(!card){
    card=document.createElement('article');card.id='smO2LiveCombined';card.className='panel sm-o2-combined-card';
    card.innerHTML='<div class="o2r-chart-head"><div><h3>SpO₂ + pulzus – élő</h3><span class="muted">Közös időtengely • bal: SpO₂ • jobb: pulzus</span></div><div class="sm-o2-legend"><span class="spo2">SpO₂</span><span class="hr">Pulzus</span></div></div><canvas id="smO2LiveCombinedCanvas"></canvas><div class="sm-o2-chart-hint">Húzással nagyíthatsz • dupla kattintás: teljes élő időablak</div>';
    grid.insertAdjacentElement('beforebegin',card);
    const c=id('smO2LiveCombinedCanvas');bindZoom(c,()=>liveRows(),()=>liveBounds(),v=>{ui.liveZoom=v;ui.liveFollow=!v;const f=id('o2rFollowLive');if(f)f.checked=!v},drawLiveCombined);addResetButton(card,()=>{ui.liveZoom=null;ui.liveFollow=true;const f=id('o2rFollowLive');if(f)f.checked=true;drawLiveCombined()});
  }
  const old=view.querySelector('.o2r-chart-grid');if(old)old.classList.add('sm-o2-secondary-live');
}
function liveRows(){return ui.live}
function liveBounds(){
  if(ui.liveZoom)return ui.liveZoom;
  if(!ui.live.length)return null;
  const v=id('o2rLiveWindow')?.value||'30',end=ui.live.at(-1).timestamp,start=v==='all'?ui.live[0].timestamp:end-Number(v)*60;
  return [Math.max(ui.live[0].timestamp,start),end];
}
function drawLiveCombined(){drawDual(id('smO2LiveCombinedCanvas'),ui.live,{bounds:liveBounds()})}
function startOwnLiveStream(){
  if(ui.liveSource||typeof EventSource==='undefined')return;
  try{
    ui.liveSource=new EventSource('/api/o2ring/live-stream');
    ui.liveSource.addEventListener('sample',e=>{
      try{
        const x=JSON.parse(e.data),timestamp=num(x.last_sample_ts)||Date.now()/1000,spo2=num(x.spo2),heart_rate=num(x.heart_rate);
        if(spo2==null&&heart_rate==null)return;
        const last=ui.live.at(-1);if(last&&last.timestamp===timestamp){last.spo2=spo2;last.heart_rate=heart_rate}else ui.live.push({timestamp,spo2,heart_rate});
        if(ui.live.length>24000)ui.live=ui.live.slice(-24000);
        if(ui.liveFollow&&!ui.liveZoom)drawLiveCombined();
      }catch{}
    });
    ui.liveSource.onerror=()=>{};
  }catch{}
}

async function refreshStatus(){
  clearTimeout(status.timer);if(status.busy)return;status.busy=true;
  try{
    status.data=await api('/api/o2ring/status');const l=status.data.live||{},cfg=status.data.settings||{},connected=!!l.connected;
    [id('o2rConnectNow'),id('o2rConnectSettings'),id('smO2QuickConnect')].forEach(b=>b?.classList.toggle('hidden',connected));
    const badge=id('o2rStatus');if(badge){badge.textContent=!cfg.o2ring_ble_enabled?'BLE kikapcsolva':connected?(l.measuring?'Mér':'Kapcsolódva'):(l.scanning?'Keresés…':'Nincs kapcsolat')}
    const n=id('smO2QuickName');if(n)n.textContent=l.device_model||l.device_name||l.remembered_address||cfg.o2ring_preferred_address||'Nincs kiválasztott gyűrű';
    const s=id('smO2QuickState');if(s)s.textContent=!cfg.o2ring_ble_enabled?'Bluetooth kikapcsolva':connected?(l.measuring?'Élő mérés':'Kapcsolódva'):(l.scanning?'Gyűrű keresése…':'Nincs kapcsolat');
    patchPwaLiveChoice(!!cfg.o2ring_enabled);
  }catch{}finally{
    status.busy=false;const active=location.hash.startsWith('#oximetry')||id('page-settings')?.classList.contains('active');status.timer=setTimeout(refreshStatus,active?5000:12000);
  }
}

function movePwaIntoPush(){
  const tabs=q('.settings-inner-tabs'),push=tabs?.querySelector('[data-settings-tab="push"]'),pwa=tabs?.querySelector('[data-settings-tab="pwa"]'),sel=id('settingsCategorySelect'),pushPanel=q('[data-settings-panel="push"]'),pwaPanel=id('smPwaSettingsPanel');
  if(push&&push.textContent!=='PWA')push.textContent='PWA';
  if(pwa){pwa.remove()}
  if(sel){const op=[...sel.options].find(o=>o.value==='push');if(op&&op.textContent!=='PWA')op.textContent='PWA';const p=[...sel.options].find(o=>o.value==='pwa');p?.remove()}
  if(pushPanel&&pwaPanel&&!pushPanel.contains(pwaPanel)){pwaPanel.classList.remove('settings-tab-panel','panel');pwaPanel.removeAttribute('data-settings-panel');pushPanel.prepend(pwaPanel)}
}
function moveO2Settings(){
  const tab=q('[data-settings-tab="display"]'),panel=q('[data-settings-panel="display"]'),sel=id('settingsCategorySelect');if(!tab||!panel)return;
  if(tab.textContent!=='O2Ring')tab.textContent='O2Ring';const op=sel?[...sel.options].find(x=>x.value==='display'):null;if(op&&op.textContent!=='O2Ring')op.textContent='O2Ring';
  panel.classList.add('sm-o2-settings-panel');
  const master=id('smO2Master'),details=id('o2rDetails');if(master&&master.parentNode!==panel)panel.prepend(master);if(details&&details.parentNode!==panel)panel.appendChild(details);
  if(master&&!id('smO2QuickBar')){
    const bar=document.createElement('div');bar.id='smO2QuickBar';bar.className='sm-o2-quickbar';
    bar.innerHTML='<div class="sm-o2-quick-copy"><i></i><div><small>O2Ring kapcsolat</small><b id="smO2QuickName">Ellenőrzés…</b><span id="smO2QuickState">Ellenőrzés…</span></div></div><div class="sm-o2-quick-actions"><button id="smO2QuickConnect" type="button">Gyűrű keresése</button><button id="smO2QuickSync" type="button">↻ Szinkron</button></div>';
    master.insertAdjacentElement('afterend',bar);
    id('smO2QuickConnect').onclick=async()=>{try{await api('/api/o2ring/connect',{method:'POST',body:'{}'});setTimeout(refreshStatus,500)}catch(e){setSettingsMsg(e.message)}};
    id('smO2QuickSync').onclick=async()=>{try{await api('/api/o2ring/sync',{method:'POST',body:'{}'});setSettingsMsg('Szinkronizálás elindítva.');clearO2Cache()}catch(e){setSettingsMsg(e.message)}};
  }
}
function setSettingsMsg(t){const e=id('smO2MasterMsg')||id('o2rSettingsMsg');if(e)e.textContent=t||''}
let saveRunning=false,saveQueued=false;
async function saveO2Toggles(){
  saveQueued=true;if(saveRunning)return;saveRunning=true;
  try{
    while(saveQueued){
      saveQueued=false;const g=x=>id(x),payload={
        o2ring_enabled:!!g('smO2Enabled')?.checked,o2ring_ble_enabled:!!g('smO2Ble')?.checked,
        o2ring_auto_connect:!!g('smO2AutoConnect')?.checked,o2ring_auto_sync:!!g('smO2AutoSync')?.checked
      };
      q('.sm-o2-settings-panel')?.classList.add('sm-saving');setSettingsMsg('Mentés…');
      try{await api('/api/o2ring/settings',{method:'POST',body:JSON.stringify(payload)});await window.SleepMateV530?.refreshO2?.();patchPwaLiveChoice(payload.o2ring_enabled);setSettingsMsg('O2Ring beállítások mentve.');clearO2Cache()}
      catch(e){setSettingsMsg(e.message)}
    }
  }finally{saveRunning=false;q('.sm-o2-settings-panel')?.classList.remove('sm-saving');moveO2Settings();refreshStatus()}
}
function captureO2Toggle(e){
  const t=e.target;if(!t||!o2SettingsIds.has(t.id))return;
  e.stopImmediatePropagation();saveO2Toggles();
}

function patchPwaLiveChoice(enabled){
  const V=window.SleepMateV530;if(!V?.NAV||!V?.ICONS)return;if(ui.pwaLiveEnabled===enabled&&((enabled&&V.NAV.oximetry_live)||(!enabled&&!V.NAV.oximetry_live)))return;ui.pwaLiveEnabled=enabled;
  if(enabled){V.ICONS.oximetry_live=V.ICONS.oximetry;V.NAV.oximetry_live={label:'Élő Oxi',page:'oximetry'}}
  else{delete V.NAV.oximetry_live;delete V.ICONS.oximetry_live}
  V.renderBottomNav?.();V.renderPwaEditor?.();
}
function openOximetryLive(){
  if(location.hash!=='#oximetry')location.hash='#oximetry';
  requestAnimationFrame(()=>{qa('[data-o2r-tab]').forEach(x=>x.classList.toggle('active',x.dataset.o2rTab==='live'));qa('[data-o2r-view]').forEach(x=>x.classList.toggle('active',x.dataset.o2rView==='live'));compactOximetry();drawLiveCombined()});
}
function patchO2Nav(){
  const b=q('[data-page="oximetry"]');if(b&&b.dataset.smV532!=='1'){b.dataset.smV532='1';b.onclick=e=>{e?.preventDefault?.();if(location.hash!=='#oximetry')location.hash='#oximetry';else openOximetryLive()}}
}
function capturePwaLive(e){
  const rec=e.target?.closest?.('[data-rid]');if(rec?.dataset?.rid)ui.currentRecordingId=rec.dataset.rid;
  const b=e.target?.closest?.('[data-sm-nav-id="oximetry_live"]');if(!b)return;e.preventDefault();e.stopImmediatePropagation();openOximetryLive();
}

function fullCoreView(){try{return Array.isArray(state?.full)?[...state.full]:null}catch{return null}}
function coreView(){try{return Array.isArray(state?.view)?[...state.view]:null}catch{return null}}
function setCoreView(v){try{if(v&&typeof setView==='function')setView(v[0],v[1],true)}catch{}}
function rememberCoreView(mode){const v=coreView();if(v)ui.views[mode]=v}
function switchDailyMode(mode){
  const prev=ui.mode;if(prev==='focus'||prev==='stack')rememberCoreView(prev);ui.mode=mode;
  const f=id('focusViewBtn'),s=id('stackViewBtn'),o=id('o2rDailyBtn'),hero=q('#dashboardDailyView .hero-panel'),ov=id('overviewBlock'),st=id('stackedBlock'),op=id('o2rDailyPanel');
  f?.classList.toggle('active',mode==='focus');s?.classList.toggle('active',mode==='stack');o?.classList.toggle('active',mode==='o2');
  if(mode==='o2'){hero?.classList.add('hidden');ov?.classList.add('hidden');st?.classList.add('hidden');op?.classList.remove('hidden');loadDailyO2(true)}
  else{
    op?.classList.add('hidden');hero?.classList.remove('hidden');
    if(mode==='focus'){ov?.classList.remove('hidden');st?.classList.add('hidden')}
    else{ov?.classList.add('hidden');st?.classList.remove('hidden');ensureStackO2()}
    const target=ui.views[mode]||fullCoreView();if(target)setTimeout(()=>setCoreView(target),0);
  }
}
function patchDailyTabs(){
  const o=id('o2rDailyBtn'),f=id('focusViewBtn'),s=id('stackViewBtn');if(!o||!f||!s)return;
  id('o2rDailyBack')?.remove();
  if(o.dataset.smV532!=='1'){o.dataset.smV532='1';o.onclick=e=>{e.preventDefault();switchDailyMode('o2')}}
  if(f.dataset.smO2Mode!=='1'){f.dataset.smO2Mode='1';f.addEventListener('click',()=>setTimeout(()=>switchDailyMode('focus'),0))}
  if(s.dataset.smO2Mode!=='1'){s.dataset.smO2Mode='1';s.addEventListener('click',()=>setTimeout(()=>switchDailyMode('stack'),0))}
  if(!f.classList.contains('active')&&!s.classList.contains('active')&&!o.classList.contains('active'))switchDailyMode('focus');
}
async function loadDailyO2(force=false){
  const code=dayCode();if(!/^\d{8}$/.test(code))return null;
  if(!force&&ui.daily&&ui.dailyCode===code)return ui.daily;
  const x=await getDay(code,true);if(!x)return null;ui.daily=x;ui.dailyCode=code;
  renderDailyPanel(x);renderFocusO2(x);ensureStackO2();renderNightCard(x);drawHeroO2Overlay();return x;
}
function dailyBounds(samples){
  const c=coreView();if(c&&fullCoreView()){return[c[0]/1000,c[1]/1000]}
  return sampleBounds(samples);
}
function ensureCombinedInDailyPanel(){
  const p=id('o2rDailyPanel'),two=p?.querySelector('.o2r-two-chart');if(!p||!two)return;
  let card=id('smO2DayCombinedCard');if(!card){card=document.createElement('article');card.id='smO2DayCombinedCard';card.className='sm-o2-day-combined';card.innerHTML='<div class="o2r-chart-head"><div><h4>SpO₂ + pulzus</h4><span class="muted">Közös időtengely • két külön skála</span></div></div><canvas id="smO2DayCombinedCanvas"></canvas><div class="sm-o2-chart-hint">Húzással nagyíthatsz • dupla kattintás: teljes O2-időtartam</div>';two.insertAdjacentElement('beforebegin',card);addResetButton(card,()=>{ui.o2DailyZoom=null;drawDailyPanelCharts()});bindZoom(id('smO2DayCombinedCanvas'),()=>ui.daily?.samples||[],()=>ui.o2DailyZoom||sampleBounds(ui.daily?.samples||[]),v=>ui.o2DailyZoom=v,drawDailyPanelCharts)}}
function renderDailyPanel(x){
  ensureCombinedInDailyPanel();const s=x.summary||{},show=!!x.available;const p=id('o2rDailyPanel');if(!p)return;
  p.classList.toggle('sm-o2-empty',!show);if(!show)return;
  const put=(k,v)=>{const e=id(k);if(e)e.textContent=v};
  put('o2rDayAvg',`${fmt(s.spo2_average,1)}%`);put('o2rDayMin',`${fmt(s.spo2_minimum,0)}%`);put('o2rDayT90',fmtT90(s.t90_seconds));put('o2rDayOdi',`${fmt(s.odi3,1)} / ${fmt(s.odi4,1)}`);put('o2rDayHr',`${fmt(s.heart_rate_average,1)} bpm`);put('o2rDayValid',`${fmt(s.coverage_percent,0)}%`);
  drawDailyPanelCharts();
}
function drawDailyPanelCharts(){
  const rs=ui.daily?.samples||[],b=ui.o2DailyZoom||sampleBounds(rs);drawDual(id('smO2DayCombinedCanvas'),rs,{bounds:b});drawSingle(id('o2rDaySpo2Chart'),rs,'spo2',{bounds:b,range:[75,100],color:COLORS.cyan,label:'SpO₂ %'});drawSingle(id('o2rDayHrChart'),rs,'heart_rate',{bounds:b,color:COLORS.violet,label:'Pulzus bpm'});
  [id('o2rDaySpo2Chart'),id('o2rDayHrChart')].forEach(c=>{if(c)bindZoom(c,()=>rs,()=>ui.o2DailyZoom||sampleBounds(rs),v=>ui.o2DailyZoom=v,drawDailyPanelCharts)});
}
function renderFocusO2(x){
  const host=id('overviewBlock');if(!host)return;let sec=id('smO2FocusSection');
  if(!sec){sec=document.createElement('section');sec.id='smO2FocusSection';sec.className='sm-o2-focus-section';sec.dataset.o2ringFeature='1';sec.innerHTML='<div class="section-title"><h3>Oximetria</h3><span>A CPAP aktuális nagyítását követő SpO₂ és pulzus</span></div><div class="sm-o2-focus-grid"><article><header><b>SpO₂</b><small>%</small></header><canvas id="smO2FocusSpo2"></canvas></article><article><header><b>Pulzus</b><small>bpm</small></header><canvas id="smO2FocusHr"></canvas></article><article class="wide"><header><b>SpO₂ + pulzus</b><small>közös időtengely</small></header><canvas id="smO2FocusDual"></canvas></article></div>';host.appendChild(sec)}
  const rs=x?.samples||[],b=dailyBounds(rs);drawSingle(id('smO2FocusSpo2'),rs,'spo2',{bounds:b,range:[75,100],color:COLORS.cyan});drawSingle(id('smO2FocusHr'),rs,'heart_rate',{bounds:b,color:COLORS.violet});drawDual(id('smO2FocusDual'),rs,{bounds:b});
  const zoomTo=v=>{if(!v)return setCoreView(fullCoreView());setCoreView([v[0]*1000,v[1]*1000])},redraw=()=>renderFocusO2(ui.daily);
  [id('smO2FocusSpo2'),id('smO2FocusHr'),id('smO2FocusDual')].forEach(c=>bindZoom(c,()=>rs,()=>dailyBounds(rs),zoomTo,redraw));
}
function ensureStackO2(){
  if(!ui.daily?.available)return;const host=id('stackedCharts');if(!host)return;
  const defs=[['smStackO2Spo2','SpO₂','%','spo2'],['smStackO2Hr','Pulzus','bpm','hr'],['smStackO2Dual','SpO₂ + pulzus','két skála','dual']];
  for(const [cid,title,unit,type] of defs){if(id(cid))continue;const card=document.createElement('section');card.id=cid;card.className='stack-chart sm-o2-stack-v532';card.dataset.o2ringFeature='1';card.innerHTML=`<div class="stack-head"><span><i class="${type}"></i>${title}</span><small>${unit}</small></div><div class="canvas-stack stack-canvas"><canvas id="${cid}Canvas"></canvas></div>`;host.appendChild(card)}
  const rs=ui.daily.samples||[],b=dailyBounds(rs);drawSingle(id('smStackO2Spo2Canvas'),rs,'spo2',{bounds:b,range:[75,100],color:COLORS.cyan});drawSingle(id('smStackO2HrCanvas'),rs,'heart_rate',{bounds:b,color:COLORS.violet});drawDual(id('smStackO2DualCanvas'),rs,{bounds:b});
  const zoomTo=v=>{if(!v)return setCoreView(fullCoreView());setCoreView([v[0]*1000,v[1]*1000])},redraw=()=>ensureStackO2();
  [id('smStackO2Spo2Canvas'),id('smStackO2HrCanvas'),id('smStackO2DualCanvas')].forEach(c=>bindZoom(c,()=>rs,()=>dailyBounds(rs),zoomTo,redraw));
}

function renderNightCard(x){
  const panel=q('.night-evaluation-panel');if(!panel)return;let c=id('smNightO2Card');
  if(!c){c=document.createElement('article');c.id='smNightO2Card';c.className='sm-night-o2-card';c.dataset.o2ringFeature='1';panel.appendChild(c)}
  let html='';if(!x?.available)html='<div><small>Oximetria</small><b>Nincs illesztett O2Ring adat</b></div>';
  else{const s=x.summary||{};html=`<div class="sm-night-o2-title"><span>O₂</span><div><small>Oximetriai összegzés</small><b>Átlag ${fmt(s.spo2_average,1)}% • ${fmt(s.heart_rate_average,0)} bpm</b></div></div><div class="sm-night-o2-values"><span>Minimum <b>${fmt(s.spo2_minimum,0)}%</b></span><span>T90 <b>${fmtT90(s.t90_seconds)}</b></span><span>ODI3 / ODI4 <b>${fmt(s.odi3,1)} / ${fmt(s.odi4,1)}</b></span><span>Lefedettség <b>${fmt(s.coverage_percent,0)}%</b></span></div>`}
  if(c.innerHTML!==html)c.innerHTML=html;
}

function ensureOverlayControl(){
  const toolbar=q('#dashboardDailyView .hero-head .toolbar');if(!toolbar)return;let wrap=id('smO2OverlayControl');
  if(!wrap){wrap=document.createElement('label');wrap.id='smO2OverlayControl';wrap.className='sm-o2-overlay-control';wrap.innerHTML='<span>O₂ overlay</span><select id="smO2OverlaySelect"><option value="off">Ki</option><option value="spo2">SpO₂</option><option value="hr">Pulzus</option><option value="both">Mindkettő</option></select>';toolbar.insertBefore(wrap,id('resetZoom'));id('smO2OverlaySelect').onchange=e=>{try{const k=state.selectedSignal;ui.overlay.set(k,e.target.value);localStorage.setItem(`sm-o2-overlay:${k}`,e.target.value)}catch{}drawHeroO2Overlay()}}
  updateOverlayControl();
}
function updateOverlayControl(){
  const wrap=id('smO2OverlayControl'),sel=id('smO2OverlaySelect');if(!wrap||!sel)return;let key='';try{key=state.selectedSignal}catch{}const ok=OVERLAY_SUPPORTED.has(key);wrap.classList.toggle('hidden',!ok);if(ok){let v=ui.overlay.get(key);if(!v){try{v=localStorage.getItem(`sm-o2-overlay:${key}`)||'off'}catch{v='off'}ui.overlay.set(key,v)}sel.value=v}}
function ensureHeroO2Canvas(){
  const host=q('#dashboardDailyView .hero-stack');if(!host)return null;let c=id('smO2HeroCanvas');if(!c){c=document.createElement('canvas');c.id='smO2HeroCanvas';c.className='canvas-overlay sm-o2-hero-overlay';c.style.pointerEvents='none';host.appendChild(c)}return c
}
function drawHeroO2Overlay(){
  const c=ensureHeroO2Canvas();if(!c)return;const {ctx,w,h}=canvasSize(c,220);ctx.clearRect(0,0,w,h);
  let key='',view=null;try{key=state.selectedSignal;view=state.view}catch{return}
  if(!OVERLAY_SUPPORTED.has(key)||!ui.daily?.available)return;const mode=ui.overlay.get(key)||'off';if(mode==='off')return;
  const rows=ui.daily.samples||[],a=view[0]/1000,b=view[1]/1000,p={l:50,r:16,t:24,b:32},iw=w-p.l-p.r,ih=h-p.t-p.b,hrs=rows.map(r=>num(r.heart_rate)).filter(v=>v!=null),hLo=hrs.length?Math.max(30,Math.floor(Math.min(...hrs)-8)):40,hHi=hrs.length?Math.min(220,Math.ceil(Math.max(...hrs)+8)):140;
  const make=(key,lo,hi)=>rows.map(r=>{const t=num(r.timestamp),v=num(r[key]);if(t==null||v==null||t<a||t>b)return null;return{x:p.l+(t-a)/(b-a)*iw,y:p.t+(hi-v)/(hi-lo)*ih}}).filter(Boolean);
  ctx.lineWidth=1.65;ctx.setLineDash([]);
  if(mode==='spo2'||mode==='both'){ctx.strokeStyle='rgba(85,216,255,.92)';line(ctx,make('spo2',75,100));ctx.fillStyle=COLORS.cyan;ctx.font='10px system-ui';ctx.fillText('SpO₂ 75–100%',w-92,14)}
  if(mode==='hr'||mode==='both'){ctx.strokeStyle='rgba(154,124,255,.92)';line(ctx,make('heart_rate',hLo,hHi));ctx.fillStyle=COLORS.violet;ctx.font='10px system-ui';ctx.fillText(`Pulzus ${hLo}–${hHi}`,w-92,mode==='both'?28:14)}
}
function hookCore(){
  if(window.__smO2CoreV532)return;window.__smO2CoreV532=true;
  try{
    if(typeof setView==='function'){const orig=setView;setView=function(a,b,reload=true){const r=orig(a,b,reload);schedule(()=>{if(ui.daily?.available){renderFocusO2(ui.daily);ensureStackO2();drawHeroO2Overlay()}});return r}}
    if(typeof selectSignal==='function'){const orig=selectSignal;selectSignal=function(key){const r=orig(key);schedule(()=>{updateOverlayControl();drawHeroO2Overlay()});return r}}
    if(typeof loadDashboard==='function'){const orig=loadDashboard;loadDashboard=async function(day){const r=await orig(day);ui.o2DailyZoom=null;await loadDailyO2(true);patchDailyTabs();ensureOverlayControl();return r}}
    if(typeof loadDashboardOverview==='function'){const orig=loadDashboardOverview;loadDashboardOverview=async function(...a){const r=await orig(...a);await refreshDashboardO2();return r}}
    if(typeof applyReportRange==='function'){const orig=applyReportRange;applyReportRange=function(...a){const r=orig(...a);schedule(hydrateReportO2);return r}}
  }catch{}
  overrideDashboardBars();
}

function overrideDashboardBars(){
  try{
    if(typeof drawUsageBars==='function')drawUsageBars=function(canvas,rows){
      if(!canvas)return;const {ctx,w,h}=setupCanvas(canvas),pr=trendRect(w,h);ctx.clearRect(0,0,w,h);ctx.fillStyle='#101722';ctx.fillRect(0,0,w,h);const max=Math.max(4,...rows.map(r=>r.usage_hours||0));ctx.strokeStyle='rgba(86,134,170,.22)';for(let i=0;i<=4;i++){const y=pr.t+pr.h*i/4;ctx.beginPath();ctx.moveTo(pr.l,y);ctx.lineTo(pr.l+pr.w,y);ctx.stroke()}const bw=pr.w/Math.max(1,rows.length);rows.forEach((r,i)=>{const v=r.usage_hours||0,x=pr.l+i*bw+bw*.16,y=pr.t+(max-v)/max*pr.h;ctx.fillStyle=v>=4?COLORS.teal:COLORS.violet;ctx.fillRect(x,y,bw*.68,pr.t+pr.h-y)});ctx.fillStyle='#899db0';ctx.font='9px Segoe UI';const step=Math.max(1,Math.ceil(rows.length/6));rows.forEach((r,i)=>{if(i%step&&i!==rows.length-1)return;const txt=trendDateLabel(r),tw=ctx.measureText(txt).width,x=trendBarX(i,rows.length,pr);ctx.fillText(txt,Math.max(pr.l,Math.min(pr.l+pr.w-tw,x-tw/2)),h-8)});canvas._trendMeta={kind:'usage',rows,xPositions:rows.map((_,i)=>trendBarX(i,rows.length,pr))};wireTrendCanvas(canvas,rows,'usage');if(state.trendHoverIndex!=null)drawTrendHoverLine(canvas,state.trendHoverIndex)
    };
    if(typeof drawEventBars==='function')drawEventBars=function(canvas,rows){
      if(!canvas)return;const {ctx,w,h}=setupCanvas(canvas),pr=trendRect(w,h),types=['OA','CA','H','RERA'];ctx.clearRect(0,0,w,h);ctx.fillStyle='#101722';ctx.fillRect(0,0,w,h);const totals=rows.map(r=>types.reduce((n,k)=>n+(r.event_index?.[k]||0),0)),max=Math.max(.1,...totals),bw=pr.w/Math.max(1,rows.length);ctx.strokeStyle='rgba(86,134,170,.22)';for(let i=0;i<=4;i++){const y=pr.t+pr.h*i/4;ctx.beginPath();ctx.moveTo(pr.l,y);ctx.lineTo(pr.l+pr.w,y);ctx.stroke()}rows.forEach((r,i)=>{let y=pr.t+pr.h;for(const k of types){const v=r.event_index?.[k]||0,hh=v/max*pr.h;if(!hh)continue;ctx.fillStyle=EVENT_COLORS[k];ctx.fillRect(pr.l+i*bw+bw*.14,y-hh,bw*.72,hh);y-=hh}});ctx.font='10px Segoe UI';drawLegend(ctx,pr,types.map(k=>({name:k,color:EVENT_COLORS[k]})));ctx.fillStyle='#899db0';const step=Math.max(1,Math.ceil(rows.length/6));rows.forEach((r,i)=>{if(i%step&&i!==rows.length-1)return;const txt=trendDateLabel(r),tw=ctx.measureText(txt).width,x=trendBarX(i,rows.length,pr);ctx.fillText(txt,Math.max(pr.l,Math.min(pr.l+pr.w-tw,x-tw/2)),h-8)});canvas._trendMeta={kind:'events',rows,xPositions:rows.map((_,i)=>trendBarX(i,rows.length,pr))};wireTrendCanvas(canvas,rows,'events');if(state.trendHoverIndex!=null)drawTrendHoverLine(canvas,state.trendHoverIndex)
    };
    if(typeof drawDashboardTrends==='function')requestAnimationFrame(drawDashboardTrends);
  }catch{}
  const tip=id('trendTooltip');if(tip&&!tip.dataset.smV532){tip.dataset.smV532='1';new MutationObserver(recolorTrendTip).observe(tip,{childList:true,subtree:true})}
}
function recolorTrendTip(){
  const tip=id('trendTooltip');if(!tip)return;for(const s of tip.querySelectorAll('span')){const t=s.textContent.trim(),dot=s.querySelector('i');if(!dot)continue;if(t.startsWith('Használat:'))dot.style.background=COLORS.teal;for(const k of Object.keys(EVENT_COLORS))if(t.startsWith(`${k}:`))dot.style.background=EVENT_COLORS[k]}
}

async function refreshDashboardO2(){
  let rows=[];try{rows=state?.dashboardOverview?.rows||[]}catch{}if(!rows.length)return;const data=await getBatch(rows.map(r=>r.day)),avail=data.filter(x=>x.available&&x.summary),s=avail.map(x=>x.summary||{});
  const agg=q('#dashboardOverviewView .aggregate-cards');if(!agg)return;let sec=id('smDashboardO2V532');
  if(!sec){sec=document.createElement('section');sec.id='smDashboardO2V532';sec.className='panel sm-dashboard-o2-v532';sec.dataset.o2ringFeature='1';sec.innerHTML='<div class="panel-head"><div><h3>Oximetriai összegzés</h3><span>Csak a CPAP-idővel ténylegesen átfedő O2Ring-adatok.</span></div><button id="smDashboardO2OpenV532" type="button">Oximetria →</button></div><div class="sm-dashboard-o2-cards"><div><span>Átlag SpO₂</span><b id="smDashO2AvgV532">–</b></div><div><span>Átlag pulzus</span><b id="smDashHrAvgV532">–</b></div><div><span>Minimum SpO₂</span><b id="smDashO2MinV532">–</b></div><div><span>Átlag T90</span><b id="smDashT90V532">–</b></div></div><div class="sm-dashboard-o2-mini"><article><header>SpO₂ trend <small>%</small></header><canvas id="smDashO2TrendV532"></canvas></article><article><header>Pulzus trend <small>bpm</small></header><canvas id="smDashHrTrendV532"></canvas></article></div><div id="smDashO2EmptyV532" class="sm-o2-empty-msg hidden">Ebben az időszakban még nincs illesztett O2Ring alvásadat.</div>';agg.insertAdjacentElement('afterend',sec);id('smDashboardO2OpenV532').onclick=()=>{location.hash='#oximetry'}}
  const av=a=>{const v=a.map(num).filter(x=>x!=null);return v.length?v.reduce((x,y)=>x+y,0)/v.length:null},mins=s.map(x=>num(x.spo2_minimum)).filter(x=>x!=null);
  id('smDashO2AvgV532').textContent=av(s.map(x=>x.spo2_average))==null?'–':`${fmt(av(s.map(x=>x.spo2_average)),1)}%`;
  id('smDashHrAvgV532').textContent=av(s.map(x=>x.heart_rate_average))==null?'–':`${fmt(av(s.map(x=>x.heart_rate_average)),1)} bpm`;
  id('smDashO2MinV532').textContent=mins.length?`${Math.min(...mins)}%`:'–';id('smDashT90V532').textContent=av(s.map(x=>x.t90_seconds))==null?'–':fmtT90(av(s.map(x=>x.t90_seconds)));
  id('smDashO2EmptyV532').classList.toggle('hidden',avail.length>0);drawSummaryMini(id('smDashO2TrendV532'),avail,r=>r.summary?.spo2_average,[75,100],COLORS.cyan);drawSummaryMini(id('smDashHrTrendV532'),avail,r=>r.summary?.heart_rate_average,null,COLORS.violet);
}
function drawSummaryMini(c,rows,get,range,color){
  if(!c)return;const {ctx,w,h}=canvasSize(c,120);ctx.clearRect(0,0,w,h);ctx.fillStyle=COLORS.bg;ctx.fillRect(0,0,w,h);const vals=rows.map(get).map(num).filter(v=>v!=null);if(!vals.length)return;let lo=range?.[0]??Math.min(...vals),hi=range?.[1]??Math.max(...vals);if(lo===hi){lo-=1;hi+=1}const p={l:30,r:8,t:10,b:20},iw=w-p.l-p.r,ih=h-p.t-p.b,pts=[];rows.forEach((r,i)=>{const v=num(get(r));if(v==null)return;pts.push({x:p.l+(rows.length===1?.5:i/(rows.length-1))*iw,y:p.t+(hi-v)/(hi-lo)*ih})});ctx.strokeStyle=color;ctx.lineWidth=2;line(ctx,pts);
}

function ensureReportColumns(){
  const table=q('.report-days-table'),head=table?.querySelector('thead tr'),body=id('reportDaysBody');if(!table||!head||!body)return false;table.classList.add('sm-report-o2-v532');
  const defs=[['spo2avg','SpO₂ átlag'],['spo2min','SpO₂ min.'],['hravg','Pulzus átlag'],['t90','T90'],['odi','ODI3 / ODI4']];
  for(const [k,l] of defs){if(head.querySelector(`[data-sm-o2-col="${k}"]`))continue;const th=document.createElement('th');th.dataset.smO2Col=k;th.textContent=l;head.appendChild(th)}
  return true;
}
async function hydrateReportO2(){
  if(!ensureReportColumns())return;const body=id('reportDaysBody'),rs=[...body.querySelectorAll('tr.report-row[data-day]')];if(!rs.length){const td=body.querySelector('td[colspan]');if(td)td.colSpan=13;return}
  for(const tr of rs)for(const k of ['spo2avg','spo2min','hravg','t90','odi'])if(!tr.querySelector(`[data-sm-o2-cell="${k}"]`)){const td=document.createElement('td');td.dataset.smO2Cell=k;td.textContent='…';tr.appendChild(td)}
  const data=await getBatch(rs.map(tr=>tr.dataset.day)),map=new Map(data.map(x=>[String(x.day),x]));
  for(const tr of rs){const x=map.get(String(tr.dataset.day)),s=x?.available?x.summary:null,put=(k,v)=>{const e=tr.querySelector(`[data-sm-o2-cell="${k}"]`);if(e)e.textContent=v};put('spo2avg',s?`${fmt(s.spo2_average,1)}%`:'–');put('spo2min',s?`${fmt(s.spo2_minimum,0)}%`:'–');put('hravg',s?fmt(s.heart_rate_average,1):'–');put('t90',s?fmtT90(s.t90_seconds):'–');put('odi',s?`${fmt(s.odi3,1)} / ${fmt(s.odi4,1)}`:'–')}
}

function patchLatestStatus(){
  const e=id('latestStatus');if(!e||e.dataset.smV532)return;e.dataset.smV532='1';
  const clean=()=>{if(e.textContent.trim()==='Befejezve')e.textContent='…'};new MutationObserver(clean).observe(e,{childList:true,characterData:true,subtree:true});clean();
}

function patchRecordingZoom(){
  const host=id('o2rRecordingDetail');if(!host||host.dataset.smV532)return;host.dataset.smV532='1';
  const enhance=()=>{const a=id('o2rRecSpo2'),b=id('o2rRecHr');if(!a&&!b)return;const cards=host.querySelector('.o2r-two-chart');if(cards&&!id('smO2RecDualCard')){const art=document.createElement('article');art.id='smO2RecDualCard';art.className='sm-o2-rec-dual';art.innerHTML='<div class="o2r-chart-head"><h4>SpO₂ + pulzus</h4></div><canvas id="smO2RecDual"></canvas><div class="sm-o2-chart-hint">Húzással nagyíthatsz • dupla kattintás: teljes felvétel</div>';cards.insertAdjacentElement('beforebegin',art)}if(ui.currentRecordingId)loadRecordingForZoom(ui.currentRecordingId)};
  const ob=new MutationObserver(()=>schedule(enhance));ob.observe(host,{childList:true,subtree:true});enhance();
}
async function loadRecordingForZoom(rid){
  if(!rid)return;try{const x=await api(`/api/o2ring/recording?id=${encodeURIComponent(rid)}&max_points=14000`),rs=x.samples||[];ui.recording=x;ui.recordingZoom=null;const redraw=()=>{const b=ui.recordingZoom||sampleBounds(rs);drawSingle(id('o2rRecSpo2'),rs,'spo2',{bounds:b,range:[75,100],color:COLORS.cyan});drawSingle(id('o2rRecHr'),rs,'heart_rate',{bounds:b,color:COLORS.violet});drawDual(id('smO2RecDual'),rs,{bounds:b})};redraw();[id('o2rRecSpo2'),id('o2rRecHr'),id('smO2RecDual')].forEach(c=>bindZoom(c,()=>rs,()=>ui.recordingZoom||sampleBounds(rs),v=>ui.recordingZoom=v,redraw));const card=id('smO2RecDualCard');if(card)addResetButton(card,()=>{ui.recordingZoom=null;redraw()})}catch{}
}

function installTrendV3(){
  const view=q('#page-oximetry [data-o2r-view="trends"]'),old=view?.querySelector('.o2r-trend-grid');if(!view||!old)return;old.classList.add('hidden');
  let box=id('smO2TrendV3');if(box)return;box=document.createElement('div');box.id='smO2TrendV3';box.innerHTML='<div class="sm-o2-trend-summary"><div><span>Átlag SpO₂</span><b id="smTrendAvgSpo2">–</b></div><div><span>Minimum SpO₂</span><b id="smTrendMinSpo2">–</b></div><div><span>Átlag pulzus</span><b id="smTrendAvgHr">–</b></div><div><span>Átlag T90</span><b id="smTrendAvgT90">–</b></div></div><div class="sm-o2-trend-grid"><article><header><b>SpO₂ trend</b><small>átlag + minimum</small></header><canvas id="smTrendSpo2"></canvas></article><article><header><b>Pulzus trend</b><small>bpm</small></header><canvas id="smTrendHr"></canvas></article><article><header><b>T90 trend</b><small>perc</small></header><canvas id="smTrendT90"></canvas></article><article><header><b>ODI3 / ODI4</b><small>esemény/óra</small></header><canvas id="smTrendOdi"></canvas></article></div><div id="smTrendEmpty" class="sm-o2-empty-msg hidden">Még nincs elég O2Ring alvásadat trend megjelenítéséhez.</div>';old.insertAdjacentElement('beforebegin',box);qa('#page-oximetry [data-o2r-limit]').forEach(b=>b.addEventListener('click',()=>setTimeout(()=>loadTrendV3(Number(b.dataset.o2rLimit)||30),0)));loadTrendV3(30);
}
async function loadTrendV3(limit=30){
  if(!id('smO2TrendV3'))return;try{const x=await api(`/api/o2ring/trends?limit=${limit}`),rows=x.rows||[],s=rows.map(r=>r.summary||{}),av=a=>{const v=a.map(num).filter(x=>x!=null);return v.length?v.reduce((p,c)=>p+c,0)/v.length:null},mins=s.map(x=>num(x.spo2_minimum)).filter(x=>x!=null);id('smTrendAvgSpo2').textContent=av(s.map(x=>x.spo2_average))==null?'–':`${fmt(av(s.map(x=>x.spo2_average)),1)}%`;id('smTrendMinSpo2').textContent=mins.length?`${Math.min(...mins)}%`:'–';id('smTrendAvgHr').textContent=av(s.map(x=>x.heart_rate_average))==null?'–':`${fmt(av(s.map(x=>x.heart_rate_average)),1)} bpm`;id('smTrendAvgT90').textContent=av(s.map(x=>x.t90_seconds))==null?'–':fmtT90(av(s.map(x=>x.t90_seconds)));id('smTrendEmpty').classList.toggle('hidden',rows.length>=2);drawTrend(id('smTrendSpo2'),rows,[{key:'spo2_average',color:COLORS.cyan},{key:'spo2_minimum',color:COLORS.violet}],[70,100]);drawTrend(id('smTrendHr'),rows,[{key:'heart_rate_average',color:COLORS.violet}],null);drawTrend(id('smTrendT90'),rows,[{key:'t90_seconds',color:COLORS.teal,div:60}],null,true);drawTrend(id('smTrendOdi'),rows,[{key:'odi3',color:COLORS.cyan},{key:'odi4',color:COLORS.rose}],null,true)}catch{}
}
function drawTrend(c,rows,series,range,zero=false){
  if(!c)return;const {ctx,w,h}=canvasSize(c,190);ctx.clearRect(0,0,w,h);ctx.fillStyle=COLORS.bg;ctx.fillRect(0,0,w,h);const values=[];rows.forEach(r=>series.forEach(s=>{let v=num(r.summary?.[s.key]);if(v!=null){if(s.div)v/=s.div;values.push(v)}}));if(!values.length)return;let lo=range?.[0]??Math.min(...values),hi=range?.[1]??Math.max(...values);if(zero)lo=0;if(lo===hi)hi=lo+1;const p={l:48,r:12,t:16,b:28},iw=w-p.l-p.r,ih=h-p.t-p.b;ctx.font='10px system-ui';for(let i=0;i<=4;i++){const y=p.t+ih*i/4;ctx.strokeStyle=COLORS.grid;ctx.beginPath();ctx.moveTo(p.l,y);ctx.lineTo(w-p.r,y);ctx.stroke();ctx.fillStyle='#7f9caf';ctx.fillText((hi-(hi-lo)*i/4).toFixed(1),4,y+3)}series.forEach(s=>{const pts=[];rows.forEach((r,i)=>{let v=num(r.summary?.[s.key]);if(v==null)return;if(s.div)v/=s.div;pts.push({x:p.l+(rows.length===1?.5:i/(rows.length-1))*iw,y:p.t+(hi-v)/(hi-lo)*ih})});ctx.strokeStyle=s.color;ctx.lineWidth=2;line(ctx,pts);for(const pt of pts){ctx.fillStyle=s.color;ctx.beginPath();ctx.arc(pt.x,pt.y,2.5,0,Math.PI*2);ctx.fill()}});ctx.fillStyle='#7f9caf';const step=Math.max(1,Math.ceil(rows.length/6));rows.forEach((r,i)=>{if(i%step&&i!==rows.length-1)return;const txt=fmtDate(r.start_ts),tw=ctx.measureText(txt).width;ctx.fillText(txt,Math.max(p.l,Math.min(w-p.r-tw,p.l+i/Math.max(1,rows.length-1)*iw-tw/2)),h-7)})
}

function mount(){
  movePwaIntoPush();moveO2Settings();compactOximetry();patchO2Nav();patchDailyTabs();patchLatestStatus();patchRecordingZoom();installTrendV3();ensureOverlayControl();
  if(ui.daily?.available){renderFocusO2(ui.daily);ensureStackO2();renderNightCard(ui.daily);drawHeroO2Overlay()}
}
function watchDom(){
  if(ui.domObserver)return;ui.domObserver=new MutationObserver(()=>schedule(mount));ui.domObserver.observe(document.body,{childList:true,subtree:true});
}
function bindGlobal(){
  document.addEventListener('change',captureO2Toggle,true);document.addEventListener('click',capturePwaLive,true);
  id('o2rLiveWindow')?.addEventListener('change',()=>{ui.liveZoom=null;drawLiveCombined()});
  id('o2rFollowLive')?.addEventListener('change',e=>{ui.liveFollow=!!e.target.checked;if(ui.liveFollow)ui.liveZoom=null;drawLiveCombined()});
  window.addEventListener('hashchange',()=>{schedule(mount);if(location.hash.startsWith('#oximetry')){setTimeout(()=>{compactOximetry();drawLiveCombined()},0)}});
  window.addEventListener('resize',()=>schedule(()=>{drawLiveCombined();if(ui.daily?.available){renderFocusO2(ui.daily);ensureStackO2();drawDailyPanelCharts();drawHeroO2Overlay()}refreshDashboardO2()}));
  document.addEventListener('sleepmate-o2-refresh',()=>{clearO2Cache();loadDailyO2(true);refreshDashboardO2();hydrateReportO2()});
}
async function boot(){
  hookCore();bindGlobal();watchDom();mount();startOwnLiveStream();refreshStatus();setTimeout(()=>loadDailyO2(true),250);setTimeout(refreshDashboardO2,450);setTimeout(hydrateReportO2,650);
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();