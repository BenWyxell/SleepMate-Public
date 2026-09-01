(()=>{
  'use strict';
  const VERSION='5.3.0';
  const api=async(path,opts={})=>{const r=await fetch(path,{cache:'no-store',...opts,headers:{'Content-Type':'application/json',...(opts.headers||{})}});const x=await r.json().catch(()=>({}));if(!r.ok)throw new Error(x.error||`HTTP ${r.status}`);return x};
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const svg=body=>`<svg viewBox="0 0 24 24" aria-hidden="true">${body}</svg>`;
  const ICONS={
    dashboard:svg('<path d="M4 11.5 12 4l8 7.5V20H4Z"/><path d="M9 20v-6h6v6"/><path d="M6.5 10.5c2.2-1.7 3.9-2.4 5.5-2.4s3.3.7 5.5 2.4"/>'),
    patient:svg('<circle cx="12" cy="8" r="3.5"/><path d="M5 21c.7-5 3.2-7.2 7-7.2s6.3 2.2 7 7.2"/><path d="M18 4.5v5M15.5 7h5"/>'),
    sessions:svg('<path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11Z"/><path d="M8 17.5h8"/>'),
    events:svg('<path d="M3 12h4l2-5 4 10 2-5h6"/><path d="M4 4v16M20 4v16"/>'),
    reports:svg('<path d="M6 3h8l4 4v14H6Z"/><path d="M14 3v5h5M9 12h6M9 16h6"/><path d="M9 8h2"/>'),
    ai:svg('<path d="M4 6a3 3 0 0 1 3-3h10a3 3 0 0 1 3 3v7a3 3 0 0 1-3 3h-5l-5 4v-4a3 3 0 0 1-3-3Z"/><path d="M8.5 9h.01M15.5 9h.01M9 12.2c1.8 1.3 4.2 1.3 6 0"/><path d="m18.5 2 .45 1.3 1.3.45-1.3.45-.45 1.3-.45-1.3-1.3-.45 1.3-.45Z"/>'),
    equipment:svg('<path d="M5 8c2-2 4-3 7-3s5 1 7 3v7c-2 2-4 3-7 3s-5-1-7-3Z"/><path d="M8 9v4M16 9v4M9 18v3M15 18v3"/>'),
    upload:svg('<path d="M7 18h10a4 4 0 0 0 .4-8A6 6 0 0 0 6 8.5 4.5 4.5 0 0 0 7 18Z"/><path d="M12 15V8m-3 3 3-3 3 3"/>'),
    logs:svg('<path d="M5 4h14v16H5Z"/><path d="M8 8h8M8 12h8M8 16h5"/><circle cx="17" cy="16" r="1"/>'),
    faq:svg('<path d="M4 5h16v14H4Z"/><path d="M8 9h8M8 13h5"/><path d="M16.5 13.5c0-1.4 2-1.1 2-2.8 0-1.1-.8-1.7-1.9-1.7-.9 0-1.5.4-2 1"/><circle cx="16.5" cy="16.5" r=".7"/>'),
    settings:svg('<circle cx="12" cy="12" r="3"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6 7 7M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4"/><circle cx="12" cy="12" r="7"/>'),
    oximetry:svg('<path d="M3 13h3.3l2-5.2L12 17l2.1-5.2H21"/><circle cx="12" cy="12" r="9"/><path d="M17.8 5.7c1.7 1.5 2.7 3.6 2.7 6"/>'),
    charts:svg('<path d="M4 19.5V5M4 19.5h16"/><path d="m6.5 15 3.1-3.5 3 2.2 4.7-6.2"/><circle cx="6.5" cy="15" r=".8"/><circle cx="9.6" cy="11.5" r=".8"/><circle cx="12.6" cy="13.7" r=".8"/><circle cx="17.3" cy="7.5" r=".8"/>'),
    more:svg('<circle cx="5" cy="12" r="1.7"/><circle cx="12" cy="12" r="1.7"/><circle cx="19" cy="12" r="1.7"/><path d="M4 5h16M4 19h16"/>'),
  };
  const NAV={
    dashboard:{label:'Dashboard',page:'dashboard'},patient:{label:'Kezelt személy',page:'patient'},sessions:{label:'Napok',page:'sessions'},events:{label:'Események',page:'events'},reports:{label:'Jelentések',page:'reports'},ai:{label:'Luna & Milo',page:'ai'},equipment:{label:'Felszerelés',page:'equipment'},upload:{label:'Feltöltés',page:'upload'},logs:{label:'Naplók',page:'logs'},faq:{label:'GYIK',page:'faq'},settings:{label:'Beállítások',page:'settings'},oximetry:{label:'Oximetria',page:'oximetry'},charts:{label:'Diagrammok',action:'charts'},more:{label:'Egyéb',action:'more'}
  };
  let prefs={pwa_bottom_nav:['dashboard','sessions','charts','ai','more'],pwa_bottom_nav_max:6};
  let o2={settings:{o2ring_enabled:false,o2ring_ble_enabled:true},live:{}};
  let o2ScriptsLoaded=false;

  function waitCore(){return new Promise(resolve=>{let n=0;const tick=()=>{const shell=document.querySelector('.hidden-until-ready');if(shell?.classList.contains('ready')&&typeof window.navigate==='function')return resolve();if(++n>600)return resolve();setTimeout(tick,50)};tick()})}

  function installAuroraScene(){
    if(document.getElementById('smAuroraScene'))return;
    const host=document.querySelector('.content-shell')||document.body;
    const wrap=document.createElement('div');wrap.id='smAuroraScene';wrap.className='sm-aurora-scene';wrap.setAttribute('aria-hidden','true');
    wrap.innerHTML=`<div class="sm-starfield"></div><svg class="sm-aurora-flow" viewBox="0 0 1600 900" preserveAspectRatio="none"><defs><linearGradient id="smAuroraGradient" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#4bdcff"/><stop offset=".46" stop-color="#49e3bd"/><stop offset=".72" stop-color="#8c78ff"/><stop offset="1" stop-color="#5aa5ff"/></linearGradient><filter id="smAuroraGlow"><feGaussianBlur stdDeviation="9" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs><path class="flow flow-a" d="M-80 210C260 20 420 420 780 210S1280 20 1690 270"/><path class="flow flow-b" d="M-100 510C250 250 520 720 850 430s520-220 850 10"/><path class="flow flow-c" d="M40 820C350 610 570 880 920 690s430-190 720-40"/></svg>`;
    host.prepend(wrap);
  }

  function activeO2(){return !!o2?.settings?.o2ring_enabled}
  function availableNavIds(){return Object.keys(NAV).filter(id=>id!=='oximetry'||activeO2())}
  function effectiveNav(){const allowed=new Set(availableNavIds());let rows=(prefs.pwa_bottom_nav||[]).filter(x=>allowed.has(x)&&NAV[x]);if(!rows.length)rows=['dashboard'];return rows.slice(0,Math.max(1,Number(prefs.pwa_bottom_nav_max)||6))}

  function makeBottomButton(id){const item=NAV[id],b=document.createElement('button');b.type='button';b.dataset.smNavId=id;if(item.page)b.dataset.mobilePage=item.page;if(item.action)b.dataset.mobileAction=item.action;b.setAttribute('aria-label',item.label);b.innerHTML=`${ICONS[id]||ICONS.more}<b>${esc(item.label)}</b>`;b.onclick=()=>{if(typeof window.handleMobileBottomNav==='function')window.handleMobileBottomNav(b);else if(item.page&&typeof window.navigate==='function')window.navigate(item.page);else if(item.action==='more')document.getElementById('mobileMenuToggle')?.click()};return b}
  function renderBottomNav(){const nav=document.getElementById('mobileBottomNav');if(!nav)return;const rows=effectiveNav();nav.innerHTML='';rows.forEach(id=>nav.appendChild(makeBottomButton(id)));nav.style.setProperty('--sm-mobile-items',String(rows.length));nav.dataset.items=String(rows.length);try{const page=(location.hash.replace(/^#/,'').split('/')[0]||'dashboard');window.updateMobileBottomNav?.(page)}catch{}}

  async function savePrefs(next){prefs=await api('/api/ui/preferences',{method:'POST',body:JSON.stringify({pwa_bottom_nav:next})});renderBottomNav();renderPwaEditor()}
  function moveItem(id,delta){const rows=[...(prefs.pwa_bottom_nav||[])],i=rows.indexOf(id),j=i+delta;if(i<0||j<0||j>=rows.length)return;[rows[i],rows[j]]=[rows[j],rows[i]];savePrefs(rows).catch(showPwaMsg)}
  function showPwaMsg(e){const el=document.getElementById('smPwaNavMsg');if(el)el.textContent=typeof e==='string'?e:(e?.message||String(e))}
  function toggleNav(id,on){let rows=[...(prefs.pwa_bottom_nav||[])];if(on){if(rows.includes(id))return;if(rows.length>=Number(prefs.pwa_bottom_nav_max||6)){showPwaMsg(`Legfeljebb ${prefs.pwa_bottom_nav_max||6} menüpont választható.`);renderPwaEditor();return}rows.push(id)}else{rows=rows.filter(x=>x!==id);if(!rows.length){showPwaMsg('Legalább 1 menüpontnak maradnia kell.');renderPwaEditor();return}}savePrefs(rows).catch(showPwaMsg)}

  function activateSettingsTab(name){document.querySelectorAll('[data-settings-tab]').forEach(x=>x.classList.toggle('active',x.dataset.settingsTab===name));document.querySelectorAll('[data-settings-panel]').forEach(x=>x.classList.toggle('active',x.dataset.settingsPanel===name));const s=document.getElementById('settingsCategorySelect');if(s&&[...s.options].some(o=>o.value===name))s.value=name}
  function installPwaSettingsTab(){
    const tabs=document.querySelector('.settings-inner-tabs'),sel=document.getElementById('settingsCategorySelect'),main=document.querySelector('#page-settings main, #page-settings');if(!tabs||!main)return;
    if(!tabs.querySelector('[data-settings-tab="pwa"]')){const b=document.createElement('button');b.type='button';b.dataset.settingsTab='pwa';b.textContent='PWA';const push=tabs.querySelector('[data-settings-tab="push"]');tabs.insertBefore(b,push||null);b.onclick=()=>activateSettingsTab('pwa')}
    if(sel&&![...sel.options].some(o=>o.value==='pwa')){const op=document.createElement('option');op.value='pwa';op.textContent='PWA';const push=[...sel.options].find(o=>o.value==='push');sel.insertBefore(op,push||null);sel.addEventListener('change',()=>{if(sel.value==='pwa')activateSettingsTab('pwa')})}
    if(!document.getElementById('smPwaSettingsPanel')){const panel=document.createElement('section');panel.id='smPwaSettingsPanel';panel.className='panel settings-tab-panel sm-pwa-settings';panel.dataset.settingsPanel='pwa';panel.innerHTML=`<div class="panel-head"><div><h3>PWA alsó navigáció</h3><span>Válassz 1–6 elemet. Nincs fenntartott üres hely: a kiválasztott elemek automatikusan kitöltik a teljes alsó sávot.</span></div><span class="security-pill">max. 6</span></div><div id="smPwaNavEditor" class="sm-pwa-nav-editor"></div><div class="sm-pwa-preview-wrap"><span>Telefonos előnézet</span><div id="smPwaNavPreview" class="sm-pwa-nav-preview"></div></div><p id="smPwaNavMsg" class="muted"></p>`;const pushPanel=document.querySelector('[data-settings-panel="push"]');pushPanel?.parentNode?.insertBefore(panel,pushPanel);if(!pushPanel)main.appendChild(panel)}
    renderPwaEditor();
  }
  function renderPwaEditor(){const root=document.getElementById('smPwaNavEditor'),preview=document.getElementById('smPwaNavPreview');if(!root)return;const selected=prefs.pwa_bottom_nav||[],available=availableNavIds();root.innerHTML=available.map(id=>{const item=NAV[id],on=selected.includes(id),pos=selected.indexOf(id);return `<article class="sm-pwa-choice ${on?'selected':''}" data-nav-choice="${id}"><div class="sm-pwa-choice-icon">${ICONS[id]}</div><div class="sm-pwa-choice-copy"><b>${esc(item.label)}</b><small>${item.action?'Gyorsművelet':'Fő nézet'}${on?` • ${pos+1}. hely`:''}</small></div><label class="sm-switch"><input type="checkbox" ${on?'checked':''}><span></span></label>${on?`<div class="sm-order-buttons"><button type="button" data-move="-1" ${pos===0?'disabled':''} aria-label="Fel">↑</button><button type="button" data-move="1" ${pos===selected.length-1?'disabled':''} aria-label="Le">↓</button></div>`:''}</article>`}).join('');root.querySelectorAll('[data-nav-choice]').forEach(card=>{const id=card.dataset.navChoice;card.querySelector('input').onchange=e=>toggleNav(id,e.target.checked);card.querySelectorAll('[data-move]').forEach(b=>b.onclick=()=>moveItem(id,Number(b.dataset.move))) });if(preview){const rows=effectiveNav();preview.style.setProperty('--sm-mobile-items',String(rows.length));preview.innerHTML=rows.map(id=>`<div>${ICONS[id]}<b>${esc(NAV[id].label)}</b></div>`).join('')}}

  function loadScript(src,id){return new Promise((resolve,reject)=>{if(document.getElementById(id))return resolve();const s=document.createElement('script');s.id=id;s.src=src;s.async=false;s.onload=resolve;s.onerror=reject;document.head.appendChild(s)})}
  function loadCss(href,id){if(document.getElementById(id))return;const l=document.createElement('link');l.id=id;l.rel='stylesheet';l.href=href;document.head.appendChild(l)}
  async function ensureO2Modules(){if(!activeO2())return;if(o2ScriptsLoaded){window.SleepMateO2Ring?.install?.();return}loadCss(`/o2ring.css?v=${VERSION}`,'smO2Css');await loadScript(`/o2ring.js?v=${VERSION}`,'smO2Js');await loadScript(`/o2ring-report-ui.js?v=${VERSION}`,'smO2ReportJs');o2ScriptsLoaded=true;window.SleepMateO2Ring?.install?.()}
  function disableO2Ui(){window.SleepMateO2Ring?.uninstall?.();document.querySelectorAll('[data-o2ring-feature]').forEach(x=>x.remove());document.getElementById('spo2Metric')?.classList.add('hidden');document.getElementById('hrMetric')?.classList.add('hidden');renderBottomNav();renderPwaEditor()}

  function installO2MasterPanel(){const display=document.querySelector('[data-settings-panel="display"]');if(!display||document.getElementById('smO2Master'))return;const p=document.createElement('section');p.id='smO2Master';p.className='sm-o2-master';p.innerHTML=`<div class="sm-o2-master-head"><div class="sm-o2-logo">${ICONS.oximetry}</div><div><h3>O2Ring integráció</h3><p>Főkapcsolóval az egész funkció eltűnik. A Bluetooth külön kapcsolható; a gyűrű és a korábbi felvételek ettől nem felejtődnek el.</p></div><label class="sm-switch sm-switch-large"><input id="smO2Enabled" type="checkbox"><span></span></label></div><div id="smO2RuntimeSettings" class="sm-o2-runtime-settings"><label><span>Bluetooth / BLE</span><small>Élő mérés és gyűrű-szinkron. Kikapcsolás nem felejti el az eszközt.</small><input id="smO2Ble" type="checkbox"></label><label><span>Automatikus kapcsolódás</span><small>A SleepMate háttérben megkeresi a megjegyzett gyűrűt.</small><input id="smO2AutoConnect" type="checkbox"></label><label><span>Automatikus felvételszinkron</span><small>Lezárt gyűrűfelvételek automatikus letöltése.</small><input id="smO2AutoSync" type="checkbox"></label><div class="sm-o2-remembered"><div><span>Megjegyzett gyűrű</span><b id="smO2Remembered">–</b></div><button id="smO2Forget" type="button">Eszköz elfelejtése</button></div></div><p id="smO2MasterMsg" class="muted"></p>`;display.prepend(p);['smO2Enabled','smO2Ble','smO2AutoConnect','smO2AutoSync'].forEach(id=>document.getElementById(id)?.addEventListener('change',saveO2Master));document.getElementById('smO2Forget').onclick=async()=>{try{o2=await api('/api/o2ring/forget-device',{method:'POST',body:'{}'});hydrateO2Master()}catch(e){o2Msg(e.message)}};hydrateO2Master()}
  function o2Msg(t){const e=document.getElementById('smO2MasterMsg');if(e)e.textContent=t||''}
  function hydrateO2Master(){const c=o2.settings||{},l=o2.live||{};const set=(id,v)=>{const e=document.getElementById(id);if(e)e.checked=!!v};set('smO2Enabled',c.o2ring_enabled);set('smO2Ble',c.o2ring_ble_enabled);set('smO2AutoConnect',c.o2ring_auto_connect);set('smO2AutoSync',c.o2ring_auto_sync);const runtime=document.getElementById('smO2RuntimeSettings');runtime?.classList.toggle('hidden',!c.o2ring_enabled);const remembered=document.getElementById('smO2Remembered');if(remembered)remembered.textContent=l.device_model||l.device_name||l.remembered_address||c.o2ring_preferred_address||'Nincs kiválasztva';const forget=document.getElementById('smO2Forget');if(forget)forget.disabled=!(l.remembered_address||c.o2ring_preferred_address)}
  async function saveO2Master(){const g=id=>document.getElementById(id),payload={o2ring_enabled:g('smO2Enabled').checked,o2ring_ble_enabled:g('smO2Ble').checked,o2ring_auto_connect:g('smO2AutoConnect').checked,o2ring_auto_sync:g('smO2AutoSync').checked};try{const settings=await api('/api/o2ring/settings',{method:'POST',body:JSON.stringify(payload)});o2.settings=settings;o2=await api('/api/o2ring/status');hydrateO2Master();if(activeO2()){await ensureO2Modules();window.SleepMateO2Ring?.refresh?.()}else disableO2Ui();renderBottomNav();renderPwaEditor();o2Msg('Beállítások mentve.')}catch(e){o2Msg(e.message)}}

  function watchNavigation(){window.addEventListener('hashchange',()=>setTimeout(renderBottomNav,0));const nav=document.querySelector('#sidebar .nav');if(nav)new MutationObserver(()=>renderBottomNav()).observe(nav,{attributes:true,subtree:true,attributeFilter:['class']})}

  async function init(){
    await waitCore();
    installAuroraScene();
    try{prefs=await api('/api/ui/preferences')}catch{}
    try{o2=await api('/api/o2ring/status')}catch{}
    renderBottomNav();
    installPwaSettingsTab();
    installO2MasterPanel();
    if(activeO2())try{await ensureO2Modules()}catch(e){o2Msg(`O2Ring UI betöltési hiba: ${e.message}`)}else disableO2Ui();
    watchNavigation();
    window.SleepMateV530={ICONS,NAV,renderBottomNav,renderPwaEditor,refreshO2:async()=>{o2=await api('/api/o2ring/status');hydrateO2Master();if(activeO2())await ensureO2Modules();else disableO2Ui()}};
  }
  init();
})();
