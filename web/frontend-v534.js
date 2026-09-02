(()=>{
'use strict';
if(window.__sleepmateFrontendV534)return;
window.__sleepmateFrontendV534=true;
const VERSION='5.3.4';
const q=s=>document.querySelector(s),qa=s=>[...document.querySelectorAll(s)],id=x=>document.getElementById(x);
const api=async(path,opts={})=>{const r=await fetch(path,{cache:'no-store',...opts,headers:{'Content-Type':'application/json',...(opts.headers||{})}});const x=await r.json().catch(()=>({}));if(!r.ok)throw new Error(x.error||`HTTP ${r.status}`);return x};
let lastO2Status=null;

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
  if(panel){panel.classList.add('sm-o2-settings-panel');const h=panel.querySelector(':scope > .panel-head h3');if(h)h.textContent='O2Ring';const sub=panel.querySelector(':scope > .panel-head span');if(sub)sub.textContent='O2Ring integráció, Bluetooth, automatikus kapcsolódás, illesztés és készülékbeállítások.'}
  installAdvancedO2Settings();
}
function normalizeSetupWizard(){
  const page=id('page-settings'),system=q('[data-settings-panel="system"]');if(!page||!system)return;
  const all=qa('.fr-settings-reopen').filter(x=>x.textContent.includes('Első beállítás varázsló'));
  let keep=id('frSettingsReopen')||all[0];if(!keep)return;
  for(const x of all)if(x!==keep)x.remove();
  keep.id='frSettingsReopen';keep.classList.add('sm-first-run-single');
  if(keep.parentNode!==system)system.appendChild(keep);
}
function normalizeLiveNav(enabled=!!lastO2Status?.settings?.o2ring_enabled){
  const V=window.SleepMateV530;if(!V?.NAV||!V?.ICONS)return;
  if(enabled){V.ICONS.oximetry_live=V.ICONS.oximetry;V.NAV.oximetry_live={label:'Élő O₂ monitor',action:'oximetry_live'}}
  else{delete V.NAV.oximetry_live;delete V.ICONS.oximetry_live}
  V.renderBottomNav?.();V.renderPwaEditor?.();
}
function normalizeAll(){normalizePwaSettings();normalizeO2Settings();normalizeSetupWizard();normalizeLiveNav()}

function installAdvancedO2Settings(){
  const panel=q('[data-settings-panel="display"]');if(!panel||id('smO2AdvancedV534')){hydrateAdvancedO2Settings();return}
  const section=document.createElement('section');section.id='smO2AdvancedV534';section.className='panel sm-o2-advanced';
  section.innerHTML=`<div class="panel-head"><div><h3>O2Ring részletes beállítások</h3><span>Időillesztés, SleepMate referenciaértékek és a csatlakoztatott gyűrű saját riasztásai.</span></div><span id="smO2AdvancedState" class="security-pill">Ellenőrzés…</span></div><div class="sm-o2-advanced-grid"><label><span>Óraeltolás</span><small>Másodpercben; csak ha a gyűrű órája eltér a CPAP órájától.</small><input id="smO2ClockOffset" type="number" min="-900" max="900" step="1"></label><label><span>SpO₂ referencia</span><small>SleepMate grafikon referencia, nem készülékriasztás.</small><input id="smO2Ref" type="number" min="70" max="100"></label><label><span>Másodlagos SpO₂ referencia</span><small>Második vizuális referenciahatár.</small><input id="smO2Ref2" type="number" min="70" max="100"></label><label class="sm-o2-check"><span>Automatikus CPAP-illesztés</span><small>Lezárt O2Ring sessionök automatikus időbeli párosítása.</small><input id="smO2AutoMatch" type="checkbox"></label></div><div class="settings-actions"><button id="smO2SaveAnalysis" type="button">Illesztési beállítások mentése</button><span id="smO2AnalysisMsg" class="muted"></span></div><details class="sm-o2-device-details"><summary>Gyűrű saját riasztási és kijelzőbeállításai</summary><p class="muted">Ezek az értékek közvetlenül a csatlakoztatott O2Ringre íródnak. Csak akkor módosítsd őket, ha ezt valóban szeretnéd.</p><div class="sm-o2-device-grid"><label class="sm-o2-check"><span>SpO₂ rezgő riasztás</span><input id="smO2DevOxiSwitch" type="checkbox"></label><label><span>SpO₂ riasztási küszöb</span><input id="smO2DevOxi" type="number" min="70" max="95"></label><label class="sm-o2-check"><span>Pulzusriasztás</span><input id="smO2DevHrSwitch" type="checkbox"></label><label><span>Pulzus alsó határ</span><input id="smO2DevHrLow" type="number" min="20" max="200"></label><label><span>Pulzus felső határ</span><input id="smO2DevHrHigh" type="number" min="20" max="200"></label><label><span>Rezgés erőssége</span><input id="smO2DevMotor" type="number" min="0" max="100"></label><label><span>Kijelzőmód</span><select id="smO2DevLighting"><option value="0">0</option><option value="1">1</option><option value="2">2</option></select></label><label><span>Fényerő</span><select id="smO2DevLight"><option value="0">0</option><option value="1">1</option><option value="2">2</option></select></label></div><div class="settings-actions"><button id="smO2WriteDevice" type="button">Készülékbeállítások alkalmazása</button><span id="smO2DeviceMsg" class="muted"></span></div></details>`;
  panel.appendChild(section);
  id('smO2SaveAnalysis').onclick=saveAdvancedO2Settings;
  id('smO2AutoMatch').onchange=saveAdvancedO2Settings;
  id('smO2WriteDevice').onclick=writeO2DeviceSettings;
  hydrateAdvancedO2Settings();
}
function setInputValue(elid,value){const el=id(elid);if(el&&document.activeElement!==el&&value!=null)el.value=String(value)}
function setChecked(elid,value){const el=id(elid);if(el&&document.activeElement!==el)el.checked=!!value}
function hydrateAdvancedO2Settings(){
  const s=lastO2Status?.settings||{},live=lastO2Status?.live||{},dc=live.device_config||{};
  setInputValue('smO2ClockOffset',s.o2ring_clock_offset_seconds??0);setInputValue('smO2Ref',s.o2ring_spo2_reference??90);setInputValue('smO2Ref2',s.o2ring_spo2_secondary_reference??88);setChecked('smO2AutoMatch',s.o2ring_auto_match);
  setChecked('smO2DevOxiSwitch',dc.CurOxiSwitch??dc.OxiSwitch);setInputValue('smO2DevOxi',dc.CurOxiThr??dc.OxiThr);setChecked('smO2DevHrSwitch',dc.CurHRSwitch??dc.HRSwitch);setInputValue('smO2DevHrLow',dc.HRLowThr);setInputValue('smO2DevHrHigh',dc.HRHighThr);setInputValue('smO2DevMotor',dc.CurMotor??dc.Motor);setInputValue('smO2DevLighting',dc.LightingMode);setInputValue('smO2DevLight',dc.LightStr);
  const badge=id('smO2AdvancedState');if(badge)badge.textContent=!s.o2ring_ble_enabled?'BLE kikapcsolva':live.connected?'Kapcsolódva':'Nincs kapcsolat';
  const write=id('smO2WriteDevice');if(write)write.disabled=!live.connected;
}
async function saveAdvancedO2Settings(){
  const msg=id('smO2AnalysisMsg');if(msg)msg.textContent='Mentés…';
  try{const settings=await api('/api/o2ring/settings',{method:'POST',body:JSON.stringify({o2ring_clock_offset_seconds:Number(id('smO2ClockOffset')?.value||0),o2ring_spo2_reference:Number(id('smO2Ref')?.value||90),o2ring_spo2_secondary_reference:Number(id('smO2Ref2')?.value||88),o2ring_auto_match:!!id('smO2AutoMatch')?.checked})});lastO2Status={...(lastO2Status||{}),settings};if(msg)msg.textContent='Illesztési beállítások mentve.';await window.SleepMateO2Ring?.refresh?.();hydrateAdvancedO2Settings()}catch(e){if(msg)msg.textContent=e.message||String(e)}}
async function writeO2DeviceSettings(){
  const msg=id('smO2DeviceMsg');if(msg)msg.textContent='Küldés a gyűrűre…';
  try{await api('/api/o2ring/device-config',{method:'POST',body:JSON.stringify({oxi_alert_enabled:!!id('smO2DevOxiSwitch')?.checked,oxi_threshold:Number(id('smO2DevOxi')?.value),hr_alert_enabled:!!id('smO2DevHrSwitch')?.checked,hr_low:Number(id('smO2DevHrLow')?.value),hr_high:Number(id('smO2DevHrHigh')?.value),motor:Number(id('smO2DevMotor')?.value),lighting_mode:Number(id('smO2DevLighting')?.value),brightness:Number(id('smO2DevLight')?.value)})});if(msg)msg.textContent='Készülékbeállítások elküldve.';setTimeout(()=>window.SleepMateO2Ring?.refreshStatus?.(),600)}catch(e){if(msg)msg.textContent=e.message||String(e)}}

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
        lastO2Status={...(lastO2Status||{}),settings};normalizeLiveNav(!!settings.o2ring_enabled);
        if(msg)msg.textContent='O2Ring beállítások mentve.';
        await window.SleepMateV530?.refreshO2?.();await window.SleepMateO2Ring?.refresh?.();
      }catch(e){if(msg)msg.textContent=e.message||String(e)}
    }
  }finally{saveBusy=false;panel?.classList.remove('sm-saving');normalizeAll()}
}
function captureO2Toggle(e){if(!['smO2Enabled','smO2Ble','smO2AutoConnect','smO2AutoSync'].includes(e.target?.id))return;e.stopImmediatePropagation();saveO2Toggles()}
function fixLatestLoading(){const e=id('latestStatus');if(e&&(e.textContent.trim()==='Befejezve'||!e.textContent.trim()))e.textContent='—'}
function hookOverviewLoading(){try{if(typeof loadDashboardOverview==='function'&&!loadDashboardOverview.__smLoading534){const orig=loadDashboardOverview;loadDashboardOverview=async function(...a){fixLatestLoading();const r=await orig(...a);return r};loadDashboardOverview.__smLoading534=true}}catch{}}
async function enforceFrontendGeneration(){
  const meta=q('meta[name="sleepmate-ui-version"]')?.content||'';let backend='';try{backend=String((await api('/api/version')).version||'')}catch{}const expected=backend||VERSION;if(expected!==VERSION)return;
  try{const keys=await caches.keys();const stale=keys.filter(k=>k.startsWith('sleepmate-')&&!k.includes(`v${VERSION}`));if(stale.length)await Promise.all(stale.map(k=>caches.delete(k)))}catch{}
  if('serviceWorker'in navigator){try{const reg=await navigator.serviceWorker.getRegistration();await reg?.update?.()}catch{}}
  if(meta&&meta!==expected&&!sessionStorage.getItem('sm-v534-reloaded')){sessionStorage.setItem('sm-v534-reloaded','1');location.reload();return}sessionStorage.removeItem('sm-v534-reloaded');
}
function waitForDynamicSettings(){normalizeAll();const page=id('page-settings');if(!page)return;if(id('smPwaSettingsPanel')&&id('smO2Master')&&id('frSettingsReopen')){normalizeAll();return}const ob=new MutationObserver(()=>{normalizeAll();if(id('smPwaSettingsPanel')&&id('smO2Master')&&id('frSettingsReopen'))ob.disconnect()});ob.observe(page,{childList:true,subtree:true});setTimeout(()=>{ob.disconnect();normalizeAll()},8000)}
function bind(){
  document.addEventListener('change',captureO2Toggle,true);window.addEventListener('hashchange',()=>{normalizeAll();fixLatestLoading()});
  window.addEventListener('sleepmate-o2-status',e=>{lastO2Status=e.detail||lastO2Status;normalizeLiveNav(!!lastO2Status?.settings?.o2ring_enabled);hydrateAdvancedO2Settings();normalizeAll()});
  window.addEventListener('sleepmate-o2-runtime-ready',normalizeAll);
  try{if(typeof setSettingsTab==='function'&&!setSettingsTab.__sm534){const orig=setSettingsTab;setSettingsTab=function(name){const r=orig(name);requestAnimationFrame(normalizeAll);return r};setSettingsTab.__sm534=true}}catch{}
}
async function refreshO2State(){try{lastO2Status=await api('/api/o2ring/status')}catch{lastO2Status=null}normalizeLiveNav(!!lastO2Status?.settings?.o2ring_enabled);hydrateAdvancedO2Settings()}
async function boot(){bind();hookOverviewLoading();fixLatestLoading();await refreshO2State();waitForDynamicSettings();normalizeAll();await enforceFrontendGeneration();setTimeout(normalizeAll,300);setTimeout(normalizeAll,1200)}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
window.SleepMateFrontendV534={normalize:normalizeAll,version:VERSION,refreshO2State};
})();
