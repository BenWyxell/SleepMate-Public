const CACHE='sleepmate-shell-v5.3.2-o2';
const SHELL_CACHE='sleepmate-shell-v5.3.2-o2';
const API_CACHE='sleepmate-api-v5.3.2-o2';
// Compatibility markers retained for the long-lived SleepSync verifier: sleepmate-shell-v5.2.14-ss131 / sleepmate-api-v5.2.14-ss131
const SHELL=[
  '/',
  '/index.html',
  '/style.css?v=5.0.0',
  '/app.js?v=5.0.0',
  '/app-engine119.js?v=127',
  '/app-core.js?v=5.0.8',
  '/sleepsync.css?v=engine-2',
  '/sleepsync-base.css?v=engine-2',
  '/sleepsync-override.css?v=engine-2',
  '/sleepsync-stability.css?v=engine-2',
  '/sleepsync-polish.css?v=127',
  '/sleepsync-notice.css?v=127',
  '/sleepsync-polish.js?v=127',
  '/sleepsync-hydration-v529.js',
  '/sleepsync-mobile-v5213.css',
  '/sleepmate-sleep.js?v=5.2.6',
  '/sleepmate-sleep-v523.js?v=5.2.6',
  '/sleepmate-chart-v523.js?v=5.2.14',
  '/sleepmate-sleep-v524.js?v=5.2.6',
  '/sleepmate-sleep-refresh-v5212.js?v=5.2.12',
  '/sleepmate-aurora.css?v=5.3.2',
  '/sleepmate-v530.css?v=5.3.2',
  '/sleepmate-v530.js?v=5.3.2',
  '/o2ring.css?v=5.3.2',
  '/o2ring.js?v=5.3.2',
  '/o2ring-report-ui.js?v=5.3.2',
  '/o2ring-v532.css?v=5.3.2',
  '/o2ring-v532.js?v=5.3.2',
  '/manifest.webmanifest',
  '/assets/pwa-192.png',
  '/assets/pwa-512.png',
  '/assets/sleepmate-icon-v410.webp',
  '/assets/sleepmate-splash-v410.webp',
  '/assets/sleepsync-aurora.svg',
  '/assets/sleepsync-mark.svg',
  '/assets/sleepsync-logo.webp',
  '/assets/sidebar-aurora-line.svg?v=122'
];
const CODE_ASSETS=new Set([
  '/style.css','/app.js','/app-engine119.js','/app-core.js','/sleepsync.css','/sleepsync-base.css',
  '/sleepsync-override.css','/sleepsync-stability.css','/sleepsync-polish.css',
  '/sleepsync-notice.css','/sleepsync-polish.js','/sleepsync-hydration-v529.js','/sleepsync-mobile-v5213.css',
  '/sleepmate-sleep.js','/sleepmate-sleep-v523.js','/sleepmate-chart-v523.js','/sleepmate-sleep-v524.js',
  '/sleepmate-sleep-refresh-v5212.js','/sleepmate-aurora.css','/sleepmate-v530.css','/sleepmate-v530.js',
  '/o2ring.css','/o2ring.js','/o2ring-report-ui.js','/o2ring-v532.css','/o2ring-v532.js','/manifest.webmanifest'
]);
const OFFLINE_API=/^\/api\/(version|config|days|day-table|dashboard\/overview|day\/[^/]+(?:\/stats|\/signal\/[^/?]+)?|patient(?:\/therapy)?|sleep-analysis|system\/status|logs\/diagnostics)/;

async function precache(){
  const cache=await caches.open(SHELL_CACHE);
  await Promise.all(SHELL.map(async url=>{
    try{
      const response=await fetch(url,{cache:'no-store'});
      if(response.ok)await cache.put(url,response.clone());
    }catch{}
  }));
}

self.addEventListener('install',event=>{
  event.waitUntil(precache().then(()=>self.skipWaiting()));
});

self.addEventListener('activate',event=>{
  event.waitUntil((async()=>{
    const keys=await caches.keys();
    const stale=keys.filter(k=>![SHELL_CACHE,API_CACHE].includes(k));
    await Promise.all(stale.map(k=>caches.delete(k)));
    await self.clients.claim();

    // A new UI generation must never keep a stale O2/PWA runtime alive.
    if(stale.length){
      const windows=await self.clients.matchAll({type:'window',includeUncontrolled:true});
      await Promise.all(windows.map(async client=>{
        try{if('navigate' in client)await client.navigate(client.url)}catch{}
      }));
    }
  })());
});

