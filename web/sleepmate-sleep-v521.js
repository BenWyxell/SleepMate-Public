(function(){
  'use strict';

  const S={period:'30',start:'',end:'',data:null,selectedDate:null,view:'daily',loading:false,chartBars:[],raf:0};
  const TYPE_LABEL={main:'Fő alvás',nap:'Szundi',short:'Rövid használat'};
  const TYPE_COLOR={main:'#57c7ff',nap:'#a995ff',short:'#f4b85b'};
  const TYPE_ICON={main:'🌙',nap:'☁️',short:'◷'};

  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const asDate=v=>{const d=new Date(v);return Number.isNaN(d.getTime())?null:d};
  function fmt(sec){sec=Math.max(0,Math.round(Number(sec)||0));const h=Math.floor(sec/3600),m=Math.round((sec%3600)/60);return h?`${h} ó ${String(m).padStart(2,'0')} p`:`${m} p`}
  function compact(sec){sec=Math.max(0,Math.round(Number(sec)||0));const h=Math.floor(sec/3600),m=Math.round((sec%3600)/60);return h?`${h}:${String(m).padStart(2,'0')}`:`${m}p`}
  function dayLabel(v){const d=asDate(`${v}T12:00:00`);return d?d.toLocaleDateString('hu-HU',{year:'numeric',month:'short',day:'2-digit'}):v}
  function shortDay(v){const d=asDate(`${v}T12:00:00`);return d?d.toLocaleDateString('hu-HU',{month:'2-digit',day:'2-digit'}):v}
  function dtLabel(v){const d=asDate(v);return d?d.toLocaleString('hu-HU',{year:'numeric',month:'short',day:'2-digit',hour:'2-digit',minute:'2-digit'}):'–'}
  function onlyTime(v){const d=asDate(v);return d?d.toLocaleTimeString('hu-HU',{hour:'2-digit',minute:'2-digit'}):'–'}
  function sourceDay(v){const s=String(v||'');return /^\d{8}$/.test(s)?`${s.slice(0,4)}-${s.slice(4,6)}-${s.slice(6,8)}`:s||'–'}

  async function getJSON(url){
    const r=await fetch(`${url}${url.includes('?')?'&':'?'}_v521=${Date.now()}`,{cache:'no-store',headers:{Accept:'application/json'}});
    const j=await r.json().catch(()=>({}));
    if(!r.ok||j.error)throw new Error(j.error||`HTTP ${r.status}`);
    return j;
  }
  async function postJSON(url,data){
    const r=await fetch(url,{method:'POST',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
    const j=await r.json().catch(()=>({}));
    if(!r.ok||j.error)throw new Error(j.error||`HTTP ${r.status}`);
    return j;
  }

  function installStyle(){
    if(document.getElementById('sleepmateSleepV521Style'))return;
    const s=document.createElement('style');s.id='sleepmateSleepV521Style';s.textContent=`
      #sleepmateSleepView[data-v521="1"]{display:block}
      #sleepmateSleepView[data-v521="1"][hidden]{display:none!important}
      .v521-head{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:12px}.v521-head h2{margin:0 0 4px}.v521-head p{margin:0;color:#8fa7b8}
      .v521-filter{display:flex;align-items:center;gap:7px;flex-wrap:wrap}.v521-filter button,.v521-view-switch button,.v521-edit,.v521-open{border:1px solid rgba(120,180,216,.22);background:rgba(10,28,48,.72);color:#b8ccda;border-radius:10px;padding:7px 10px;cursor:pointer;font-weight:700}.v521-filter button.active,.v521-view-switch button.active{color:#fff;border-color:rgba(87,199,255,.58);background:rgba(52,164,206,.19)}
      .v521-range{display:flex;align-items:center;gap:6px;padding:6px;border:1px solid rgba(120,180,216,.16);border-radius:12px;background:rgba(10,24,42,.54)}.v521-range.hidden{display:none}.v521-range input{background:#0d2035;color:#e9f4fa;border:1px solid rgba(125,183,215,.24);border-radius:8px;padding:6px}.v521-range span{color:#8099ab;font-size:11px}
      .v521-status{min-height:19px;color:#8ea7b8;font-size:11px;margin:6px 0 11px}.v521-status.bad{color:#ff9b9b}
      .v521-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:12px}.v521-summary article{padding:14px 15px;border-radius:15px;border:1px solid rgba(118,169,208,.16);background:linear-gradient(145deg,rgba(13,31,53,.92),rgba(10,22,39,.88))}.v521-summary label{display:block;color:#8fa8ba;font-size:11px;margin-bottom:6px}.v521-summary strong{font-size:21px;color:#f2f8fc}.v521-summary small{display:block;color:#849cac;margin-top:4px}
      .v521-panel{border:1px solid rgba(118,169,208,.16);border-radius:17px;background:rgba(10,24,42,.82);padding:14px;margin-bottom:12px;overflow:hidden}.v521-panel-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:10px}.v521-panel-head h3{margin:0 0 3px}.v521-panel-head span{color:#8fa7b8;font-size:11px}.v521-legend{display:flex;gap:12px;flex-wrap:wrap;color:#a9bdcb;font-size:11px}.v521-legend i{display:inline-block;width:9px;height:9px;border-radius:3px;margin-right:5px}
      .v521-chart-scroll{overflow-x:auto;overflow-y:hidden;width:100%;padding-bottom:4px}.v521-chart-scroll canvas{height:320px;display:block;max-width:none}
      .v521-table-wrap{overflow:auto}.v521-table{width:100%;border-collapse:collapse;min-width:840px}.v521-table th,.v521-table td{padding:9px 10px;border-bottom:1px solid rgba(120,169,199,.1);text-align:left;white-space:nowrap}.v521-table th{font-size:10px;text-transform:uppercase;letter-spacing:.04em;color:#7f9aac}.v521-table td{font-size:12px;color:#d8e5ed}.v521-table tr[data-v521-day]{cursor:pointer}.v521-table tr[data-v521-day]:hover,.v521-table tr.selected{background:rgba(73,171,204,.07)}
      .v521-view-switch{display:flex;gap:6px}.v521-view[hidden]{display:none!important}
      .v521-blocks,.v521-timeline{display:grid;gap:9px}.v521-block{border:1px solid rgba(120,174,208,.14);border-radius:14px;background:rgba(13,29,48,.58);padding:11px 12px}.v521-block-top{display:grid;grid-template-columns:minmax(220px,1.4fr) minmax(90px,.45fr) auto;gap:12px;align-items:center}.v521-block-main{min-width:0}.v521-type{display:inline-flex;align-items:center;gap:5px;padding:4px 7px;border-radius:999px;border:1px solid color-mix(in srgb,var(--c) 48%,transparent);background:color-mix(in srgb,var(--c) 12%,transparent);font-size:10px;color:#eaf5fb}.v521-interval{display:block;margin-top:6px;color:#edf7fc;font-size:13px}.v521-sub{display:block;color:#839cab;font-size:10px;margin-top:3px}.v521-manual{color:#d6b05f}.v521-ahi small{display:block;color:#8098a9;font-size:10px}.v521-ahi strong{font-size:16px}.v521-actions{display:flex;gap:6px;align-items:center;justify-content:flex-end;flex-wrap:wrap}.v521-edit{padding:6px 9px}.v521-editor{display:flex;gap:6px;align-items:center;margin-top:9px;padding-top:9px;border-top:1px solid rgba(120,174,208,.11)}.v521-editor.hidden{display:none}.v521-editor select{background:#0d2035;color:#eaf4fa;border:1px solid rgba(125,183,215,.24);border-radius:9px;padding:7px;min-width:150px}.v521-editor button{padding:7px 9px}
      .v521-session-list{display:grid;gap:5px;margin-top:9px}.v521-session{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:8px;align-items:center;padding:7px 9px;border-radius:10px;background:rgba(8,20,35,.54);border:1px solid rgba(114,161,195,.09)}.v521-session b{font-size:10px;color:#90a9ba}.v521-session span{font-size:11px;color:#d5e4ed;overflow-wrap:anywhere}.v521-session em{font-style:normal;font-size:10px;color:#8da4b4;white-space:nowrap}
      .v521-empty{padding:24px;text-align:center;color:#8ca4b4}.v521-timeline-date{font-size:12px;color:#91aabb;margin:4px 0 -2px}.v521-tooltip{position:fixed;z-index:1200;pointer-events:none;padding:9px 11px;border:1px solid rgba(125,190,224,.25);border-radius:12px;background:rgba(5,16,29,.96);box-shadow:0 12px 34px rgba(0,0,0,.3);color:#eaf4fa;font-size:11px;line-height:1.45}.v521-tooltip.hidden{display:none}
      @media(max-width:900px){.v521-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.v521-block-top{grid-template-columns:minmax(0,1fr) auto}.v521-ahi{grid-column:1}.v521-actions{grid-column:2;grid-row:1/3}.v521-filter{width:100%}}
      @media(max-width:620px){.v521-summary{grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.v521-summary article{padding:11px}.v521-summary strong{font-size:18px}.v521-panel{padding:11px}.v521-filter button{flex:1}.v521-range{width:100%;display:grid;grid-template-columns:1fr auto 1fr auto}.v521-range.hidden{display:none}.v521-range input{min-width:0;width:100%;box-sizing:border-box}.v521-block-top{grid-template-columns:1fr}.v521-actions,.v521-ahi{grid-column:auto;grid-row:auto;justify-content:flex-start}.v521-session{grid-template-columns:auto minmax(0,1fr)}.v521-session em{grid-column:2}.v521-view-switch{width:100%}.v521-view-switch button{flex:1}}
    `;document.head.appendChild(s);
  }

  function markup(){return `
    <div class="v521-head">
      <div><h2>Alvások</h2><p>Az éjszaka ahhoz a naphoz tartozik, amelyiken befejeződött.</p></div>
      <div class="v521-filter" id="v521Filter">
        <button type="button" data-p="7">7 nap</button>
        <button type="button" data-p="30" class="active">30 nap</button>
        <button type="button" data-p="prev_week">Előző hét</button>
        <button type="button" data-p="prev_month">Előző hónap</button>
        <button type="button" data-p="all">Teljes</button>
        <button type="button" data-p="range">Egyedi</button>
        <div class="v521-range hidden" id="v521Range"><input id="v521Start" type="date"><span>–</span><input id="v521End" type="date"><button id="v521ApplyRange" type="button">Alkalmaz</button></div>
      </div>
    </div>
    <div class="v521-status" id="v521Status"></div>
    <section class="v521-summary">
      <article><label>Fő alvás átlaga</label><strong id="v521AvgMain">–</strong><small>fő alvással rendelkező napokon</small></article>
      <article><label>Napi összes alvás</label><strong id="v521AvgTotal">–</strong><small>fő + szundi + rövid használat</small></article>
      <article><label>Szundik</label><strong id="v521NapCount">–</strong><small id="v521NapTime">–</small></article>
      <article><label>Töredezett fő alvás</label><strong id="v521Fragments">–</strong><small id="v521Shorts">–</small></article>
    </section>
    <section class="v521-panel">
      <div class="v521-panel-head"><div><h3>Alvások napi összetétele</h3><span>Egy oszlop = befejezési nap. Így az éjfél után véget érő fő alvás nem az előző napra kerül.</span></div><div class="v521-legend"><span><i style="background:${TYPE_COLOR.main}"></i>Fő alvás</span><span><i style="background:${TYPE_COLOR.nap}"></i>Szundi</span><span><i style="background:${TYPE_COLOR.short}"></i>Rövid használat</span></div></div>
      <div class="v521-chart-scroll" id="v521ChartScroll"><canvas id="v521Chart" height="320"></canvas></div>
    </section>
    <section class="v521-panel">
      <div class="v521-panel-head"><div><h3>Részletek</h3><span>Napi összesítés vagy pontos idővonal, az összefűzött CPAP-szakaszokkal együtt.</span></div><div class="v521-view-switch"><button type="button" data-v="daily" class="active">Napi bontás</button><button type="button" data-v="timeline">Idővonal</button></div></div>
      <div class="v521-view" id="v521Daily">
        <div class="v521-table-wrap"><table class="v521-table"><thead><tr><th>Nap</th><th>Összes alvás</th><th>Fő alvás</th><th>Szundi</th><th>Rövid használat</th><th>Fő AHI</th><th>Alvások</th></tr></thead><tbody id="v521Body"></tbody></table></div>
        <div id="v521DayDetail" style="margin-top:12px"></div>
      </div>
      <div class="v521-view" id="v521Timeline" hidden></div>
    </section>`}

  function periodValue(){
    if(S.period!=='range')return S.period;
    if(!S.start||!S.end)return'30';
    return `range:${S.start}:${S.end}`;
  }
  function setStatus(text,bad=false){const el=document.getElementById('v521Status');if(el){el.textContent=text||'';el.classList.toggle('bad',!!bad)}}
  function setText(id,v){const el=document.getElementById(id);if(el)el.textContent=v}

  function initDefaultRange(){
    if(S.start&&S.end)return;
    const rows=S.data?.rows||[];
    const end=rows.length?rows[rows.length-1].date:new Date().toISOString().slice(0,10);
    const d=asDate(`${end}T12:00:00`)||new Date();d.setDate(d.getDate()-29);
    S.start=d.toISOString().slice(0,10);S.end=end;
    const a=document.getElementById('v521Start'),b=document.getElementById('v521End');if(a)a.value=S.start;if(b)b.value=S.end;
  }

  async function refresh(){
    if(S.loading)return;S.loading=true;setStatus('Alvások elemzése…');
    try{
      S.data=await getJSON(`/api/sleep-analysis?period=${encodeURIComponent(periodValue())}`);
      initDefaultRange();
      const rows=S.data.rows||[];
      if(!S.selectedDate||!rows.some(r=>r.date===S.selectedDate))S.selectedDate=rows.length?rows[rows.length-1].date:null;
      render();
      const f=S.data.filter||{};setStatus(`${f.label||'Időszak'}${f.start&&f.end?` • ${f.start} – ${f.end}`:''} • ${rows.length} nap`);
    }catch(e){setStatus(e.message||String(e),true)}finally{S.loading=false}
  }

  function render(){
    const s=S.data?.summary||{};
    setText('v521AvgMain',fmt(s.average_main_seconds));setText('v521AvgTotal',fmt(s.average_total_seconds));setText('v521NapCount',String(s.nap_count||0));setText('v521NapTime',`${fmt(s.nap_seconds)} összesen`);setText('v521Fragments',String(s.fragmented_main_days||0));setText('v521Shorts',`${s.short_count||0} rövid használat`);
    renderTable();renderDay();renderTimeline();scheduleChart();
  }

  function renderTable(){
    const body=document.getElementById('v521Body');if(!body)return;
    const rows=[...(S.data?.rows||[])].reverse();
    body.innerHTML=rows.length?rows.map(r=>`<tr data-v521-day="${esc(r.date)}" class="${r.date===S.selectedDate?'selected':''}"><td><strong>${esc(dayLabel(r.date))}</strong></td><td><strong>${fmt(r.total_seconds)}</strong></td><td>${r.main_seconds?fmt(r.main_seconds):'–'}</td><td>${r.nap_count?`${fmt(r.nap_seconds)} · ${r.nap_count}×`:'–'}</td><td>${r.short_count?`${fmt(r.short_seconds)} · ${r.short_count}×`:'–'}</td><td>${r.main_ahi==null?'–':Number(r.main_ahi).toFixed(2)}</td><td>${(r.blocks||[]).length}</td></tr>`).join(''):'<tr><td colspan="7">Ebben az időszakban nincs alvásadat.</td></tr>';
  }

  function blockHtml(b,index){
    const type=b.type||'nap',sessions=b.session_details||[],manual=b.manual?'<span class="v521-manual"> • kézzel módosítva</span>':'';
    const source=(b.source_days||[])[0]||'';
    const sess=sessions.length?sessions.map((x,i)=>`<div class="v521-session"><b>${i+1}. CPAP-szakasz</b><span>${esc(dtLabel(x.start))} → ${esc(dtLabel(x.end))}</span><em>${fmt(x.therapy_seconds)}</em></div>`).join(''):`<div class="v521-session"><b>CPAP-szakasz</b><span>${esc(dtLabel(b.start))} → ${esc(dtLabel(b.end))}</span><em>${fmt(b.therapy_seconds)}</em></div>`;
    return `<article class="v521-block" data-block-id="${esc(b.id)}"><div class="v521-block-top"><div class="v521-block-main"><span class="v521-type" style="--c:${TYPE_COLOR[type]||'#8fa7b8'}">${TYPE_ICON[type]||''} ${esc(TYPE_LABEL[type]||type)}</span><strong class="v521-interval">${esc(dtLabel(b.start))} → ${esc(dtLabel(b.end))}</strong><span class="v521-sub">${fmt(b.therapy_seconds)} terápia • ${b.session_count||sessions.length||1} CPAP-szakasz${manual}</span></div><div class="v521-ahi"><small>AHI</small><strong>${Number(b.ahi||0).toFixed(2)}</strong></div><div class="v521-actions"><button class="v521-edit" type="button" data-edit="${esc(b.id)}">✎ Szerkesztés</button><button class="v521-open" type="button" data-open-source="${esc(source)}" ${source?'':'disabled'}>Terápiás részletek</button></div></div><div class="v521-session-list">${sess}</div><div class="v521-editor hidden" data-editor="${esc(b.id)}"><select data-select="${esc(b.id)}"><option value="auto" ${b.manual?'':'selected'}>Automatikus besorolás</option><option value="main" ${b.manual&&type==='main'?'selected':''}>Fő alvás</option><option value="nap" ${b.manual&&type==='nap'?'selected':''}>Szundi</option><option value="short" ${b.manual&&type==='short'?'selected':''}>Rövid használat</option></select><button type="button" data-save="${esc(b.id)}">Mentés</button><button type="button" data-cancel="${esc(b.id)}">Mégse</button></div></article>`;
  }

  function renderDay(){
    const box=document.getElementById('v521DayDetail');if(!box)return;
    const row=(S.data?.rows||[]).find(r=>r.date===S.selectedDate);
    if(!row){box.innerHTML='<div class="v521-empty">Válassz egy napot a részletekhez.</div>';return}
    box.innerHTML=`<div class="v521-panel-head"><div><h3>${esc(dayLabel(row.date))}</h3><span>${fmt(row.total_seconds)} összes alvás • ${row.blocks?.length||0} alvásblokk</span></div></div><div class="v521-blocks">${(row.blocks||[]).map(blockHtml).join('')}</div>`;
  }

  function renderTimeline(){
    const box=document.getElementById('v521Timeline');if(!box)return;
    const blocks=[];(S.data?.rows||[]).forEach(r=>(r.blocks||[]).forEach(b=>blocks.push({...b,sleep_date:r.date})));
    blocks.sort((a,b)=>String(b.start).localeCompare(String(a.start)));
    if(!blocks.length){box.innerHTML='<div class="v521-empty">Ebben az időszakban nincs idővonalon megjeleníthető alvás.</div>';return}
    let last='';box.innerHTML=blocks.map((b,i)=>{const head=b.sleep_date!==last?`<div class="v521-timeline-date">${esc(dayLabel(b.sleep_date))}</div>`:'';last=b.sleep_date;return head+blockHtml(b,i)}).join('');
  }

  function scheduleChart(){cancelAnimationFrame(S.raf);S.raf=requestAnimationFrame(drawChart)}
  function drawChart(){
    const canvas=document.getElementById('v521Chart'),wrap=document.getElementById('v521ChartScroll');if(!canvas||!wrap||!S.data)return;
    const rows=S.data.rows||[],cssW=Math.max(wrap.clientWidth||320,rows.length*64+72),cssH=320,dpr=Math.max(1,window.devicePixelRatio||1);canvas.style.width=`${cssW}px`;canvas.style.height=`${cssH}px`;canvas.width=Math.round(cssW*dpr);canvas.height=Math.round(cssH*dpr);const x=canvas.getContext('2d');x.setTransform(dpr,0,0,dpr,0,0);x.clearRect(0,0,cssW,cssH);const pad={l:48,r:18,t:31,b:38},pw=cssW-pad.l-pad.r,ph=cssH-pad.t-pad.b,max=Math.max(3600,...rows.map(r=>Number(r.total_seconds)||0)),ceil=Math.ceil(max/3600)*3600;S.chartBars=[];x.font='10px system-ui,-apple-system,sans-serif';x.textBaseline='middle';x.strokeStyle='rgba(137,177,202,.12)';x.fillStyle='rgba(151,180,199,.7)';for(let i=0;i<=4;i++){const y=pad.t+ph-(ph*i/4),val=ceil*i/4;x.beginPath();x.moveTo(pad.l,y);x.lineTo(pad.l+pw,y);x.stroke();x.textAlign='right';x.fillText(`${(val/3600).toFixed(val%3600?1:0)}h`,pad.l-8,y)}if(!rows.length){x.textAlign='center';x.fillText('Nincs adat',pad.l+pw/2,pad.t+ph/2);return}const step=pw/rows.length,bw=Math.min(38,Math.max(20,step*.62));rows.forEach((r,i)=>{const cx=pad.l+step*i+step/2;let y=pad.t+ph;const segs=[['main',Number(r.main_seconds)||0],['nap',Number(r.nap_seconds)||0],['short',Number(r.short_seconds)||0]];const bar={row:r,x1:cx-bw/2,x2:cx+bw/2,top:y,bottom:pad.t+ph};segs.forEach(([kind,val])=>{if(val<=0)return;const h=Math.max(1,ph*val/ceil);y-=h;x.fillStyle=TYPE_COLOR[kind];x.globalAlpha=.86;x.fillRect(cx-bw/2,y,bw,h);x.globalAlpha=1;if(h>=19&&bw>=28){x.fillStyle='#06111d';x.font='700 9px system-ui,-apple-system,sans-serif';x.textAlign='center';x.fillText(compact(val),cx,y+h/2)}});bar.top=y;S.chartBars.push(bar);x.fillStyle='#dbeaf2';x.font='700 10px system-ui,-apple-system,sans-serif';x.textAlign='center';x.fillText(compact(r.total_seconds),cx,Math.max(12,y-10));x.fillStyle='rgba(151,180,199,.78)';x.font='9px system-ui,-apple-system,sans-serif';x.fillText(shortDay(r.date),cx,pad.t+ph+20)})
  }

  function chartMove(e){
    const canvas=document.getElementById('v521Chart');if(!canvas||!S.chartBars.length)return;
    const rect=canvas.getBoundingClientRect(),px=e.clientX-rect.left,bar=S.chartBars.find(b=>px>=b.x1&&px<=b.x2);let tip=document.getElementById('v521Tooltip');if(!bar){tip?.classList.add('hidden');return}if(!tip){tip=document.createElement('div');tip.id='v521Tooltip';tip.className='v521-tooltip hidden';document.body.appendChild(tip)}const r=bar.row;tip.innerHTML=`<strong>${esc(dayLabel(r.date))}</strong><br><b>Összes alvás: ${fmt(r.total_seconds)}</b><br>🌙 Fő: ${fmt(r.main_seconds)}<br>☁️ Szundi: ${fmt(r.nap_seconds)}<br>◷ Rövid: ${fmt(r.short_seconds)}`;tip.classList.remove('hidden');tip.style.left=`${Math.min(innerWidth-tip.offsetWidth-8,Math.max(8,e.clientX+12))}px`;tip.style.top=`${Math.min(innerHeight-tip.offsetHeight-8,Math.max(8,e.clientY+12))}px`;
  }

  async function saveBlock(id,select){
    if(!id||!select)return;select.disabled=true;setStatus('Besorolás mentése…');
    try{const j=await postJSON('/api/sleep-analysis/override',{block_id:id,type:select.value,period:periodValue()});S.data=j.analysis;render();setStatus(select.value==='auto'?'Automatikus besorolás visszaállítva.':'Kézi javítás elmentve.')}catch(e){setStatus(e.message||String(e),true)}finally{select.disabled=false}
  }

  function bind(root){
    document.getElementById('v521Filter')?.addEventListener('click',e=>{const b=e.target.closest('[data-p]');if(!b)return;S.period=b.dataset.p;document.querySelectorAll('#v521Filter [data-p]').forEach(x=>x.classList.toggle('active',x===b));const range=document.getElementById('v521Range');range?.classList.toggle('hidden',S.period!=='range');if(S.period!=='range')refresh();else initDefaultRange()});
    document.getElementById('v521ApplyRange')?.addEventListener('click',()=>{S.start=document.getElementById('v521Start')?.value||'';S.end=document.getElementById('v521End')?.value||'';if(!S.start||!S.end){setStatus('Add meg a kezdő és záró dátumot.',true);return}refresh()});
    root.addEventListener('click',e=>{
      const tr=e.target.closest('[data-v521-day]');if(tr){S.selectedDate=tr.dataset.v521Day;renderTable();renderDay();return}
      const view=e.target.closest('[data-v]');if(view){S.view=view.dataset.v;root.querySelectorAll('[data-v]').forEach(x=>x.classList.toggle('active',x===view));document.getElementById('v521Daily').hidden=S.view!=='daily';document.getElementById('v521Timeline').hidden=S.view!=='timeline';return}
      const edit=e.target.closest('[data-edit]');if(edit){root.querySelector(`[data-editor="${CSS.escape(edit.dataset.edit)}"]`)?.classList.toggle('hidden');return}
      const cancel=e.target.closest('[data-cancel]');if(cancel){root.querySelector(`[data-editor="${CSS.escape(cancel.dataset.cancel)}"]`)?.classList.add('hidden');return}
      const save=e.target.closest('[data-save]');if(save){const sel=root.querySelector(`[data-select="${CSS.escape(save.dataset.save)}"]`);saveBlock(save.dataset.save,sel);return}
      const open=e.target.closest('[data-open-source]');if(open&&open.dataset.openSource){const day=open.dataset.openSource;if(typeof window.navigate==='function')window.navigate('dashboard',day);else location.hash=`#dashboard/${day}`;}
    });
    const canvas=document.getElementById('v521Chart');canvas?.addEventListener('pointermove',chartMove);canvas?.addEventListener('pointerleave',()=>document.getElementById('v521Tooltip')?.classList.add('hidden'));
    window.addEventListener('resize',scheduleChart);
    document.addEventListener('click',e=>{if(e.target.closest('#refresh'))setTimeout(refresh,1700)},true);
  }

  function mount(){
    const root=document.getElementById('sleepmateSleepView');if(!root)return false;if(root.dataset.v521==='1')return true;
    root.dataset.v521='1';installStyle();root.innerHTML=markup();bind(root);refresh();return true;
  }

  function wait(n=0){if(mount())return;if(n<1200)setTimeout(()=>wait(n+1),50)}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>wait(),{once:true});else wait();
})();