(function(){
  'use strict';
  let offlineActive=false;
  let recoveryBusy=false;

  function banner(offline){
    offlineActive=!!offline;
    window.__sleepmateOfflineActive=offlineActive;
    document.body?.classList.toggle('sleepmate-offline',offlineActive);
    const el=document.getElementById('offlineReadOnlyBanner');
    if(el)el.classList.toggle('hidden',!offlineActive);
  }

  const previousSet=window.setConnectionState;
  if(typeof previousSet==='function'){
    window.setConnectionState=function(offline,stamp=null){
      const result=previousSet(offline,stamp);
      banner(offline);
      return result;
    };
  }

  const previousWrite=window.apiWrite;
  if(typeof previousWrite==='function'){
    window.apiWrite=async function(...args){
      if(offlineActive){
        const err=new Error('Offline módban a SleepMate csak olvasható. A módosításhoz a SleepMate szervernek újra elérhetőnek kell lennie.');
        err.technical='SleepMate offline read-only guard';
        throw err;
      }
      return previousWrite(...args);
    };
  }

  async function recover(force=false){
    if(recoveryBusy||(!force&&!offlineActive))return;
    recoveryBusy=true;
    const controller=typeof AbortController==='function'?new AbortController():null;
    const timer=controller?setTimeout(()=>controller.abort(),4000):null;
    try{
      const response=await fetch('/api/version?_live='+Date.now(),{cache:'no-store',signal:controller?.signal});
      const cached=response.headers.get('X-SleepMate-Offline')==='1';
      if(response.ok&&!cached){
        window.setConnectionState?.(false,new Date().toISOString());
        if(typeof window.refreshData==='function')window.refreshData().catch(()=>{});
      }else if(force){banner(true)}
    }catch{if(force)banner(true)}finally{if(timer)clearTimeout(timer);recoveryBusy=false}
  }

  // The enhancement layer already owns the explicit Retry button and browser
  // online event. This runtime only provides periodic background recovery so a
  // single user action cannot launch duplicate probes or duplicate refreshes.
  window.__sleepmateCheckServerRecovery=recover;
  setInterval(()=>recover(false),12000);

  // v5.2.0 adaptive sleep analysis is an additive SleepMate feature. Load it
  // after the proven core + v5.1 enhancement stack is already alive; the module
  // itself waits for the core shell's .ready marker before touching the UI.
  if(!document.querySelector('script[data-sleepmate-sleep-analysis]')){
    const feature=document.createElement('script');
    feature.dataset.sleepmateSleepAnalysis='1';
    feature.src='/sleepmate-sleep.js';
    feature.async=false;
    document.head.appendChild(feature);
  }
})();