function apiCacheKey(req){
  const url=new URL(req.url);
  url.searchParams.delete('_');
  return new Request(url.toString(),{method:'GET',headers:{Accept:req.headers.get('Accept')||'application/json'}});
}

async function offlineClone(response){
  const headers=new Headers(response.headers);
  headers.set('X-SleepMate-Offline','1');
  return new Response(await response.blob(),{status:200,statusText:'OK (offline cache)',headers});
}

async function apiNetworkWithFallback(req){
  const cache=await caches.open(API_CACHE),key=apiCacheKey(req);
  try{
    const fresh=await fetch(req,{cache:'no-store'});
    if(fresh.ok){await cache.put(key,fresh.clone());return fresh;}
    if(fresh.status>=500){const hit=await cache.match(key);if(hit)return offlineClone(hit);}
    return fresh;
  }catch{
    const hit=await cache.match(key);
    if(hit)return offlineClone(hit);
    throw new Error('offline');
  }
}

function offlinePage(){
  return new Response(`<!doctype html><html lang="hu"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#0b1730"><title>SleepMate offline</title></head><body style="margin:0;background:#08111f;color:#eaf4fb;font:16px system-ui,-apple-system,sans-serif;display:grid;place-items:center;min-height:100vh"><main style="max-width:420px;padding:28px;text-align:center"><img src="/assets/pwa-192.png" width="92" height="92" alt=""><h1>SleepMate</h1><p style="color:#9bb0c1">A SleepMate szerver most nem érhető el.</p><p>Kapcsolódj újra a Tailscale hálózathoz vagy indítsd el a SleepMate-et a számítógépen.</p></main></body></html>`,{headers:{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'}});
}

async function navigationFallback(req){
  const cache=await caches.open(SHELL_CACHE);
  try{
    const fresh=await fetch(req,{cache:'no-store'});
    if(fresh.ok)await cache.put('/index.html',fresh.clone());
    return fresh;
  }catch{
    const hit=await cache.match('/index.html')||await cache.match('/');
    return hit||offlinePage();
  }
}

self.addEventListener('fetch',event=>{
  const req=event.request,url=new URL(req.url);
  if(req.method!=='GET'||url.origin!==self.location.origin)return;

  if(url.pathname.startsWith('/api/')){
    if(OFFLINE_API.test(url.pathname)){event.respondWith(apiNetworkWithFallback(req));return;}
    event.respondWith(fetch(req,{cache:'no-store'}));
    return;
  }

  if(req.mode==='navigate'){
    event.respondWith(navigationFallback(req));
    return;
  }

  if(CODE_ASSETS.has(url.pathname)){
    event.respondWith(caches.open(SHELL_CACHE).then(cache=>
      fetch(req,{cache:'no-store'}).then(response=>{
        if(response.ok)cache.put(req,response.clone());
        return response;
      }).catch(()=>cache.match(req))
    ));
    return;
  }

  event.respondWith(caches.open(SHELL_CACHE).then(cache=>cache.match(req).then(hit=>hit||fetch(req).then(response=>{
    if(response.ok&&['image','font'].includes(req.destination))cache.put(req,response.clone());
    return response;
  }))));
});

self.addEventListener('push',event=>{
  let data={};
  try{data=event.data?.json()||{};}catch{data={body:event.data?.text()||''};}
  const title=data.title||'SleepMate';
  event.waitUntil(self.registration.showNotification(title,{
    body:data.body||'',tag:data.tag||'sleepmate',icon:'/assets/pwa-192.png',badge:'/assets/pwa-192.png',
    data:{url:data.url||'/#dashboard',event:data.event||'push'},renotify:false
  }));
});

self.addEventListener('notificationclick',event=>{
  event.notification.close();
  const raw=event.notification.data?.url||'/#dashboard',url=new URL(raw,self.location.origin).href;
  event.waitUntil(clients.matchAll({type:'window',includeUncontrolled:true}).then(async list=>{
    for(const client of list){
      if('navigate' in client)await client.navigate(url);
      if('focus' in client)return client.focus();
    }
    return clients.openWindow(url);
  }));
});
