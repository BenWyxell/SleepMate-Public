(()=>{
'use strict';
if(window.__sleepmateO2RecoveryV5318)return;
window.__sleepmateO2RecoveryV5318=true;

const BUILD='5.3.19-recovery';
const q=(selector,root=document)=>root.querySelector(selector);
let running=null;
let retryTimer=null;
let attempts=0;

function coreReady(){
  return !!(q('.hidden-until-ready')?.classList.contains('ready')&&typeof window.navigate==='function');
}
function placeholder(){return q('#page-oximetry[data-o2-recovery-placeholder="1"]');}
function realO2UiPresent(){
  const page=document.getElementById('page-oximetry');
  return !!(q('#sidebar [data-page="oximetry"]')&&page&&page.dataset.o2RecoveryPlaceholder!=='1');
}
function enabled(status){return status?.settings?.o2ring_enabled===true;}

async function api(path){
  const response=await fetch(path,{cache:'no-store',headers:{'Accept':'application/json'}});
  const payload=await response.json().catch(()=>({}));
  if(!response.ok)throw new Error(payload.error||`HTTP ${response.status}`);
  return payload;
}
function ensureCss(href,id){
  const wanted=new URL(href,location.href).href;
  const current=document.getElementById(id);
  if(current?.href===wanted)return;
  current?.remove();
  const link=document.createElement('link');
  link.id=id;link.rel='stylesheet';link.href=href;
  link.onerror=()=>link.remove();
  document.head.appendChild(link);
}
function loadScript(src,id,ready){
  return new Promise((resolve,reject)=>{
    if(ready?.())return resolve();
    const wanted=new URL(src,location.href).href;
    const current=document.getElementById(id);
    if(current){
      if(current.src===wanted&&current.dataset.smLoaded==='1')return resolve();
      current.remove();
    }
    const script=document.createElement('script');
    script.id=id;script.src=src;script.async=false;
    script.onload=()=>{script.dataset.smLoaded='1';resolve();};
    script.onerror=()=>{script.remove();reject(new Error(`Nem tölthető be: ${src}`));};
    document.head.appendChild(script);
  });
}
function o2Nav(){return q('#sidebar [data-page="oximetry"]');}
function ensureSidebarButton(){
  let button=o2Nav();
  if(button)return button;
  const nav=q('#sidebar .nav');if(!nav)return null;
  button=document.createElement('button');
  button.type='button';button.className='nav-item';button.dataset.page='oximetry';button.dataset.o2ringFeature='1';button.title='Oximetria';
  button.innerHTML='<svg viewBox="0 0 24 24"><path d="M3 13h3l2-5 4 9 2-5h7"/></svg><span>Oximetria</span>';
  const reports=q('[data-page="reports"]',nav);
  if(reports)nav.insertBefore(button,reports);else nav.appendChild(button);
  return button;
}
function openPlaceholder(){
  const page=placeholder();if(!page)return;
  document.querySelectorAll('.page.active').forEach(x=>x.classList.remove('active'));
  page.classList.remove('hidden');page.classList.add('active');
  q('#sidebar .nav-item.active')?.classList.remove('active');
  o2Nav()?.classList.add('active');
  if(!location.hash.startsWith('#oximetry'))history.replaceState({sleepmate:true},'','#oximetry');
}
function installPlaceholder(message){
  const button=ensureSidebarButton();
  let page=placeholder();
  if(!page){
    const existing=document.getElementById('page-oximetry');
    if(existing&&existing.dataset.o2RecoveryPlaceholder!=='1')return;
    page=document.createElement('section');
    page.id='page-oximetry';page.className='page hidden';page.dataset.o2RecoveryPlaceholder='1';page.dataset.o2ringFeature='1';
    const host=q('main')||q('.main')||document.body;
    host.appendChild(page);
  }
  page.innerHTML=`<div class="card" style="max-width:760px;margin:24px auto;padding:24px"><h2 style="margin-top:0">Oximetria</h2><p><strong>Az O2Ring háttérszolgáltatás most nem válaszol.</strong></p><p id="smO2RecoveryMessage">${String(message||'Ismeretlen O2Ring betöltési hiba.')}</p><p>A SleepMate automatikusan újrapróbálja. Az Oximetria menüpont azért marad látható, hogy a hiba többé ne tűnjön el nyomtalanul.</p><button type="button" id="smO2RecoveryRetry" class="btn primary">Újrapróbálás</button></div>`;
  q('#smO2RecoveryRetry',page)?.addEventListener('click',()=>requestRecovery('manual-retry'));
  if(button&&!button.dataset.o2RecoveryBound){
    button.dataset.o2RecoveryBound='1';
    button.addEventListener('click',event=>{
      if(!placeholder())return;
      event.preventDefault();event.stopImmediatePropagation();openPlaceholder();
    },true);
  }
  if(location.hash.startsWith('#oximetry'))openPlaceholder();
}
function removePlaceholder(){
  const page=placeholder();
  if(page)page.remove();
  const button=o2Nav();
  if(button?.dataset.o2RecoveryBound==='1')button.remove();
}
function installSidebarFallback(){
  if(o2Nav()||!window.SleepMateO2Ring)return;
  const button=ensureSidebarButton();if(!button)return;
  button.addEventListener('click',event=>{event.preventDefault();event.stopImmediatePropagation();window.SleepMateO2Ring?.open?.('live');},true);
}
function showRecoveryError(message){installPlaceholder(message);}
function clearRecoveryError(){document.getElementById('smO2RecoveryError')?.remove();}
function scheduleRetry(){
  if(retryTimer)return;
  const delays=[500,1200,2500,5000,10000,20000];
  const delay=delays[Math.min(attempts,delays.length-1)];attempts++;
  retryTimer=setTimeout(()=>{retryTimer=null;recover('retry').catch(()=>scheduleRetry());},delay);
}
async function waitForCore(){
  if(coreReady())return;
  for(let i=0;i<240;i++){
    await new Promise(resolve=>setTimeout(resolve,50));
    if(coreReady())return;
  }
}
async function recover(reason='boot'){
  if(running)return running;
  running=(async()=>{
    await waitForCore();
    const status=await api('/api/o2ring/status');
    if(!enabled(status)){
      attempts=0;removePlaceholder();clearRecoveryError();
      return;
    }
    window.__sleepmateO2Bootstrap=status;
    removePlaceholder();
    ensureCss(`/o2ring.css?v=${encodeURIComponent(BUILD)}`,'smO2CssRecovery');
    ensureCss(`/o2ring-v534.css?v=${encodeURIComponent(BUILD)}`,'smO2CssV534Recovery');

    if(!window.SleepMateO2Ring){
      await loadScript(`/o2ring.js?v=${encodeURIComponent(BUILD)}`,'smO2JsRecovery',()=>!!window.SleepMateO2Ring);
    }
    if(!window.SleepMateO2Ring)throw new Error('Az O2Ring runtime nem inicializálódott.');

    if(!realO2UiPresent()){
      try{window.SleepMateO2Ring.uninstall?.();}catch{}
      await Promise.resolve(window.SleepMateO2Ring.install?.());
    }else{
      await Promise.resolve(window.SleepMateO2Ring.refresh?.());
    }

    installSidebarFallback();
    if(!document.getElementById('page-oximetry')){
      try{window.SleepMateO2Ring.uninstall?.();}catch{}
      await Promise.resolve(window.SleepMateO2Ring.install?.());
      installSidebarFallback();
    }
    if(!realO2UiPresent())throw new Error('Az Oximetria oldal vagy a desktop menüpont nem jött létre.');

    attempts=0;clearRecoveryError();
    window.SleepMateV530?.renderBottomNav?.();
    window.SleepMateFrontendV534?.normalize?.();
    if(location.hash.startsWith('#oximetry'))window.SleepMateO2Ring.open?.('live');
    window.dispatchEvent(new CustomEvent('sleepmate-o2-recovered',{detail:{reason,build:BUILD}}));
  })().catch(error=>{showRecoveryError(error?.message||String(error));throw error;}).finally(()=>{running=null;});
  return running;
}

function requestRecovery(reason){recover(reason).catch(()=>scheduleRetry());}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>requestRecovery('dom-ready'),{once:true});else requestRecovery('immediate');
window.addEventListener('load',()=>requestRecovery('window-load'),{once:true});
window.addEventListener('pageshow',()=>requestRecovery('pageshow'));
window.addEventListener('focus',()=>{if(!realO2UiPresent())requestRecovery('focus');});
window.addEventListener('online',()=>requestRecovery('online'));
window.addEventListener('hashchange',()=>{if(location.hash.startsWith('#oximetry')&&!realO2UiPresent())requestRecovery('route');});
window.addEventListener('sleepmate-o2-config-ready',event=>{if(event.detail?.enabled)requestRecovery('config-ready');});

window.SleepMateO2RecoveryV5318={recover:requestRecovery,uiPresent:realO2UiPresent,version:BUILD};
})();
