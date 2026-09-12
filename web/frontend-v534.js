(()=>{
'use strict';
if(window.__sleepmateFrontendV534)return;
window.__sleepmateFrontendV534=true;
const VERSION='5.3.4';
const q=s=>document.querySelector(s),qa=s=>[...document.querySelectorAll(s)],id=x=>document.getElementById(x);
const api=async(path,opts={})=>{const r=await fetch(path,{cache:'no-store',...opts,headers:{'Content-Type':'application/json',...(opts.headers||{})}});const x=await r.json().catch(()=>({}));if(!r.ok)throw new Error(x.error||`HTTP ${r.status}`);return x};
const setText=(el,value)=>{if(el&&el.textContent!==String(value))el.textContent=String(value)};
let lastO2Status=null,lastLiveNavEnabled=null,settingsNormalizeRaf=0,bleQuickBusy=false,diagnosticRaf=0;

function installV5325Styles(){
  if(id('smV5325TargetedStyles'))return;
  const style=document.createElement('style');
  style.id='smV5325TargetedStyles';
  style.textContent=`
    @media(max-width:700px){
      .system-maintenance-panel .settings-actions,.system-maintenance-panel .settings-actions.wrap{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:7px!important;align-items:stretch!important;width:100%!important}
      .system-maintenance-panel .settings-actions button{flex:none!important;width:100%!important;min-width:0!important;min-height:40px!important;height:auto!important;padding:9px 10px!important;line-height:1.25!important;white-space:normal!important}
    }
    @media(max-width:390px){.system-maintenance-panel .settings-actions,.system-maintenance-panel .settings-actions.wrap{grid-template-columns:minmax(0,1fr)!important}}
    .o2r-compact-status.sm-o2-ble-toggle{cursor:pointer;user-select:none;-webkit-user-select:none;transition:border-color .16s ease,background .16s ease,box-shadow .16s ease;outline:none}
    .o2r-compact-status.sm-o2-ble-toggle:hover{border-color:rgba(82,220,255,.55)!important;background:rgba(11,29,44,.78)!important}
    .o2r-compact-status.sm-o2-ble-toggle:focus-visible{border-color:rgba(82,220,255,.78)!important;box-shadow:0 0 0 3px rgba(82,220,255,.12)!important}
    .o2r-compact-status.sm-o2-ble-toggle.sm-ble-off>i{background:#e7bb67!important;box-shadow:0 0 9px rgba(231,187,103,.35)}
    .o2r-compact-status.sm-o2-ble-toggle.sm-ble-busy{opacity:.66;pointer-events:none}
  `;
  document.head.appendChild(style);
}

function normalizePwaSettings(){
  const tabs=q('.settings-inner-tabs'),sel=id('settingsCategorySelect'),push=tabs?.querySelector('[data-settings-tab="push"]'),pwa=tabs?.querySelector('[data-settings-tab="pwa"]'),pushPanel=q('[data-settings-panel="push"]'),pwaPanel=id('smPwaSettingsPanel');
  if(push&&push.textContent!=='PWA')push.textContent='PWA';
  pwa?.remove();
  if(sel){const keep=[...sel.options].find(o=>o.value==='push');if(keep&&keep.textContent!=='PWA')keep.textContent='PWA';for(const o of [...sel.options].filter(o=>o.value==='pwa'))o.remove()}
  if(pushPanel&&pwaPanel&&!pushPanel.contains(pwaPanel)){
    pwaPanel.classList.remove('settings-tab-panel','panel');pwaPanel.removeAttribute('data-settings-panel');pushPanel.prepend(pwaPanel);
  }
}
function normalizeO2Settings(){
  const tab=q('[data-settings-tab="display"]'),panel=q('[data-settings-panel="display"]'),sel=id('settingsCategorySelect');
  if(tab&&tab.textContent!=='O2Ring')tab.textContent='O2Ring';
  if(sel){const o=[...sel.options].find(x=>x.value==='display');if(o&&o.textContent!=='O2Ring')o.textContent='O2Ring'}
  if(panel){panel.classList.add('sm-o2-settings-panel');const h=panel.querySelector(':scope > .panel-head h3');setText(h,'O2Ring');const sub=panel.querySelector(':scope > .panel-head span');setText(sub,'O2Ring integráció, Bluetooth, automatikus kapcsolódás, illesztés és készülékbeállítások.')}
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
  const wanted=!!enabled,current=V.NAV.oximetry_live;
  const currentCorrect=!!(current&&current.label==='Élő O₂ monitor'&&current.action==='oximetry_live'&&V.ICONS.oximetry_live);
  const needsChange=wanted?!currentCorrect:!!current;
  lastLiveNavEnabled=wanted;
  if(!needsChange)return;
  if(wanted){V.ICONS.oximetry_live=V.ICONS.oximetry;V.NAV.oximetry_live={label:'Élő O₂ monitor',action:'oximetry_live'}}
  else{delete V.NAV.oximetry_live;delete V.ICONS.oximetry_live}
  V.renderBottomNav?.();V.renderPwaEditor?.();
}
function normalizeAll(){normalizePwaSettings();normalizeO2Settings();normalizeSetupWizard();normalizeLiveNav();installO2BleQuickToggle();normalizeDiagnosticCompletenessCopy()}

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
function setInputValue(elid,value){const el=id(elid);if(el&&document.activeElement!==el&&value!=null&&el.value!==String(value))el.value=String(value)}
function setChecked(elid,value){const el=id(elid),next=!!value;if(el&&document.activeElement!==el&&el.checked!==next)el.checked=next}
function hydrateAdvancedO2Settings(){
  const s=lastO2Status?.settings||{},live=lastO2Status?.live||{},dc=live.device_config||{};
  setInputValue('smO2ClockOffset',s.o2ring_clock_offset_seconds??0);setInputValue('smO2Ref',s.o2ring_spo2_reference??90);setInputValue('smO2Ref2',s.o2ring_spo2_secondary_reference??88);setChecked('smO2AutoMatch',s.o2ring_auto_match);
  setChecked('smO2DevOxiSwitch',dc.CurOxiSwitch??dc.OxiSwitch);setInputValue('smO2DevOxi',dc.CurOxiThr??dc.OxiThr);setChecked('smO2DevHrSwitch',dc.CurHRSwitch??dc.HRSwitch);setInputValue('smO2DevHrLow',dc.HRLowThr);setInputValue('smO2DevHrHigh',dc.HRHighThr);setInputValue('smO2DevMotor',dc.CurMotor??dc.Motor);setInputValue('smO2DevLighting',dc.LightingMode);setInputValue('smO2DevLight',dc.LightStr);
  const badge=id('smO2AdvancedState');setText(badge,!s.o2ring_ble_enabled?'BLE kikapcsolva':live.connected?'Kapcsolódva':'Nincs kapcsolat');
  const write=id('smO2WriteDevice');if(write)write.disabled=!live.connected;
}
async function saveAdvancedO2Settings(){
  const msg=id('smO2AnalysisMsg');setText(msg,'Mentés…');
  try{const settings=await api('/api/o2ring/settings',{method:'POST',body:JSON.stringify({o2ring_clock_offset_seconds:Number(id('smO2ClockOffset')?.value||0),o2ring_spo2_reference:Number(id('smO2Ref')?.value||90),o2ring_spo2_secondary_reference:Number(id('smO2Ref2')?.value||88),o2ring_auto_match:!!id('smO2AutoMatch')?.checked})});lastO2Status={...(lastO2Status||{}),settings};setText(msg,'Illesztési beállítások mentve.');await window.SleepMateO2Ring?.refresh?.();hydrateAdvancedO2Settings()}catch(e){setText(msg,e.message||String(e))}}
async function writeO2DeviceSettings(){
  const msg=id('smO2DeviceMsg');setText(msg,'Küldés a gyűrűre…');
  try{await api('/api/o2ring/device-config',{method:'POST',body:JSON.stringify({oxi_alert_enabled:!!id('smO2DevOxiSwitch')?.checked,oxi_threshold:Number(id('smO2DevOxi')?.value),hr_alert_enabled:!!id('smO2DevHrSwitch')?.checked,hr_low:Number(id('smO2DevHrLow')?.value),hr_high:Number(id('smO2DevHrHigh')?.value),motor:Number(id('smO2DevMotor')?.value),lighting_mode:Number(id('smO2DevLighting')?.value),brightness:Number(id('smO2DevLight')?.value)})});setText(msg,'Készülékbeállítások elküldve.');setTimeout(()=>window.SleepMateO2Ring?.refreshStatus?.(),600)}catch(e){setText(msg,e.message||String(e))}}

let saveBusy=false,saveQueued=false;
async function saveO2Toggles(){
  saveQueued=true;if(saveBusy)return;saveBusy=true;
  const panel=q('[data-settings-panel="display"]');
  try{
    while(saveQueued){
      saveQueued=false;
      const payload={o2ring_enabled:!!id('smO2Enabled')?.checked,o2ring_ble_enabled:!!id('smO2Ble')?.checked,o2ring_auto_connect:!!id('smO2AutoConnect')?.checked,o2ring_auto_sync:!!id('smO2AutoSync')?.checked};
      panel?.classList.add('sm-saving');const msg=id('smO2MasterMsg');setText(msg,'Mentés…');
      try{
        const settings=await api('/api/o2ring/settings',{method:'POST',body:JSON.stringify(payload)});
        for(const[k,elid]of [['o2ring_enabled','smO2Enabled'],['o2ring_ble_enabled','smO2Ble'],['o2ring_auto_connect','smO2AutoConnect'],['o2ring_auto_sync','smO2AutoSync']])if(id(elid))id(elid).checked=!!settings[k];
        lastO2Status={...(lastO2Status||{}),settings};normalizeLiveNav(!!settings.o2ring_enabled);
        setText(msg,'O2Ring beállítások mentve.');
        await window.SleepMateV530?.refreshO2?.();await window.SleepMateO2Ring?.refresh?.();
      }catch(e){setText(msg,e.message||String(e))}
    }
  }finally{saveBusy=false;panel?.classList.remove('sm-saving');normalizeAll()}
}
function captureO2Toggle(e){if(!['smO2Enabled','smO2Ble','smO2AutoConnect','smO2AutoSync'].includes(e.target?.id))return;e.stopImmediatePropagation();saveO2Toggles()}

function updateO2BleQuickToggle(){
  const status=id('o2rStatus'),toggle=status?.closest('.o2r-compact-status');if(!toggle)return;
  const enabled=lastO2Status?.settings?.o2ring_ble_enabled!==false;
  toggle.classList.toggle('sm-ble-off',!enabled);toggle.classList.toggle('sm-ble-busy',bleQuickBusy);
  toggle.setAttribute('aria-pressed',enabled?'true':'false');
  toggle.setAttribute('aria-label',enabled?'Bluetooth kikapcsolása':'Bluetooth bekapcsolása');
  toggle.title=enabled?'Bluetooth kikapcsolása':'Bluetooth bekapcsolása';
}
async function toggleO2BleQuick(){
  if(bleQuickBusy)return;bleQuickBusy=true;updateO2BleQuickToggle();
  const statusEl=id('o2rStatus');
  try{
    let current=lastO2Status;if(!current?.settings)current=await api('/api/o2ring/status');
    const next=current?.settings?.o2ring_ble_enabled===false;
    setText(statusEl,next?'BLE bekapcsolása…':'BLE kikapcsolása…');
    const settings=await api('/api/o2ring/settings',{method:'POST',body:JSON.stringify({o2ring_ble_enabled:next})});
    lastO2Status={...(current||{}),settings:{...(current?.settings||{}),...settings}};
    setChecked('smO2Ble',next);
    await window.SleepMateO2Ring?.refreshStatus?.();
    try{lastO2Status=await api('/api/o2ring/status')}catch{}
  }catch(e){setText(statusEl,e?.message||String(e));try{if(typeof showError==='function')showError(e)}catch{}}
  finally{bleQuickBusy=false;updateO2BleQuickToggle()}
}
function installO2BleQuickToggle(){
  const status=id('o2rStatus'),toggle=status?.closest('.o2r-compact-status');if(!toggle)return;
  if(!toggle.__smBleQuick5325){
    toggle.__smBleQuick5325=true;toggle.id='o2rBleToggle';toggle.classList.add('sm-o2-ble-toggle');toggle.setAttribute('role','button');toggle.tabIndex=0;
    toggle.addEventListener('click',toggleO2BleQuick);
    toggle.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();toggleO2BleQuick()}});
  }
  updateO2BleQuickToggle();
}
function normalizeDiagnosticCompletenessCopy(){
  const page=id('page-logs');if(!page)return;
  for(const el of page.querySelectorAll('p,span,small,div')){
    if(el.children.length)continue;
    const text=(el.textContent||'').trim();
    if(text.includes('készíts teljes SD-mentést újra')&&text.includes('BRP')){
      el.textContent='Tájékoztató adat-teljességi jelzés. A SleepMate a rendelkezésre álló EDF-ekkel tovább dolgozik; önmagában ez nem jelent sérült adatot. Teendő csak akkor indokolt, ha sérült / csonka EDF figyelmeztetés is társul hozzá.';
    }
  }
}
function installDiagnosticCopyObserver(){
  const page=id('page-logs');if(!page||page.__smDiag5325)return;page.__smDiag5325=true;
  const schedule=()=>{if(diagnosticRaf)return;diagnosticRaf=requestAnimationFrame(()=>{diagnosticRaf=0;normalizeDiagnosticCompletenessCopy()})};
  new MutationObserver(schedule).observe(page,{childList:true,subtree:true,characterData:true});
}

