(function(){
  const ENGINE='/app-engine119.js?v=130';
  const POLISH='/sleepsync-polish.js?v=130';
  const HYDRATION='/sleepsync-hydration-v529.js?v=130';

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

  // SleepSync presentation and settings hydration are non-critical add-ons.
  // They start after the main document, but hydration blocks settings/schedule
  // saving until the already-persisted backend configuration is actually in the
  // form. This prevents empty lazy fields from overwriting valid settings.
  window.addEventListener('load',()=>{
    if(!document.querySelector('script[data-sleepsync-polish="130"]')){
      const polish=document.createElement('script');
      polish.src=POLISH;
      polish.async=true;
      polish.dataset.sleepsyncPolish='130';
      document.head.appendChild(polish);
    }
    if(!document.querySelector('script[data-sleepsync-hydration="130"]')){
      const hydration=document.createElement('script');
      hydration.src=HYDRATION;
      hydration.async=true;
      hydration.dataset.sleepsyncHydration='130';
      document.head.appendChild(hydration);
    }
  },{once:true});
})();