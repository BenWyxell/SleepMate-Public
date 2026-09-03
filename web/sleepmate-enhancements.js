(function(){
  'use strict';

  const LOGO='/assets/sleepmate-icon-v410.webp';
  let recoveryBusy=false;
  let driveRestoreCandidate=null;

  // -------------------------------------------------------------------------
  // Trend markers: the old quadratic path used data points as control points,
  // so the visible curve did not actually pass through its own markers.
  // Catmull-Rom -> Bezier interpolation passes through every measurement point.
  // -------------------------------------------------------------------------
  window.traceSmooth=function(ctx,pts,move=true){
    if(!pts?.length)return;
    if(move)ctx.moveTo(pts[0].x,pts[0].y);else ctx.lineTo(pts[0].x,pts[0].y);
    if(pts.length===1)return;
    for(let i=0;i<pts.length-1;i++){
      const p0=pts[i-1]||pts[i],p1=pts[i],p2=pts[i+1],p3=pts[i+2]||p2;
      const cp1x=p1.x+(p2.x-p0.x)/6,cp1y=p1.y+(p2.y-p0.y)/6;
      const cp2x=p2.x-(p3.x-p1.x)/6,cp2y=p2.y-(p3.y-p1.y)/6;
      ctx.bezierCurveTo(cp1x,cp1y,cp2x,cp2y,p2.x,p2.y);
    }
  };

  // -------------------------------------------------------------------------
  // Daily PWA share image: keep the proven card renderer, then brand the PNG.
  // -------------------------------------------------------------------------
  function loadImage(src){return new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=()=>reject(new Error('A SleepMate logó nem tölthető be.'));img.src=src})}
  async function imageFromBlob(blob){const url=URL.createObjectURL(blob);try{return await loadImage(url)}finally{setTimeout(()=>URL.revokeObjectURL(url),0)}}
  const coreShareCard=window.createDailyShareCard;
  if(typeof coreShareCard==='function'){
    window.createDailyShareCard=async function(){
      const base=await coreShareCard();
      try{
        const [card,logo]=await Promise.all([imageFromBlob(base),loadImage(LOGO)]);
        const c=document.createElement('canvas');c.width=1080;c.height=card.naturalHeight||card.height||1350;
        const x=c.getContext('2d');x.drawImage(card,0,0,c.width,c.height);
        const size=142,pad=18,left=c.width-70-size,top=52;
        x.save();x.fillStyle='rgba(8,17,31,.72)';x.beginPath();x.roundRect(left-pad,top-pad,size+pad*2,size+pad*2,28);x.fill();x.globalAlpha=.96;x.drawImage(logo,left,top,size,size);x.restore();
        return await new Promise((res,rej)=>c.toBlob(b=>b?res(b):rej(new Error('A megosztási kép nem készíthető el.')),'image/png',.94));
      }catch(err){
        // Branding failure must never make the underlying share feature unusable.
        console.warn('SleepMate share logo skipped',err);return base;
      }
    };
  }

  // -------------------------------------------------------------------------
  // True offline/read-only mode. Network remains authoritative; the worker only
  // supplies cached GET data when the backend/upstream is genuinely unavailable.
  // -------------------------------------------------------------------------
  function ensureOfflineBanner(){
    let el=document.getElementById('offlineReadOnlyBanner');if(el)return el;
    el=document.createElement('section');el.id='offlineReadOnlyBanner';el.className='offline-readonly-banner hidden';
    el.innerHTML='<div><strong>Offline mód – csak olvasás</strong><span>A SleepMate szerver nem érhető el. A készüléken utoljára eltárolt adatokat látod.</span></div><button type="button" id="offlineRetryNow">Kapcsolat ellenőrzése</button>';
    const badge=document.getElementById('connectionBadge'),main=document.querySelector('.content-shell main');
    if(badge?.parentNode)badge.insertAdjacentElement('afterend',el);else main?.prepend(el);
    el.querySelector('#offlineRetryNow')?.addEventListener('click',()=>checkServerRecovery(true));
    return el;
  }
  function updateOfflineBanner(offline){
    const el=ensureOfflineBanner();el.classList.toggle('hidden',!offline);document.body.classList.toggle('sleepmate-offline',!!offline);
  }
  const coreConnectionState=window.setConnectionState;
  if(typeof coreConnectionState==='function'){
    window.setConnectionState=function(offline,stamp=null){const result=coreConnectionState(offline,stamp);updateOfflineBanner(!!offline);return result};
  }
  const coreApiWrite=window.apiWrite;
  if(typeof coreApiWrite==='function'){
    window.apiWrite=async function(...args){
      if(window.state?.connectionOffline){const e=new Error('Offline módban a SleepMate csak olvasható. A módosításhoz indítsd el vagy tedd újra elérhetővé a SleepMate szervert.');e.technical='Offline read-only guard';throw e}
      return coreApiWrite(...args);
    };
  }
  async function checkServerRecovery(force=false){
    if(recoveryBusy||(!force&&!window.state?.connectionOffline))return;
    recoveryBusy=true;const ctrl=typeof AbortController==='function'?new AbortController():null,t=ctrl?setTimeout(()=>ctrl.abort(),4000):null;
    try{
      const r=await fetch('/api/version?_live='+Date.now(),{cache:'no-store',signal:ctrl?.signal});
      const cached=r.headers.get('X-SleepMate-Offline')==='1';
      if(r.ok&&!cached){
        window.setConnectionState?.(false,new Date().toISOString());
        if(typeof window.refreshData==='function')window.refreshData().catch(()=>{});
      }else if(force&&window.state?.connectionOffline){updateOfflineBanner(true)}
    }catch{if(force)updateOfflineBanner(true)}finally{if(t)clearTimeout(t);recoveryBusy=false}
  }
  setInterval(()=>checkServerRecovery(false),12000);
  window.addEventListener('online',()=>checkServerRecovery(true));

  // -------------------------------------------------------------------------
  // Google Drive UI. OAuth is intentionally optional: SleepMate/local backup
  // keeps working even when Drive is not configured or has no internet.
  // -------------------------------------------------------------------------
  function installStyles(){
    if(document.getElementById('v511EnhancementStyle'))return;
    const s=document.createElement('style');s.id='v511EnhancementStyle';s.textContent=`
      .offline-readonly-banner{margin:0 0 14px;padding:12px 14px;border:1px solid rgba(85,183,255,.42);border-radius:12px;background:linear-gradient(135deg,rgba(36,88,121,.28),rgba(71,49,118,.24));display:flex;align-items:center;justify-content:space-between;gap:14px;box-shadow:0 8px 30px rgba(0,0,0,.16)}
      .offline-readonly-banner.hidden{display:none}.offline-readonly-banner div{display:grid;gap:3px}.offline-readonly-banner span{color:#9db1c3;font-size:12px}.sleepmate-offline [data-offline-write],.sleepmate-offline .drive-write-action{opacity:.55}
      .drive-card{position:relative;overflow:hidden}.drive-card:before{content:'';position:absolute;inset:-50% 45% 40% -20%;background:radial-gradient(circle,rgba(74,216,255,.14),transparent 62%);pointer-events:none}.drive-logo{background:linear-gradient(135deg,#4ad8ff,#43e6c4 48%,#7867ff)!important;color:#07121f!important;font-weight:900}.drive-form{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:14px}.drive-form label{display:grid;gap:5px;color:#9db1c3;font-size:12px}.drive-form label.drive-wide{grid-column:1/-1}.drive-form input{width:100%;box-sizing:border-box}.drive-actions{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:12px}.drive-help{margin-top:10px;color:#8fa7ba;font-size:12px;line-height:1.5}.drive-backup-list{display:grid;gap:8px;margin-top:12px}.drive-backup-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;align-items:center;padding:10px 12px;border:1px solid rgba(95,143,179,.25);border-radius:10px;background:rgba(8,17,31,.28)}.drive-backup-row strong{display:block;overflow:hidden;text-overflow:ellipsis}.drive-backup-row small{color:#91a6b8}.drive-inline-confirm{margin-top:10px;padding:11px;border:1px solid rgba(255,185,93,.38);border-radius:10px;background:rgba(113,77,28,.18)}.drive-inline-confirm.hidden{display:none}
      @media(max-width:700px){.drive-form{grid-template-columns:1fr}.drive-form label.drive-wide{grid-column:auto}.offline-readonly-banner{align-items:flex-start;flex-direction:column}.drive-backup-row{grid-template-columns:1fr}.drive-backup-row button{width:100%}}
    `;document.head.appendChild(s);
  }
  function driveFmtBytes(n){const v=Number(n||0);if(v<1024*1024)return Math.max(1,Math.round(v/1024))+' KB';return (v/1024/1024).toFixed(1).replace('.',',')+' MB'}
  function driveSetStatus(text,bad=false){for(const el of document.querySelectorAll('.drive-live-status')){el.textContent=text||'';el.classList.toggle('bad',!!bad)}}
  async function drivePollJob(jid,label){
    for(;;){const j=await window.api('/api/job/'+encodeURIComponent(jid));driveSetStatus(`${label}: ${j.phase||''}${j.message?' – '+j.message:''}`);if(j.status==='done')return j;if(j.status==='error')throw new Error(j.message||j.error||'A Google Drive művelet sikertelen.');await new Promise(r=>setTimeout(r,500))}
  }
  function driveRenderRows(rows){
    const box=document.getElementById('driveBackupList');if(!box)return;
    if(!rows?.length){box.innerHTML='<div class="empty-state">Még nincs SleepMate backup a Google Drive mappában.</div>';return}
    box.innerHTML=rows.map(r=>`<div class="drive-backup-row"><div><strong>${window.escapeHtml(r.name||'Backup')}</strong><small>${driveFmtBytes(r.size)}${r.created_at?' • '+new Date(r.created_at).toLocaleString('hu-HU'):''}</small></div><button type="button" class="drive-restore-pick drive-write-action" data-id="${window.escapeHtml(r.id||'')}" data-name="${window.escapeHtml(r.name||'')}">Visszaállítás</button></div>`).join('');
    box.querySelectorAll('.drive-restore-pick').forEach(btn=>btn.addEventListener('click',()=>{
      driveRestoreCandidate={id:btn.dataset.id,name:btn.dataset.name};const panel=document.getElementById('driveRestoreConfirm');panel?.classList.remove('hidden');const n=document.getElementById('driveRestoreName');if(n)n.textContent=driveRestoreCandidate.name;
    }));
  }
  async function loadDriveState(loadRows=false){
    try{
      const [st,cfg]=await Promise.all([window.api('/api/google-drive/status'),window.api('/api/google-drive/settings')]);
      const client=document.getElementById('driveClientId'),folder=document.getElementById('driveFolderName'),auto=document.getElementById('driveAutoUpload');
      if(client&&document.activeElement!==client)client.value=cfg.client_id||'';if(folder&&document.activeElement!==folder)folder.value=cfg.folder_name||'SleepMate Backups';if(auto)auto.checked=!!cfg.auto_upload;
      const account=st.connected?(st.account_email||'Google-fiók'):'Nincs csatlakoztatva';driveSetStatus(st.connected?`Csatlakoztatva: ${account}${st.last_upload?' • utolsó feltöltés: '+new Date(st.last_upload).toLocaleString('hu-HU'):''}`:'Nincs csatlakoztatva');
      document.getElementById('driveConnect')?.toggleAttribute('disabled',!st.configured||st.connected);document.getElementById('driveDisconnect')?.toggleAttribute('disabled',!st.connected);document.getElementById('driveUploadNow')?.toggleAttribute('disabled',!st.connected);
      if(loadRows&&st.connected){const list=await window.api('/api/google-drive/backups');driveRenderRows(list.rows||[])}else if(loadRows)driveRenderRows([]);
      return st;
    }catch(err){driveSetStatus(err.message||String(err),true);return null}
  }
  function injectDriveUi(){
    installStyles();ensureOfflineBanner();
    const remote=document.querySelector('[data-settings-panel="remote"] .remote-grid')||document.querySelector('[data-settings-panel="remote"]');
    if(remote&&!document.getElementById('googleDriveRemoteCard')){
      const card=document.createElement('article');card.id='googleDriveRemoteCard';card.className='panel remote-card drive-card';card.innerHTML=`<div class="remote-card-head"><div class="remote-logo drive-logo">G</div><div><h3>Google Drive</h3><span>Felhős másolat az automatikus SleepMate backupokról</span></div><span class="remote-status neutral drive-live-status">Ellenőrzés…</span></div><div class="drive-form"><label class="drive-wide"><span>Google OAuth Desktop Client ID</span><input id="driveClientId" type="text" autocomplete="off" placeholder="…apps.googleusercontent.com"></label><label><span>Client secret <small>(ha a Google projekt ad ilyet)</small></span><input id="driveClientSecret" type="password" autocomplete="new-password" placeholder="Már mentett érték nem jelenik meg"></label><label><span>Drive célmappa</span><input id="driveFolderName" type="text" value="SleepMate Backups"></label></div><div class="drive-actions"><button id="driveSave" type="button">Beállítás mentése</button><button id="driveConnect" type="button">Google Drive csatlakoztatása</button><button id="driveDisconnect" type="button">Leválasztás</button></div><div class="drive-help">Egyszeri Google Cloud OAuth „Desktop app” Client ID szükséges. A bejelentkezés a SleepMate-et futtató Windows gép böngészőjében nyílik meg. A Drive funkció opcionális; a helyi backup ettől függetlenül működik.</div>`;remote.appendChild(card);
    }
    const backup=document.querySelector('[data-settings-panel="backup"]');
    if(backup&&!document.getElementById('googleDriveBackupCard')){
      const card=document.createElement('section');card.id='googleDriveBackupCard';card.className='panel drive-card';card.innerHTML=`<div class="panel-head"><div><h3>Google Drive backup</h3><span>A helyben elkészült automatikus backup ZIP-ek opcionális felhős másolata.</span></div><span class="drive-live-status">Ellenőrzés…</span></div><label class="toggle-row"><input id="driveAutoUpload" type="checkbox"><span><strong>Automatikus backupok feltöltése Drive-ra</strong><small>A helyi mentés sikere nem függ a Drive-tól; sikertelen feltöltés később újrapróbálható.</small></span></label><div class="drive-actions"><button id="driveSaveAuto" type="button">Beállítás mentése</button><button id="driveUploadNow" class="drive-write-action" type="button">Legutóbbi backup feltöltése</button><button id="driveRefreshList" type="button">Drive lista frissítése</button></div><div id="driveBackupList" class="drive-backup-list"><div class="empty-state">A Drive backupok betöltése még nem történt meg.</div></div><div id="driveRestoreConfirm" class="drive-inline-confirm hidden"><strong>Teljes visszaállítás Drive-ról</strong><p>A kiválasztott mentés: <span id="driveRestoreName"></span>. A meglévő SleepMate teljes-visszaállítási folyamat fut le.</p><div class="drive-actions"><button id="driveRestoreConfirmGo" class="drive-write-action" type="button">Visszaállítás indítása</button><button id="driveRestoreCancel" type="button">Mégse</button></div></div>`;backup.appendChild(card);
    }
    document.getElementById('driveSave')?.addEventListener('click',async()=>{try{const payload={client_id:document.getElementById('driveClientId')?.value||'',client_secret:document.getElementById('driveClientSecret')?.value||'',folder_name:document.getElementById('driveFolderName')?.value||'SleepMate Backups'};await window.apiWrite('/api/google-drive/settings','POST',payload);const sec=document.getElementById('driveClientSecret');if(sec)sec.value='';await loadDriveState(false)}catch(e){window.showError(e)}});
    document.getElementById('driveSaveAuto')?.addEventListener('click',async()=>{try{await window.apiWrite('/api/google-drive/settings','POST',{auto_upload:!!document.getElementById('driveAutoUpload')?.checked});await loadDriveState(false)}catch(e){window.showError(e)}});
    document.getElementById('driveConnect')?.addEventListener('click',async()=>{try{const r=await window.apiWrite('/api/google-drive/connect','POST',{});await drivePollJob(r.job,'Google Drive');await loadDriveState(true)}catch(e){window.showError(e);driveSetStatus(e.message||String(e),true)}});
    document.getElementById('driveDisconnect')?.addEventListener('click',async()=>{try{await window.apiWrite('/api/google-drive/disconnect','POST',{});driveRenderRows([]);await loadDriveState(false)}catch(e){window.showError(e)}});
    document.getElementById('driveUploadNow')?.addEventListener('click',async()=>{try{const r=await window.apiWrite('/api/google-drive/upload-latest','POST',{});await drivePollJob(r.job,'Drive feltöltés');await loadDriveState(true)}catch(e){window.showError(e)}});
    document.getElementById('driveRefreshList')?.addEventListener('click',()=>loadDriveState(true));
    document.getElementById('driveRestoreCancel')?.addEventListener('click',()=>{driveRestoreCandidate=null;document.getElementById('driveRestoreConfirm')?.classList.add('hidden')});
    document.getElementById('driveRestoreConfirmGo')?.addEventListener('click',async()=>{if(!driveRestoreCandidate)return;try{const chosen=driveRestoreCandidate;driveRestoreCandidate=null;document.getElementById('driveRestoreConfirm')?.classList.add('hidden');const r=await window.apiWrite('/api/google-drive/restore','POST',{file_id:chosen.id});await drivePollJob(r.job,'Drive visszaállítás');driveSetStatus('Visszaállítás kész • SleepMate adatok újratöltve');setTimeout(()=>location.reload(),800)}catch(e){window.showError(e);driveSetStatus(e.message||String(e),true)}});
    loadDriveState(false);
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',injectDriveUi,{once:true});else injectDriveUi();
})();
