(()=>{
  'use strict';
  function install(){
    const grid=document.querySelector('.report-check-grid.report-sections');
    if(!grid||grid.querySelector('[data-report-section="oximetry"]'))return;
    const label=document.createElement('label');
    label.className='o2ring-report-option';
    label.dataset.o2ringFeature='1';
    label.innerHTML='<input type="checkbox" data-report-section="oximetry" checked><span><b>Oximetria és pulzus</b><small>SpO₂ • minimum • T90 • ODI3/ODI4 • pulzus • CPAP-időre illesztett trendek</small></span>';
    const pressure=grid.querySelector('[data-report-section="pressure_leak"]')?.closest('label');
    if(pressure?.nextSibling)grid.insertBefore(label,pressure.nextSibling);else grid.appendChild(label);
  }
  function uninstall(){document.querySelectorAll('.o2ring-report-option,[data-report-section="oximetry"]').forEach(el=>{const owned=el.closest?.('.o2ring-report-option')||el;if(owned?.dataset?.o2ringFeature==='1'||owned?.classList?.contains('o2ring-report-option'))owned.remove()})}
  window.SleepMateO2RingReport={install,uninstall};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();
})();
