(function(){
  'use strict';

  let initialized=false;
  let lastSuccessfulRun='';
  let busy=false;
  let timer=null;

  function refreshSleepView(at){
    try{
      window.dispatchEvent(new CustomEvent('sleepmate:data-refreshed',{detail:{source:'sleepsync',at:at||''}}));
    }catch{}

    // v5.2.3 owns the Alvások view and keeps its refresh() function private.
    // Its period selector's change handler is the public DOM-level refresh hook:
    // dispatching change preserves the user's currently selected period while
    // forcing a fresh /api/sleep-analysis request and a complete re-render.
    const period=document.getElementById('v523Period');
    if(period){
      try{period.dispatchEvent(new Event('change',{bubbles:true}));}catch{}
    }
  }

  async function inspectSleepSync(){
    if(busy||document.hidden)return;
    busy=true;
    try{
      const response=await fetch('/api/sleepsync/status?_sleep_refresh='+Date.now(),{
        cache:'no-store',
        headers:{Accept:'application/json'}
      });
      if(!response.ok)return;
      const status=await response.json().catch(()=>null);
      if(!status||typeof status!=='object')return;

      const run=String(status.last_run||'');
      if(!initialized){
        lastSuccessfulRun=run;
        initialized=true;
        return;
      }

      if(run&&run!==lastSuccessfulRun){
        lastSuccessfulRun=run;
        if(!status.running&&!status.last_error)refreshSleepView(run);
      }
    }catch{
      // Best-effort freshness bridge. SleepMate/PWA must remain usable when the
      // backend is temporarily unreachable; the normal view refresh still works.
    }finally{
      busy=false;
    }
  }

  function start(){
    if(timer)return;
    inspectSleepSync();
    timer=setInterval(inspectSleepSync,8000);
  }

  document.addEventListener('visibilitychange',()=>{if(!document.hidden)inspectSleepSync();});
  window.addEventListener('focus',inspectSleepSync);
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});
  else start();
})();
