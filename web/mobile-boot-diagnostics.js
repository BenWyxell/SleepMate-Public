(function(){
  'use strict';
  const BUILD='__SLEEPMATE_FRONTEND_ID__';
  const started=Date.now();
  let seq=0;

  function slimUrl(raw){
    try{const u=new URL(raw,location.href);return `${u.pathname}${u.search}${u.hash}`.slice(0,500)}catch{return String(raw||'').slice(0,500)}
  }
  function rect(el){
    if(!el)return null;
    const r=el.getBoundingClientRect();
    return {x:Math.round(r.x),y:Math.round(r.y),w:Math.round(r.width),h:Math.round(r.height)};
  }
  function css(el){
    if(!el)return null;
    try{const s=getComputedStyle(el);return {display:s.display,visibility:s.visibility,opacity:s.opacity,position:s.position,overflow:s.overflow}}catch{return null}
  }
  function base(){
    return {
      build:BUILD,
      seq:++seq,
      elapsed_ms:Date.now()-started,
      href:`${location.pathname}${location.hash}`.slice(0,500),
      origin:location.origin.slice(0,300),
      ready_state:document.readyState,
      visibility:document.visibilityState,
      online:navigator.onLine,
      standalone:!!(window.matchMedia&&window.matchMedia('(display-mode: standalone)').matches),
      ios_standalone:!!navigator.standalone,
      viewport:{w:innerWidth,h:innerHeight,dpr:devicePixelRatio||1},
      ua:String(navigator.userAgent||'').slice(0,500)
    };
  }
  function send(stage,details){
    const payload={...base(),stage,details:details||{}};
    try{
      fetch('/api/mobile-boot',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify(payload),cache:'no-store',keepalive:true
      }).catch(()=>{});
    }catch{}
  }
  function snapshot(label){
    const shell=document.querySelector('.hidden-until-ready');
    const content=document.querySelector('.content-shell');
    const main=document.querySelector('main');
    const dash=document.getElementById('page-dashboard');
    const overview=document.getElementById('dashboardOverviewView');
    const splash=document.getElementById('startupSplash');
    const active=[...document.querySelectorAll('.page.active')].map(x=>x.id).slice(0,20);
    send('snapshot',{
      label,
      hash:location.hash,
      active_pages:active,
      shell:{class:shell?.className||'',rect:rect(shell),css:css(shell)},
      content:{rect:rect(content),css:css(content),scroll_height:content?.scrollHeight||0},
      main:{rect:rect(main),css:css(main)},
      dashboard:{class:dash?.className||'',rect:rect(dash),css:css(dash)},
      overview:{class:overview?.className||'',rect:rect(overview),css:css(overview)},
      splash:{class:splash?.className||'',rect:rect(splash),css:css(splash)},
      scripts:[...document.scripts].map(s=>slimUrl(s.src)).filter(Boolean).slice(-20)
    });
  }
  async function probe(path){
    const t=Date.now();
    const controller=typeof AbortController==='function'?new AbortController():null;
    const timer=controller?setTimeout(()=>controller.abort(),6000):null;
    try{
      const r=await fetch(`${path}${path.includes('?')?'&':'?'}boot_probe=${Date.now()}`,{cache:'no-store',signal:controller?.signal});
      send('probe',{path,status:r.status,ok:r.ok,content_type:(r.headers.get('content-type')||'').slice(0,120),duration_ms:Date.now()-t,offline:r.headers.get('X-SleepMate-Offline')==='1'});
    }catch(e){
      send('probe-failed',{path,duration_ms:Date.now()-t,error:String(e?.name||'')+': '+String(e?.message||e)});
    }finally{if(timer)clearTimeout(timer)}
  }
  async function swSnapshot(){
    if(!('serviceWorker'in navigator)){send('service-worker',{supported:false});return}
    try{
      const reg=await navigator.serviceWorker.getRegistration();
      send('service-worker',{
        supported:true,
        controlled:!!navigator.serviceWorker.controller,
        controller:slimUrl(navigator.serviceWorker.controller?.scriptURL||''),
        active:slimUrl(reg?.active?.scriptURL||''),active_state:reg?.active?.state||'',
        waiting:slimUrl(reg?.waiting?.scriptURL||''),waiting_state:reg?.waiting?.state||'',
        installing:slimUrl(reg?.installing?.scriptURL||''),installing_state:reg?.installing?.state||''
      });
    }catch(e){send('service-worker',{supported:true,error:String(e?.message||e)})}
  }

  function installV512MobileSettingsStyles(){
    if(document.getElementById('sleepmateV512MobileSettingsStyle'))return;
    const style=document.createElement('style');
    style.id='sleepmateV512MobileSettingsStyle';
    style.textContent=`
      @media(max-width:700px){
        #page-settings,#page-settings .settings-tab-panel,#page-settings .panel,#page-settings .remote-grid,#page-settings .maintenance-grid,#page-settings .settings-data-grid{min-width:0;max-width:100%}
        #page-settings{width:100%;overflow-x:hidden}
        #page-settings .panel{padding:12px;margin-bottom:10px}
        #page-settings .panel-head{align-items:flex-start;gap:8px;flex-wrap:wrap}
        #page-settings .panel-head>div{min-width:0;flex:1 1 220px}
        #page-settings .panel-head span,#page-settings .panel-head small,#page-settings p,#page-settings code{overflow-wrap:anywhere;word-break:break-word}
        #page-settings input,#page-settings select{min-width:0;max-width:100%}

        .remote-intro-panel .panel-head{display:grid;grid-template-columns:minmax(0,1fr);align-items:start}
        .remote-intro-panel .security-pill{justify-self:start;max-width:100%;white-space:normal}
        .remote-backend-line{grid-template-columns:minmax(0,1fr)!important}
        .remote-backend-line>strong{font-size:11px;overflow-wrap:anywhere;word-break:break-all}
        .remote-grid{grid-template-columns:minmax(0,1fr)!important;gap:10px}
        .remote-card{padding:12px!important;overflow:hidden}
        .remote-card-head{display:grid!important;grid-template-columns:42px minmax(0,1fr);align-items:center;gap:9px;margin-bottom:11px}
        .remote-card-head>div:nth-child(2){min-width:0}
        .remote-card-head h3,.remote-card-head span{overflow-wrap:anywhere}
        .remote-card-head>.remote-status{grid-column:1/-1;justify-self:start;max-width:100%;white-space:normal;text-align:left}
        .remote-facts{grid-template-columns:1fr 1fr!important;gap:6px}
        .remote-facts span{min-width:0;padding:7px 8px}
        .remote-facts b{white-space:normal;overflow-wrap:anywhere}
        .remote-url-field input{width:100%;font-size:11px}
        .remote-actions,.pwa-actions,.drive-actions{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;align-items:stretch}
        .remote-actions button,.pwa-actions button,.drive-actions button{flex:none!important;width:100%;min-width:0;min-height:40px;height:auto;padding:8px 9px!important;font-size:10.5px!important;line-height:1.25;white-space:normal}
        .pwa-card{grid-template-columns:52px minmax(0,1fr)!important;gap:10px!important;padding:12px!important;align-items:start!important}
        .pwa-icon-wrap img{width:48px!important;height:48px!important;border-radius:14px!important}
        .pwa-copy{min-width:0}.pwa-copy h3{font-size:13px}.pwa-copy p{font-size:10.5px}
        .pwa-actions,.pwa-status-grid{grid-column:1/-1}
        .pwa-status-grid{grid-template-columns:1fr 1fr!important;gap:6px}
        .remote-note{font-size:9.5px;padding:10px}

        #googleDriveRemoteCard .drive-form{grid-template-columns:minmax(0,1fr)!important;gap:8px}
        #googleDriveRemoteCard .drive-form label.drive-wide{grid-column:auto!important}
        #googleDriveRemoteCard .drive-form input{width:100%;min-width:0}
        #googleDriveRemoteCard .drive-help{font-size:10.5px;line-height:1.45}
        #googleDriveBackupCard{overflow:hidden}
        #googleDriveBackupCard .panel-head{display:grid;grid-template-columns:minmax(0,1fr);align-items:start}
        #googleDriveBackupCard .drive-live-status{max-width:100%;white-space:normal;overflow-wrap:anywhere}
        #googleDriveBackupCard .toggle-row{align-items:flex-start;min-width:0}
        #googleDriveBackupCard .toggle-row span{min-width:0}
        #googleDriveBackupCard .drive-backup-row{grid-template-columns:minmax(0,1fr)!important}
        #googleDriveBackupCard .drive-backup-row strong{white-space:normal;overflow-wrap:anywhere}

        [data-settings-panel="backup"].settings-data-grid.active{grid-template-columns:minmax(0,1fr)!important;gap:10px}
        [data-settings-panel="backup"] .auto-backup-grid{grid-template-columns:minmax(0,1fr)!important;gap:8px}
        [data-settings-panel="backup"] .path-picker{display:grid!important;grid-template-columns:minmax(0,1fr) auto;gap:7px}
        [data-settings-panel="backup"] .path-picker input{width:100%;min-width:0}
        [data-settings-panel="backup"] .path-picker button{width:auto;min-width:86px;padding:8px 10px}
        [data-settings-panel="backup"] .schedule-status{display:grid;grid-template-columns:minmax(0,1fr);gap:5px}
        [data-settings-panel="backup"] .auto-backup-last-file code{display:block;max-width:100%;white-space:normal;overflow-wrap:anywhere;word-break:break-all}
        [data-settings-panel="backup"] input[type="file"]{width:100%;max-width:100%;font-size:10px}
        [data-settings-panel="backup"] .settings-actions{align-items:flex-start!important;gap:7px}
        [data-settings-panel="backup"] .settings-actions button{flex:none!important;min-height:40px;height:auto;padding:8px 10px!important;white-space:normal}

        .system-maintenance-panel.active{gap:10px!important}
        .maintenance-grid{grid-template-columns:minmax(0,1fr)!important;gap:10px!important}
        .maintenance-card{overflow:hidden}
        .maintenance-hero .panel-head,.maintenance-card .panel-head{align-items:flex-start}
        .maintenance-hero .security-pill,.maintenance-card .remote-status{max-width:100%;white-space:normal}
        .update-version-grid{grid-template-columns:1fr 1fr!important;gap:7px!important;margin:10px 0!important}
        .update-version-grid>div{min-width:0;padding:9px 10px!important;border-radius:11px!important}
        .update-version-grid>div:last-child{grid-column:1/-1}
        .update-version-grid strong{font-size:12px!important;overflow-wrap:anywhere;word-break:break-word}
        .system-maintenance-panel .secret-input-row{display:grid!important;grid-template-columns:minmax(0,1fr) auto;gap:6px}
        .system-maintenance-panel .secret-input-row input{width:100%;min-width:0}
        .system-maintenance-panel .secret-input-row button{width:auto!important;min-width:62px!important;padding:8px 9px!important}
        .system-maintenance-panel .settings-actions,.system-maintenance-panel .settings-actions.wrap{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;align-items:stretch!important}
        .system-maintenance-panel .settings-actions button{flex:none!important;width:100%!important;min-width:0!important;min-height:40px!important;height:auto!important;padding:8px 9px!important;font-size:10.5px!important;line-height:1.25!important;white-space:normal!important}
        .rollback-line{display:grid!important;grid-template-columns:minmax(0,1fr);gap:8px!important;align-items:start!important}
        .rollback-line button{justify-self:start;width:auto!important;min-height:38px!important;padding:8px 10px!important}
        .self-check-row{grid-template-columns:28px minmax(0,1fr);padding:9px 10px}
      }
      @media(max-width:390px){
        .remote-actions,.pwa-actions,.drive-actions,.system-maintenance-panel .settings-actions,.system-maintenance-panel .settings-actions.wrap{grid-template-columns:minmax(0,1fr)!important}
        .update-version-grid,.pwa-status-grid{grid-template-columns:minmax(0,1fr)!important}
        .update-version-grid>div:last-child{grid-column:auto}
        [data-settings-panel="backup"] .path-picker{grid-template-columns:minmax(0,1fr)}
        [data-settings-panel="backup"] .path-picker button{width:100%}
      }
    `;
    document.head.appendChild(style);
    send('v512-mobile-settings-style-installed',{id:style.id});
  }

  function loadPushRepair(){
    if(document.querySelector('script[data-sleepmate-push-repair]'))return;
    const script=document.createElement('script');
    script.dataset.sleepmatePushRepair='1';
    script.src=`/pwa-push-fix.js?v=${encodeURIComponent(BUILD)}`;
    script.async=false;
    script.onload=()=>send('push-repair-loaded',{src:slimUrl(script.src)});
    script.onerror=()=>send('push-repair-error',{src:slimUrl(script.src)});
    document.head.appendChild(script);
  }
  function loadV511Enhancements(){
    if(document.querySelector('script[data-sleepmate-v511]'))return;
    const first=document.createElement('script');
    first.dataset.sleepmateV511='1';
    first.src='/sleepmate-enhancements.js';
    first.async=false;
    first.onload=()=>{
      send('v511-enhancements-loaded',{src:slimUrl(first.src)});
      const offline=document.createElement('script');
      offline.dataset.sleepmateV511Offline='1';
      offline.src='/sleepmate-offline-runtime.js';
      offline.async=false;
      offline.onload=()=>send('v511-offline-runtime-loaded',{src:slimUrl(offline.src)});
      offline.onerror=()=>send('v511-offline-runtime-error',{src:slimUrl(offline.src)});
      document.head.appendChild(offline);
    };
    first.onerror=()=>send('v511-enhancements-error',{src:slimUrl(first.src)});
    document.head.appendChild(first);
  }

  window.addEventListener('error',e=>send('window-error',{
    message:String(e.message||'').slice(0,1200),file:slimUrl(e.filename||''),line:e.lineno||0,column:e.colno||0,
    error:String(e.error?.stack||e.error||'').slice(0,3000)
  }),true);
  window.addEventListener('unhandledrejection',e=>send('unhandled-rejection',{
    reason:String(e.reason?.stack||e.reason||'').slice(0,3000)
  }));
  window.addEventListener('pageshow',e=>{send('pageshow',{persisted:!!e.persisted});setTimeout(()=>snapshot('pageshow+150'),150)});
  window.addEventListener('pagehide',e=>send('pagehide',{persisted:!!e.persisted}));
  document.addEventListener('visibilitychange',()=>send('visibilitychange',{value:document.visibilityState}));
  document.addEventListener('click',e=>{
    const el=e.target?.closest?.('button,a');
    if(!el)return;
    send('click',{
      id:el.id||'',page:el.dataset?.page||'',action:el.dataset?.ssAction||'',tab:el.dataset?.sleepsyncTab||'',
      text:String(el.textContent||'').trim().replace(/\s+/g,' ').slice(0,100),
      active_pages:[...document.querySelectorAll('.page.active')].map(x=>x.id).slice(0,10)
    });
    setTimeout(()=>snapshot('after-click'),80);
  },true);

  send('diagnostics-loaded',{script:slimUrl(document.currentScript?.src||'')});
  installV512MobileSettingsStyles();
  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',()=>{
      send('dom-content-loaded');
      snapshot('dom-content-loaded');
      probe('/api/version');probe('/api/config');probe('/api/days');
    },{once:true});
  }else{
    send('dom-already-ready');snapshot('dom-already-ready');probe('/api/version');probe('/api/config');probe('/api/days');
  }
  window.addEventListener('load',()=>{send('window-load');snapshot('window-load');swSnapshot();loadPushRepair();loadV511Enhancements()},{once:true});
  [250,800,1600,3000,5000,8000,12000].forEach(ms=>setTimeout(()=>snapshot(`t+${ms}`),ms));
  setTimeout(swSnapshot,2500);
})();
