(function(){
  const ENGINE='/app-engine119.js?v=130';
  const POLISH='/sleepsync-polish.js?v=130';
  const HYDRATION='/sleepsync-hydration-v529.js?v=130';
  const O2RING='/o2ring.js?v=5.3.0';

  function appendEngine(){
    if(window.__sleepmateStableEngine130)return;
    window.__sleepmateStableEngine130=true;
    const engine=document.createElement('script');
    engine.src=ENGINE;
    engine.async=false;
    document.head.appendChild(engine);
  }

  if(document.readyState==='loading'&&document.currentScript){
    window.__sleepmateStableEngine130=true;
    document.write('<script src="'+ENGINE+'"><\/script>');
  }else{
    appendEngine();
  }

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
    if(!document.querySelector('script[data-o2ring="530"]')){
      const o2=document.createElement('script');
      o2.src=O2RING;
      o2.async=true;
      o2.dataset.o2ring='530';
      document.head.appendChild(o2);
    }
  },{once:true});
})();