(function(){
  'use strict';
  const UI={period:'30',data:null,active:'legacy',selectedDate:null,chartBars:[],chartRaf:0,loading:false,lastFetch:0};
  const TYPE_LABEL={main:'Fő alvás',nap:'Szundi',short:'Rövid használat'};
  const TYPE_ICON={main:'🌙',nap:'☁️',short:'◷'};
  const TYPE_COLOR={main:'#57c7ff',nap:'#a995ff',short:'#f4b85b'};

  function esc(v){return String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
  function fmt(sec){sec=Math.max(0,Math.round(Number(sec)||0));const h=Math.floor(sec/3600),m=Math.round((sec%3600)/60);return h?`${h} ó ${String(m).padStart(2,'0')} p`:`${m} p`}
  function fmtCompact(sec){sec=Math.max(0,Math.round(Number(sec)||0));const h=Math.floor(sec/3600),m=Math.round((sec%3600)/60);return h?`${h}:${String(m).padStart(2,'0')}`:`${m}p`}
  function dt(v){try{return new Date(v)}catch{return null}}
  function clock(v){const d=dt(v);return d?d.toLocaleTimeString('hu-HU',{hour:'2-digit',minute:'2-digit'}):'–'}
  function dayLabel(v){const d=dt(`${v}T12:00:00`);return d?d.toLocaleDateString('hu-HU',{year:'numeric',month:'short',day:'2-digit'}):v}
  function chartDay(v){const d=dt(`${v}T12:00:00`);return d?d.toLocaleDateString('hu-HU',{month:'2-digit',day:'2-digit'}).replace('.','.') : v.slice(5)}

  async function getJSON(url){
    const r=await fetch(`${url}${url.includes('?')?'&':'?'}_sleep=${Date.now()}`,{cache:'no-store',headers:{Accept:'application/json'}});
    const ct=(r.headers.get('content-type')||'').toLowerCase();
    if(!ct.includes('application/json'))throw new Error(`A SleepMate nem JSON választ adott (${r.status}).`);
    const j=await r.json();if(!r.ok||j.error)throw new Error(j.error||`HTTP ${r.status}`);return j;
  }
  async function postJSON(url,data){
    const r=await fetch(url,{method:'POST',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
    const j=await r.json().catch(()=>({}));if(!r.ok||j.error)throw new Error(j.error||`HTTP ${r.status}`);return j;
  }

  function installStyle(){
    if(document.getElementById('sleepmateSleepStyle'))return;
    const s=document.createElement('style');s.id='sleepmateSleepStyle';s.textContent=`
      .sleepmate-sessions-tabs{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 14px}
      .sleepmate-sessions-tabs button{border:1px solid rgba(130,183,220,.23);background:rgba(10,25,45,.72);color:#b9cad8;border-radius:999px;padding:8px 14px;font-weight:750;cursor:pointer}
      .sleepmate-sessions-tabs button.active{background:linear-gradient(135deg,rgba(48,184,219,.22),rgba(131,104,238,.24));border-color:rgba(89,206,232,.55);color:#f4fbff;box-shadow:0 8px 24px rgba(26,119,159,.12)}
      #sleepmateSleepView[hidden],#sleepmateLegacySessionsView[hidden]{display:none!important}
      .sleep-overview-head{display:flex;justify-content:space-between;align-items:flex-end;gap:14px;flex-wrap:wrap;margin:0 0 14px}
      .sleep-overview-head h2{margin:0 0 4px}.sleep-overview-head p{margin:0}
      .sleep-period-switch{display:flex;gap:6px;flex-wrap:wrap}
      .sleep-period-switch button{padding:7px 10px;border-radius:10px;border:1px solid rgba(130,183,220,.2);background:rgba(12,28,48,.72);color:#adc2d2;cursor:pointer}
      .sleep-period-switch button.active{color:#fff;border-color:rgba(92,205,231,.52);background:rgba(55,175,210,.16)}
      .sleep-summary-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:12px}
      .sleep-summary-card{min-width:0;padding:15px 16px;border-radius:16px;border:1px solid rgba(118,169,208,.16);background:linear-gradient(145deg,rgba(13,31,53,.92),rgba(10,22,39,.88));box-shadow:0 12px 30px rgba(0,0,0,.11)}
      .sleep-summary-card label{display:block;color:#8fa8ba;font-size:11px;margin-bottom:6px}.sleep-summary-card strong{font-size:22px;color:#f2f8fc}.sleep-summary-card small{display:block;margin-top:5px;color:#8ea3b3}
      .sleep-panel{border:1px solid rgba(118,169,208,.16);border-radius:17px;background:rgba(10,24,42,.82);padding:14px;margin-bottom:12px;overflow:hidden}
      .sleep-panel-head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;flex-wrap:wrap;margin-bottom:10px}.sleep-panel-head h3{margin:0 0 3px}.sleep-panel-head span{color:#8fa7b8;font-size:11px}
      .sleep-legend{display:flex;gap:12px;flex-wrap:wrap;color:#a9bdcb;font-size:11px}.sleep-legend i{display:inline-block;width:9px;height:9px;border-radius:3px;margin-right:5px;vertical-align:0}
      .sleep-chart-scroll{width:100%;overflow-x:auto;overflow-y:hidden;padding-bottom:4px;overscroll-behavior-x:contain}.sleep-chart-scroll canvas{height:330px;display:block;max-width:none}
      .sleep-chart-tooltip{position:fixed;z-index:1100;pointer-events:none;min-width:160px;max-width:240px;padding:9px 11px;border:1px solid rgba(125,190,224,.25);border-radius:12px;background:rgba(5,16,29,.95);box-shadow:0 12px 34px rgba(0,0,0,.3);color:#eaf4fa;font-size:11px;line-height:1.45}.sleep-chart-tooltip.hidden{display:none}
      .sleep-learning-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.sleep-learning-grid div{padding:10px 11px;border:1px solid rgba(120,174,208,.12);border-radius:12px;background:rgba(14,31,50,.62);min-width:0}.sleep-learning-grid span{display:block;color:#8198aa;font-size:10px;margin-bottom:4px}.sleep-learning-grid strong{display:block;color:#dceaf3;font-size:12px;overflow-wrap:anywhere}
      .sleep-table-wrap{overflow:auto}.sleep-table{width:100%;border-collapse:collapse;min-width:760px}.sleep-table th,.sleep-table td{padding:9px 10px;border-bottom:1px solid rgba(120,169,199,.1);text-align:left;white-space:nowrap}.sleep-table th{font-size:10px;text-transform:uppercase;letter-spacing:.04em;color:#7f9aac}.sleep-table td{font-size:12px;color:#d8e5ed}.sleep-table tr[data-sleep-day]{cursor:pointer}.sleep-table tr[data-sleep-day]:hover{background:rgba(73,171,204,.07)}
      .sleep-type-pill{display:inline-flex;align-items:center;gap:5px;padding:4px 7px;border-radius:999px;border:1px solid color-mix(in srgb,var(--sleep-type) 48%,transparent);background:color-mix(in srgb,var(--sleep-type) 12%,transparent);font-size:10px;color:#eaf5fb;white-space:nowrap}
      .sleep-block-list{display:grid;gap:8px}.sleep-block-row{display:grid;grid-template-columns:minmax(180px,1.25fr) minmax(100px,.65fr) minmax(80px,.45fr) minmax(155px,.75fr) auto;gap:10px;align-items:center;padding:10px 11px;border:1px solid rgba(120,174,208,.13);border-radius:13px;background:rgba(13,29,48,.58)}
      .sleep-block-row>div{min-width:0}.sleep-block-time strong{display:block;font-size:12px;color:#edf7fc}.sleep-block-time span{display:block;color:#839cab;font-size:10px;margin-top:3px}.sleep-block-row select{width:100%;min-width:0;background:#0d2035;color:#eaf4fa;border:1px solid rgba(125,183,215,.24);border-radius:9px;padding:7px}.sleep-block-row button{padding:7px 9px;white-space:nowrap}.sleep-manual-badge{display:inline-block;margin-left:5px;color:#f4c86b;font-size:9px}
      .sleep-empty{padding:28px;text-align:center;color:#8ca4b4}
      .metric.session-status.sleep-summary-clickable{cursor:pointer;position:relative}.metric.session-status.sleep-summary-clickable:after{content:'›';position:absolute;right:12px;top:50%;transform:translateY(-50%);font-size:24px;color:rgba(142,213,231,.55)}
      .sleep-status{min-height:18px;margin:7px 0;color:#92aabd;font-size:11px}.sleep-status.error{color:#ff9b9b}
      @media(max-width:900px){.sleep-summary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.sleep-learning-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.sleep-block-row{grid-template-columns:minmax(0,1fr) minmax(110px,.55fr)}.sleep-block-row .sleep-block-ahi,.sleep-block-row .sleep-block-session{grid-column:auto}.sleep-block-row .sleep-block-open{grid-column:1/-1;justify-self:start}}
      @media(max-width:600px){.sleep-summary-grid{grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:7px}.sleep-summary-card{padding:12px}.sleep-summary-card strong{font-size:18px}.sleep-panel{padding:11px}.sleep-learning-grid{grid-template-columns:minmax(0,1fr)}.sleep-block-row{grid-template-columns:minmax(0,1fr);gap:7px}.sleep-block-row .sleep-block-open{grid-column:auto;width:100%}.sleep-period-switch{width:100%}.sleep-period-switch button{flex:1;min-width:52px}.sleep-overview-head{align-items:flex-start}.sleep-table{min-width:700px}.sleep-chart-scroll canvas{height:300px}}
    `;document.head.appendChild(s);
  }

  function mount(){
    const page=document.getElementById('page-sessions');if(!page||document.getElementById('sleepmateSleepView'))return false;
    const legacy=document.createElement('div');legacy.id='sleepmateLegacySessionsView';
    while(page.firstChild)legacy.appendChild(page.firstChild);
    const tabs=document.createElement('div');tabs.className='sleepmate-sessions-tabs';tabs.innerHTML='<button type="button" data-sleep-tab="legacy" class="active">Szekciók</button><button type="button" data-sleep-tab="sleep">Alvások</button>';
    const view=document.createElement('div');view.id='sleepmateSleepView';view.hidden=true;view.innerHTML=`
      <div class="sleep-overview-head"><div><h2>Alvások</h2><p class="muted">Automatikus, időpont-független felismerés a meglévő CPAP-szekciókból.</p></div><div class="sleep-period-switch" id="sleepPeriodSwitch"><button type="button" data-sleep-period="7">7 nap</button><button type="button" data-sleep-period="30" class="active">30 nap</button><button type="button" data-sleep-period="90">90 nap</button><button type="button" data-sleep-period="all">Teljes</button></div></div>
      <div class="sleep-status" id="sleepStatus"></div>
      <section class="sleep-summary-grid">
        <article class="sleep-summary-card"><label>Fő alvás átlaga</label><strong id="sleepAvgMain">–</strong><small>domináns alvásblokkok</small></article>
        <article class="sleep-summary-card"><label>Napi összes alvás</label><strong id="sleepAvgTotal">–</strong><small>fő + szundi + rövid</small></article>
        <article class="sleep-summary-card"><label>Szundik</label><strong id="sleepNapCount">–</strong><small id="sleepNapTotal">–</small></article>
        <article class="sleep-summary-card"><label>Töredezett fő alvás</label><strong id="sleepFragmented">–</strong><small id="sleepShortCount">–</small></article>
      </section>
      <section class="sleep-panel"><div class="sleep-panel-head"><div><h3>Alvások napi összetétele</h3><span>Egy oszlop = egy nap; az oszlop tetején a napi teljes idő.</span></div><div class="sleep-legend"><span><i style="background:${TYPE_COLOR.main}"></i>Fő alvás</span><span><i style="background:${TYPE_COLOR.nap}"></i>Szundi</span><span><i style="background:${TYPE_COLOR.short}"></i>Rövid használat</span></div></div><div class="sleep-chart-scroll" id="sleepChartScroll"><canvas id="sleepStackedChart" height="330"></canvas></div></section>
      <section class="sleep-panel"><div class="sleep-panel-head"><div><h3>Adaptív felismerés</h3><span>A kezdési napszak nem része a besorolási pontszámnak.</span></div></div><div class="sleep-learning-grid" id="sleepLearningGrid"></div></section>
      <section class="sleep-panel"><div class="sleep-panel-head"><div><h3>Napi bontás</h3><span>Kattints egy napra a blokkok részletes besorolásához.</span></div></div><div class="sleep-table-wrap"><table class="sleep-table"><thead><tr><th>Nap</th><th>Fő alvás</th><th>Szundi</th><th>Rövid</th><th>Összesen</th><th>Fő AHI</th><th>Blokkok</th></tr></thead><tbody id="sleepTableBody"></tbody></table></div></section>
      <section class="sleep-panel" id="sleepDayDetail"><div class="sleep-empty">Válassz egy napot a részletekhez.</div></section>`;
    page.appendChild(tabs);page.appendChild(legacy);page.appendChild(view);
    tabs.addEventListener('click',e=>{const b=e.target.closest('[data-sleep-tab]');if(!b)return;selectTab(b.dataset.sleepTab,true)});
    document.getElementById('sleepPeriodSwitch').addEventListener('click',e=>{const b=e.target.closest('[data-sleep-period]');if(!b)return;UI.period=b.dataset.sleepPeriod;document.querySelectorAll('[data-sleep-period]').forEach(x=>x.classList.toggle('active',x.dataset.sleepPeriod===UI.period));refresh(true)});
    document.getElementById('sleepTableBody').addEventListener('click',e=>{const tr=e.target.closest('tr[data-sleep-day]');if(tr){UI.selectedDate=tr.dataset.sleepDay;renderDayDetail()}});
    document.getElementById('sleepDayDetail').addEventListener('change',async e=>{const sel=e.target.closest('select[data-sleep-block]');if(!sel)return;sel.disabled=true;setStatus('Besorolás mentése…');try{const j=await postJSON('/api/sleep-analysis/override',{block_id:sel.dataset.sleepBlock,type:sel.value,period:UI.period});UI.data=j.analysis;UI.lastFetch=Date.now();renderAll();setStatus(sel.value==='auto'?'Automatikus besorolás visszaállítva.':'Kézi javítás elmentve.')}catch(err){setStatus(err.message,true)}finally{sel.disabled=false}});
    document.getElementById('sleepDayDetail').addEventListener('click',e=>{const b=e.target.closest('[data-sleep-open-day]');if(b)location.hash=`#dashboard/${b.dataset.sleepOpenDay}`});
    const canvas=document.getElementById('sleepStackedChart');canvas.addEventListener('pointermove',chartPointer);canvas.addEventListener('pointerleave',hideTooltip);canvas.addEventListener('pointerdown',chartPointer);
    window.addEventListener('resize',()=>scheduleChart());
    return true;
  }

  function setStatus(msg,error=false){const el=document.getElementById('sleepStatus');if(!el)return;el.textContent=msg||'';el.classList.toggle('error',!!error)}
  function selectTab(name,updateUrl=false){
    UI.active=name==='sleep'?'sleep':'legacy';const legacy=document.getElementById('sleepmateLegacySessionsView'),sleep=document.getElementById('sleepmateSleepView');if(!legacy||!sleep)return;
    legacy.hidden=UI.active==='sleep';sleep.hidden=UI.active!=='sleep';document.querySelectorAll('[data-sleep-tab]').forEach(b=>b.classList.toggle('active',b.dataset.sleepTab===UI.active));
    if(updateUrl){history.replaceState({sleepmate:true},'',UI.active==='sleep'?'#sessions/sleep':'#sessions')}
    if(UI.active==='sleep'){refresh(false);setTimeout(scheduleChart,50)}
  }
  function selectFromHash(){const raw=(location.hash||'').replace(/^#/,'').split('/');if(raw[0]==='sessions')selectTab(raw[1]==='sleep'?'sleep':'legacy',false)}

  async function refresh(force=false){
    if(UI.loading)return;if(!force&&UI.data&&Date.now()-UI.lastFetch<30000){renderAll();return}
    UI.loading=true;setStatus('Alvásblokkok elemzése…');try{UI.data=await getJSON(`/api/sleep-analysis?period=${encodeURIComponent(UI.period)}`);UI.lastFetch=Date.now();renderAll();setStatus(`Kész • ${UI.data.learned?.history_blocks||0} történeti alvásblokk elemezve.`)}catch(err){setStatus(err.message,true)}finally{UI.loading=false}
  }

  function renderAll(){if(!UI.data)return;renderSummary();renderLearning();renderTable();renderDayDetail();updateDashboardCard();scheduleChart()}
  function renderSummary(){const s=UI.data.summary||{};const set=(id,v)=>{const el=document.getElementById(id);if(el)el.textContent=v};set('sleepAvgMain',fmt(s.average_main_seconds));set('sleepAvgTotal',fmt(s.average_total_seconds));set('sleepNapCount',String(s.nap_count||0));set('sleepNapTotal',`${fmt(s.nap_seconds)} összesen`);set('sleepFragmented',String(s.fragmented_main_days||0));set('sleepShortCount',`${s.short_count||0} rövid használat`)}
  function renderLearning(){const l=UI.data.learned||{},cfg=UI.data.settings||{},el=document.getElementById('sleepLearningGrid');if(!el)return;el.innerHTML=`<div><span>Tanult jellemző fő alvás</span><strong>${l.typical_main_seconds?fmt(l.typical_main_seconds):'Még nincs elég adat'}</strong></div><div><span>Elemzett történet</span><strong>${l.history_blocks||0} alvásblokk</strong></div><div><span>Egy blokk megszakítása</span><strong>legfeljebb ${cfg.merge_gap_minutes||90} perc</strong></div><div><span>Rövid használat</span><strong>${cfg.short_usage_minutes||20} perc alatt</strong></div><div><span>Dominancia-környezet</span><strong>${cfg.local_window_hours||24} órás gördülő ablak</strong></div><div><span>Töredezett fő alvás</span><strong>legfeljebb ${cfg.fragment_gap_minutes||180} perc szünet</strong></div><div><span>Kezdési időpont</span><strong>nem minősít</strong></div><div><span>Kézi javítások</span><strong>${UI.data.overrides||0} rögzített felülbírálás</strong></div>`}
  function renderTable(){const body=document.getElementById('sleepTableBody');if(!body)return;const rows=[...(UI.data.rows||[])].reverse();body.innerHTML=rows.length?rows.map(r=>`<tr data-sleep-day="${esc(r.date)}"><td><strong>${esc(dayLabel(r.date))}</strong></td><td>${fmt(r.main_seconds)}</td><td>${r.nap_count?`${fmt(r.nap_seconds)} · ${r.nap_count}×`:'–'}</td><td>${r.short_count?`${fmt(r.short_seconds)} · ${r.short_count}×`:'–'}</td><td><strong>${fmt(r.total_seconds)}</strong></td><td>${r.main_ahi==null?'–':Number(r.main_ahi).toFixed(2)}</td><td>${(r.blocks||[]).length}</td></tr>`).join(''):'<tr><td colspan="7">Nincs elemezhető alvásadat.</td></tr>'}

  function renderDayDetail(){const box=document.getElementById('sleepDayDetail');if(!box||!UI.data)return;const rows=UI.data.rows||[];let row=rows.find(r=>r.date===UI.selectedDate);if(!row&&rows.length){row=rows[rows.length-1];UI.selectedDate=row.date}if(!row){box.innerHTML='<div class="sleep-empty">Nincs elemezhető alvásadat.</div>';return}box.innerHTML=`<div class="sleep-panel-head"><div><h3>${esc(dayLabel(row.date))}</h3><span>${fmt(row.total_seconds)} összes CPAP-használat • fő AHI ${row.main_ahi==null?'–':Number(row.main_ahi).toFixed(2)}</span></div></div><div class="sleep-block-list">${(row.blocks||[]).map(blockHtml).join('')}</div>`}
  function blockHtml(b){const type=b.type||'nap',manual=b.manual?'<span class="sleep-manual-badge">kézi</span>':'',src=(b.source_days||[])[0]||'';return `<div class="sleep-block-row"><div class="sleep-block-time"><span class="sleep-type-pill" style="--sleep-type:${TYPE_COLOR[type]||'#8fa7b8'}">${TYPE_ICON[type]||''} ${TYPE_LABEL[type]||type}</span>${manual}<strong>${clock(b.start)}–${clock(b.end)} · ${fmt(b.therapy_seconds)}</strong><span>${b.session_count||0} CPAP-szekció${b.session_count===1?'':' • összefűzve'}${b.automatic_type&&b.automatic_type!==type?` • automatikus: ${TYPE_LABEL[b.automatic_type]||b.automatic_type}`:''}</span></div><div class="sleep-block-ahi"><span class="muted">AHI</span><strong>${Number(b.ahi||0).toFixed(2)}</strong></div><div class="sleep-block-session"><span class="muted">Forrásnap</span><strong>${src?esc(src.slice(0,4)+'-'+src.slice(4,6)+'-'+src.slice(6,8)):'–'}</strong></div><div><select data-sleep-block="${esc(b.id)}" aria-label="Alvásblokk besorolása"><option value="auto"${!b.manual?' selected':''}>Automatikus</option><option value="main"${b.manual&&type==='main'?' selected':''}>Fő alvás</option><option value="nap"${b.manual&&type==='nap'?' selected':''}>Szundi</option><option value="short"${b.manual&&type==='short'?' selected':''}>Rövid használat</option></select></div><button class="sleep-block-open" type="button" data-sleep-open-day="${esc(src)}"${src?'':' disabled'}>Terápiás részletek</button></div>`}

  function updateDashboardCard(){const latest=UI.data?.latest,card=document.querySelector('.metric.session-status');if(!latest||!card)return;card.classList.add('sleep-summary-clickable');card.setAttribute('role','button');card.tabIndex=0;const label=card.querySelector('label'),strong=document.getElementById('latestStatus'),small=document.getElementById('latestSessions');if(label)label.textContent='Alvások';if(strong)strong.textContent=fmt(latest.total_seconds);if(small){const parts=[`Fő ${fmtCompact(latest.main_seconds)}`];if(latest.nap_seconds)parts.push(`Szundi ${fmtCompact(latest.nap_seconds)}`);if(latest.short_seconds)parts.push(`Rövid ${fmtCompact(latest.short_seconds)}`);small.textContent=parts.join(' • ')}if(!card.dataset.sleepBound){card.dataset.sleepBound='1';const open=()=>{location.hash='#sessions/sleep'};card.addEventListener('click',open);card.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open()}})}}

  function scheduleChart(){cancelAnimationFrame(UI.chartRaf);UI.chartRaf=requestAnimationFrame(drawChart)}
  function drawChart(){const canvas=document.getElementById('sleepStackedChart'),wrap=document.getElementById('sleepChartScroll');if(!canvas||!wrap||!UI.data)return;const rows=UI.data.rows||[],cssW=Math.max(wrap.clientWidth||320,rows.length*62+70),cssH=innerWidth<=600?300:330,dpr=Math.max(1,window.devicePixelRatio||1);canvas.style.width=`${cssW}px`;canvas.style.height=`${cssH}px`;canvas.width=Math.round(cssW*dpr);canvas.height=Math.round(cssH*dpr);const x=canvas.getContext('2d');x.setTransform(dpr,0,0,dpr,0,0);x.clearRect(0,0,cssW,cssH);const pad={l:48,r:18,t:31,b:38},pw=cssW-pad.l-pad.r,ph=cssH-pad.t-pad.b,max=Math.max(3600,...rows.map(r=>Number(r.total_seconds)||0)),ceil=Math.ceil(max/3600)*3600;UI.chartBars=[];x.font='10px system-ui,-apple-system,sans-serif';x.textBaseline='middle';x.strokeStyle='rgba(137,177,202,.12)';x.fillStyle='rgba(151,180,199,.7)';x.lineWidth=1;for(let i=0;i<=4;i++){const y=pad.t+ph-(ph*i/4),val=ceil*i/4;x.beginPath();x.moveTo(pad.l,y);x.lineTo(pad.l+pw,y);x.stroke();x.textAlign='right';x.fillText(`${(val/3600).toFixed(val%3600?1:0)}h`,pad.l-8,y)}if(!rows.length){x.textAlign='center';x.fillText('Nincs adat',pad.l+pw/2,pad.t+ph/2);return}const step=pw/rows.length,bw=Math.min(38,Math.max(20,step*.62));rows.forEach((r,i)=>{const cx=pad.l+step*i+step/2;let y=pad.t+ph;const segs=[['main',Number(r.main_seconds)||0],['nap',Number(r.nap_seconds)||0],['short',Number(r.short_seconds)||0]];const bar={row:r,x1:cx-bw/2,x2:cx+bw/2,top:y,bottom:pad.t+ph};segs.forEach(([kind,val])=>{if(val<=0)return;const h=Math.max(1,ph*val/ceil);y-=h;x.fillStyle=TYPE_COLOR[kind];x.globalAlpha=.86;x.fillRect(cx-bw/2,y,bw,h);x.globalAlpha=1;if(h>=19&&bw>=28){x.fillStyle='#06111d';x.font='700 9px system-ui,-apple-system,sans-serif';x.textAlign='center';x.fillText(fmtCompact(val),cx,y+h/2)}});bar.top=y;UI.chartBars.push(bar);x.fillStyle='#dbeaf2';x.font='700 10px system-ui,-apple-system,sans-serif';x.textAlign='center';x.fillText(fmtCompact(r.total_seconds),cx,Math.max(12,y-10));x.fillStyle='rgba(151,180,199,.78)';x.font='9px system-ui,-apple-system,sans-serif';x.fillText(chartDay(r.date),cx,pad.t+ph+20)})}
  function chartPointer(e){const canvas=document.getElementById('sleepStackedChart');if(!canvas||!UI.chartBars.length)return;const rect=canvas.getBoundingClientRect(),sx=canvas.width/(window.devicePixelRatio||1)/rect.width,px=(e.clientX-rect.left)*sx,bar=UI.chartBars.find(b=>px>=b.x1&&px<=b.x2);if(!bar){hideTooltip();return}let tip=document.getElementById('sleepChartTooltip');if(!tip){tip=document.createElement('div');tip.id='sleepChartTooltip';tip.className='sleep-chart-tooltip hidden';document.body.appendChild(tip)}const r=bar.row;tip.innerHTML=`<strong>${esc(dayLabel(r.date))}</strong><br>🌙 Fő alvás: ${fmt(r.main_seconds)}<br>☁️ Szundi: ${fmt(r.nap_seconds)}${r.nap_count?` (${r.nap_count}×)`:''}<br>◷ Rövid: ${fmt(r.short_seconds)}${r.short_count?` (${r.short_count}×)`:''}<br><b>Összesen: ${fmt(r.total_seconds)}</b>`;tip.classList.remove('hidden');const left=Math.min(innerWidth-tip.offsetWidth-8,Math.max(8,e.clientX+12)),top=Math.min(innerHeight-tip.offsetHeight-8,Math.max(8,e.clientY+12));tip.style.left=`${left}px`;tip.style.top=`${top}px`}
  function hideTooltip(){document.getElementById('sleepChartTooltip')?.classList.add('hidden')}

  function patchCore(){
    if(window.__sleepmateSleepCorePatched)return;window.__sleepmateSleepCorePatched=true;
    if(typeof window.loadDashboardOverview==='function'){const orig=window.loadDashboardOverview;window.loadDashboardOverview=async function(){const out=await orig.apply(this,arguments);setTimeout(()=>refresh(true),40);return out}}
    if(typeof window.loadSessionsPage==='function'){const orig=window.loadSessionsPage;window.loadSessionsPage=async function(){const out=await orig.apply(this,arguments);setTimeout(()=>{selectFromHash();if(UI.active==='sleep')refresh(true)},40);return out}}
  }

  function install(){installStyle();if(!mount())return false;patchCore();selectFromHash();refresh(true);window.addEventListener('hashchange',()=>setTimeout(selectFromHash,20));document.addEventListener('click',e=>{if(e.target.closest('#refresh'))setTimeout(()=>refresh(true),1800)},true);document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible'&&Date.now()-UI.lastFetch>60000)refresh(true)});return true}
  function wait(attempt=0){const shell=document.querySelector('.hidden-until-ready'),ready=!!shell&&shell.classList.contains('ready')&&typeof window.route==='function';if(ready&&install())return;if(attempt<600)setTimeout(()=>wait(attempt+1),50)}
  wait();
})();
