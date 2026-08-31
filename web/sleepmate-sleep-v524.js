(function(){
  'use strict';

  let lastWidth=0;
  let queued=0;

  function requestSleepChartRedraw(){
    cancelAnimationFrame(queued);
    queued=requestAnimationFrame(()=>requestAnimationFrame(()=>{
      window.dispatchEvent(new Event('resize'));
    }));
  }

  function updateUsageDayLabel(){
    const canvas=document.getElementById('trendUsage');
    const label=canvas?.closest('.trend-card')?.querySelector('.panel-head span');
    if(label&&label.textContent!=='óra • ResMed terápiás nap szerint'){
      label.textContent='óra • ResMed terápiás nap szerint';
      label.title='A Dashboard ezt a ResMed DATALOG terápiás napjához csoportosítja. Az Alvások nézet az ébredés napjához csoportosít, ezért ugyanaz a kiírt dátum eltérő szakaszokat jelenthet.';
    }
  }

  function install(){
    const wrap=document.getElementById('v523ChartScroll');
    if(!wrap){setTimeout(install,50);return}

    const remeasure=()=>{
      const width=Math.round(wrap.getBoundingClientRect().width||wrap.clientWidth||0);
      if(width<120)return;
      if(width!==lastWidth){
        lastWidth=width;
        requestSleepChartRedraw();
      }
    };

    if('ResizeObserver' in window){
      const ro=new ResizeObserver(remeasure);
      ro.observe(wrap);
      wrap._sleepmateV524ResizeObserver=ro;
    }

    const mo=new MutationObserver(()=>{
      updateUsageDayLabel();
      if(wrap.offsetParent!==null)remeasure();
    });
    mo.observe(document.body,{subtree:true,attributes:true,attributeFilter:['class','hidden','style']});
    wrap._sleepmateV524MutationObserver=mo;

    window.addEventListener('pageshow',()=>setTimeout(remeasure,0));
    document.addEventListener('visibilitychange',()=>{if(!document.hidden)setTimeout(remeasure,0)});
    updateUsageDayLabel();
    remeasure();
    setTimeout(remeasure,80);
    setTimeout(remeasure,300);
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});
  else install();
})();
