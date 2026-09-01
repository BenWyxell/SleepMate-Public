const CACHE='sleepmate-shell-v5.2.14';
const SHELL_CACHE='sleepmate-shell-v5.2.14';
const API_CACHE='sleepmate-api-v5.2.14';
const SHELL=['/','/index.html','/style.css?v=5.0.0','/app.js?v=5.0.0','/sleepmate-enhancements.js','/sleepmate-offline-runtime.js','/sleepsync-hydration-v529.js','/sleepsync-mobile-v5213.css','/sleepmate-sleep.js?v=5.2.6','/sleepmate-sleep-v523.js?v=5.2.6','/sleepmate-chart-v523.js?v=5.2.14','/sleepmate-sleep-v524.js?v=5.2.6','/sleepmate-sleep-refresh-v5212.js?v=5.2.12','/sleepmate-aurora.css?v=5.3.2','/sleepmate-v530.css?v=5.3.2','/sleepmate-v530.js?v=5.3.2','/o2ring.css?v=5.3.2','/o2ring.js?v=5.3.2','/o2ring-report-ui.js?v=5.3.2','/o2ring-v532.css?v=5.3.2','/o2ring-v532.js?v=5.3.2','/manifest.webmanifest','/assets/pwa-192.png','/assets/pwa-512.png','/assets/sleepmate-icon-v410.webp','/assets/sleepmate-splash-v410.webp'];
const OFFLINE_API=/^\/api\/(version|config|days|day-table|dashboard\/overview|day\/[^/]+(?:\/stats|\/signal\/[^/?]+)?|patient(?:\/therapy)?|equipment(?:\/catalog)?|faq|glossary|system\/status|logs\/diagnostics|sleep-analysis|o2ring\/(?:day|day-batch|trends))/;

/*
 * A service worker must never fail to install merely because one optional shell
 * asset was temporarily unavailable over Tailscale/WebKit. cache.addAll() is
 * atomic: one failed request rejects the entire install and leaves iOS waiting
 * forever for navigator.serviceWorker.ready. Cache each asset independently and
 * bound each fetch, so the worker can activate and Web Push remains available.
 */
async function cacheShellAsset(cache,url){
  const controller=typeof AbortController==='function'?new AbortController():null;
  const timer=controller?setTimeout(()=>controller.abort(),3500):null;
  try{
    const response=await fetch(url,{cache:'no-store',signal:controller?.signal});
    if(response.ok)await cache.put(url,response.clone());
  }catch{}
  finally{if(timer)clearTimeout(timer)}
}
async function precacheShell(){
  const cache=await caches.open(SHELL_CACHE);
  await Promise.all(SHELL.map(url=>cacheShellAsset(cache,url)));
}
self.addEventListener('install',event=>{event.waitUntil(precacheShell().then(()=>self.skipWaiting()))});
self.addEventListener('activate',event=>{event.waitUntil((async()=>{
  const keys=await caches.keys();
  const stale=keys.filter(k=>![SHELL_CACHE,API_CACHE].includes(k));
  await Promise.all(stale.map(k=>caches.delete(k)));
  await self.clients.claim();
  // Feature modules are versioned shell assets. When a new worker replaces an
  // old PWA shell, reload live clients once so O2Ring/dashboard code cannot stay stale.
  if(stale.length){
    const windows=await self.clients.matchAll({type:'window',includeUncontrolled:true});
    await Promise.all(windows.map(async client=>{try{if('navigate'in client)await client.navigate(client.url)}catch{}}));
  }
})())});

