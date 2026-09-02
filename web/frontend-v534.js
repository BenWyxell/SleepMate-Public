(()=>{
'use strict';
if(window.__sleepmateFrontendV534)return;
window.__sleepmateFrontendV534=true;
const VERSION='5.3.4';
const q=s=>document.querySelector(s),qa=s=>[...document.querySelectorAll(s)],id=x=>document.getElementById(x);
const api=async(path,opts={})=>{const r=await fetch(path,{cache:'no-store',...opts,headers:{'Content-Type':'application/json',...(opts.headers||{})}});const x=await r.json().catch(()=>({}));if(!r.ok)throw new Error(x.error||`HTTP ${r.status}`);return x};

function normalizePwaSettings(){
  const tabs=q('.settings-inner-tabs'),sel=id('settingsCategorySelect'),push=tabs?.querySelector('[data-settings-tab="push"]'),pwa=tabs?.querySelector('[data-settings-tab="pwa"]'),pushPanel=q('[data-settings-panel="push"]'),pwaPanel=id('smPwaSettingsPanel');
  if(push)push.textContent='PWA';
  pwa?.remove();
  if(sel){const keep=[...sel.options].find(o=>o.value==='push');if(keep)keep.textContent='PWA';for(const o of [...sel.options].filter(o=>o.value==='pwa'))o.remove()}
  if(pushPanel&&pwaPanel&&!pushPanel.contains(pwaPanel)){
    pwaPanel.classList.remove('settings-tab-panel','panel');pwaPanel.removeAttribute('data-settings-panel');pushPanel.prepend(pwaPanel);
  }
}
function normalizeO2Settings(){
  const tab=q('[data-settings-tab="display"]'),panel=q('[data-settings-panel="display"]'),sel=id('settingsCategorySelect');
  if(tab)tab.textContent='O2Ring';
  if(sel){const o=[...sel.options].find(x=>x.value==='display');if(o)o.textContent='O2Ring'}
  if(panel){panel.classList.add('sm-o2-settings-panel');const h=panel.querySelector(':scope > .panel-head h3');if(h)h.textContent='O2Ring'}
}
function normalizeSetupWizard(){
  const page=id('page-settings'),system=q('[data-settings-panel="system"]');if(!page||!system)return;
  const all=qa('.fr-settings-reopen').filter(x=>x.textContent.includes('Első beállítás varázsló'));
  let keep=id('frSettingsReopen')||all[0];if(!keep)return;
  for(const x of all)if(x!==keep)x.remove();
  keep.id='frSettingsReopen';keep.classList.add('sm-first-run-single');
  if(keep.parentNode!==system)system.appendChild(keep);
}
function normalizeLiveNav(){
  const V=window.SleepMateV530;if(!V?.NAV||!V?.ICONS)return;
  V.ICONS.oximetry_live=V.ICONS.oximetry;
  V.NAV.oximetry_live={label:'Élő O₂ monitor',action:'oximetry_live'};
  V.renderBottomNav?.();V.renderPwaEditor?.();
}
function normalizeAll(){normalizePwaSettings();normalizeO2Settings();normalizeSetupWizard();normalizeLiveNav()}

let saveBusy=false,saveQueued=false;
async function saveO2Toggles(){
  saveQueued=true;if(saveBusy)return;saveBusy=true;
  const panel=q('[data-settings-panel="display"]');
  try{
    while(saveQueued){
      saveQueued=false;
      const payload={o2ring_enabled:!!id('smO2Enabled')?.checked,o2ring_ble_enabled:!!id('smO2Ble')?.checked,o2ring_auto_connect:!!id('smO2AutoConnect')?.checked,o2ring_auto_sync:!!id('smO2AutoSync')?.checked};
      panel?.classList.add('sm-saving');const msg=id('smO2MasterMsg');if(msg)msg.textContent='Mentés…';
      try{
        const settings=await api('/api/o2ring/settings',{method:'POST',body:JSON.stringify(payload)});
        for(const[k,elid]of [['o2ring_enabled','smO2Enabled'],['o2ring_ble_enabled','smO2Ble'],['o2ring_auto_connect','smO2AutoConnect'],['o2ring_auto_sync','smO2AutoSync']])if(id(elid))id(elid).checked=!!settings[k];
        if(msg)msg.textContent='O2Ring beállítások mentve.';
        await window.SleepMateV530?.refreshO2?.();
        await window.SleepMateO2Ring?.refresh?.();
      }catch(e){if(msg)msg.textContent=e.message||String(e)}
    }
  }finally{saveBusy=false;panel?.classList.remove('sm-saving');normalizeAll()}
}
function captureO2Toggle(e){if(!['smO2Enabled','smO2Ble','smO2AutoConnect','smO2AutoSync'].includes(e.target?.id))return;e.stopImmediatePropagation();saveO2Toggles()}

function fixLatestLoading(){const e=id('latestStatus');if(e&&(e.textContent.trim()==='Befejezve'||!e.textContent.trim()))e.textContent='—'}
function hookOverviewLoading(){try{if(typeof loadDashboardOverview==='function'&&!loadDashboardOverview.__smLoading534){const orig=loadDashboardOverview;loadDashboardOverview=async function(...a){fixLatestLoading();const r=await orig(...a);return r};loadDashboardOverview.__smLoading534=true}}catch{}}

async function enforceFrontendGeneration(){
  const meta=q('meta[name="sleepmate-ui-version"]')?.content||'';let backend='';try{backend=String((await api('/api/version')).version||'')}catch{}
  const expected=backend||VERSION;if(expected!==VERSION)return;
  try{
    const keys=await caches.keys();const stale=keys.filter(k=>k.startsWith('sleepmate-')&&!k.includes(`v${VERSION}`));if(stale.length)await Promise.all(stale.map(k=>caches.delete(k)));
  }catch{}
  if('serviceWorker'in navigator){try{const reg=await navigator.serviceWorker.getRegistration();await reg?.update?.()}catch{}}
  if(meta&&meta!==expected&&!sessionStorage.getItem('sm-v534-reloaded')){sessionStorage.setItem('sm-v534-reloaded','1');location.reload();return}
  sessionStorage.removeItem('sm-v534-reloaded');
}

function waitForDynamicSettings(){
  normalizeAll();
  const page=id('page-settings');if(!page)return;
  if(id('smPwaSettingsPanel')&&id('smO2Master')&&id('frSettingsReopen')){normalizeAll();return}
  const ob=new MutationObserver(()=>{normalizeAll();if(id('smPwaSettingsPanel')&&id('smO2Master')&&id('frSettingsReopen'))ob.disconnect()});ob.observe(page,{childList:true,subtree:true});setTimeout(()=>{ob.disconnect();normalizeAll()},8000);
}
function bind(){
  document.addEventListener('change',captureO2Toggle,true);
  window.addEventListener('hashchange',()=>{normalizeAll();fixLatestLoading()});
  window.addEventListener('sleepmate-o2-status',normalizeAll);
  window.addEventListener('sleepmate-o2-runtime-ready',normalizeAll);
  try{if(typeof setSettingsTab==='function'&&!setSettingsTab.__sm534){const orig=setSettingsTab;setSettingsTab=function(name){const r=orig(name);requestAnimationFrame(normalizeAll);return r};setSettingsTab.__sm534=true}}catch{}
}
async function boot(){bind();hookOverviewLoading();fixLatestLoading();waitForDynamicSettings();normalizeAll();await enforceFrontendGeneration();setTimeout(normalizeAll,300);setTimeout(normalizeAll,1200)}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
window.SleepMateFrontendV534={normalize:normalizeAll,version:VERSION};
})();
