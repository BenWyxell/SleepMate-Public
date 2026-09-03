(function(){
  const style=document.createElement('link');
  style.rel='stylesheet';
  style.href='/sleepsync.css?v=engine-2';
  document.head.appendChild(style);

  const core=document.createElement('script');
  core.src='/app-core.js?v=5.0.8';
  core.async=false;
  core.onload=()=>{
    const coreNavigate=window.navigate;
    const coreRoute=window.route;
    if(typeof coreNavigate!=='function'||typeof coreRoute!=='function')return;

    const esc=(value)=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const fmtTime=(raw)=>{
      if(!raw)return'Még nem volt';
      try{return new Date(raw).toLocaleString('hu-HU',{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'});}catch{return raw;}
    };
    const scheduleDayNames={monday:'Hétfő',tuesday:'Kedd',wednesday:'Szerda',thursday:'Csütörtök',friday:'Péntek',saturday:'Szombat',sunday:'Vasárnap'};
    const scheduleSummaryText=(settings={})=>{
      const days=(settings.schedule_days||[]).map(day=>scheduleDayNames[day]).filter(Boolean);
      const dayText=days.length===7?'Minden nap':days.length?days.join(', '):'Nincs kiválasztott nap';
      const times=Array.isArray(settings.schedule_times)&&settings.schedule_times.length?settings.schedule_times:['09:00'];
      return `${dayText} • ${times.join(', ')}`;
    };
    const metric=(title,value,sub,accent,id)=>`
      <article class="ss-metric">
        <i class="${accent}"></i>
        <span>${title}</span>
        <strong${id?` id="${id}"`:''}>${value}</strong>
        <small${id?` id="${id}Sub"`:''}>${sub}</small>
      </article>`;

    const pipeline=()=>`
      <div class="ss-pipeline">
        <div id="ssPipe0"><span>1</span><b>Kapcsolódás</b><small>Várakozik</small></div>
        <div id="ssPipe1"><span>2</span><b>SD ellenőrzése</b><small>Várakozik</small></div>
        <div id="ssPipe2"><span>3</span><b>Változások keresése</b><small>Várakozik</small></div>
        <div id="ssPipe3"><span>4</span><b>Adatok szinkronizálása</b><small>Várakozik</small></div>
        <div id="ssPipe4"><span>5</span><b>Kapcsolat visszaállítása</b><small>Várakozik</small></div>
      </div>`;

    const sectionTitle=(title,subtitle)=>`
      <div class="ss-section-title">
        <h2>${title}</h2><div></div><p>${subtitle}</p>
      </div>`;

    const sleepSyncMarkup=()=>`
      <section class="page sleepsync-page" id="page-sleepsync" aria-label="SleepSync">
        <div class="sleepsync-module">
          <nav class="sleepsync-tabs" aria-label="SleepSync menü">
            <button class="active" type="button" data-sleepsync-tab="overview">Áttekintés</button>
            <button type="button" data-sleepsync-tab="sync">Szinkronizálás</button>
            <button type="button" data-sleepsync-tab="history">Előzmények</button>
            <button type="button" data-sleepsync-tab="settings">Beállítások</button>
          </nav>

          <div id="sleepSyncInlineNotice" class="ss-notice hidden" role="status" aria-live="polite"></div>

          <div class="sleepsync-tab-panel active" data-sleepsync-panel="overview">
            <section class="ss-overview-hero ss-card">
              <div class="ss-hero-aurora" aria-hidden="true"></div>
              <div class="ss-hero-copy">
                <h2>SleepSync</h2>
                <p class="ss-tagline">Tartsd szinkronban a terápiád</p>
                <strong class="ss-overview-state" id="ssOverviewState">○&nbsp; Állapot betöltése…</strong>
                <button class="ss-main-action" type="button" data-ss-action="sync">↻&nbsp;&nbsp; SZINKRONIZÁLÁS MOST</button>
              </div>
              <img class="ss-hero-logo" src="/assets/sleepsync-logo.webp" alt="SleepSync">
            </section>

            <section class="ss-overview-metrics">
              ${metric('CPAP SD','Ellenőrzés…','ez Share elérhetőség','teal','ssOverviewSd')}
              ${metric('Utolsó szinkron','Még nem volt','Legutóbbi sikeres futás','cyan','ssOverviewLast')}
              ${metric('Adatmappa','—','SleepMate forrásmappa','violet','ssOverviewFolder')}
              ${metric('Automatika','Kikapcsolva','Automatikus szinkron','green','ssOverviewAuto')}
            </section>

            <section class="ss-card ss-flow-card">
              <span class="ss-kicker">ADATÚT</span>
              <div class="ss-data-flow">
                <article><i class="teal"></i><b>CPAP SD</b><small>ez Share kártya</small></article>
                <em>→</em>
                <article><i class="cyan"></i><b>SleepSync</b><small>ellenőrzés + biztonságos letöltés</small></article>
                <em>→</em>
                <article><i class="violet"></i><b>SleepMate</b><small>saját importmotor + kezelt mérési adattár</small></article>
              </div>
            </section>

            <section class="ss-card ss-recent-card">
              <h3>Legutóbbi események</h3>
              <div id="ssRecentHistory" class="ss-empty">Betöltés…</div>
            </section>
          </div>

          <div class="sleepsync-tab-panel" data-sleepsync-panel="sync">
            ${sectionTitle('Szinkronizálás','Valódi ez Share kapcsolat, stabil fájlellenőrzés, inkrementális letöltés és azonnali SleepMate-import.')}

            <section class="ss-card ss-sync-action">
              <div class="ss-card-line cyan"></div>
              <div class="ss-card-head">
                <h3>Terápiás adatok szinkronizálása</h3>
                <strong class="ss-live-state" id="ssLiveState">Készen áll.</strong>
              </div>
              <section class="ss-sync-metrics">
                ${metric('SD összes fájl','0','','teal','ssTotalFiles')}
                ${metric('Feldolgozandó','0','','cyan','ssWorkFiles')}
                ${metric('Feldolgozva','0','','violet','ssProcessedFiles')}
                ${metric('Frissítve','0','','green','ssDownloaded')}
              </section>
              <div class="ss-current-file" id="ssCurrentFile">Aktuális: — &nbsp;&nbsp; • &nbsp;&nbsp; Változatlan: 0 &nbsp;&nbsp; • &nbsp;&nbsp; Hibák: 0</div>
              <div class="ss-progress"><i id="ssProgressBar"></i></div>
              ${pipeline()}
              <div class="ss-action-row">
                <button class="ss-main-action" id="ssSyncNow" type="button" data-ss-action="sync">↻&nbsp;&nbsp; Szinkronizálás most</button>
                <button type="button" data-ss-action="folder">Terápiás adatmappa megnyitása</button>
              </div>
            </section>

            <section class="ss-card ss-schedule-card">
              <div class="ss-card-line teal"></div>
              <div class="ss-card-head">
                <h3>Automatikus szinkron</h3>
                <label class="ss-switch"><input id="ssAutoEnabled" type="checkbox"><span></span><b>Bekapcsolva</b></label>
              </div>
              <div class="ss-mode-row">
                <strong>Mikor fusson?</strong>
                <select id="ssScheduleMode">
                  <option value="card_available">Amikor elérhető a kártya</option>
                  <option value="scheduled">Időzítve</option>
                </select>
              </div>
              <div id="ssCardSchedule" class="ss-schedule-detail">
                A SleepSync figyeli az ez Share hálózatot. Amikor a kártya megjelenik, egyszer szinkronizál; újra csak akkor indul, ha eltűnt, majd ismét elérhető lett.
              </div>
              <div id="ssTimedSchedule" class="ss-schedule-detail hidden">
                <div class="ss-current-schedule" role="status">
                  <span>Jelenlegi mentett ütemezés</span>
                  <strong id="ssCurrentSchedule">Betöltés…</strong>
                  <small>A napok és időpontok lent közvetlenül módosíthatók.</small>
                </div>
                <strong class="ss-subhead">Napok</strong>
                <div class="ss-days" id="ssScheduleDays">
                  <label><input data-day="monday" type="checkbox"> Hétfő</label>
                  <label><input data-day="tuesday" type="checkbox"> Kedd</label>
                  <label><input data-day="wednesday" type="checkbox"> Szerda</label>
                  <label><input data-day="thursday" type="checkbox"> Csütörtök</label>
                  <label><input data-day="friday" type="checkbox"> Péntek</label>
                  <label><input data-day="saturday" type="checkbox"> Szombat</label>
                  <label><input data-day="sunday" type="checkbox"> Vasárnap</label>
                </div>
                <strong class="ss-subhead">Időpontok</strong>
                <div id="ssTimeList"></div>
                <div class="ss-time-row"><button id="ssAddTime" type="button">+ időpont</button><small>ÓÓ:PP • több időpont is megadható</small></div>
              </div>
              <div class="ss-schedule-foot">
                <strong id="ssNextRun">Következő futás: Kikapcsolva</strong>
                <button type="button" data-ss-action="save-settings">Ütemezés mentése</button>
              </div>
            </section>

            <section class="ss-card ss-backup-card">
              <div class="ss-card-line violet"></div>
              <h3>Teljes SD biztonsági mentés</h3>
              <p>Külön dátumozott, teljes SD-pillanatképet és ZIP-et készít az ez Share kártyáról. Ez a ResMed SD mentése; a teljes SleepMate + SleepSync rendszermentés a SleepMate Beállítások → Backup menüben van.</p>
              <div class="ss-action-row">
                <button class="ss-violet-action" id="ssSdBackup" type="button" data-ss-action="backup">Teljes SD mentés készítése</button>
                <button type="button" data-ss-action="backup-folder">SD mentések megnyitása</button>
                <input id="ssSdImportFile" type="file" accept=".zip,application/zip" hidden>
                <button id="ssSdImportChoose" type="button">Teljes SD mentés beolvasása</button>
              </div>
              <small id="ssSdBackupInfo">A beolvasott SleepSync SD-ZIP-et a SleepMate saját biztonságos ZIP-importja dolgozza fel.</small>
            </section>

            <button class="ss-wide-link" type="button" data-sleepsync-tab-jump="history">Élő műszaki napló megnyitása az Előzményekben</button>
          </div>

          <div class="sleepsync-tab-panel" data-sleepsync-panel="history">
            ${sectionTitle('Előzmények','Az integrált motor műszaki naplója és a szinkron/SD-mentés futási előzményei.')}

            <section class="ss-card ss-log-card">
              <div class="ss-card-line teal"></div>
              <div class="ss-card-head">
                <h3>Élő műszaki napló</h3>
                <div class="ss-mini-actions">
                  <button type="button" data-ss-action="copy-log">Másolás vágólapra</button>
                  <button type="button" data-ss-action="log-folder">Naplómappa</button>
                </div>
              </div>
              <small class="ss-log-path">SleepMate privát adattár → sleepsync → technical.log</small>
              <pre class="ss-log" id="ssTechnicalLog">Betöltés…</pre>
            </section>

            <div class="ss-history-head">
              <h3>Futási előzmények</h3>
              <button class="ss-danger-action" type="button" data-ss-action="clear-history">Előzmények törlése</button>
            </div>
            <section class="ss-card ss-history-empty" id="ssHistoryList">
              <strong>Betöltés…</strong>
            </section>
          </div>

          <div class="sleepsync-tab-panel" data-sleepsync-panel="settings">
            ${sectionTitle('Beállítások','A SleepSync saját szinkronbeállításai. A teljes backupot és a programfrissítést a SleepMate kezeli.')}

            <section class="ss-card ss-settings-card">
              <div class="ss-card-line cyan"></div>
              <h3>Adatok és SD-mentések</h3>
              <div class="ss-setting-row">
                <label>Terápiás adatmappa</label>
                <input id="ssTherapyDir" type="text" value="">
                <button type="button" data-ss-action="folder">Megnyitás</button>
              </div>
              <div class="ss-setting-row">
                <label>SD biztonsági mentések helye</label>
                <input id="ssBackupDir" type="text" value="">
                <button type="button" data-ss-action="backup-folder">Megnyitás</button>
              </div>
            </section>

            <section class="ss-card ss-settings-card">
              <div class="ss-card-line violet"></div>
              <h3>Működés</h3>
              <p>A buffer 0 napnál csak az új vagy valóban megváltozott fájlokat tölti le. A kötelező ResMed index- és beállításfájlok minden sikeres szinkronnál frissen letöltődnek.</p>
              <div class="ss-setting-row compact">
                <label>Biztonsági buffer</label>
                <select id="ssBufferDays"><option>0</option><option>1</option><option>2</option><option>3</option><option>4</option><option>5</option><option>7</option><option>14</option><option>30</option></select>
              </div>
              <div class="ss-setting-row compact">
                <label>Fájlstabilitási várakozás</label>
                <select id="ssStabilityWait"><option>2</option><option>3</option><option>4</option><option>5</option><option>6</option><option>8</option><option>10</option></select>
              </div>
              <p><b>Háttérben futás:</b> az integrált SleepSync a SleepMate háttérfolyamatával együtt fut; nincs külön SleepSync.exe vagy külön tálcaalkalmazás.</p>
            </section>

            <section class="ss-card ss-settings-card">
              <div class="ss-card-line teal"></div>
              <div class="ss-card-head"><h3>Internet Wi-Fi visszaállítás</h3><button type="button" data-ss-action="wifi-refresh">Frissítés</button></div>
              <p>Szinkron után először az eredeti hálózatot próbálja visszaállítani, utána az itt kijelölt, éppen látható mentett hálózatokat.</p>
              <div class="ss-wifi-box" id="ssWifiBox"><span>Wi-Fi lista betöltése…</span></div>
            </section>

            <button class="ss-save-button" type="button" data-ss-action="save-settings">SleepSync beállítások mentése</button>
            <div id="ssSettingsSaveStatus" class="ss-save-status" aria-live="polite"></div>

            <section class="ss-card ss-settings-card">
              <div class="ss-card-line cyan"></div>
              <div class="ss-card-head"><h3>Frissítések</h3><span class="ss-status success">SLEEPMATE KEZELI</span></div>
              <p>A beépített SleepSync modulnak nincs külön önfrissítője. A SleepSync a SleepMate kiadásával együtt frissül, így egyetlen updater és egyetlen telepítés marad.</p>
              <div class="ss-integrated-update"><span>SleepSync modul</span><b>Integrált komponens</b><small>Frissítés: SleepMate → Beállítások → Frissítések</small></div>
            </section>

            <section class="ss-card ss-about-card">
              <h3>SleepSync</h3>
              <strong>Tartsd szinkronban a terápiád</strong>
              <p>A SleepMate integrált ez Share szinkronmodulja.</p>
            </section>
          </div>
        </div>
      </section>`;

    function ensureSleepSyncUi(){
      if(!document.getElementById('page-sleepsync')){
        const main=document.querySelector('.content-shell main');
        if(main)main.insertAdjacentHTML('beforeend',sleepSyncMarkup());
      }
      const nav=document.querySelector('#sidebar .nav');
      const settings=nav?.querySelector('.nav-settings');
      if(nav&&settings&&!nav.querySelector('[data-page="sleepsync"]')){
        const button=document.createElement('button');
        button.className='nav-item sleepsync-nav-item';
        button.dataset.page='sleepsync';
        button.title='SleepSync';
        button.type='button';
        button.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7h10l-2.5-2.5M19 17H9l2.5 2.5M15 7a6 6 0 0 1 4 5M9 17a6 6 0 0 1-4-5"/></svg><span>SleepSync</span>';
        nav.insertBefore(button,settings);
      }
      bindSleepSyncUi();
    }

    let noticeTimer=null;
    function showSleepSyncNotice(kind,title,text){
      const box=document.getElementById('sleepSyncInlineNotice');
      if(!box)return;
      box.className=`ss-notice ${kind}`;
      box.innerHTML=`<b>${esc(title)}</b><span>${esc(text)}</span>`;
      clearTimeout(noticeTimer);
      noticeTimer=setTimeout(()=>box.classList.add('hidden'),5000);
    }

    async function ssApi(path,options={}){
      const response=await fetch(path,{cache:'no-store',...options});
      const type=response.headers.get('content-type')||'';
      const body=type.includes('application/json')?await response.json():await response.text();
      if(!response.ok)throw new Error((body&&body.error)||body||`HTTP ${response.status}`);
      return body;
    }

    async function pollJob(job,onUpdate){
      for(let i=0;i<720;i++){
        const row=await ssApi(`/api/job/${encodeURIComponent(job)}`);
        if(onUpdate)onUpdate(row);
        if(row.status==='done')return row;
        if(row.status==='error')throw new Error(row.error||row.message||'A művelet sikertelen.');
        await new Promise(r=>setTimeout(r,1000));
      }
      throw new Error('A művelet időtúllépés miatt nem fejeződött be.');
    }

    function setText(id,value){
      const el=document.getElementById(id);
      if(el)el.textContent=value;
    }

    function setPipeline(progress,phase,running,error){
      const thresholds=[4,10,28,88,96];
      const nextIndex=thresholds.findIndex(x=>progress<x);
      for(let i=0;i<5;i++){
        const row=document.getElementById(`ssPipe${i}`);
        if(!row)continue;
        row.classList.remove('done','current','error');
        const small=row.querySelector('small');
        if(error&&!running&&i===Math.max(0,nextIndex)){
          row.classList.add('error');
          if(small)small.textContent='Hiba';
        }else if(progress>=thresholds[i]){
          row.classList.add('done');
          if(small)small.textContent='Kész';
        }else if(running&&i===Math.max(0,nextIndex)){
          row.classList.add('current');
          if(small)small.textContent=phase||'Fut';
        }else if(small)small.textContent='Várakozik';
      }
    }

    function renderJobProgress(row){
      const running=row.status!=='done'&&row.status!=='error';
      const progress=Number(row.progress)||0;
      const phase=row.message||row.phase||'Folyamatban…';
      setText('ssLiveState',phase);
      const bar=document.getElementById('ssProgressBar');
      if(bar)bar.style.width=`${Math.max(0,Math.min(100,progress))}%`;
      setPipeline(progress,phase,running,row.status==='error');
    }

    function renderHistory(rows){
      const target=document.getElementById('ssHistoryList');
      const recent=document.getElementById('ssRecentHistory');
      if(!Array.isArray(rows)||!rows.length){
        if(target)target.innerHTML='<strong>Még nincs futási előzmény.</strong>';
        if(recent)recent.innerHTML='Még nincs szinkronizálási előzmény.';
        return;
      }
      const one=row=>{
        const label=row.kind==='backup'?'Teljes SD mentés':'Szinkronizálás';
        const state=row.success?'✓':'!';
        const detail=row.success
          ?`ellenőrizve: ${row.checked||0} • frissítve: ${row.downloaded||0} • hiba: ${row.errors||0}`
          :esc(row.error||'Sikertelen művelet');
        return `<div class="ss-history-row"><b>${state} ${label}</b><span>${fmtTime(row.timestamp)}</span><small>${detail}</small></div>`;
      };
      if(target)target.innerHTML=rows.map(one).join('');
      if(recent)recent.innerHTML=rows.slice(0,3).map(one).join('');
    }

    function renderStatus(data){
      if(!data)return;
      const settings=data.settings||{};
      const running=!!data.running;
      const error=data.last_error||'';
      setText('ssLiveState',data.phase||'Készen áll.');
      const state=document.getElementById('ssOverviewState');
      if(state)state.textContent=running?`↻ ${data.phase||'SleepSync fut…'}`:(error?`! ${error}`:'✓ SleepSync készen áll');
      setText('ssOverviewSd',data.sd_visible?'Elérhető':'Nem látható');
      setText('ssOverviewSdSub',data.current_wifi?`Aktív Wi-Fi: ${data.current_wifi}`:'ez Share elérhetőség');
      setText('ssOverviewLast',fmtTime(data.last_run||(data.history||[]).find(x=>x.success)?.timestamp));
      const therapy=settings.therapy_data_dir||'—';
      setText('ssOverviewFolder',therapy.split(/[\\/]/).filter(Boolean).pop()||therapy);
      setText('ssOverviewFolderSub',therapy);
      setText('ssOverviewAuto',settings.auto_sync_enabled?'Bekapcsolva':'Kikapcsolva');
      setText('ssOverviewAutoSub',settings.auto_sync_mode==='scheduled'?'Időzített szinkron':'Kártya megjelenésekor');
      setText('ssCurrentSchedule',scheduleSummaryText(settings));
      setText('ssTotalFiles',String(data.total_files||0));
      setText('ssWorkFiles',String(data.work_files||0));
      setText('ssProcessedFiles',String(data.processed_files||0));
      setText('ssDownloaded',String(data.downloaded||0));
      setText('ssCurrentFile',`Aktuális: ${data.current_file||'—'}  •  Változatlan: ${data.unchanged||0}  •  Hibák: ${data.errors||0}`);
      const bar=document.getElementById('ssProgressBar');
      if(bar)bar.style.width=`${Math.max(0,Math.min(100,Number(data.progress)||0))}%`;
      setPipeline(Number(data.progress)||0,data.phase,running,!!error);
      document.querySelectorAll('[data-ss-action="sync"],[data-ss-action="backup"]').forEach(btn=>btn.disabled=running);
      setText('ssNextRun',settings.auto_sync_enabled?(data.next_run?`Következő futás: ${fmtTime(data.next_run)}`:(settings.auto_sync_mode==='card_available'?'Következő futás: amikor az ez Share elérhető':'Következő futás számítása…')):'Következő futás: Kikapcsolva');
      renderHistory(data.history||[]);
    }

    let statusRequest=null;
    async function refreshSleepSyncStatus(silent=true){
      if(statusRequest)return statusRequest;
      statusRequest=(async()=>{
        try{
          const data=await ssApi('/api/sleepsync/status');
          renderStatus(data);
          return data;
        }catch(err){
          if(!silent)showSleepSyncNotice('error','SleepSync hiba',err.message);
          return null;
        }finally{
          statusRequest=null;
        }
      })();
      return statusRequest;
    }

    async function loadHistoryAndLog(){
      try{
        const [history,log]=await Promise.all([ssApi('/api/sleepsync/history'),ssApi('/api/sleepsync/log')]);
        renderHistory(history.rows||[]);
        const pre=document.getElementById('ssTechnicalLog');
        if(pre)pre.textContent=log.text||'Még nincs műszaki napló.';
      }catch(err){
        showSleepSyncNotice('error','Előzmények nem tölthetők be',err.message);
      }
    }

    function renderTimes(values){
      const box=document.getElementById('ssTimeList');
      if(!box)return;
      const times=Array.isArray(values)&&values.length?values:['09:00'];
      box.innerHTML=times.map((v,i)=>`<div class="ss-time-row"><input class="ssScheduleTime" type="time" value="${esc(v)}"><button type="button" data-remove-time="${i}" ${times.length===1?'disabled':''}>Törlés</button></div>`).join('');
      box.querySelectorAll('[data-remove-time]').forEach(btn=>btn.onclick=()=>{
        btn.parentElement?.remove();
        const left=box.querySelectorAll('.ssScheduleTime');
        if(left.length===1)box.querySelector('[data-remove-time]')?.setAttribute('disabled','');
      });
    }

    async function loadSettings(){
      try{
        const cfg=await ssApi('/api/sleepsync/settings');
        const auto=document.getElementById('ssAutoEnabled');
        if(auto)auto.checked=!!cfg.auto_sync_enabled;
        const mode=document.getElementById('ssScheduleMode');
        if(mode)mode.value=cfg.auto_sync_mode||'card_available';
        document.querySelectorAll('#ssScheduleDays [data-day]').forEach(input=>input.checked=(cfg.schedule_days||[]).includes(input.dataset.day));
        renderTimes(cfg.schedule_times||['09:00']);
        setText('ssCurrentSchedule',scheduleSummaryText(cfg));
        const therapy=document.getElementById('ssTherapyDir');
        const backup=document.getElementById('ssBackupDir');
        const buffer=document.getElementById('ssBufferDays');
        const wait=document.getElementById('ssStabilityWait');
        if(therapy)therapy.value=cfg.therapy_data_dir||'';
        if(backup)backup.value=cfg.backup_root||'';
        if(buffer)buffer.value=String(cfg.buffer_days??2);
        if(wait)wait.value=String(cfg.stability_wait_seconds??4);
        updateScheduleVisibility();
        await refreshWifi(true);
      }catch(err){
        showSleepSyncNotice('error','Beállítások nem tölthetők be',err.message);
      }
    }

    function updateScheduleVisibility(){
      const mode=document.getElementById('ssScheduleMode');
      document.getElementById('ssCardSchedule')?.classList.toggle('hidden',mode?.value!=='card_available');
      document.getElementById('ssTimedSchedule')?.classList.toggle('hidden',mode?.value!=='scheduled');
    }

    let settingsSaving=false;
    async function saveSettings(){
      if(settingsSaving)return;
      settingsSaving=true;
      const buttons=[...document.querySelectorAll('[data-ss-action="save-settings"]')];
      const status=document.getElementById('ssSettingsSaveStatus');
      buttons.forEach(btn=>{btn.disabled=true;btn.dataset.oldText=btn.textContent;btn.textContent='Mentés…';});
      if(status){status.className='ss-save-status working';status.textContent='Beállítások mentése…';}
      try{
        const days=[...document.querySelectorAll('#ssScheduleDays [data-day]:checked')].map(x=>x.dataset.day);
        const times=[...document.querySelectorAll('.ssScheduleTime')].map(x=>x.value).filter(Boolean);
        const fallbacks=[...document.querySelectorAll('#ssWifiBox [data-wifi]:checked')].map(x=>x.dataset.wifi);
        const payload={
          auto_sync_enabled:!!document.getElementById('ssAutoEnabled')?.checked,
          auto_sync_mode:document.getElementById('ssScheduleMode')?.value||'card_available',
          schedule_days:days,
          schedule_times:times,
          therapy_data_dir:document.getElementById('ssTherapyDir')?.value||'',
          backup_root:document.getElementById('ssBackupDir')?.value||'',
          buffer_days:Number(document.getElementById('ssBufferDays')?.value||2),
          stability_wait_seconds:Number(document.getElementById('ssStabilityWait')?.value||4),
          internet_wifi_fallbacks:fallbacks
        };
        const result=await ssApi('/api/sleepsync/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
        if(status){status.className='ss-save-status success';status.textContent='✓ Beállítások mentve és azonnal érvényesek.';}
        showSleepSyncNotice('success','SleepSync beállítások mentve','Az új szinkron- és ütemezési beállítások azonnal érvényesek.');
        await refreshSleepSyncStatus(true);
        return result;
      }catch(err){
        if(status){status.className='ss-save-status error';status.textContent=`Hiba: ${err.message}`;}
        throw err;
      }finally{
        buttons.forEach(btn=>{btn.disabled=false;btn.textContent=btn.dataset.oldText||'Mentés';delete btn.dataset.oldText;});
        settingsSaving=false;
      }
    }

    async function refreshWifi(silent=false){
      try{
        const data=await ssApi('/api/sleepsync/wifi');
        const box=document.getElementById('ssWifiBox');
        if(!box)return;
        if(!data.choices?.length){
          box.innerHTML='<span>Jelenleg nincs választható, látható és mentett internetes Wi-Fi hálózat.</span>';
          return;
        }
        const selected=new Set((data.selected||[]).map(x=>String(x).toLowerCase()));
        box.innerHTML=data.choices.map(name=>`<label class="ss-checkline"><input type="checkbox" data-wifi="${esc(name)}" ${selected.has(String(name).toLowerCase())?'checked':''}> <span>${esc(name)}</span></label>`).join('');
      }catch(err){
        if(!silent)showSleepSyncNotice('error','Wi-Fi lista hiba',err.message);
      }
    }

    async function runSync(){
      setSleepSyncTab('sync');
      showSleepSyncNotice('info','Szinkronizálás indul','A SleepSync átveszi az ez Share kapcsolatot és ellenőrzi a kártyát.');
      try{
        const start=await ssApi('/api/sleepsync/start',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
        const job=await pollJob(start.job,renderJobProgress);
        const result=job.result||{};
        if(Number(result.checked_files||0)<=0)throw new Error('Érvénytelen szinkroneredmény: 0 ellenőrzött fájl.');
        showSleepSyncNotice('success','Szinkronizálás kész',`Ellenőrizve: ${result.checked_files} • frissítve: ${result.downloaded||0} • változatlan: ${result.unchanged||0} • hiba: ${result.errors||0}`);
        await refreshSleepSyncStatus(true);
      }catch(err){
        showSleepSyncNotice('error','A szinkronizálás nem sikerült',err.message);
        await refreshSleepSyncStatus(true);
      }
    }

    async function runSdBackup(){
      setSleepSyncTab('sync');
      showSleepSyncNotice('info','Teljes SD mentés indul','A SleepSync dátumozott SD-pillanatképet és ZIP-et készít.');
      try{
        const start=await ssApi('/api/sleepsync/backup',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
        const job=await pollJob(start.job,renderJobProgress);
        const result=job.result||{};
        showSleepSyncNotice('success','Teljes SD mentés kész',`ZIP: ${result.zip_path||'elkészült'} • frissítve: ${result.successful||0} • újrahasznált: ${result.skipped||0}`);
        await refreshSleepSyncStatus(true);
      }catch(err){
        showSleepSyncNotice('error','A teljes SD mentés nem sikerült',err.message);
        await refreshSleepSyncStatus(true);
      }
    }

    async function openHostFolder(kind){
      try{
        const result=await ssApi('/api/sleepsync/open-folder',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind})});
        showSleepSyncNotice('success','Mappa megnyitva',result.path||'A Windows gazdagépen megnyílt.');
      }catch(err){
        showSleepSyncNotice('error','A mappa nem nyitható meg',err.message);
      }
    }

    async function importSdBackup(file){
      if(!file)return;
      const info=document.getElementById('ssSdBackupInfo');
      try{
        if(info)info.textContent=`SleepSync SD backup feltöltése: ${file.name}`;
        const start=await ssApi('/api/import/zip/create',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
        const upload=await fetch(start.upload_url,{method:'PUT',headers:{'Content-Type':'application/zip'},body:file});
        const uploadBody=await upload.json().catch(()=>({}));
        if(!upload.ok)throw new Error(uploadBody.error||`Feltöltési hiba: HTTP ${upload.status}`);
        const job=await pollJob(start.job,row=>{if(info)info.textContent=`${row.phase||'Beolvasás'} • ${row.progress||0}% • ${row.message||''}`;});
        if(info)info.textContent=`Beolvasva. Terápiás napok: ${job.result?.days??'—'}.`;
        showSleepSyncNotice('success','Teljes SD mentés beolvasva','A ZIP terápiás adatait a SleepMate feldolgozta.');
        await refreshSleepSyncStatus(true);
      }catch(err){
        if(info)info.textContent=`Hiba: ${err.message}`;
        showSleepSyncNotice('error','Az SD mentés beolvasása nem sikerült',err.message);
      }finally{
        const input=document.getElementById('ssSdImportFile');
        if(input)input.value='';
      }
    }

    function setSleepSyncTab(tab){
      document.querySelectorAll('[data-sleepsync-tab]').forEach(btn=>btn.classList.toggle('active',btn.dataset.sleepsyncTab===tab));
      document.querySelectorAll('[data-sleepsync-panel]').forEach(panel=>panel.classList.toggle('active',panel.dataset.sleepsyncPanel===tab));
      if(tab==='history')loadHistoryAndLog();
      if(tab==='settings'||tab==='sync')loadSettings();
    }

    let bound=false;
    function bindSleepSyncUi(){
      if(bound)return;
      bound=true;
      document.querySelectorAll('[data-sleepsync-tab]').forEach(btn=>btn.onclick=()=>setSleepSyncTab(btn.dataset.sleepsyncTab));
      document.querySelectorAll('[data-sleepsync-tab-jump]').forEach(btn=>btn.onclick=()=>setSleepSyncTab(btn.dataset.sleepsyncTabJump));
      document.getElementById('ssScheduleMode')?.addEventListener('change',updateScheduleVisibility);
      document.getElementById('ssAddTime')?.addEventListener('click',()=>{
        const box=document.getElementById('ssTimeList');
        if(!box)return;
        const row=document.createElement('div');
        row.className='ss-time-row';
        row.innerHTML='<input class="ssScheduleTime" type="time" value="09:00"><button type="button">Törlés</button>';
        row.querySelector('button').onclick=()=>row.remove();
        box.appendChild(row);
      });
      document.querySelectorAll('[data-ss-action]').forEach(btn=>btn.onclick=async()=>{
        const action=btn.dataset.ssAction;
        if(action==='sync')return runSync();
        if(action==='backup')return runSdBackup();
        if(action==='folder')return openHostFolder('data');
        if(action==='backup-folder')return openHostFolder('backup');
        if(action==='log-folder')return openHostFolder('log');
        if(action==='save-settings'){
          try{await saveSettings();}catch(err){showSleepSyncNotice('error','A beállítások nem menthetők',err.message);}
          return;
        }
        if(action==='wifi-refresh')return refreshWifi(false);
        if(action==='clear-history'){
          try{
            await ssApi('/api/sleepsync/history/clear',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
            await loadHistoryAndLog();
            showSleepSyncNotice('success','Előzmények törölve','A SleepSync futási előzményei kiürültek.');
          }catch(err){showSleepSyncNotice('error','Az előzmények nem törölhetők',err.message);}
          return;
        }
        if(action==='copy-log'){
          const text=document.getElementById('ssTechnicalLog')?.textContent||'';
          try{await navigator.clipboard.writeText(text);showSleepSyncNotice('success','Napló kimásolva','A műszaki napló a vágólapra került.');}
          catch(err){showSleepSyncNotice('error','A másolás nem sikerült',err.message);}
        }
      });
      document.getElementById('ssSdImportChoose')?.addEventListener('click',()=>document.getElementById('ssSdImportFile')?.click());
      document.getElementById('ssSdImportFile')?.addEventListener('change',e=>importSdBackup(e.target.files?.[0]));
    }

    function showSleepSyncPage(){
      ensureSleepSyncUi();
      document.querySelectorAll('.page').forEach(x=>x.classList.toggle('active',x.id==='page-sleepsync'));
      document.querySelectorAll('.nav-item').forEach(x=>x.classList.toggle('active',x.dataset.page==='sleepsync'));
      const title=document.getElementById('pageTitle');
      const subtitle=document.getElementById('pageSubtitle');
      if(title)title.textContent='SleepSync';
      if(subtitle)subtitle.textContent='Tartsd szinkronban a terápiád';
      document.getElementById('refresh')?.classList.add('sleepsync-hidden-action');
      try{window.updateMobileBottomNav?.('sleepsync')}catch{}
      refreshSleepSyncStatus(false);
    }

    function restoreCoreHeader(){
      document.getElementById('refresh')?.classList.remove('sleepsync-hidden-action');
    }

    function integrationRoute(){
      const raw=(location.hash||'#dashboard').slice(1);
      const pageRaw=raw.split('/')[0];
      if(pageRaw==='sleepsync'){showSleepSyncPage();return;}
      restoreCoreHeader();
      coreRoute();
    }

    function integrationNavigate(page,day=null){
      if(page!=='sleepsync')return coreNavigate(page,day);
      if(typeof window.clearTrendHover==='function')try{window.clearTrendHover()}catch{}
      const next='#sleepsync';
      const standalone=typeof window.standalonePwa==='function'&&window.standalonePwa();
      if(standalone){history.replaceState({sleepmate:true},'',next);integrationRoute();}
      else location.hash=next;
    }

    ensureSleepSyncUi();
    window.__sleepSyncUiReady=true;
    document.dispatchEvent(new CustomEvent('sleepmate:sleepsync-ready'));
    window.removeEventListener('hashchange',coreRoute);
    window.navigate=integrationNavigate;
    window.route=integrationRoute;
    window.addEventListener('hashchange',integrationRoute);
    setInterval(()=>{
      if(document.visibilityState==='visible'&&location.hash.startsWith('#sleepsync'))refreshSleepSyncStatus(true);
    },2000);
    integrationRoute();
  };
  document.head.appendChild(core);
})();