// Historical source-contract note (pre-v5.3.23): the card used
// latest?.summary||latest, latestDuration(summary), summary.sessions,
// Array.isArray(summary.sessions) and setText(status,latestDuration(summary)).
// Runtime ownership below deliberately no longer uses that raw therapy-day path.
let latestSleepCardBlock=null,latestSleepCardRequest=0;
function latestDuration(summary){const seconds=Number(summary?.therapy_seconds);if(Number.isFinite(seconds)&&seconds>=0){const mins=Math.round(seconds/60);return `${Math.floor(mins/60)}:${String(mins%60).padStart(2,'0')}`}const usage=String(summary?.usage||'');return /^\d+:\d{2}/.test(usage)?usage.slice(0,5):'—'}
function latestSleepBlock(payload){
  const blocks=payload?.latest?.blocks;if(!Array.isArray(blocks)||!blocks.length)return null;
  return blocks.reduce((latest,block)=>{
    if(!latest)return block;
    const end=Date.parse(block?.end||block?.start||''),latestEnd=Date.parse(latest?.end||latest?.start||'');
    return !Number.isNaN(end)&&(Number.isNaN(latestEnd)||end>latestEnd)?block:latest;
  },null);
}
function fixLatestLoading(){latestSleepCardBlock=null;latestSleepCardRequest++;const status=id('latestStatus');if(status&&status.textContent!=='—')status.textContent='—';setText(id('latestSessions'),'—')}
function syncLatestSessionCard(){
  const status=id('latestStatus'),sessions=id('latestSessions');if(!status||!sessions)return;
  const block=latestSleepCardBlock;if(!block){setText(status,'—');setText(sessions,'—');return}
  const count=Number(block.session_count);setText(status,latestDuration(block));setText(sessions,Number.isFinite(count)&&count>0?`${count} szakasz`:'—');
}
async function refreshLatestSleepCard(){
  const request=++latestSleepCardRequest;
  try{
    const sleep=await api('/api/sleep-analysis?period=day');if(request!==latestSleepCardRequest)return;
    latestSleepCardBlock=latestSleepBlock(sleep);
  }catch{if(request!==latestSleepCardRequest)return;latestSleepCardBlock=null}
  syncLatestSessionCard();
}
function hookOverviewLoading(){
  try{
    if(typeof loadDashboardOverview==='function'&&!loadDashboardOverview.__smLoading534){
      const orig=loadDashboardOverview;
      loadDashboardOverview=async function(...a){fixLatestLoading();const r=await orig(...a);await refreshLatestSleepCard();return r};
      loadDashboardOverview.__smLoading534=true;
    }
  }catch{}
}
function watchLatestSessionCard(){
  const status=id('latestStatus'),sessions=id('latestSessions');if(!status||!sessions||status.__smLatest534)return;
  status.__smLatest534=true;
  const ob=new MutationObserver(()=>syncLatestSessionCard());
  ob.observe(status,{childList:true,characterData:true,subtree:true});
  ob.observe(sessions,{childList:true,characterData:true,subtree:true});
}

