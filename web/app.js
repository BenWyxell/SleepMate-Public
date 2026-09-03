(function(){
  const ENGINE='/app-engine119.js?v=130';
  const POLISH='/sleepsync-polish.js?v=130';
  const HYDRATION='/sleepsync-hydration-v529.js?v=131';
  const FIRST_RUN='/first-run.js?v=4';

  function appendEngine(){
    if(window.__sleepmateStableEngine130)return;
    window.__sleepmateStableEngine130=true;
    const engine=document.createElement('script');
    engine.src=ENGINE;
    engine.async=false;
    document.head.appendChild(engine);
  }

  // Keep the proven parser-stream ordering for the integration engine.
  if(document.readyState==='loading'&&document.currentScript){
    window.__sleepmateStableEngine130=true;
    document.write('<script src="'+ENGINE+'"><\/script>');
  }else{
    appendEngine();
  }

  // Register the first-run module before window.load. It stays completely silent
  // on already-configured installations and can later be reopened from Settings.
  if(!document.querySelector('script[data-sleepmate-first-run="1"]')){
    const firstRun=document.createElement('script');
    firstRun.src=FIRST_RUN;
    firstRun.async=false;
    firstRun.dataset.sleepmateFirstRun='1';
    document.head.appendChild(firstRun);
  }

  // Load the complete SleepSync bundle as part of the initial application boot.
  // The engine publishes a readiness event after it has created the module UI;
  // polish and hydration bind to that event instead of racing window.load.
  for(const [src,key,value] of [[POLISH,'sleepsyncPolish','130'],[HYDRATION,'sleepsyncHydration','131']]){
    if(document.querySelector(`script[data-${key.replace(/[A-Z]/g,m=>'-'+m.toLowerCase())}="${value}"]`))continue;
    const script=document.createElement('script');script.src=src;script.async=false;script.dataset[key]=value;document.head.appendChild(script);
  }
})();
