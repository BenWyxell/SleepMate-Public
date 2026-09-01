(()=>{
  'use strict';
  function apply(){
    const value=document.getElementById('o2rLivePi');
    if(!value)return;
    const card=value.closest('.o2r-live-card');
    if(!card)return;
    const label=card.querySelector('label');
    const unit=card.querySelector('small');
    if(label&&label.textContent!=='Pulzus-jelerősség')label.textContent='Pulzus-jelerősség';
    if(unit&&unit.textContent!=='jel')unit.textContent='jel';
  }
  const observer=new MutationObserver(apply);
  observer.observe(document.documentElement,{childList:true,subtree:true});
  apply();
})();
