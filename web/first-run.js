(function(){
  'use strict';

  const TOTAL=6;
  const state={step:1,status:null,config:null,sleepsync:null,remote:null,ai:null,choices:{remote_mode:'local'}};
  const $=(s,r=document)=>r.querySelector(s);
  const $$=(s,r=document)=>[...r.querySelectorAll(s)];

  function addStyle(){
    if(document.querySelector('link[data-sleepmate-first-run]'))return;
    const link=document.createElement('link');
    link.rel='stylesheet';link.href='/first-run.css?v=4';link.dataset.sleepmateFirstRun='1';
    document.head.appendChild(link);
  }
  async function request(url,options={}){
    const opts={cache:'no-store',...options};
    if(opts.body&&typeof opts.body!=='string'&&!(opts.body instanceof Blob)){opts.headers={...(opts.headers||{}),'Content-Type':'application/json'};opts.body=JSON.stringify(opts.body)}
    const r=await fetch(url,opts);const ct=(r.headers.get('content-type')||'').toLowerCase();const data=ct.includes('json')?await r.json():{text:await r.text()};
    if(!r.ok||data?.error)throw new Error(data?.error||`HTTP ${r.status}`);return data;
  }
  function message(text='',type='info'){
    const el=$('#frMessage');if(!el)return;el.textContent=text;el.className='fr-message'+(text?` show ${type}`:'');
  }
  function busy(on,label='Dolgozom…'){
    const next=$('#frNext');if(next){next.disabled=!!on;if(on){next.dataset.old=next.textContent;next.textContent=label}else if(next.dataset.old){next.textContent=next.dataset.old;delete next.dataset.old}}
    $$('.fr-btn[data-busy-lock]').forEach(b=>b.disabled=!!on);
  }
  function choicePatch(patch){state.choices={...state.choices,...patch}}
  async function persistProgress(step=state.step){
    try{await request('/api/onboarding/state',{method:'POST',body:{action:'progress',step,choices:state.choices}})}catch{}
  }

  function shell(){
    if($('#sleepmateFirstRun'))return $('#sleepmateFirstRun');
    const root=document.createElement('div');root.id='sleepmateFirstRun';root.className='fr-hidden';
    root.innerHTML=`
      <div class="fr-shell" role="dialog" aria-modal="true" aria-labelledby="frTitle">
        <header class="fr-top">
          <div class="fr-brand"><div><b>SleepMate</b><small>Első beállítás</small></div></div>
          <div class="fr-progress" aria-label="Beállítás folyamata">${Array.from({length:TOTAL},(_,i)=>`<i data-progress="${i+1}"></i>`).join('')}</div>
          <div class="fr-step-count"><span id="frStepNum">1</span> / ${TOTAL}</div>
        </header>
        <main class="fr-body">
          <div id="frMessage" class="fr-message"></div>

          <section class="fr-panel" data-step="1">
            <span class="fr-kicker">Első indítás</span>
            <h1 class="fr-title" id="frTitle">Rakjuk össze a <span class="fr-highlight">SleepMate-et</span> úgy, ahogy használni szeretnéd.</h1>
            <p class="fr-lead">A program már telepítve van. Itt azokat a dolgokat állítjuk be, amelyek gépenként vagy felhasználónként eltérnek: terápiás adatok, SleepSync, távoli elérés, backup és opcionális AI.</p>
            <div class="fr-grid three">
              <div class="fr-card"><div class="fr-icon">🗂️</div><h3>Saját adatok</h3><p>A terápiás adatok helyben maradnak, a SleepMate saját kezelt adattárában dolgozik velük.</p></div>
              <div class="fr-card"><div class="fr-icon">🔒</div><h3>Biztonságos elérés</h3><p>Tailscale vagy Cloudflare csak akkor kerül beállításra, ha te kéred.</p></div>
              <div class="fr-card"><div class="fr-icon">✨</div><h3>Később is módosítható</h3><p>Ezt a varázslót a Beállításokból bármikor újra megnyithatod.</p></div>
            </div>
          </section>

          <section class="fr-panel" data-step="2">
            <span class="fr-kicker">2. lépés · Terápiás adatok</span>
            <h1 class="fr-title">Hol legyen a CPAP-adatok <span class="fr-highlight">forrása?</span></h1>
            <p class="fr-lead">Ez lehet egy ResMed SD-kártyáról készített mappa, hálózati könyvtár vagy a SleepSync által frissített terápiás mappa. A forrást a SleepMate csak olvassa.</p>
            <div class="fr-field"><label>Alapértelmezett beolvasási mappa</label><div class="fr-input-row"><input class="fr-input" id="frDataDir" placeholder="C:\\Users\\...\\Documents\\CPAP_mentes"><button class="fr-btn" id="frBrowseData" type="button">Tallózás…</button></div></div>
            <label class="fr-check"><input id="frAutoScan" type="checkbox" checked><span><b>Automatikus változásellenőrzés</b><br><small>A SleepMate időszakosan ellenőrzi a forrásmappát, és csak a tényleges változásokat dolgozza fel.</small></span></label>
            <div class="fr-note">Ha még nincs kész adatforrásod, ezt a lépést nyugodtan hagyd változatlanul. Később a Beállítások → Adatforrás résznél módosítható.</div>
          </section>

          <section class="fr-panel" data-step="3">
            <span class="fr-kicker">3. lépés · SleepSync</span>
            <h1 class="fr-title">Kéred az <span class="fr-highlight">automatikus ez Share</span> szinkront?</h1>
            <p class="fr-lead">A SleepSync az ez Share Wi-Fi kártyáról biztonságosan letölti a ResMed SD változásait, majd átadja azokat a SleepMate saját importmotorjának.</p>
            <div class="fr-grid">
              <div class="fr-card"><div class="fr-icon">↻</div><h3>SleepSync motor</h3><p>A program része, külön alkalmazást nem kell telepíteni.</p></div>
              <div class="fr-card"><div class="fr-icon">📶</div><h3>Wi-Fi profil</h3><p>Az ez Share hálózatnak a Windowsban egyszer már elmentett Wi-Fi profilként kell szerepelnie.</p></div>
            </div>
            <label class="fr-check"><input id="frSleepSync" type="checkbox"><span><b>Automatikus SleepSync bekapcsolása</b><br><small>Az időzítést és a napokat később a SleepSync → Beállítások résznél finomíthatod.</small></span></label>
            <div class="fr-note warn">Az automatikus szinkron csak akkor működik, amikor az ez Share kártya elérhető és a Windows Wi-Fi adaptere használható.</div>
          </section>

          <section class="fr-panel" data-step="4">
            <span class="fr-kicker">4. lépés · Távoli elérés</span>
            <h1 class="fr-title">Honnan szeretnéd elérni a <span class="fr-highlight">SleepMate-et?</span></h1>
            <p class="fr-lead">A SleepMate backend továbbra is csak a saját gépen, a 127.0.0.1 címen figyel. A távoli elérés reverse proxyval történik, így nem nyitunk közvetlen bejövő portot.</p>
            <div class="fr-choice-grid">
              <label class="fr-choice"><input type="radio" name="frRemote" value="local" checked><span><div class="fr-icon">💻</div><b>Csak ezen a gépen</b><small>Sem Tailscale, sem Cloudflare nem szükséges.</small></span></label>
              <label class="fr-choice"><input type="radio" name="frRemote" value="tailscale"><span><div class="fr-icon">🔐</div><b>Tailscale</b><small>Privát HTTPS elérés a saját tailneteden. Telefonhoz ezt ajánljuk.</small></span></label>
              <label class="fr-choice"><input type="radio" name="frRemote" value="cloudflare"><span><div class="fr-icon">☁️</div><b>Cloudflare Tunnel</b><small>Saját domain + Zero Trust / Access védelemmel.</small></span></label>
            </div>

            <div class="fr-remote-detail" data-remote="tailscale">
              <div class="fr-subsection"><div class="fr-subsection-head"><b>Tailscale kliens</b><span id="frTsState" class="fr-status-pill">Ellenőrzés…</span></div><p class="fr-lead" style="font-size:13px;margin-bottom:8px">Ha nincs telepítve, a SleepMate a hivatalos <b>Tailscale.Tailscale</b> winget csomagot telepíti. A Tailscale-fiókba a saját Tailscale ablakában jelentkezel be.</p><div class="fr-actions"><button class="fr-btn primary" id="frTsInstall" type="button" data-busy-lock>Tailscale telepítése</button><button class="fr-btn" id="frRemoteRefresh" type="button">Állapot frissítése</button><button class="fr-btn success" id="frTsEnable" type="button" data-busy-lock>SleepMate HTTPS bekapcsolása</button></div><div id="frTsUrlBox" class="fr-url" hidden><code id="frTsUrl"></code><button class="fr-btn" id="frTsOpen" type="button">Megnyitás</button></div><img id="frTsQr" class="fr-qr" alt="Tailscale QR-kód" hidden></div>
            </div>

            <div class="fr-remote-detail" data-remote="cloudflare">
              <div class="fr-subsection"><div class="fr-subsection-head"><b>Cloudflare Tunnel</b><span id="frCfState" class="fr-status-pill">Ellenőrzés…</span></div><p class="fr-lead" style="font-size:13px;margin-bottom:8px">A cloudflared kliens telepíthető innen. A Cloudflare-fiók, domain és Zero Trust szabály a te Cloudflare környezetedben marad.</p><div class="fr-actions"><button class="fr-btn primary" id="frCfInstall" type="button" data-busy-lock>cloudflared telepítése</button><button class="fr-btn" id="frCfRefresh" type="button">Állapot frissítése</button></div>
                <div class="fr-field"><label>Publikus hostname</label><input id="frCfHost" class="fr-input" placeholder="sleepmate.pelda.hu"><small id="frCfHostOrigin" class="fr-saved-origin" hidden>Korábban mentett SleepMate-beállítás.</small></div>
                <label class="fr-check"><input id="frCfAccess" type="checkbox"><span><b>Cloudflare Access / Zero Trust védelem be van állítva</b><br><small>A SleepMate biztonsági okból enélkül nem indítja el a saját tunnel folyamatát.</small></span></label>
                <div class="fr-field"><label>Tunnel token <small style="color:#8190a8">(csak ha a SleepMate indítja a tunnelt)</small></label><input id="frCfToken" type="password" class="fr-input" autocomplete="off" placeholder="A token titkosítva, DPAPI-val kerül mentésre"></div>
                <label class="fr-check"><input id="frCfStart" type="checkbox"><span><b>Tunnel indítása most</b><br><small>Csak a fenti hostname és Access-visszaigazolás után.</small></span></label>
              </div>
            </div>
          </section>

          <section class="fr-panel" data-step="5">
            <span class="fr-kicker">5. lépés · Extrák</span>
            <h1 class="fr-title">Backup és <span class="fr-highlight">AI</span>.</h1>
            <p class="fr-lead">Mindkettő opcionális. Itt bekapcsolhatod a heti automatikus biztonsági mentést, illetve megadhatod a helyben, DPAPI-val titkosított AI API-kulcsokat.</p>
            <div class="fr-grid single">
              <div class="fr-card"><div class="fr-icon">🛟</div><h3>Automatikus backup</h3><p>Alapértelmezés szerint heti teljes SleepMate biztonsági mentést tudunk bekapcsolni.</p><label class="fr-check"><input id="frBackup" type="checkbox"><span>Heti automatikus backup bekapcsolása</span></label></div>
            </div>
            <div class="fr-subsection"><div class="fr-subsection-head"><b>AI összegzés – opcionális</b><span class="fr-status-pill">helyben titkosított kulcsok</span></div><div class="fr-grid">
              <div class="fr-field"><label>Luna · Google Gemini API-kulcs</label><input id="frGemini" class="fr-input" type="password" autocomplete="off" placeholder="Hagyd üresen, ha később állítod be"></div>
              <div class="fr-field"><label>Milo · Groq API-kulcs</label><input id="frGroq" class="fr-input" type="password" autocomplete="off" placeholder="Hagyd üresen, ha később állítod be"></div>
            </div><div class="fr-note">Az API-kulcsok a Windows felhasználói fiókjához kötött DPAPI titkosítással kerülnek helyben tárolásra. Google Drive backupot később a Beállításokban kapcsolhatsz hozzá.</div></div>
          </section>

          <section class="fr-panel" data-step="6">
            <span class="fr-kicker">6. lépés · Kész</span>
            <h1 class="fr-title">A SleepMate <span class="fr-highlight">használatra kész.</span></h1>
            <p class="fr-lead">Az összes beállítás később módosítható. A varázsló semmilyen API-kulcsot vagy tunnel tokent nem tárol a saját állapotfájljában; csak azt jegyzi meg, hogy mely lépéseket választottad.</p>
            <div id="frSummary" class="fr-summary"></div>
            <div class="fr-note" style="margin-top:18px">A SleepMate nem orvosi diagnosztikai szoftver. A terápiás adatok értelmezése nem helyettesíti az orvosi vizsgálatot vagy terápiás döntést.</div>
          </section>
        </main>
        <footer class="fr-footer"><div class="fr-footer-left"><button class="fr-btn" id="frBack" type="button">Vissza</button><button class="fr-btn" id="frSkip" type="button">Most kihagyom</button></div><small id="frFooterHint">Minden később módosítható.</small><div class="fr-footer-right"><button class="fr-btn primary" id="frNext" type="button">Tovább</button></div></footer>
      </div>`;
    document.body.appendChild(root);bind(root);return root;
  }

  function selectedRemote(){return $('input[name="frRemote"]:checked')?.value||'local'}
  function updateRemotePanels(){const mode=selectedRemote();state.choices.remote_mode=mode;$$('.fr-remote-detail').forEach(x=>x.classList.toggle('active',x.dataset.remote===mode))}
  function setPill(el,text,kind=''){if(!el)return;el.textContent=text;el.className='fr-status-pill'+(kind?` ${kind}`:'')}

  async function loadRemote(showError=false){
    try{
      state.remote=await request('/api/remote/status');const t=state.remote.tailscale||{},c=state.remote.cloudflare||{};
      setPill($('#frTsState'),!t.installed?'Nincs telepítve':t.serve_active&&t.url?'HTTPS kész':t.online?'Bejelentkezve':'Telepítve · belépés kell',t.serve_active&&t.url?'ok':t.installed?'warn':'');
      $('#frTsInstall').disabled=!!t.installed;$('#frTsEnable').disabled=!t.installed||!t.online||!!t.serve_active;
      const tsUrl=t.url||t.setup_url||'';$('#frTsUrlBox').hidden=!tsUrl;$('#frTsUrl').textContent=tsUrl;$('#frTsQr').hidden=!(t.serve_active&&t.url);if(t.serve_active&&t.url)$('#frTsQr').src=`/api/remote/tailscale/qr?_=${Date.now()}`;
      setPill($('#frCfState'),!c.installed?'Nincs telepítve':c.running?'Tunnel fut':'Telepítve',c.running?'ok':c.installed?'warn':'');$('#frCfInstall').disabled=!!c.installed;
      if(!$('#frCfHost').value)$('#frCfHost').value=c.hostname||state.config?.cloudflare_hostname||'';
      $('#frCfAccess').checked=!!(c.access_confirmed||state.config?.cloudflare_access_confirmed);
      choicePatch({tailscale_installed:!!t.installed,cloudflare_installed:!!c.installed});return state.remote;
    }catch(e){if(showError)message(`Távoli elérés ellenőrzési hiba: ${e.message}`,'error');return null}
  }

  function setStep(step){
    state.step=Math.max(1,Math.min(TOTAL,Number(step)||1));message();$$('.fr-panel').forEach(x=>x.classList.toggle('active',Number(x.dataset.step)===state.step));$$('[data-progress]').forEach(x=>x.classList.toggle('done',Number(x.dataset.progress)<=state.step));$('#frStepNum').textContent=state.step;$('#frBack').style.visibility=state.step===1?'hidden':'visible';$('#frSkip').style.display=state.step===6?'none':'';$('#frNext').textContent=state.step===6?'Kezdjük':'Tovább';
    if(state.step===4)loadRemote(false);if(state.step===6)renderSummary();
    const body=$('.fr-body');if(body)body.scrollTop=0;persistProgress(state.step);
  }

  async function saveStep2(){
    const val=$('#frDataDir').value.trim(),patch={auto_scan_enabled:$('#frAutoScan').checked};
    if(val&&val!==(state.config?.data_dir||''))patch.data_dir=val;
    const r=await request('/api/settings',{method:'POST',body:patch});state.config={...(state.config||{}),...r};choicePatch({data_source_configured:!!val});
  }
  async function saveStep3(){const enabled=$('#frSleepSync').checked;state.sleepsync=await request('/api/sleepsync/settings',{method:'POST',body:{auto_sync_enabled:enabled}});choicePatch({sleepsync_enabled:enabled})}
  async function saveStep4(){
    const mode=selectedRemote();choicePatch({remote_mode:mode});
    if(mode==='local')return;
    await loadRemote(false);
    if(mode==='tailscale'){
      if(!state.remote?.tailscale?.installed){message('A Tailscale telepítése…','info');await request('/api/remote/install',{method:'POST',body:{component:'tailscale'}});await loadRemote(false)}
      const t=state.remote?.tailscale||{};
      if(t.installed&&t.online&&!t.serve_active){try{await request('/api/remote/tailscale',{method:'POST',body:{action:'enable'}});await loadRemote(false)}catch(e){message(`A Tailscale települt, de a HTTPS még nem kapcsolható be: ${e.message}`,'info')}}
      choicePatch({tailscale_installed:!!state.remote?.tailscale?.installed});return;
    }
    if(mode==='cloudflare'){
      if(!state.remote?.cloudflare?.installed){message('A cloudflared telepítése…','info');await request('/api/remote/install',{method:'POST',body:{component:'cloudflare'}});await loadRemote(false)}
      const host=$('#frCfHost').value.trim(),token=$('#frCfToken').value.trim(),confirmed=$('#frCfAccess').checked;
      if(host||token||confirmed){await request('/api/remote/config',{method:'POST',body:{cloudflare_hostname:host,cloudflare_access_confirmed:confirmed,cloudflare_token:token}});$('#frCfToken').value='';state.config={...(state.config||{}),cloudflare_hostname:host,cloudflare_access_confirmed:confirmed}}
      if($('#frCfStart').checked){if(!host)throw new Error('A tunnel indításához add meg a Cloudflare hostnevet.');if(!confirmed)throw new Error('A tunnel indításához igazold a Cloudflare Access / Zero Trust védelmet.');await request('/api/remote/cloudflare',{method:'POST',body:{action:'start'}})}
      await loadRemote(false);choicePatch({cloudflare_installed:!!state.remote?.cloudflare?.installed});
    }
  }
  async function saveStep5(){
    const backup=$('#frBackup').checked;await request('/api/settings',{method:'POST',body:{auto_backup_enabled:backup}});choicePatch({backup_enabled:backup});
    const gemini=$('#frGemini').value.trim(),groq=$('#frGroq').value.trim();if(gemini||groq){const payload={};if(gemini)payload.gemini_api_key=gemini;if(groq)payload.groq_api_key=groq;state.ai=await request('/api/ai/config',{method:'POST',body:payload});$('#frGemini').value='';$('#frGroq').value=''}
    const providers=state.ai?.providers||{};choicePatch({gemini_configured:!!providers.gemini?.configured||!!gemini,groq_configured:!!providers.groq?.configured||!!groq});
  }

  async function next(){
    if(state.step===6){await finish(false);return}
    busy(true,'Mentés…');message();
    try{if(state.step===2)await saveStep2();if(state.step===3)await saveStep3();if(state.step===4)await saveStep4();if(state.step===5)await saveStep5();setStep(state.step+1)}catch(e){message(e.message,'error')}finally{busy(false)}
  }
  async function finish(skipped){
    busy(true,'Befejezés…');
    try{await request('/api/onboarding/state',{method:'POST',body:{action:'complete',step:6,choices:state.choices}});shell().classList.add('fr-hidden');document.documentElement.classList.remove('fr-open');if(!skipped&&typeof window.navigate==='function')try{window.navigate('dashboard')}catch{}}
    catch(e){message(e.message,'error')}finally{busy(false)}
  }

  function renderSummary(){
    const mode=state.choices.remote_mode||selectedRemote();const remoteLabel=mode==='tailscale'?'Tailscale':mode==='cloudflare'?'Cloudflare Tunnel':'Csak helyi használat';const rows=[
      ['🗂️','Adatforrás',state.choices.data_source_configured?'Beállítva':'Később állítható'],
      ['↻','SleepSync',state.choices.sleepsync_enabled?'Automatika bekapcsolva':'Kézi / később'],
      ['🔒','Távoli elérés',remoteLabel],
      ['🛟','Automatikus backup',state.choices.backup_enabled?'Bekapcsolva':'Kikapcsolva'],
      ['✨','Luna / Milo',state.choices.gemini_configured||state.choices.groq_configured?'Legalább egy AI beállítva':'Később állítható']
    ];$('#frSummary').innerHTML=rows.map(r=>`<div class="fr-summary-row"><b>${r[0]}</b><span>${r[1]}</span><small>${r[2]}</small></div>`).join('');
  }

  async function installRemote(component){busy(true,'Telepítés…');message(`${component==='tailscale'?'Tailscale':'cloudflared'} telepítése elindult…`,'info');try{const r=await request('/api/remote/install',{method:'POST',body:{component}});if(r.result?.manual_required&&r.result?.url){message('Az automatikus telepítés nem érhető el; megnyitom a hivatalos letöltési oldalt.','info');window.open(r.result.url,'_blank','noopener')}else message('Telepítés kész.','ok');await loadRemote(true)}catch(e){message(e.message,'error')}finally{busy(false)}}

  function bind(root){
    $('#frNext',root).onclick=next;$('#frBack',root).onclick=()=>setStep(state.step-1);$('#frSkip',root).onclick=()=>finish(true);
    $('#frBrowseData',root).onclick=async()=>{try{const r=await request('/api/system/pick-folder',{method:'POST',body:{user_initiated:true,initial_dir:$('#frDataDir').value.trim()}});if(r.folder)$('#frDataDir').value=r.folder}catch(e){message(e.message,'error')}};
    $$('input[name="frRemote"]',root).forEach(x=>x.onchange=updateRemotePanels);
    $('#frTsInstall',root).onclick=()=>installRemote('tailscale');$('#frCfInstall',root).onclick=()=>installRemote('cloudflare');$('#frRemoteRefresh',root).onclick=()=>loadRemote(true);$('#frCfRefresh',root).onclick=()=>loadRemote(true);$('#frCfHost',root).oninput=()=>{const origin=$('#frCfHostOrigin',root);if(origin)origin.hidden=true};
    $('#frTsEnable',root).onclick=async()=>{busy(true,'Bekapcsolás…');try{await request('/api/remote/tailscale',{method:'POST',body:{action:'enable'}});await loadRemote(true);message('Tailscale HTTPS elérés kész.','ok')}catch(e){message(e.message,'error')}finally{busy(false)}};
    $('#frTsOpen',root).onclick=()=>{const u=$('#frTsUrl').textContent.trim();if(u)window.open(u,'_blank','noopener')};
  }

  async function hydrate(){
    const results=await Promise.allSettled([request('/api/config'),request('/api/sleepsync/settings'),request('/api/remote/status'),request('/api/ai/config')]);
    state.config=results[0].status==='fulfilled'?results[0].value:{};state.sleepsync=results[1].status==='fulfilled'?results[1].value:{};state.remote=results[2].status==='fulfilled'?results[2].value:{};state.ai=results[3].status==='fulfilled'?results[3].value:{};
    $('#frDataDir').value=state.config.data_dir||'';$('#frAutoScan').checked=state.config.auto_scan_enabled!==false;$('#frSleepSync').checked=!!state.sleepsync.auto_sync_enabled;$('#frBackup').checked=!!state.config.auto_backup_enabled;const savedCfHost=String(state.config.cloudflare_hostname||'').trim();$('#frCfHost').value=savedCfHost;const cfOrigin=$('#frCfHostOrigin');if(cfOrigin)cfOrigin.hidden=!savedCfHost;$('#frCfAccess').checked=!!state.config.cloudflare_access_confirmed;
    const old=state.status?.choices||{};state.choices={...state.choices,...old,data_source_configured:!!state.config.data_dir,sleepsync_enabled:!!state.sleepsync.auto_sync_enabled,backup_enabled:!!state.config.auto_backup_enabled,gemini_configured:!!state.ai?.providers?.gemini?.configured,groq_configured:!!state.ai?.providers?.groq?.configured};
    if(old.remote_mode&&['local','tailscale','cloudflare'].includes(old.remote_mode)){const radio=$(`input[name="frRemote"][value="${old.remote_mode}"]`);if(radio)radio.checked=true}updateRemotePanels();await loadRemote(false);
  }

  async function open(force=false){
    addStyle();const root=shell();
    try{state.status=await request('/api/onboarding/status')}catch{return}
    if(state.status.completed&&!force){injectReopen();return}
    await hydrate();root.classList.remove('fr-hidden');document.documentElement.classList.add('fr-open');setStep(force?1:(state.status.last_step||1));
  }

  function injectReopen(){
    if($('#frSettingsReopen'))return true;const page=$('#page-settings');if(!page)return false;const box=document.createElement('section');box.id='frSettingsReopen';box.className='fr-settings-reopen';box.innerHTML='<b>Első beállítás varázsló</b><p>Újra végigvezet az adatforrás, SleepSync, távoli elérés, backup és AI alapbeállításain.</p><button type="button" class="fr-btn">Varázsló megnyitása</button>';box.querySelector('button').onclick=()=>open(true);page.appendChild(box);return true
  }

  window.openSleepMateFirstRun=()=>open(true);
  window.addEventListener('load',()=>{setTimeout(()=>open(false),650);let tries=0;const timer=setInterval(()=>{tries++;if(injectReopen()||tries>30)clearInterval(timer)},500)},{once:true});
})();
