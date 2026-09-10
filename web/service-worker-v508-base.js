const UI_VERSION='5.3.4';
const RELEASE_VERSION='5.3.28';
const BUILD_ID='5.3.28';
const SHELL_CACHE='sleepmate-shell-v5.3.28';
const API_CACHE='sleepmate-api-v5.3.28';
const SHELL=[
  '/','/index.html','/style.css?v=5.3.28',
  '/app-core.js?v=5.3.28','/app-engine119.js?v=5.3.28','/first-run.js?v=4','/first-run.css?v=4',
  '/sleepsync.css?v=5.3.28','/sleepsync-base.css?v=5.3.28','/sleepsync-override.css?v=5.3.28',
  '/sleepsync-stability.css?v=5.3.28','/sleepsync-polish.css?v=5.3.28','/sleepsync-notice.css?v=5.3.28',
  '/sleepsync-polish.js?v=5.3.28','/sleepsync-hydration-v529.js?v=5.3.28','/sleepsync-mobile-v5213.css?v=5.3.28',
  '/sleepmate-sleep.js?v=5.2.6','/sleepmate-sleep-v523.js?v=5.2.6','/sleepmate-chart-v523.js?v=5.2.14',
  '/sleepmate-sleep-v524.js?v=5.2.6','/sleepmate-sleep-refresh-v5212.js?v=5.2.12',
  '/sleepmate-aurora.css?v=5.3.28','/sleepmate-v530.css?v=5.3.28','/dashboard-pwa-v5312.css?v=5.3.28',
  '/sleepmate-v530.js?v=5.3.28','/o2ring.css?v=5.3.28','/o2ring.js?v=5.3.28',
  '/o2ring-report-ui.js?v=5.3.28','/o2ring-v534.css?v=5.3.28','/frontend-v534.js?v=5.3.28',
  '/o2ring-data-management.js?v=5.3.28','/manifest.webmanifest',
  '/assets/pwa-192.png','/assets/pwa-512.png','/assets/sleepmate-icon-v410.webp','/assets/sleepmate-splash-v410.webp',
  '/assets/sleepsync-aurora.svg','/assets/sleepsync-mark.svg','/assets/sleepsync-logo.webp','/assets/sidebar-aurora-line.svg?v=122'
];
const CODE_ASSETS=new Set([
  '/style.css','/app-core.js','/app-engine119.js','/first-run.js','/first-run.css',
  '/sleepsync.css','/sleepsync-base.css','/sleepsync-override.css','/sleepsync-stability.css',
  '/sleepsync-polish.css','/sleepsync-notice.css','/sleepsync-polish.js','/sleepsync-hydration-v529.js','/sleepsync-mobile-v5213.css',
  '/sleepmate-sleep.js','/sleepmate-sleep-v523.js','/sleepmate-chart-v523.js','/sleepmate-sleep-v524.js',
  '/sleepmate-sleep-refresh-v5212.js','/sleepmate-aurora.css','/sleepmate-v530.css','/dashboard-pwa-v5312.css',
  '/sleepmate-v530.js','/o2ring.css','/o2ring.js','/o2ring-report-ui.js','/o2ring-v534.css',
  '/frontend-v534.js','/o2ring-data-management.js','/manifest.webmanifest'
]);
const SHELL_BY_PATH=new Map(SHELL.map(value=>[new URL(value,self.location.origin).pathname,value]));
const OFFLINE_API=/^\/api\/(version|config|days|day-table|dashboard\/overview|day\/[^/]+(?:\/stats|\/signal\/[^/?]+)?|patient(?:\/therapy)?|sleep-analysis|system\/status|logs\/diagnostics|o2ring\/(?:day|day-batch|trends))/;

function isSleepMateCache(key){return key.startsWith('sleepmate-shell-')||key.startsWith('sleepmate-api-')}
function backendUnavailable(response){return !!response&&[502,503,504].includes(Number(response.status))}
function releaseMatches(response){return response.headers.get('X-SleepMate-Release-Version')===RELEASE_VERSION}
async function boundedFetch(request,timeout=15000){const controller=typeof AbortController==='function'?new AbortController():null,timer=controller?setTimeout(()=>controller.abort(),timeout):null;try{return await fetch(request,{cache:'no-store',signal:controller?.signal})}finally{if(timer)clearTimeout(timer)}}
async function fetchShellAsset(url){let response;try{response=await boundedFetch(new Request(url,{cache:'no-store'}))}catch(error){throw new Error(`${url}: ${error instanceof Error?error.message:String(error)}`)}if(!response.ok)throw new Error(`${url}: HTTP ${response.status}`);if(!releaseMatches(response))throw new Error(`${url}: release identity mismatch`);return response}
async function precacheShellAtomic(){const cache=await caches.open(SHELL_CACHE);try{for(const url of SHELL){const response=await fetchShellAsset(url);await cache.put(url,response)}}catch(error){await caches.delete(SHELL_CACHE);throw error}}
async function cleanupStaleSleepMateCaches(){const keys=await caches.keys(),keep=new Set([SHELL_CACHE,API_CACHE]);await Promise.all(keys.filter(key=>isSleepMateCache(key)&&!keep.has(key)).map(key=>caches.delete(key)))}