function backendUnavailable(response){return !!response&&[502,503,504].includes(Number(response.status))}
async function boundedFetch(req,timeout=5000){
  const controller=typeof AbortController==='function'?new AbortController():null;
  const timer=controller?setTimeout(()=>controller.abort(),timeout):null;
  try{return await fetch(req,{cache:'no-store',signal:controller?.signal})}
  finally{if(timer)clearTimeout(timer)}
}
function apiCacheKey(req){const u=new URL(req.url);u.searchParams.delete('_');u.searchParams.delete('_live');u.searchParams.delete('_sleep');return new Request(u.toString(),{method:'GET',headers:{Accept:req.headers.get('Accept')||'application/json'}})}
async function offlineClone(response){const h=new Headers(response.headers);h.set('X-SleepMate-Offline','1');return new Response(await response.blob(),{status:200,statusText:'OK (offline cache)',headers:h})}
async function apiNetworkWithFallback(req){
  const cache=await caches.open(API_CACHE),key=apiCacheKey(req);
  try{
    const fresh=await boundedFetch(req,5000);
    if(fresh.ok){await cache.put(key,fresh.clone());return fresh}
    if(backendUnavailable(fresh)){const hit=await cache.match(key);if(hit)return offlineClone(hit)}
    return fresh;
  }catch{
    const hit=await cache.match(key);if(hit)return offlineClone(hit);throw new Error('offline');
  }
}
function offlinePage(){return new Response(`<!doctype html><html lang="hu"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#0b1730"><title>SleepMate offline</title></head><body style="margin:0;background:radial-gradient(circle at 20% 10%,#123b51 0,transparent 34%),radial-gradient(circle at 85% 18%,#30255f 0,transparent 34%),#08111f;color:#eaf4fb;font:16px system-ui,-apple-system,sans-serif;display:grid;place-items:center;min-height:100vh"><main style="max-width:430px;padding:32px;text-align:center"><img src="/assets/sleepmate-icon-v410.webp" width="132" height="132" alt="SleepMate" style="border-radius:28px"><h1>Offline mód</h1><p style="color:#9bb0c1">A SleepMate szerver jelenleg nem érhető el.</p><p>Ha ezen az eszközön még nincs korábban eltárolt SleepMate felület és adat, az élő nézet a szerver következő elérésekor töltődik be.</p></main></body></html>`,{headers:{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'}})}
async function cachedNavigation(cache){return await cache.match('/index.html')||await cache.match('/')||offlinePage()}
async function navigationFallback(req){
  const cache=await caches.open(SHELL_CACHE);
  try{
    const fresh=await boundedFetch(req,5000);
    if(fresh.ok){await cache.put('/index.html',fresh.clone());return fresh}
    if(backendUnavailable(fresh))return cachedNavigation(cache);
    return fresh;
  }catch{return cachedNavigation(cache)}
}
async function codeNetworkFirst(req){
  const cache=await caches.open(SHELL_CACHE);
  try{
    const fresh=await boundedFetch(req,5000);
    if(fresh.ok){await cache.put(req,fresh.clone());return fresh}
    if(backendUnavailable(fresh)){const hit=await cache.match(req);if(hit)return hit}
    return fresh;
  }catch{const hit=await cache.match(req);if(hit)return hit;throw new Error('offline')}
}
self.addEventListener('fetch',event=>{const req=event.request,url=new URL(req.url);if(req.method!=='GET'||url.origin!==self.location.origin)return;if(url.pathname.startsWith('/api/')){if(OFFLINE_API.test(url.pathname)){event.respondWith(apiNetworkWithFallback(req));return}event.respondWith(fetch(req,{cache:'no-store'}));return}if(req.mode==='navigate'){event.respondWith(navigationFallback(req));return}const codeAsset=['/style.css','/app.js','/sleepmate-sleep.js','/sleepmate-sleep-v523.js','/sleepmate-chart-v523.js','/sleepmate-sleep-v524.js','/sleepmate-sleep-refresh-v5212.js','/sleepmate-aurora.css','/sleepmate-v530.css','/sleepmate-v530.js','/o2ring.css','/o2ring.js','/o2ring-report-ui.js','/o2ring-v532.css','/o2ring-v532.js','/manifest.webmanifest'].includes(url.pathname);if(codeAsset){event.respondWith(codeNetworkFirst(req));return}event.respondWith(caches.open(SHELL_CACHE).then(cache=>cache.match(req).then(hit=>hit||fetch(req).then(r=>{if(r.ok&&['image','font'].includes(req.destination))cache.put(req,r.clone());return r}))));});
self.addEventListener('push',event=>{let data={};try{data=event.data?.json()||{}}catch{data={body:event.data?.text()||''}}const title=data.title||'SleepMate';event.waitUntil(self.registration.showNotification(title,{body:data.body||'',tag:data.tag||'sleepmate',icon:'/assets/pwa-192.png',badge:'/assets/pwa-192.png',data:{url:data.url||'/#dashboard',event:data.event||'push'},renotify:false}))});
self.addEventListener('notificationclick',event=>{event.notification.close();const raw=event.notification.data?.url||'/#dashboard',url=new URL(raw,self.location.origin).href;event.waitUntil(clients.matchAll({type:'window',includeUncontrolled:true}).then(async list=>{for(const c of list){if('navigate'in c)await c.navigate(url);if('focus'in c)return c.focus()}return clients.openWindow(url)}))});