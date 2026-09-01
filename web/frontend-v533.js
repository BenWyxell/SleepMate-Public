(()=>{
'use strict';
if(window.__sleepmateFrontendV533)return;
window.__sleepmateFrontendV533=true;

const q=(s,r=document)=>r.querySelector(s);
const qa=(s,r=document)=>[...r.querySelectorAll(s)];
const byId=id=>document.getElementById(id);
let raf=0,pwaLiveState=null,overviewRefreshRequested=false;
const schedule=fn=>{cancelAnimationFrame(raf);raf=requestAnimationFrame(()=>{raf=0;fn()})};
const modeState={active:'focus',views:{focus:null,stack:null}};

async function api(path,opts={}){
  const r=await fetch(path,{cache:'no-store',...opts,headers:{'Content-Type':'application/json',...(opts.headers||{})}});
  const x=await r.json().catch(()=>({}));
  if(!r.ok)throw new Error(x.error||`HTTP ${r.status}`);
  return x;
}

async function enforceFrontendGeneration(){
  try{
    const v=await api('/api/version'),actual=String(v.version||'');
    if(actual&&byId('sidebarVersion'))byId('sidebarVersion').textContent=`v${actual}`;
    document.documentElement.dataset.sleepmateBackendVersion=actual;
    const marker=document.querySelector('meta[name="sleepmate-ui-version"]')?.content||'';
    if(actual&&actual!==marker){
      const key=`sleepmate-ui-recovered:${actual}`;
      if(!sessionStorage.getItem(key)){
        sessionStorage.setItem(key,'1');
        try{
          if('caches' in window){
            const keys=await caches.keys();
            await Promise.all(keys.filter(k=>/^sleepmate-(?:shell|api)-/i.test(k)).map(k=>caches.delete(k)));
          }
          const reg=await navigator.serviceWorker?.getRegistration?.();await reg?.update?.();
        }catch{}
        const hash=location.hash||'#dashboard';
        location.replace(`/?ui=${encodeURIComponent(actual)}&t=${Date.now()}${hash}`);
        return false;
      }
    }
  }catch{}
  return true;
}

function normalizeSettings(){
  const tabs=q('.settings-inner-tabs'),select=byId('settingsCategorySelect');if(!tabs)return;
  const push=tabs.querySelector('[data-settings-tab="push"]'),pwa=tabs.querySelector('[data-settings-tab="pwa"]');
  if(push&&push.textContent!=='PWA')push.textContent='PWA';pwa?.remove();
  if(select){const pushOpt=[...select.options].find(o=>o.value==='push');if(pushOpt&&pushOpt.textContent!=='PWA')pushOpt.textContent='PWA';[...select.options].filter(o=>o.value==='pwa').forEach(o=>o.remove())}
  const pushPanel=q('[data-settings-panel="push"]'),pwaPanel=byId('smPwaSettingsPanel');
  if(pushPanel&&pwaPanel&&pwaPanel.parentNode!==pushPanel){pwaPanel.classList.remove('settings-tab-panel');pwaPanel.removeAttribute('data-settings-panel');pushPanel.prepend(pwaPanel)}
  const display=tabs.querySelector('[data-settings-tab="display"]');if(display&&display.textContent!=='O2Ring')display.textContent='O2Ring';
  if(select){const d=[...select.options].find(o=>o.value==='display');if(d&&d.textContent!=='O2Ring')d.textContent='O2Ring'}
  q('[data-settings-panel="display"]')?.classList.add('sm-v533-o2-settings');
}

function dedupeSetupWizard(){
  const all=qa('#frSettingsReopen,.fr-settings-reopen');if(!all.length)return;
  const keep=all[0];all.slice(1).forEach(x=>x.remove());keep.id='frSettingsReopen';
  const target=q('[data-settings-panel="system"]')||q('#page-settings');if(target&&keep.parentNode!==target)target.appendChild(keep);
  keep.classList.add('sm-v533-first-run-single');
}

function o2Enabled(){return !!byId('smO2Enabled')?.checked||!!q('#sidebar [data-page="oximetry"]')}
function normalizePwaLiveChoice(){
  const V=window.SleepMateV530;if(!V?.NAV||!V?.ICONS)return;
  const enabled=o2Enabled(),current=!!V.NAV.oximetry_live,correct=current&&V.NAV.oximetry_live.label==='Élő O₂'&&V.NAV.oximetry_live.action==='oximetry_live';
  if(enabled===pwaLiveState&&((enabled&&correct)||(!enabled&&!current)))return;
  pwaLiveState=enabled;
  if(enabled){V.ICONS.oximetry_live=V.ICONS.oximetry;V.NAV.oximetry_live={label:'Élő O₂',action:'oximetry_live'}}
  else{delete V.NAV.oximetry_live;delete V.ICONS.oximetry_live}
  V.renderPwaEditor?.();V.renderBottomNav?.();
}

function openOximetryLive(){
  if(location.hash!=='#oximetry')location.hash='#oximetry';else window.dispatchEvent(new HashChangeEvent('hashchange'));
  requestAnimationFrame(()=>{qa('[data-o2r-tab]').forEach(x=>x.classList.toggle('active',x.dataset.o2rTab==='live'));qa('[data-o2r-view]').forEach(x=>x.classList.toggle('active',x.dataset.o2rView==='live'));window.dispatchEvent(new Event('resize'))});
}
window.openSleepMateOximetryLive=openOximetryLive;

function bindOximetryNavigation(){
  if(document.documentElement.dataset.smV533O2Nav==='1')return;document.documentElement.dataset.smV533O2Nav='1';
  document.addEventListener('click',e=>{
    const live=e.target?.closest?.('[data-sm-nav-id="oximetry_live"]');if(live){e.preventDefault();e.stopImmediatePropagation();openOximetryLive();return}
    const nav=e.target?.closest?.('#sidebar [data-page="oximetry"]');if(!nav)return;e.preventDefault();e.stopImmediatePropagation();
    if(location.hash!=='#oximetry')location.hash='#oximetry';else window.dispatchEvent(new HashChangeEvent('hashchange'));
  },true);
}

function coreView(){try{return typeof state!=='undefined'&&Array.isArray(state.view)?[...state.view]:null}catch{return null}}
function fullView(){try{return typeof state!=='undefined'&&Array.isArray(state.full)?[...state.full]:null}catch{return null}}
function clearCoreDrag(){try{if(typeof state!=='undefined'){state.chartDrag=null;state.stackDrag=null;state.navDrag=null;state.navPreview=null}}catch{}}
function restoreView(mode){const v=modeState.views[mode]||fullView();if(!v)return;try{if(typeof setView==='function')setView(v[0],v[1],true)}catch{}}
function requestO2Refresh(){document.dispatchEvent(new CustomEvent('sleepmate-o2-refresh'))}
function setDailyMode(mode){
  if(modeState.active==='focus'||modeState.active==='stack'){const v=coreView();if(v)modeState.views[modeState.active]=v}
  modeState.active=mode;clearCoreDrag();
  const f=byId('focusViewBtn'),s=byId('stackViewBtn'),o=byId('o2rDailyBtn');f?.classList.toggle('active',mode==='focus');s?.classList.toggle('active',mode==='stack');o?.classList.toggle('active',mode==='o2');
  const hero=q('#dashboardDailyView .hero-panel'),focus=byId('overviewBlock'),stack=byId('stackedBlock'),ox=byId('o2rDailyPanel');
  if(mode==='o2'){
    hero?.classList.add('hidden');focus?.classList.add('hidden');stack?.classList.add('hidden');ox?.classList.remove('hidden');requestO2Refresh();
  }else{
    ox?.classList.add('hidden');hero?.classList.remove('hidden');try{if(typeof setChartMode==='function')setChartMode(mode==='stack'?'stack':'focus',false)}catch{}
    focus?.classList.toggle('hidden',mode!=='focus');stack?.classList.toggle('hidden',mode!=='stack');requestAnimationFrame(()=>restoreView(mode));
  }
  requestAnimationFrame(()=>window.dispatchEvent(new Event('resize')));
}
function bindDailyModes(){
  if(document.documentElement.dataset.smV533DailyModes==='1')return;document.documentElement.dataset.smV533DailyModes='1';
  document.addEventListener('click',e=>{const b=e.target?.closest?.('#focusViewBtn,#stackViewBtn,#o2rDailyBtn');if(!b)return;e.preventDefault();e.stopImmediatePropagation();setDailyMode(b.id==='focusViewBtn'?'focus':b.id==='stackViewBtn'?'stack':'o2')},true);
}

function fixLatestStatusFlash(){
  const el=byId('latestStatus');if(!el||el.dataset.smV533)return;el.dataset.smV533='1';
  const clean=()=>{if(el.textContent.trim()==='Befejezve')el.textContent='–'};new MutationObserver(clean).observe(el,{childList:true,characterData:true,subtree:true});clean();
}

function hookOverviewRefresh(){
  if(window.__smV533OverviewHook)return;window.__smV533OverviewHook=true;
  try{
    if(typeof loadDashboardOverview==='function'&&!loadDashboardOverview.__smV533){const orig=loadDashboardOverview;const wrapped=async function(...a){const r=await orig.apply(this,a);overviewRefreshRequested=false;requestO2Refresh();return r};wrapped.__smV533=true;loadDashboardOverview=wrapped}
    if(typeof loadDashboard==='function'&&!loadDashboard.__smV533){const orig=loadDashboard;const wrapped=async function(...a){const r=await orig.apply(this,a);requestO2Refresh();return r};wrapped.__smV533=true;loadDashboard=wrapped}
  }catch{}
}

function normalizeO2Hero(){
  const hero=q('#page-oximetry .o2r-hero');if(!hero)return;hero.classList.add('sm-v533-o2-hero');
  const connected=/Kapcsolódva|Mér|Élő mérés|csatlakoztatva/i.test(byId('o2rStatus')?.textContent||'');byId('o2rConnectNow')?.classList.toggle('hidden',connected);
}

function mount(){
  normalizeSettings();dedupeSetupWizard();normalizePwaLiveChoice();fixLatestStatusFlash();normalizeO2Hero();
  if(o2Enabled()&&byId('dashboardOverviewView')&&!byId('smDashboardO2V532')&&!overviewRefreshRequested){overviewRefreshRequested=true;requestO2Refresh()}
}
function watchDom(){if(window.__smV533Observer)return;window.__smV533Observer=true;const obs=new MutationObserver(()=>schedule(mount));obs.observe(document.body,{childList:true,subtree:true})}

async function boot(){
  const ok=await enforceFrontendGeneration();if(!ok)return;bindOximetryNavigation();bindDailyModes();hookOverviewRefresh();watchDom();mount();
  setTimeout(()=>{hookOverviewRefresh();requestO2Refresh();mount()},250);setTimeout(()=>{requestO2Refresh();mount()},900);
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();