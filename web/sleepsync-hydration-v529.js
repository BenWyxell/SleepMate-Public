(function(){
  const nativeFetch=window.fetch.bind(window);
  let hydrated=false;
  let hydrating=null;
  let attempts=0;
  let applying=false;
  let dirty=false;
  let lastSettings=null;
  let observer=null;

  const esc=(value)=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function page(){return document.getElementById('page-sleepsync')}
  function scheduleCard(){return document.querySelector('.sleepsync-page .ss-schedule-card')}
  function saveButtons(){return [...document.querySelectorAll('[data-ss-action="save-settings"]')]}

  function setSaveReady(ready){
    const card=scheduleCard();
    if(card){
      card.classList.toggle('ss-schedule-ready',!!ready);
      card.setAttribute('aria-busy',ready?'false':'true');
    }
    saveButtons().forEach(btn=>{
      if(btn.dataset.ssSaving==='1')return;
      btn.disabled=!ready;
      if(!ready){
        btn.dataset.ssHydrationBlocked='1';
        btn.title='A SleepSync beállítások betöltése folyamatban van.';
      }else if(btn.dataset.ssHydrationBlocked==='1'){
        delete btn.dataset.ssHydrationBlocked;
        btn.removeAttribute('title');
      }
    });
  }

  function bindTimeDeleteButtons(){
    const box=document.getElementById('ssTimeList');
    if(!box)return;
    const rows=[...box.querySelectorAll('.ss-time-row')];
    rows.forEach(row=>{
      const btn=row.querySelector('button');
      if(!btn)return;
      btn.title='Időpont törlése';
      btn.setAttribute('aria-label','Időpont törlése');
      btn.disabled=rows.length<=1;
      if(btn.dataset.ssHydrationBound==='1')return;
      btn.dataset.ssHydrationBound='1';
      btn.addEventListener('click',event=>{
        event.preventDefault();
        event.stopPropagation();
        if(box.querySelectorAll('.ss-time-row').length<=1)return;
        dirty=true;
        row.remove();
        bindTimeDeleteButtons();
      },true);
    });
  }

  function renderTimes(values){
    const box=document.getElementById('ssTimeList');
    if(!box)return;
    const times=Array.isArray(values)&&values.length?values:['09:00'];
    box.innerHTML=times.map(v=>`<div class="ss-time-row"><input class="ssScheduleTime" type="time" value="${esc(v)}"><button type="button">Törlés</button></div>`).join('');
    bindTimeDeleteButtons();
  }

  function renderWifi(data){
    const box=document.getElementById('ssWifiBox');
    if(!box)return;
    const choices=Array.isArray(data?.choices)?data.choices:[];
    const selected=new Set((Array.isArray(data?.selected)?data.selected:[]).map(v=>String(v).toLowerCase()));
    if(!choices.length){
      box.innerHTML='<span>Jelenleg nincs választható, látható és mentett internetes Wi-Fi hálózat.</span>';
      return;
    }
    box.innerHTML=choices.map(name=>`<label class="ss-checkline"><input type="checkbox" data-wifi="${esc(name)}" ${selected.has(String(name).toLowerCase())?'checked':''}> <span>${esc(name)}</span></label>`).join('');
  }

  function applySchedule(cfg){
    const auto=document.getElementById('ssAutoEnabled');
    if(auto&&!auto.dataset.ssChanging)auto.checked=!!cfg.auto_sync_enabled;

    const mode=document.getElementById('ssScheduleMode');
    if(mode)mode.value='scheduled';

    document.querySelectorAll('#ssScheduleDays [data-day]').forEach(input=>{
      input.checked=(cfg.schedule_days||[]).includes(input.dataset.day);
    });
    renderTimes(cfg.schedule_times||['09:00']);
  }

  function applySettings(cfg){
    if(!cfg||typeof cfg!=='object')throw new Error('Érvénytelen SleepSync beállításválasz.');
    applying=true;
    try{
      lastSettings=cfg;
      applySchedule(cfg);

      const therapy=document.getElementById('ssTherapyDir');
      const backup=document.getElementById('ssBackupDir');
      const buffer=document.getElementById('ssBufferDays');
      const wait=document.getElementById('ssStabilityWait');
      if(therapy)therapy.value=cfg.therapy_data_dir||'';
      if(backup)backup.value=cfg.backup_root||'';
      if(buffer)buffer.value=String(cfg.buffer_days??2);
      if(wait)wait.value=String(cfg.stability_wait_seconds??4);

      hydrated=true;
      dirty=false;
      const root=page();
      if(root)root.dataset.ssSettingsHydrated='1';
      setSaveReady(true);
    }finally{
      applying=false;
    }
  }

  function repairScheduleIfCleared(){
    if(!hydrated||dirty||applying||!lastSettings)return;
    const box=document.getElementById('ssTimeList');
    const days=document.getElementById('ssScheduleDays');
    if(!box||!days)return;
    const expectedTimes=Array.isArray(lastSettings.schedule_times)&&lastSettings.schedule_times.length?lastSettings.schedule_times:['09:00'];
    const timeInputs=box.querySelectorAll('.ssScheduleTime');
    const activePanel=document.querySelector('[data-sleepsync-panel="sync"].active');
    if(activePanel&&timeInputs.length===0&&expectedTimes.length){
      applying=true;
      try{applySchedule(lastSettings)}finally{applying=false}
    }
  }

  async function hydrate(force=false){
    if(hydrated&&!force)return true;
    if(dirty&&force)return true;
    if(hydrating)return hydrating;
    if(!page())return false;

    setSaveReady(false);
    hydrating=(async()=>{
      try{
        const [settingsResponse,wifiResponse]=await Promise.all([
          nativeFetch('/api/sleepsync/settings',{cache:'no-store'}),
          nativeFetch('/api/sleepsync/wifi',{cache:'no-store'})
        ]);
        if(!settingsResponse.ok)throw new Error(`SleepSync beállítások: HTTP ${settingsResponse.status}`);
        const cfg=await settingsResponse.json();
        applySettings(cfg);
        if(wifiResponse.ok){
          const wifi=await wifiResponse.json();
          renderWifi(wifi);
        }
        document.dispatchEvent(new CustomEvent('sleepmate:sleepsync-settings-hydrated',{detail:{settings:cfg}}));
        return true;
      }catch(err){
        hydrated=false;
        const root=page();
        if(root)delete root.dataset.ssSettingsHydrated;
        setSaveReady(false);
        const status=document.getElementById('ssSettingsSaveStatus');
        if(status){
          status.className='ss-save-status error';
          status.textContent=`A SleepSync beállításai még nem tölthetők be: ${err.message||err}`;
        }
        return false;
      }finally{
        hydrating=null;
      }
    })();
    return hydrating;
  }

  function bindDirtyTracking(root){
    if(root.dataset.ssHydrationDirtyBound==='1')return;
    root.dataset.ssHydrationDirtyBound='1';
    const mark=event=>{
      if(applying)return;
      const target=event.target;
      if(!(target instanceof Element))return;
      if(target.matches('#ssScheduleDays [data-day],#ssTimeList .ssScheduleTime,#ssTherapyDir,#ssBackupDir,#ssBufferDays,#ssStabilityWait,#ssWifiBox [data-wifi]'))dirty=true;
    };
    root.addEventListener('change',mark,true);
    root.addEventListener('input',mark,true);
  }

  function bindObserver(root){
    if(observer)return;
    observer=new MutationObserver(()=>{
      if(!hydrated||dirty)return;
      setTimeout(repairScheduleIfCleared,0);
    });
    observer.observe(root,{childList:true,subtree:true});
  }

  function scheduleHydrationChecks(){
    [0,90,260,600].forEach(delay=>setTimeout(()=>{
      if(!dirty)hydrate(false);
      repairScheduleIfCleared();
    },delay));
  }

  function confirmSavedAndRefresh(){
    setTimeout(()=>{
      const notice=document.getElementById('sleepSyncInlineNotice');
      const saved=!!notice&&notice.classList.contains('success')&&/beállítások mentve/i.test(notice.textContent||'');
      if(!saved)return;
      dirty=false;
      hydrated=false;
      hydrate(true);
    },850);
  }

  function bind(){
    const root=page();
    if(!root)return false;
    if(root.dataset.ssHydration529Bound==='1')return true;
    root.dataset.ssHydration529Bound='1';
    setSaveReady(false);
    bindDirtyTracking(root);
    bindObserver(root);

    root.addEventListener('click',event=>{
      const target=event.target.closest('button');
      if(!target)return;
      if(target.id==='ssAddTime'){
        dirty=true;
        setTimeout(bindTimeDeleteButtons,0);
      }
      if(target.matches('[data-sleepsync-tab="settings"],[data-sleepsync-tab="sync"]')){
        scheduleHydrationChecks();
      }
      if(target.matches('[data-ss-action="save-settings"]')){
        confirmSavedAndRefresh();
      }
    });

    hydrate(false);
    return true;
  }

  function boot(){
    if(bind())return;
    attempts+=1;
    if(attempts<120)setTimeout(boot,100);
  }

  function injectPackagedOnboardingReopen(){
    if(document.getElementById('frPackagedReopen'))return true;
    const settings=document.getElementById('page-settings');
    if(!settings||typeof window.openSleepMateFirstRun!=='function')return false;
    const box=document.createElement('section');
    box.id='frPackagedReopen';
    box.className='fr-settings-reopen';
    box.innerHTML='<b>Első beállítás varázsló</b><p>Újra végigvezet az adatforrás, SleepSync, távoli elérés, backup és AI alapbeállításain.</p><button type="button" class="fr-btn">Varázsló megnyitása</button>';
    box.querySelector('button').onclick=()=>window.openSleepMateFirstRun();
    settings.appendChild(box);
    return true;
  }

  async function lateBootPackagedOnboarding(){
    try{
      const response=await nativeFetch('/api/onboarding/status',{cache:'no-store'});
      if(!response.ok)return;
      const status=await response.json();
      if(!status.completed&&typeof window.openSleepMateFirstRun==='function'){
        window.openSleepMateFirstRun();
        return;
      }
      let checks=0;
      const timer=setInterval(()=>{
        checks+=1;
        if(injectPackagedOnboardingReopen()||checks>30)clearInterval(timer);
      },500);
    }catch{}
  }

  function loadPackagedOnboarding(){
    // Development builds load first-run.js from web/app.js. Packaged builds
    // deliberately restore the frozen app-core.js, so attach the wizard here,
    // on the integration path that is actually present in the MSI/PWA bundle.
    if(document.querySelector('script[data-sleepmate-first-run="1"]'))return;
    const script=document.createElement('script');
    script.src='/first-run.js?v=4';
    script.async=false;
    script.dataset.sleepmateFirstRun='1';
    script.onload=lateBootPackagedOnboarding;
    document.head.appendChild(script);
  }

  window.__sleepSyncHydrateSettings=hydrate;

  document.addEventListener('click',event=>{
    if(event.target.closest('[data-page="sleepsync"]')){
      setTimeout(()=>{bind();scheduleHydrationChecks();},0);
    }
  },true);

  window.addEventListener('hashchange',()=>{
    if(location.hash.startsWith('#sleepsync'))setTimeout(()=>{bind();scheduleHydrationChecks();},0);
  });

  document.addEventListener('visibilitychange',()=>{
    if(document.visibilityState==='visible'&&location.hash.startsWith('#sleepsync')){
      setTimeout(()=>{bind();scheduleHydrationChecks();},0);
    }
  });

  loadPackagedOnboarding();
  boot();
})();