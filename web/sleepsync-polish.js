(function(){
  const nativeFetch=window.fetch.bind(window);
  const orderedDays=['monday','tuesday','wednesday','thursday','friday','saturday','sunday'];
  const dayNames={monday:'Hétfő',tuesday:'Kedd',wednesday:'Szerda',thursday:'Csütörtök',friday:'Péntek',saturday:'Szombat',sunday:'Vasárnap'};
  let lastStatus=null;
  let initialized=false;
  let bootAttempts=0;

  const esc=(value)=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}[c]));
  const fmtTime=(raw)=>{
    if(!raw)return '—';
    try{return new Date(raw).toLocaleString('hu-HU',{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'});}catch{return String(raw);}
  };

  function ensureHydrationModule(){
    if(typeof window.__sleepSyncHydrateSettings==='function')return;
    if(document.querySelector('script[src*="sleepsync-hydration-v529.js"]'))return;
    const script=document.createElement('script');
    script.src='/sleepsync-hydration-v529.js?v=131';
    script.async=false;
    script.dataset.sleepsyncHydrationFallback='5213';
    script.onload=()=>{try{window.__sleepSyncHydrateSettings?.(false)}catch{}};
    document.head.appendChild(script);
  }

  function requestHydration(force=false){
    ensureHydrationModule();
    const run=()=>{try{window.__sleepSyncHydrateSettings?.(force)}catch{}};
    run();
    setTimeout(run,100);
    setTimeout(run,360);
  }

  function scheduleSummary(settings){
    const days=orderedDays.filter(day=>(settings.schedule_days||[]).includes(day));
    let dayText='Nincs kiválasztott nap';
    if(days.length===7)dayText='Minden nap';
    else if(days.join(',')===orderedDays.slice(0,5).join(','))dayText='Hétfő–péntek';
    else if(days.join(',')===orderedDays.slice(5).join(','))dayText='Hétvége';
    else if(days.length)dayText=days.map(day=>dayNames[day]).join(', ');
    const times=Array.isArray(settings.schedule_times)&&settings.schedule_times.length?settings.schedule_times:['09:00'];
    return `${dayText} • ${times.join(', ')}`;
  }

  function showNotice(kind,title,text){
    const box=document.getElementById('sleepSyncInlineNotice');
    if(!box)return;
    box.className=`ss-notice ${kind}`;
    box.innerHTML=`<b>${esc(title)}</b><span>${esc(text)}</span>`;
    clearTimeout(box.__ssPolishTimer);
    box.__ssPolishTimer=setTimeout(()=>box.classList.add('hidden'),5000);
  }

  function ensureOverviewSummary(){
    const original=document.getElementById('ssOverviewAutoSub');
    if(!original)return null;
    original.classList.add('ss-polish-original-summary');
    let custom=document.getElementById('ssOverviewAutoSchedule');
    if(!custom){
      custom=document.createElement('small');
      custom.id='ssOverviewAutoSchedule';
      custom.className='ss-overview-schedule-summary';
      original.insertAdjacentElement('afterend',custom);
    }
    return custom;
  }

  function patchIntegratedBackupCopy(){
    const backupButton=document.getElementById('ssSdBackup');
    if(backupButton){
      backupButton.classList.add('ss-polish-hidden');
      backupButton.setAttribute('aria-hidden','true');
      backupButton.tabIndex=-1;
    }
    const card=backupButton?.closest('.ss-backup-card')||document.querySelector('.ss-backup-card');
    if(!card)return;
    const heading=card.querySelector('h3');
    const text=card.querySelector('p');
    if(heading)heading.textContent='SD biztonsági mentés';
    if(text)text.textContent='Minden sikeres kézi és időzített szinkron automatikusan létrehozza a teljes, dátumozott SD-tükröt és a ZIP mentést is. Külön mentési futtatás nem szükséges.';
  }

  function enforceScheduledOnlyUi(){
    const mode=document.getElementById('ssScheduleMode');
    if(mode){
      mode.value='scheduled';
      mode.setAttribute('aria-hidden','true');
      mode.tabIndex=-1;
    }
    const modeRow=mode?.closest('.ss-mode-row');
    if(modeRow)modeRow.style.setProperty('display','none','important');
    const cardSchedule=document.getElementById('ssCardSchedule');
    if(cardSchedule){
      cardSchedule.classList.add('hidden');
      cardSchedule.style.setProperty('display','none','important');
    }
    const timedSchedule=document.getElementById('ssTimedSchedule');
    if(timedSchedule){
      timedSchedule.classList.remove('hidden');
      timedSchedule.style.setProperty('display','block','important');
    }
    const foot=document.querySelector('.ss-schedule-card .ss-schedule-foot');
    if(foot)foot.style.setProperty('display','flex','important');
  }

  function updateScheduleVisibility(enabled){
    enforceScheduledOnlyUi();
    const next=document.getElementById('ssNextRun');
    if(next){
      next.classList.remove('ss-polish-hidden');
      next.style.removeProperty('display');
      if(!enabled)next.textContent='Következő futás: Kikapcsolva';
    }
  }

  function applyStatus(data){
    if(!data||typeof data!=='object')return;
    lastStatus=data;
    const settings=data.settings||{};
    const enabled=!!settings.auto_sync_enabled;

    const auto=document.getElementById('ssOverviewAuto');
    if(auto)auto.textContent=enabled?'Ütemezve':'Kikapcsolva';
    const summary=ensureOverviewSummary();
    if(summary)summary.textContent=enabled?scheduleSummary(settings):'Automatikus szinkron';
    const current=document.getElementById('ssCurrentSchedule');
    if(current)current.textContent=scheduleSummary(settings);

    const sdSub=document.getElementById('ssOverviewSdSub');
    if(sdSub){
      sdSub.textContent=data.sd_visible
        ? 'ez Share kártya észlelve • készen áll a szinkronra'
        : 'ez Share kártya jelenleg nem látható';
    }

    const toggle=document.getElementById('ssAutoEnabled');
    if(toggle&&!toggle.dataset.ssChanging)toggle.checked=enabled;
    enforceScheduledOnlyUi();
    updateScheduleVisibility(enabled);

    const next=document.getElementById('ssNextRun');
    if(next&&enabled){
      next.classList.remove('ss-polish-hidden');
      next.textContent=data.next_run?`Következő futás: ${fmtTime(data.next_run)}`:'Következő futás számítása…';
    }
  }

  async function refreshStatus(silent=true){
    try{
      const response=await nativeFetch('/api/sleepsync/status',{cache:'no-store'});
      if(!response.ok)throw new Error(`HTTP ${response.status}`);
      const data=await response.json();
      applyStatus(data);
      return data;
    }catch(err){
      if(!silent)showNotice('error','SleepSync állapot nem tölthető be',err.message||String(err));
      return null;
    }
  }

  async function persistAutoToggle(toggle){
    if(toggle.dataset.ssChanging)return;
    const enabled=!!toggle.checked;
    toggle.dataset.ssChanging='1';
    toggle.disabled=true;
    updateScheduleVisibility(enabled);
    try{
      const response=await nativeFetch('/api/sleepsync/settings',{
        method:'POST',
        cache:'no-store',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({auto_sync_enabled:enabled,auto_sync_mode:'scheduled'})
      });
      const body=await response.json().catch(()=>({}));
      if(!response.ok)throw new Error(body.error||`HTTP ${response.status}`);
      const detail=enabled
        ? 'Az időzített futások aktívak. A napokat és időpontokat lent bármikor módosíthatod.'
        : 'Az automatikus futás kikapcsolt, de az ütemezés továbbra is szerkeszthető.';
      showNotice('success',enabled?'Automatikus szinkron bekapcsolva':'Automatikus szinkron kikapcsolva',detail);
      await refreshStatus(true);
      requestHydration(true);
    }catch(err){
      toggle.checked=!enabled;
      updateScheduleVisibility(!enabled);
      showNotice('error','Az automatika nem állítható',err.message||String(err));
    }finally{
      toggle.disabled=false;
      delete toggle.dataset.ssChanging;
    }
  }

  function patchFolderButtons(){
    const labels={folder:'Terápiás adatmappa megnyitása','backup-folder':'SD mentések mappájának megnyitása','log-folder':'Naplómappa megnyitása'};
    document.querySelectorAll('button[data-ss-action="folder"],button[data-ss-action="backup-folder"],button[data-ss-action="log-folder"]').forEach(btn=>{
      const label=labels[btn.dataset.ssAction]||'Mappa megnyitása';
      if(btn.title!==label)btn.title=label;
      if(btn.getAttribute('aria-label')!==label)btn.setAttribute('aria-label',label);
    });
  }

  function patchTimeDeleteButtons(){
    document.querySelectorAll('#ssTimeList .ss-time-row>button').forEach(btn=>{
      if(btn.title!=='Időpont törlése')btn.title='Időpont törlése';
      if(btn.getAttribute('aria-label')!=='Időpont törlése')btn.setAttribute('aria-label','Időpont törlése');
    });
  }

  function scheduleRefreshes(){
    [120,650,1400].forEach(delay=>setTimeout(()=>refreshStatus(true),delay));
  }

  function bindUi(){
    const page=document.getElementById('page-sleepsync');
    if(!page)return false;

    ensureHydrationModule();
    const toggle=document.getElementById('ssAutoEnabled');
    enforceScheduledOnlyUi();
    ensureOverviewSummary();
    patchIntegratedBackupCopy();
    patchFolderButtons();
    patchTimeDeleteButtons();

    if(toggle&&!toggle.dataset.ssPolishBound){
      toggle.dataset.ssPolishBound='1';
      toggle.addEventListener('change',()=>persistAutoToggle(toggle));
    }

    if(!page.dataset.ssPolishBound){
      page.dataset.ssPolishBound='1';
      page.addEventListener('click',event=>{
        const target=event.target.closest('button');
        if(!target)return;
        if(target.id==='ssAddTime'){
          setTimeout(patchTimeDeleteButtons,0);
          setTimeout(patchTimeDeleteButtons,120);
        }
        if(target.matches('[data-ss-action="save-settings"]')){
          enforceScheduledOnlyUi();
          scheduleRefreshes();
        }
        if(target.matches('[data-sleepsync-tab]')){
          setTimeout(enforceScheduledOnlyUi,0);
          setTimeout(patchIntegratedBackupCopy,0);
          setTimeout(patchFolderButtons,0);
          setTimeout(patchTimeDeleteButtons,180);
          const tab=target.dataset.sleepsyncTab;
          if(tab==='overview'||tab==='sync')scheduleRefreshes();
          if(tab==='sync'||tab==='settings')requestHydration(false);
        }
      });
    }

    updateScheduleVisibility(!!toggle?.checked);
    initialized=true;
    if(location.hash.startsWith('#sleepsync')){
      refreshStatus(true);
      requestHydration(false);
    }
    return true;
  }

  function boot(){
    ensureHydrationModule();
    if(initialized)return;
    if(bindUi())return;
    bootAttempts+=1;
    if(bootAttempts<80)setTimeout(boot,100);
  }

  document.addEventListener('click',event=>{
    const nav=event.target.closest('[data-page="sleepsync"]');
    if(nav){
      setTimeout(()=>{
        if(!initialized)boot();else refreshStatus(true);
        requestHydration(false);
      },60);
    }
  },true);

  window.addEventListener('hashchange',()=>{
    if(location.hash.startsWith('#sleepsync'))setTimeout(()=>{
      if(!initialized)boot();else refreshStatus(true);
      requestHydration(false);
    },50);
  });

  document.addEventListener('visibilitychange',()=>{
    if(document.visibilityState==='visible'&&location.hash.startsWith('#sleepsync')){
      if(!initialized)boot();else refreshStatus(true);
      requestHydration(false);
    }
  });

  boot();
})();
