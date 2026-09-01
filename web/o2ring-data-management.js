(()=>{
  'use strict';
  const MARK='o2rDataManagement';
  let busy=false;

  async function api(path,options={}){
    const response=await fetch(path,{cache:'no-store',...options,headers:{'Content-Type':'application/json',...(options.headers||{})}});
    const data=await response.json().catch(()=>({}));
    if(!response.ok||data.error)throw new Error(data.error||`HTTP ${response.status}`);
    return data;
  }

  function install(){
    if(document.getElementById(MARK))return;
    const details=document.getElementById('o2rDetails');
    if(!details)return;
    const section=document.createElement('section');
    section.id=MARK;
    section.className='o2r-device-config o2r-data-management';
    section.dataset.o2ringFeature='1';
    section.innerHTML=`
      <h4>Oximetriai mérési adatok</h4>
      <p class="muted">A SleepMate-ben tárolt O2Ring felvételek és nyers VLD fájlok külön törölhetők. A megjegyzett gyűrű, a Bluetooth-párosítási cél és az O2Ring beállításai megmaradnak.</p>
      <p class="muted">A már törölt, de még a gyűrű memóriájában lévő régi felvételeket a SleepMate nem tölti vissza automatikusan.</p>
      <div class="o2r-setting-actions"><button id="o2rDeleteLocalData" type="button" class="danger-action">Helyi O2Ring mérési adatok törlése</button></div>
      <p id="o2rDeleteLocalDataMsg" class="muted"></p>`;
    details.appendChild(section);
    document.getElementById('o2rDeleteLocalData').onclick=removeData;
  }

  async function removeData(){
    if(busy)return;
    const button=document.getElementById('o2rDeleteLocalData');
    const msg=document.getElementById('o2rDeleteLocalDataMsg');
    const confirmed=window.confirm('Biztosan törlöd a SleepMate-ben tárolt összes O2Ring mérési adatot?\n\nA gyűrű megjegyzése és a beállításai megmaradnak. A törölt felvételek nem szinkronizálódnak vissza a gyűrű memóriájából.');
    if(!confirmed)return;
    busy=true;
    if(button)button.disabled=true;
    if(msg)msg.textContent='O2Ring mérési adatok törlése…';
    try{
      const result=await api('/api/o2ring/delete-data',{method:'POST',body:JSON.stringify({confirm:'DELETE_OXIMETRY'})});
      if(msg)msg.textContent=`Törlés kész: ${result.recordings_deleted||0} felvétel és ${result.raw_files_deleted||0} nyers fájl eltávolítva. A gyűrű megjegyzése megmaradt.`;
      window.SleepMateO2Ring?.refresh?.();
      window.SleepMateO2Combined?.refresh?.();
      window.dispatchEvent(new CustomEvent('sleepmate:o2ring-data-deleted',{detail:result}));
    }catch(error){
      if(msg)msg.textContent=error?.message||String(error);
    }finally{
      busy=false;
      if(button)button.disabled=false;
    }
  }

  const observer=new MutationObserver(()=>install());
  function start(){observer.observe(document.documentElement,{subtree:true,childList:true});install()}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
  window.SleepMateO2DataManagement={install};
})();