self.addEventListener('install',event=>event.waitUntil((async()=>{try{await precacheShellAtomic();await self.skipWaiting()}catch(error){const message=error instanceof Error?error.message:String(error);console.error('SleepMate shell installation failed:',message);const windows=await self.clients.matchAll({type:'window',includeUncontrolled:true});for(const client of windows)client.postMessage({type:'SLEEPMATE_SHELL_ERROR',releaseVersion:RELEASE_VERSION,message});throw error}})()));
self.addEventListener('activate',event=>event.waitUntil((async()=>{await self.clients.claim();await cleanupStaleSleepMateCaches();const windows=await self.clients.matchAll({type:'window',includeUncontrolled:true});for(const client of windows)client.postMessage({type:'SLEEPMATE_SHELL_READY',uiVersion:UI_VERSION,releaseVersion:RELEASE_VERSION,buildId:BUILD_ID})})()));

function apiCacheKey(request){const url=new URL(request.url);url.searchParams.delete('_');url.searchParams.delete('_live');url.searchParams.delete('_sleep');return new Request(url.toString(),{method:'GET',headers:{Accept:request.headers.get('Accept')||'application/json'}})}
async function offlineClone(response){const headers=new Headers(response.headers);headers.set('X-SleepMate-Offline','1');return new Response(await response.blob(),{status:200,statusText:'OK (offline cache)',headers})}
async function apiNetworkWithFallback(request){const cache=await caches.open(API_CACHE),key=apiCacheKey(request);try{const fresh=await boundedFetch(request);if(fresh.ok){await cache.put(key,fresh.clone());return fresh}if(backendUnavailable(fresh)){const hit=await cache.match(key);if(hit)return offlineClone(hit)}return fresh}catch{const hit=await cache.match(key);if(hit)return offlineClone(hit);throw new Error('offline')}}
function offlinePage(){return new Response(`<!doctype html><html lang="hu"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#0b1730"><title>SleepMate offline</title></head><body style="margin:0;background:#08111f;color:#eaf4fb;font:16px system-ui,-apple-system,sans-serif;display:grid;place-items:center;min-height:100vh"><main style="max-width:420px;padding:28px;text-align:center"><img src="/assets/pwa-192.png" width="92" height="92" alt=""><h1>SleepMate</h1><p style="color:#9bb0c1">A SleepMate szerver most nem érhető el.</p><p>Kapcsolódj újra a Tailscale hálózathoz vagy indítsd el a SleepMate-et a számítógépen.</p></main></body></html>`,{headers:{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'}})}
async function cachedNavigation(cache){return await cache.match('/index.html')||await cache.match('/')||offlinePage()}
async function navigationFallback(request){const cache=await caches.open(SHELL_CACHE);try{const fresh=await boundedFetch(request);if(fresh.ok&&releaseMatches(fresh)){await cache.put('/index.html',fresh.clone());return fresh}if(fresh.ok||backendUnavailable(fresh))return cachedNavigation(cache);return fresh}catch{return cachedNavigation(cache)}}
async function currentCodeAsset(pathname){const cache=await caches.open(SHELL_CACHE),canonical=SHELL_BY_PATH.get(pathname);if(!canonical)throw new Error(`Missing canonical shell asset: ${pathname}`);const hit=await cache.match(canonical);if(hit)return hit;const fresh=await boundedFetch(new Request(canonical,{cache:'no-store'}));if(fresh.ok){await cache.put(canonical,fresh.clone());return fresh}return fresh}

self.addEventListener('fetch',event=>{const request=event.request,url=new URL(request.url);if(request.method!=='GET'||url.origin!==self.location.origin)return;if(url.pathname.startsWith('/api/')){event.respondWith(OFFLINE_API.test(url.pathname)?apiNetworkWithFallback(request):fetch(request,{cache:'no-store'}));return}if(request.mode==='navigate'){event.respondWith(navigationFallback(request));return}if(CODE_ASSETS.has(url.pathname)){event.respondWith(currentCodeAsset(url.pathname));return}event.respondWith(caches.open(SHELL_CACHE).then(cache=>cache.match(request).then(hit=>hit||fetch(request).then(response=>{if(response.ok&&['image','font'].includes(request.destination))cache.put(request,response.clone());return response}))));});
self.addEventListener('push',event=>{let data={};try{data=event.data?.json()||{}}catch{data={body:event.data?.text()||''}}const title=data.title||'SleepMate';event.waitUntil(self.registration.showNotification(title,{body:data.body||'',tag:data.tag||'sleepmate',icon:'/assets/pwa-192.png',badge:'/assets/pwa-192.png',data:{url:data.url||'/#dashboard',event:data.event||'push'},renotify:false}))});
self.addEventListener('notificationclick',event=>{event.notification.close();const raw=event.notification.data?.url||'/#dashboard',url=new URL(raw,self.location.origin).href;event.waitUntil(clients.matchAll({type:'window',includeUncontrolled:true}).then(async list=>{for(const client of list){if('navigate'in client)await client.navigate(url);if('focus'in client)return client.focus()}return clients.openWindow(url)}))});
