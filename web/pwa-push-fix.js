/* SleepMate iOS/PWA Web Push lifecycle repair.
 *
 * Own the complete push UI lifecycle, not only the permission button. The
 * original v5.0.8 helpers can wait forever on navigator.serviceWorker.ready on
 * iOS and a late legacy status call can overwrite a newly-created subscription
 * with "Nincs feliratkozva". Every service-worker / PushManager / backend step
 * below is bounded, stage-labelled and re-verifies the browser subscription.
 */
(function(){
  'use strict';

  const STEP_TIMEOUT=7000;
  const SW_TIMEOUT=10000;
  const SUBSCRIBE_TIMEOUT=15000;

  function iosPushDevice(){
    return /iPad|iPhone|iPod/.test(navigator.userAgent) ||
      (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  }

  function standalone(){
    try{return window.navigator.standalone===true || !!window.matchMedia?.('(display-mode: standalone)').matches}catch{return false}
  }

  function pushText(message){
    const el=document.querySelector('#pushStatusText');
    if(el)el.textContent=message;
  }

  function pushDiag(stage,details={}){
    try{
      fetch('/api/mobile-boot',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          stage,
          details:{
            ...details,
            permission:('Notification' in window)?Notification.permission:'unsupported',
            standalone:standalone(),
            secure:window.isSecureContext,
            controlled:!!navigator.serviceWorker?.controller
          }
        }),
        keepalive:true,
        cache:'no-store'
      }).catch(()=>{});
    }catch{}
  }

  function timeoutError(message){
    const e=new Error(message);e.name='SleepMatePushTimeout';return e;
  }

  function withTimeout(promise,ms,message){
    let timer;
    return Promise.race([
      Promise.resolve(promise),
      new Promise((_,reject)=>{timer=setTimeout(()=>reject(timeoutError(message)),ms)})
    ]).finally(()=>clearTimeout(timer));
  }

  async function fetchJson(path,{method='GET',data=null,timeout=STEP_TIMEOUT}={}){
    const controller=typeof AbortController==='function'?new AbortController():null;
    const timer=controller?setTimeout(()=>controller.abort(),timeout):null;
    try{
      const opt={method,cache:'no-store',headers:{Accept:'application/json'}};
      if(controller)opt.signal=controller.signal;
      if(data!==null){opt.headers['Content-Type']='application/json';opt.body=JSON.stringify(data)}
      const r=await fetch(path,opt);
      const ct=(r.headers.get('content-type')||'').toLowerCase();
      const body=ct.includes('application/json')?await r.json():{error:await r.text()};
      if(!r.ok||body?.error)throw new Error(body?.error||`HTTP ${r.status}`);
      return body;
    }catch(e){
      if(e?.name==='AbortError')throw timeoutError(`A SleepMate háttérszerver nem válaszolt ${Math.round(timeout/1000)} másodpercen belül.`);
      throw e;
    }finally{if(timer)clearTimeout(timer)}
  }

  function urlBase64ToBytes(base64String){
    const padding='='.repeat((4-base64String.length%4)%4);
    const base64=(base64String+padding).replace(/-/g,'+').replace(/_/g,'/');
    const raw=atob(base64);
    return Uint8Array.from([...raw].map(c=>c.charCodeAt(0)));
  }

  function bytesEqual(a,b){
    if(!a||!b)return false;
    try{
      const x=new Uint8Array(a),y=b instanceof Uint8Array?b:new Uint8Array(b);
      if(x.length!==y.length)return false;
      for(let i=0;i<x.length;i++)if(x[i]!==y[i])return false;
      return true;
    }catch{return false}
  }

  function subscriptionKeyMatches(sub,publicKey){
    try{
      const existing=sub?.options?.applicationServerKey;
      if(!existing)return true;
      return bytesEqual(existing,urlBase64ToBytes(publicKey));
    }catch{return true}
  }

  function currentPrefs(){
    return{
      new_night:!!document.querySelector('#pushPrefNewNight')?.checked,
      data_update:!!document.querySelector('#pushPrefDataUpdate')?.checked,
      warning:!!document.querySelector('#pushPrefWarning')?.checked,
      backup_error:!!document.querySelector('#pushPrefBackupError')?.checked
    };
  }

  function applyPrefs(p={}){
    const set=(id,v)=>{const el=document.querySelector(id);if(el)el.checked=!!v};
    set('#pushPrefNewNight',p.new_night!==false);
    set('#pushPrefDataUpdate',!!p.data_update);
    set('#pushPrefWarning',p.warning!==false);
    set('#pushPrefBackupError',p.backup_error!==false);
  }

  async function getRegistrationBounded({create=false}={}){
    if(!('serviceWorker' in navigator))throw new Error('A Service Worker ezen az eszközön nem támogatott.');
    let reg=null;
    try{
      reg=await withTimeout(
        navigator.serviceWorker.getRegistration(),
        3500,
        'A PWA háttérszolgáltatás regisztrációja nem válaszolt 3,5 másodpercen belül.'
      );
    }catch(e){
      pushDiag('push-sw-get-registration-timeout',{message:e.message});
      if(!create)throw e;
    }
    if(!reg&&create){
      pushText('PWA háttérszolgáltatás indítása…');
      reg=await withTimeout(
        navigator.serviceWorker.register('/service-worker.js',{updateViaCache:'none'}),
        SW_TIMEOUT,
        'A PWA háttérszolgáltatás regisztrálása nem fejeződött be 10 másodpercen belül.'
      );
    }
    return reg;
  }

  async function ensureActiveRegistration(){
    pushText('PWA háttérszolgáltatás keresése…');
    let reg=await getRegistrationBounded({create:true});
    if(reg?.active?.state==='activated')return reg;

    pushText('PWA háttérszolgáltatás aktiválása…');
    try{
      const ready=await withTimeout(
        navigator.serviceWorker.ready,
        SW_TIMEOUT,
        'A PWA háttérszolgáltatás 10 másodpercen belül sem vált aktívvá.'
      );
      if(ready)reg=ready;
    }catch(e){
      const worker=reg?.installing||reg?.waiting||reg?.active;
      pushDiag('push-sw-ready-timeout',{
        message:e.message,
        installing:reg?.installing?.state||'',
        waiting:reg?.waiting?.state||'',
        active:reg?.active?.state||'',
        worker:worker?.state||''
      });
      throw e;
    }
    if(!reg?.pushManager)throw new Error('A PWA háttérszolgáltatás aktív, de a PushManager nem érhető el.');
    return reg;
  }

  async function getBrowserSubscription(reg,{quiet=false}={}){
    if(!reg?.pushManager)return null;
    try{
      return await withTimeout(
        reg.pushManager.getSubscription(),
        5000,
        'Az Apple PushManager 5 másodpercen belül nem válaszolt a feliratkozás lekérdezésére.'
      );
    }catch(e){
      if(!quiet)pushDiag('push-get-subscription-timeout',{message:e.message});
      throw e;
    }
  }

  async function serverStatus(){
    return await fetchJson('/api/push/status',{timeout:7000});
  }

  async function registerSubscription(reg,status,{force=false}={}){
    if(!status?.available||!status.public_key)throw new Error(status?.dependency_error||'A SleepMate Web Push backend még nem áll készen.');
    let sub=await getBrowserSubscription(reg);
    const mismatch=!!sub&&!subscriptionKeyMatches(sub,status.public_key);
    if(force||mismatch){
      if(sub){
        try{await fetchJson('/api/push/unsubscribe',{method:'POST',data:{endpoint:sub.endpoint},timeout:4500})}catch{}
        try{await withTimeout(sub.unsubscribe(),5000,'A régi Apple push-feliratkozás törlése nem fejeződött be.')}catch{}
      }
      sub=null;
    }
    if(!sub){
      pushText('Apple Web Push feliratkozás létrehozása…');
      sub=await withTimeout(
        reg.pushManager.subscribe({
          userVisibleOnly:true,
          applicationServerKey:urlBase64ToBytes(status.public_key)
        }),
        SUBSCRIBE_TIMEOUT,
        'Az Apple Web Push szolgáltatás 15 másodpercen belül nem adott vissza feliratkozást.'
      );
    }
    if(!sub?.endpoint)throw new Error('Az Apple PushManager nem adott vissza érvényes feliratkozási végpontot.');
    const json=sub.toJSON?.()||{};
    if(!json?.keys?.p256dh||!json?.keys?.auth)throw new Error('Az Apple Web Push feliratkozásból hiányzik a titkosítási kulcs.');

    pushText('Feliratkozás rögzítése a SleepMate szerverén…');
    await fetchJson('/api/push/subscribe',{
      method:'POST',
      data:{subscription:json,preferences:currentPrefs(),origin:location.origin},
      timeout:8000
    });
    return sub;
  }

  function renderStatus({status=null,sub=null,permission=null,swError=null}={}){
    const badge=document.querySelector('#pushCapabilityBadge');
    const stateEl=document.querySelector('#pushDeviceState');
    const detail=document.querySelector('#pushDeviceDetail');
    const count=document.querySelector('#pushSubscriptionCount');
    const notif=document.querySelector('#pwaStatusNotifications');
    const secure=window.isSecureContext;
    permission=permission||(('Notification' in window)?Notification.permission:'unsupported');
    const supported=!!(status?.available&&secure&&'serviceWorker'in navigator&&'PushManager'in window&&'Notification'in window);

    if(count)count.textContent=String(status?.subscriptions||0);
    if(badge){
      badge.classList.toggle('warn',!supported||!!swError);
      badge.textContent=swError?'Háttérszolgáltatás hiba':supported?'Web Push kész ✓':status?.dependency_error?'Függőség hiányzik':'Nem érhető el';
    }
    if(stateEl){
      stateEl.textContent=sub?'Feliratkozva ✓':permission==='denied'?'Értesítések letiltva':swError?'PWA háttérszolgáltatás nem válaszol':'Nincs feliratkozva';
    }
    if(detail){
      if(!secure)detail.textContent='A Web Push HTTPS-t igényel.';
      else if(permission==='denied')detail.textContent='Az iPhone Beállítások → Értesítések → SleepMate menüjében engedélyezd újra.';
      else if(swError)detail.textContent=swError;
      else if(sub)detail.textContent='Ez a PWA aktív Apple Web Push feliratkozással rendelkezik.';
      else if((status?.subscriptions||0)>0)detail.textContent='A szerveren van regisztrált push-eszköz, de ez a PWA jelenleg nem lát saját feliratkozást.';
      else detail.textContent='Kapcsold be ezen az eszközön.';
    }
    if(notif)notif.textContent=sub&&permission==='granted'?'Web Push aktív ✓':permission==='denied'?'Letiltva':swError?'Háttérszolgáltatás hiba':status?.available?'Bekapcsolható':'Nincs beállítva';

    if(typeof state==='object'&&state){
      state.pushStatus=status;
      state.notificationEnabled=!!sub&&permission==='granted';
    }
    try{localStorage.setItem('sleepmate-notifications-enabled',sub&&permission==='granted'?'1':'0')}catch{}
    try{if(typeof updatePwaStatus==='function')updatePwaStatus()}catch{}
  }

  async function fixedLoadPushStatus(showErrors=false){
    let status=null,sub=null,swError=null;
    try{
      status=await serverStatus();
      if(status?.default_preferences){
        try{
          const saved=JSON.parse(localStorage.getItem('sleepmate-push-prefs')||'null');
          if(saved)applyPrefs(saved);
        }catch{}
      }
      if('serviceWorker'in navigator&&'PushManager'in window){
        try{
          const reg=await getRegistrationBounded({create:false});
          if(reg?.pushManager)sub=await getBrowserSubscription(reg,{quiet:true});
        }catch(e){swError=e.message||String(e)}
      }
      renderStatus({status,sub,swError});
      const txt=document.querySelector('#pushStatusText');
      if(txt&&!txt.textContent?.includes('Feliratkozás')){
        txt.textContent=swError
          ?`PWA háttérszolgáltatás: ${swError}`
          :(status?.dependency_error||'A VAPID kulcspárt a SleepMate automatikusan, helyben kezeli. A privát kulcs nem hagyja el a szervert.');
      }
      return{status,sub,swError};
    }catch(e){
      renderStatus({status,sub,swError:e.message||String(e)});
      pushText(`Push állapotellenőrzési hiba: ${e.message||e}`);
      if(showErrors&&typeof showError==='function')showError(e);
      return{status:null,sub:null,swError:e.message||String(e)};
    }
  }

  async function fixedEnablePwaNotifications(){
    const btn=document.querySelector('#pushEnableButton');
    try{
      if(btn)btn.disabled=true;
      if(!window.isSecureContext)throw new Error('A valódi PWA értesítésekhez HTTPS kapcsolat szükséges.');
      if(!('Notification'in window)||!('serviceWorker'in navigator)||!('PushManager'in window))throw new Error('Ezen az eszközön a Web Push nem támogatott.');
      if(iosPushDevice()&&!standalone())throw new Error('iPhone/iPadon a Web Push csak a Főképernyőhöz hozzáadott SleepMate PWA-ban kapcsolható be.');

      let permission=Notification.permission;
      if(permission==='denied'){
        pushDiag('push-subscribe-tap',{initial_permission:permission});
        throw new Error('A SleepMate értesítései le vannak tiltva az iPhone-on. Engedélyezd a Beállítások → Értesítések → SleepMate alatt, majd próbáld újra.');
      }

      /* iOS: while permission is default this must be the FIRST privileged async
       * operation after the tap. No fetch / service-worker request may precede it. */
      if(permission==='default'){
        pushText('iOS értesítési engedély kérése…');
        permission=await Notification.requestPermission();
        pushDiag('push-permission-result',{initial_permission:'default',result:permission});
        if(permission!=='granted')throw new Error('Az értesítési engedély nem lett megadva.');
      }else pushDiag('push-subscribe-tap',{initial_permission:permission});

      const reg=await ensureActiveRegistration();
      pushText('SleepMate Web Push háttérszolgáltatás ellenőrzése…');
      const status=await serverStatus();
      let sub=await registerSubscription(reg,status);

      // Re-read from PushManager before declaring success. This catches the exact
      // iOS case where subscribe() resolved but the registration was not retained.
      const verified=await getBrowserSubscription(reg);
      if(!verified?.endpoint||verified.endpoint!==sub.endpoint)throw new Error('Az iPhone nem tartotta meg a létrehozott Web Push feliratkozást.');
      sub=verified;

      const prefs=currentPrefs();
      try{localStorage.setItem('sleepmate-push-prefs',JSON.stringify(prefs));localStorage.setItem('sleepmate-notifications-enabled','1')}catch{}
      renderStatus({status:{...status,subscriptions:Math.max(Number(status.subscriptions||0),1)},sub,permission:'granted'});
      pushDiag('push-subscribe-created',{endpoint_host:(()=>{try{return new URL(sub.endpoint).host}catch{return''}})()});

      pushText('Feliratkozva ✓ • Próbaértesítés küldése…');
      let test=await fetchJson('/api/push/test',{method:'POST',data:{endpoint:sub.endpoint,origin:location.origin},timeout:12000});
      const badJwt=!test?.sent&&(test?.errors||[]).some(x=>/BadJwtToken|korábbi VAPID kulccsal/i.test(String(x)));
      if(badJwt){
        pushText('VAPID kapcsolat újraépítése…');
        sub=await registerSubscription(reg,status,{force:true});
        test=await fetchJson('/api/push/test',{method:'POST',data:{endpoint:sub.endpoint,origin:location.origin},timeout:12000});
      }
      if(!test?.sent){
        const detail=(test?.errors||[])[0]||'A SleepMate szerver nem tudta elküldeni a próbaértesítést.';
        throw new Error(detail);
      }

      renderStatus({status:{...status,subscriptions:Math.max(Number(status.subscriptions||0),1)},sub,permission:'granted'});
      pushText('Feliratkozva ✓ • A SleepMate szerver elküldte a próbaértesítést erre az iPhone-ra.');
      try{if(typeof addLog==='function')addLog('INFO','PWA push feliratkozás ellenőrizve; próbaértesítés elküldve.')}catch{}
      pushDiag('push-subscribe-success');
      setTimeout(()=>fixedLoadPushStatus(false),800);
    }catch(e){
      const message=e?.message||String(e);
      pushText(`Feliratkozás sikertelen: ${message}`);
      pushDiag('push-subscribe-error',{name:e?.name||'',message});
      await fixedLoadPushStatus(false).catch(()=>{});
      if(typeof showError==='function')showError(e);
    }finally{if(btn)btn.disabled=false}
  }

  async function fixedTestPushNotification(){
    const btn=document.querySelector('#pushTestButton');
    try{
      if(btn)btn.disabled=true;
      pushText('PWA háttérszolgáltatás és feliratkozás ellenőrzése…');
      const reg=await ensureActiveRegistration();
      const status=await serverStatus();
      let sub=await getBrowserSubscription(reg);
      if(!sub)throw new Error('Ez az iPhone jelenleg nem rendelkezik Apple Web Push feliratkozással. Kapcsold be újra az értesítéseket.');
      sub=await registerSubscription(reg,status);
      pushText('Próbaértesítés küldése…');
      const r=await fetchJson('/api/push/test',{method:'POST',data:{endpoint:sub.endpoint,origin:location.origin},timeout:12000});
      if(!r?.sent)throw new Error((r?.errors||[])[0]||'A push szolgáltató nem fogadta el a próbaértesítést.');
      renderStatus({status,sub,permission:Notification.permission});
      pushText('Próbaértesítés elküldve ✓ • Nézd meg az iPhone értesítési sávját / zárolási képernyőjét.');
      pushDiag('push-test-success');
    }catch(e){
      pushText(`Próbaértesítés sikertelen: ${e.message||e}`);
      pushDiag('push-test-error',{name:e?.name||'',message:e?.message||String(e)});
      if(typeof showError==='function')showError(e);
    }finally{if(btn)btn.disabled=false}
  }

  async function fixedSavePushPreferences(){
    try{
      const reg=await ensureActiveRegistration();
      const sub=await getBrowserSubscription(reg);
      if(!sub)throw new Error('Ez az eszköz még nincs feliratkozva push értesítésekre.');
      const prefs=currentPrefs();
      await fetchJson('/api/push/preferences',{method:'POST',data:{endpoint:sub.endpoint,preferences:prefs},timeout:7000});
      try{localStorage.setItem('sleepmate-push-prefs',JSON.stringify(prefs))}catch{}
      pushText('Értesítési beállítások mentve ✓');
    }catch(e){pushText(`Beállításmentési hiba: ${e.message||e}`);if(typeof showError==='function')showError(e)}
  }

  async function fixedDisablePushNotifications(){
    try{
      const reg=await getRegistrationBounded({create:false});
      const sub=reg?await getBrowserSubscription(reg,{quiet:true}):null;
      if(sub){
        try{await fetchJson('/api/push/unsubscribe',{method:'POST',data:{endpoint:sub.endpoint},timeout:6000})}catch{}
        await withTimeout(sub.unsubscribe(),6000,'Az Apple push-feliratkozás kikapcsolása nem fejeződött be.');
      }
      try{localStorage.setItem('sleepmate-notifications-enabled','0')}catch{}
      await fixedLoadPushStatus(false);
      pushText('Push értesítések kikapcsolva ezen az eszközön.');
    }catch(e){pushText(`Kikapcsolási hiba: ${e.message||e}`);if(typeof showError==='function')showError(e)}
  }

  function bind(){
    const enable=document.querySelector('#pushEnableButton');
    const test=document.querySelector('#pushTestButton');
    const save=document.querySelector('#pushSaveButton');
    const disable=document.querySelector('#pushDisableButton');
    if(!enable)return false;
    enable.onclick=fixedEnablePwaNotifications;
    if(test)test.onclick=fixedTestPushNotification;
    if(save)save.onclick=fixedSavePushPreferences;
    if(disable)disable.onclick=fixedDisablePushNotifications;

    // Replace the global status function used by Settings tab navigation and by
    // the original PWA boot path. This removes the unbounded legacy ready wait.
    try{window.loadPushStatus=fixedLoadPushStatus}catch{}
    try{window.enablePwaNotifications=fixedEnablePwaNotifications}catch{}
    try{window.testPushNotification=fixedTestPushNotification}catch{}
    try{window.savePushPreferences=fixedSavePushPreferences}catch{}
    try{window.disablePushNotifications=fixedDisablePushNotifications}catch{}
    return true;
  }

  if(bind()){
    fixedLoadPushStatus(false);
  }else{
    let tries=0;
    const timer=setInterval(()=>{
      tries++;
      if(bind()){
        clearInterval(timer);
        fixedLoadPushStatus(false);
      }else if(tries>=100)clearInterval(timer);
    },100);
  }
})();
