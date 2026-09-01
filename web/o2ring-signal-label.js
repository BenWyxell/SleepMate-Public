(()=>{
  'use strict';
  function apply(){
    const value=document.getElementById('o2rLivePi');
    if(!value)return;
    const card=value.closest('.o2r-live-card');
    if(!card)return;
    const label=card.querySelector('label');
    const unit=card.querySelector('small');
    if(label)label.textContent='Pulzus-jelerősség';
    if(unit)unit.textContent='jel';
    value.id='o2rLiveSignalStrength';
  }
  const observer=new MutationObserver(apply);
  observer.observe(document.documentElement,{childList:true,subtree:true});
  apply();
  // Older o2ring.js bundles still update #o2rLivePi. Keep a compatibility
  // mirror without presenting the protocol byte as a medical perfusion index.
  const mirror=()=>{
    const target=document.getElementById('o2rLiveSignalStrength');
    if(!target)return;
    if(!document.getElementById('o2rLivePi')){
      const hidden=document.createElement('span');
      hidden.id='o2rLivePi';
      hidden.hidden=true;
      target.parentNode.appendChild(hidden);
      new MutationObserver(()=>{target.textContent=hidden.textContent||'–'}).observe(hidden,{childList:true,characterData:true,subtree:true});
    }
  };
  new MutationObserver(mirror).observe(document.documentElement,{childList:true,subtree:true});
  mirror();
})();