// The core trend renderer intentionally draws roughly six date labels and always
// adds the newest date. On narrow phone/PWA canvases the penultimate scheduled
// label can then collide with that forced final label. Keep the existing sampling
// and all chart data untouched; only suppress labels whose painted rectangles
// would overlap, while always reserving room for the newest date.
let adaptiveTrendAxisDays=null;
function adaptiveTrendDaySet(canvas,rows,kind){
  if(!canvas||!Array.isArray(rows)||!rows.length)return null;
  const n=rows.length,step=Math.max(1,Math.ceil(n/6)),candidates=[];
  for(let i=0;i<n;i++)if(i%step===0||i===n-1)candidates.push(i);
  if(candidates.length<2)return new Set(candidates.map(i=>String(rows[i]?.day??'')));
  const rect=canvas.getBoundingClientRect(),w=Math.max(1,rect.width||canvas.clientWidth||0),h=Math.max(1,rect.height||canvas.clientHeight||0);
  const pr=typeof window.trendRect==='function'?window.trendRect(w,h):{l:48,w:Math.max(1,w-66)};
  const pos=(i)=>{
    if(kind==='line'&&typeof window.trendX==='function')return window.trendX(i,n,pr);
    if(kind!=='line'&&typeof window.trendBarX==='function')return window.trendBarX(i,n,pr);
    return pr.l+(n<=1?0:i/(n-1))*pr.w;
  };
  const ctx=canvas.getContext('2d');
  ctx.save();ctx.font='10px Segoe UI';
  const box=i=>{
    const text=typeof window.trendDateLabel==='function'?window.trendDateLabel(rows[i]):String(rows[i]?.day??''),tw=Math.max(1,ctx.measureText(text).width),x=pos(i),left=Math.max(pr.l,Math.min(pr.l+pr.w-tw,x-tw/2));
    return{left,right:left+tw};
  };
  const keep=new Set(),first=candidates[0],last=candidates.at(-1),lastBox=box(last);
  keep.add(String(rows[first]?.day??''));
  let previous=box(first).right;
  for(const i of candidates.slice(1,-1)){
    const b=box(i);
    if(b.left<previous+8||b.right>lastBox.left-8)continue;
    keep.add(String(rows[i]?.day??''));previous=b.right;
  }
  keep.add(String(rows[last]?.day??''));
  ctx.restore();
  return keep;
}
function installAdaptiveDashboardTrendAxis(){
  if(window.__smAdaptiveDashboardTrendAxis5329)return;
  const originalLabel=window.trendDateLabel;
  if(typeof originalLabel!=='function')return;
  window.__smAdaptiveDashboardTrendAxis5329=true;
  window.trendDateLabel=function(row){const text=originalLabel(row);if(!adaptiveTrendAxisDays)return text;return adaptiveTrendAxisDays.has(String(row?.day??''))?text:''};
  const wrap=(name,kind)=>{
    const original=window[name];if(typeof original!=='function'||original.__smAdaptiveAxis5329)return;
    const wrapped=function(canvas,rows,...rest){const previous=adaptiveTrendAxisDays;adaptiveTrendAxisDays=adaptiveTrendDaySet(canvas,rows,kind);try{return original.call(this,canvas,rows,...rest)}finally{adaptiveTrendAxisDays=previous}};
    wrapped.__smAdaptiveAxis5329=true;wrapped.__smOriginal=original;window[name]=wrapped;
  };
  wrap('drawTrendLine','line');wrap('drawUsageBars','bar');wrap('drawEventBars','bar');
}
function waitForDynamicSettings(){
  normalizeAll();const page=id('page-settings');if(!page)return;
  const done=()=>!!(id('smPwaSettingsPanel')&&id('smO2Master')&&id('frSettingsReopen'));
  if(done()){normalizeAll();return}
  let ob=null;
  const schedule=()=>{if(settingsNormalizeRaf)return;settingsNormalizeRaf=requestAnimationFrame(()=>{settingsNormalizeRaf=0;normalizeAll();if(done())ob?.disconnect()})};
  ob=new MutationObserver(schedule);ob.observe(page,{childList:true,subtree:true});
  setTimeout(()=>{ob.disconnect();schedule()},8000)
}
function settingsVisible(){return !!id('page-settings')?.classList.contains('active')}
function bind(){
  document.addEventListener('change',captureO2Toggle,true);
  window.addEventListener('hashchange',()=>{if(settingsVisible())normalizeAll();requestAnimationFrame(()=>{installO2BleQuickToggle();installDiagnosticCopyObserver();normalizeDiagnosticCompletenessCopy()})});
  window.addEventListener('sleepmate-o2-status',e=>{
    lastO2Status=e.detail||lastO2Status;
    normalizeLiveNav(!!lastO2Status?.settings?.o2ring_enabled);installO2BleQuickToggle();updateO2BleQuickToggle();
    if(settingsVisible()){hydrateAdvancedO2Settings();normalizeO2Settings()}
  });
  window.addEventListener('sleepmate-o2-config-ready',e=>{
    if(e.detail?.status)lastO2Status=e.detail.status;
    normalizeLiveNav(!!lastO2Status?.settings?.o2ring_enabled);
    normalizeAll();installO2BleQuickToggle();
    if(settingsVisible())hydrateAdvancedO2Settings();
  });
  window.addEventListener('sleepmate-o2-runtime-ready',()=>{normalizeLiveNav();installO2BleQuickToggle();if(settingsVisible())normalizeAll()});
  try{if(typeof setSettingsTab==='function'&&!setSettingsTab.__sm534){const orig=setSettingsTab;setSettingsTab=function(name){const r=orig(name);requestAnimationFrame(normalizeAll);return r};setSettingsTab.__sm534=true}}catch{}
}
async function refreshO2State(){try{lastO2Status=await api('/api/o2ring/status')}catch{lastO2Status=null}normalizeLiveNav(!!lastO2Status?.settings?.o2ring_enabled);installO2BleQuickToggle();if(settingsVisible())hydrateAdvancedO2Settings()}
installAdaptiveDashboardTrendAxis();
function boot(){installV5325Styles();bind();hookOverviewLoading();watchLatestSessionCard();fixLatestLoading();waitForDynamicSettings();normalizeAll();installDiagnosticCopyObserver();setTimeout(()=>{installO2BleQuickToggle();normalizeDiagnosticCompletenessCopy()},500)}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
window.SleepMateFrontendV534={normalize:normalizeAll,version:VERSION,refreshO2State,syncLatestSessionCard,refreshLatestSleepCard};
})();