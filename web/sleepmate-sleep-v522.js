(function(){
  'use strict';

  const S={period:'30',start:'',end:'',data:null,loading:false,chartBars:[],raf:0};
  const TYPE_LABEL={main:'Fő alvás',nap:'Szundi',short:'Rövid használat'};
  const TYPE_ICON={main:'🌙',nap:'☁️',short:'◷'};
  const TYPE_COLOR={main:'#57c7ff',nap:'#a995ff',short:'#f4b85b'};
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const asDate=v=>{const d=new Date(v);return Number.isNaN(d.getTime())?null:d};

  function fmt(sec){
    const mins=Math.max(0,Math.round((Number(sec)||0)/60));
    const h=Math.floor(mins/60),m=mins%60;
    return h?`${h} ó ${String(m).padStart(2,'0')} p`:`${m} p`;
  }
  function compact(sec){
    const mins=Math.max(0,Math.round((Number(sec)||0)/60));
    const h=Math.floor(mins/60),m=mins%60;
    return h?`${h}ó${String(m).padStart(2,'0')}p`:`${m}p`;
  }
  function dayLabel(v){const d=asDate(`${v}T12:00:00`);return d?d.toLocaleDateString('hu-HU',{year:'numeric',month:'short',day:'2-digit'}):v}
  function shortDay(v){const d=asDate(`${v}T12:00:00`);return d?d.toLocaleDateString('hu-HU',{month:'2-digit',day:'2-digit'}):v}
  function time(v){const d=asDate(v);return d?d.toLocaleTimeString('hu-HU',{hour:'2-digit',minute:'2-digit'}):'–'}
  function dateOnly(v){const d=asDate(v);return d?d.toLocaleDateString('hu-HU',{year:'numeric',month:'short',day:'2-digit'}):'–'}
  function sameDay(a,b){const x=asDate(a),y=asDate(b);return !!x&&!!y&&x.getFullYear()===y.getFullYear()&&x.getMonth()===y.getMonth()&&x.getDate()===y.getDate()}
  function interruption(b){return Math.max(0,Number(b.wall_seconds||0)-Number(b.therapy_seconds||0))}
  function sourceDay(v){const s=String(v||'');return /^\d{8}$/.test(s)?`${s.slice(0,4)}-${s.slice(4,6)}-${s.slice(6,8)}`:s||''}

  async function getJSON(url){
    const r=await fetch(`${url}${url.includes('?')?'&':'?'}_v522=${Date.now()}`,{cache:'no-store',headers:{Accept:'application/json'}});
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
    if(document.getElementById('sleepmateSleepV522Style'))return;
    const style=document.createElement('style');style.id='sleepmateSleepV522Style';style.textContent=`
      #sleepmateSleepView[data-v522="1"]{display:block}#sleepmateSleepView[data-v522="1"][hidden]{display:none!important}
      .v522-head{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:10px}.v522-head h2{margin:0 0 4px}.v522-head p{margin:0;color:#8fa7b8;max-width:760px;line-height:1.5}
      .v522-filter{display:flex;align-items:flex-end;gap:8px;flex-wrap:wrap}.v522-filter label{display:grid;gap:4px;color:#839cad;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.04em}.v522-filter select,.v522-range input{background:#0d2035;color:#e9f4fa;border:1px solid rgba(125,183,215,.24);border-radius:10px;padding:8px 10px;min-height:36px}.v522-filter select{min-width:170px}.v522-range{display:flex;align-items:flex-end;gap:6px}.v522-range.hidden{display:none}.v522-range button,.v522-edit,.v522-toggle,.v522-save,.v522-cancel,.v522-open{border:1px solid rgba(120,180,216,.22);background:rgba(10,28,48,.72);color:#c4d6e1;border-radius:10px;padding:8px 10px;cursor:pointer;font-weight:700}.v522-range button:hover,.v522-edit:hover,.v522-toggle:hover,.v522-open:hover{border-color:rgba(87,199,255,.5)}
      .v522-status{min-height:18px;color:#849dac;font-size:11px;margin:3px 0 11px}.v522-status.bad{color:#ff9b9b}
      .v522-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin-bottom:12px}.v522-summary article{padding:13px 14px;border-radius:15px;border:1px solid rgba(118,169,208,.16);background:linear-gradient(145deg,rgba(13,31,53,.92),rgba(10,22,39,.88))}.v522-summary label{display:block;color:#8fa8ba;font-size:10px;margin-bottom:6px}.v522-summary strong{font-size:20px;color:#f2f8fc}.v522-summary small{display:block;color:#849cac;margin-top:4px;font-size:10px}
      .v522-panel{border:1px solid rgba(118,169,208,.16);border-radius:17px;background:rgba(10,24,42,.82);padding:14px;margin-bottom:12px;overflow:hidden}.v522-panel-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:10px}.v522-panel-head h3{margin:0 0 3px}.v522-panel-head span{color:#8fa7b8;font-size:11px;line-height:1.45}.v522-legend{display:flex;gap:12px;flex-wrap:wrap;color:#a9bdcb;font-size:11px}.v522-legend i{display:inline-block;width:9px;height:9px;border-radius:3px;margin-right:5px}
      .v522-chart-scroll{overflow-x:auto;overflow-y:hidden;width:100%;padding-bottom:4px}.v522-chart-scroll canvas{height:310px;display:block;max-width:none}.v522-tooltip{position:fixed;z-index:1200;pointer-events:none;padding:9px 11px;border:1px solid rgba(125,190,224,.25);border-radius:12px;background:rgba(5,16,29,.96);box-shadow:0 12px 34px rgba(0,0,0,.3);color:#eaf4fa;font-size:11px;line-height:1.5}.v522-tooltip.hidden{display:none}
      .v522-table-wrap{overflow:auto}.v522-table{width:100%;border-collapse:collapse;min-width:810px}.v522-table th,.v522-table td{padding:9px 10px;border-bottom:1px solid rgba(120,169,199,.1);text-align:left;white-space:nowrap}.v522-table th{font-size:9px;text-transform:uppercase;letter-spacing:.04em;color:#7f9aac}.v522-table td{font-size:12px;color:#d8e5ed}.v522-table tr[data-day]{cursor:pointer}.v522-table tr[data-day]:hover{background:rgba(73,171,204,.07)}
      .v522-journal{display:grid;gap:14px}.v522-day{display:grid;gap:8px;scroll-margin-top:80px}.v522-day-title{display:flex;align-items:baseline;justify-content:space-between;gap:10px;padding:2px 2px 0}.v522-day-title strong{font-size:13px;color:#eef7fb}.v522-day-title span{font-size:10px;color:#819baa}.v522-cards{display:grid;gap:8px}
      .v522-card{border:1px solid rgba(120,174,208,.14);border-radius:15px;background:linear-gradient(145deg,rgba(13,29,48,.78),rgba(9,22,38,.7));padding:12px}.v522-card-main{display:grid;grid-template-columns:minmax(220px,1fr) auto auto;align-items:center;gap:14px}.v522-card-copy{min-width:0}.v522-type{display:inline-flex;align-items:center;gap:5px;padding:4px 7px;border-radius:999px;border:1px solid color-mix(in srgb,var(--c) 48%,transparent);background:color-mix(in srgb,var(--c) 12%,transparent);font-size:10px;color:#eaf5fb}.v522-manual{font-size:9px;color:#d6b05f;margin-left:5px}.v522-clock{display:block;margin-top:7px;font-size:17px;font-weight:800;color:#f0f8fc;letter-spacing:.01em}.v522-date-range{display:block;color:#8199a9;font-size:10px;margin-top:3px}.v522-duration{text-align:right;min-width:105px}.v522-duration strong{display:block;font-size:21px;color:#f4f9fc;white-space:nowrap}.v522-duration small{display:block;color:#819aaa;font-size:9px;margin-top:2px}.v522-actions{display:flex;gap:6px;justify-content:flex-end;flex-wrap:wrap}.v522-edit,.v522-toggle,.v522-open{padding:7px 9px;font-size:10px}.v522-meta{display:flex;gap:8px 14px;flex-wrap:wrap;padding-top:9px;margin-top:9px;border-top:1px solid rgba(120,174,208,.09);color:#8ca5b5;font-size:10px}.v522-meta b{color:#c7d9e4;font-weight:700}
      .v522-sessions{display:grid;gap:5px;margin-top:9px}.v522-sessions.hidden{display:none}.v522-session{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:8px;align-items:center;padding:7px 9px;border-radius:10px;background:rgba(8,20,35,.54);border:1px solid rgba(114,161,195,.09)}.v522-session b{font-size:9px;color:#90a9ba}.v522-session span{font-size:10px;color:#d5e4ed}.v522-session em{font-style:normal;font-size:10px;color:#9ab0be;white-space:nowrap}
      .v522-editor{display:flex;gap:6px;align-items:center;margin-top:9px;padding-top:9px;border-top:1px solid rgba(120,174,208,.11)}.v522-editor.hidden{display:none}.v522-editor select{background:#0d2035;color:#eaf4fa;border:1px solid rgba(125,183,215,.24);border-radius:9px;padding:7px;min-width:160px}.v522-save,.v522-cancel{padding:7px 9px;font-size:10px}.v522-empty{padding:24px;text-align:center;color:#8ca4b4}
      @media(max-width:900px){.v522-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.v522-card-main{grid-template-columns:minmax(0,1fr) auto}.v522-actions{grid-column:1/-1;justify-content:flex-start}.v522-filter{width:100%}}
      @media(max-width:620px){.v522-head{align-items:stretch}.v522-filter{display:grid;grid-template-columns:1fr}.v522-filter select{width:100%}.v522-range{display:grid;grid-template-columns:1fr 1fr}.v522-range.hidden{display:none}.v522-range label{min-width:0}.v522-range input{width:100%;min-width:0;box-sizing:border-box}.v522-range button{grid-column:1/-1}.v522-summary{gap:7px}.v522-summary article{padding:10px}.v522-summary strong{font-size:17px}.v522-panel{padding:11px}.v522-card-main{grid-template-columns:1fr}.v522-duration{text-align:left}.v522-duration strong{font-size:24px}.v522-actions{grid-column:auto}.v522-session{grid-template-columns:auto minmax(0,1fr)}.v522-session em{grid-column:2}.v522-meta{gap:6px 10px}}
    `;document.head.appendChild(style);
  }

  function markup(){return `
    <div class="v522-head">
      <div><h2>Alvások</h2><p>Az alvás egy időintervallum. A napi összesítés csak az áttekinthetőség miatt az <b>ébredés napjához</b> csoportosít; a Fő alvás / Szundi / Rövid használat besorolást a dátum és a kezdési óra nem dönti el.</p></div>
      <div class="v522-filter">
        <label><span>Időszak</span><select id="v522Period">
          <option value="7">Utolsó 7 nap</option>
          <option value="30" selected>Utolsó 30 nap</option>
          <option value="all">Teljes időszak</option>
          <option value="range">Egyedi időszak</option>
          <option value="prev7">Előző 7 nap</option>
          <option value="prev30">Előző 30 nap</option>
        </select></label>
        <div class="v522-range hidden" id="v522Range">
          <label><span>Kezdete</span><input id="v522Start" type="date"></label>
          <label><span>Vége</span><input id="v522End" type="date"></label>
          <button id="v522Apply" type="button">Alkalmaz</button>
        </div>
      </div>
    </div>
    <div class="v522-status" id="v522Status"></div>
    <section class="v522-summary">
      <article><label>Fő alvás átlaga</label><strong id="v522AvgMain">–</strong><small>fő alvással rendelkező napokon</small></article>
      <article><label>Összes alvás átlaga</label><strong id="v522AvgTotal">–</strong><small>ébredési nap szerinti átlag</small></article>
      <article><label>Szundi</label><strong id="v522NapCount">–</strong><small id="v522NapTime">–</small></article>
      <article><label>Rövid használat</label><strong id="v522ShortCount">–</strong><small id="v522ShortTime">–</small></article>
    </section>
    <section class="v522-panel">
      <div class="v522-panel-head"><div><h3>Napi összetétel</h3><span>Egy oszlop = egy ébredési nap. Az oszlop tetején a teljes CPAP-val töltött alvási idő látszik.</span></div><div class="v522-legend"><span><i style="background:${TYPE_COLOR.main}"></i>Fő alvás</span><span><i style="background:${TYPE_COLOR.nap}"></i>Szundi</span><span><i style="background:${TYPE_COLOR.short}"></i>Rövid használat</span></div></div>
      <div class="v522-chart-scroll" id="v522ChartScroll"><canvas id="v522Chart" height="310"></canvas></div>
    </section>
    <section class="v522-panel">
      <div class="v522-panel-head"><div><h3>Napi bontás</h3><span>A dátum az ébredés napja. Koppints egy sorra, és az Alvásnapló odaugrik az adott naphoz.</span></div></div>
      <div class="v522-table-wrap"><table class="v522-table"><thead><tr><th>Ébredés napja</th><th>Összes alvás</th><th>Fő alvás</th><th>Szundi</th><th>Rövid használat</th><th>Fő AHI</th><th>Alvások</th></tr></thead><tbody id="v522Body"></tbody></table></div>
    </section>
    <section class="v522-panel">
      <div class="v522-panel-head"><div><h3>Alvásnapló</h3><span>Itt az alvások maguk az elsődlegesek: pontos kezdés, befejezés és időtartam. Az összefűzött CPAP-szakaszok csak akkor nyílnak le, ha szükséged van rájuk.</span></div></div>
      <div class="v522-journal" id="v522Journal"></div>
    </section>`}

  function periodValue(){if(S.period!=='range')return S.period;if(!S.start||!S.end)return'30';return`range:${S.start}:${S.end}`}
  function setText(id,v){const el=document.getElementById(id);if(el)el.textContent=v}
  function setStatus(text,bad=false){const el=document.getElementById('v522Status');if(el){el.textContent=text||'';el.classList.toggle('bad',!!bad)}}
  function initRange(){
    if(S.start&&S.end)return;
    const rows=S.data?.rows||[];const end=rows.length?rows[rows.length-1].date:new Date().toISOString().slice(0,10);const d=asDate(`${end}T12:00:00`)||new Date();d.setDate(d.getDate()-29);S.start=d.toISOString().slice(0,10);S.end=end;
    const a=document.getElementById('v522Start'),b=document.getElementById('v522End');if(a)a.value=S.start;if(b)b.value=S.end;
  }

  async function refresh(){
    if(S.loading)return;S.loading=true;setStatus('Alvások elemzése…');
    try{
      S.data=await getJSON(`/api/sleep-analysis?period=${encodeURIComponent(periodValue())}`);initRange();render();
      const f=S.data.filter||{},rows=S.data.rows||[];setStatus(`${f.label||'Időszak'}${f.start&&f.end?` • ${f.start} – ${f.end}`:''} • ${rows.length} ébredési nap`);
    }catch(e){setStatus(e.message||String(e),true)}finally{S.loading=false}
  }

  function render(){
    const s=S.data?.summary||{};setText('v522AvgMain',fmt(s.average_main_seconds));setText('v522AvgTotal',fmt(s.average_total_seconds));setText('v522NapCount',String(s.nap_count||0));setText('v522NapTime',`${fmt(s.nap_seconds)} összesen`);setText('v522ShortCount',String(s.short_count||0));setText('v522ShortTime',`${fmt(s.short_seconds)} összesen`);renderTable();renderJournal();scheduleChart();
  }

  function renderTable(){
    const body=document.getElementById('v522Body');if(!body)return;const rows=[...(S.data?.rows||[])].reverse();
    body.innerHTML=rows.length?rows.map(r=>`<tr data-day="${esc(r.date)}"><td><strong>${esc(dayLabel(r.date))}</strong></td><td><strong>${fmt(r.total_seconds)}</strong></td><td>${r.main_seconds?fmt(r.main_seconds):'–'}</td><td>${r.nap_count?`${fmt(r.nap_seconds)} · ${r.nap_count}×`:'–'}</td><td>${r.short_count?`${fmt(r.short_seconds)} · ${r.short_count}×`:'–'}</td><td>${r.main_ahi==null?'–':Number(r.main_ahi).toFixed(2)}</td><td>${(r.blocks||[]).length}</td></tr>`).join(''):'<tr><td colspan="7">Ebben az időszakban nincs alvásadat.</td></tr>';
  }

  function cardHtml(b){
    const type=b.type||'nap',sessions=b.session_details||[],source=(b.source_days||[])[0]||'',gap=interruption(b),manual=b.manual?'<span class="v522-manual">kézzel módosítva</span>':'';
    const cross=!sameDay(b.start,b.end);const dates=cross?`${esc(dateOnly(b.start))} → ${esc(dateOnly(b.end))}`:esc(dateOnly(b.end));
    const sessionRows=(sessions.length?sessions:[{start:b.start,end:b.end,therapy_seconds:b.therapy_seconds}]).map((x,i)=>`<div class="v522-session"><b>${i+1}. szakasz</b><span>${esc(time(x.start))} → ${esc(time(x.end))}${sameDay(x.start,x.end)?'':` · ${esc(dateOnly(x.start))} → ${esc(dateOnly(x.end))}`}</span><em>${fmt(x.therapy_seconds)}</em></div>`).join('');
    return `<article class="v522-card" data-block="${esc(b.id)}"><div class="v522-card-main"><div class="v522-card-copy"><span class="v522-type" style="--c:${TYPE_COLOR[type]||'#8fa7b8'}">${TYPE_ICON[type]||''} ${esc(TYPE_LABEL[type]||type)}</span>${manual}<strong class="v522-clock">${esc(time(b.start))} → ${esc(time(b.end))}</strong><span class="v522-date-range">${dates}</span></div><div class="v522-duration"><strong>${fmt(b.therapy_seconds)}</strong><small>CPAP-val töltött idő</small></div><div class="v522-actions"><button class="v522-edit" type="button" data-edit="${esc(b.id)}">Szerkesztés</button>${(sessions.length||b.session_count)>1?`<button class="v522-toggle" type="button" data-toggle="${esc(b.id)}">${b.session_count||sessions.length} szakasz</button>`:''}<button class="v522-open" type="button" data-open="${esc(source)}" ${source?'':'disabled'}>Terápia</button></div></div><div class="v522-meta"><span>AHI <b>${Number(b.ahi||0).toFixed(2)}</b></span><span>CPAP-szakasz <b>${b.session_count||sessions.length||1}</b></span>${gap>=60?`<span>Megszakítás <b>${fmt(gap)}</b></span>`:''}${Number(b.wall_seconds||0)>0?`<span>Teljes időablak <b>${fmt(b.wall_seconds)}</b></span>`:''}</div><div class="v522-sessions hidden" data-sessions="${esc(b.id)}">${sessionRows}</div><div class="v522-editor hidden" data-editor="${esc(b.id)}"><select data-select="${esc(b.id)}"><option value="auto" ${b.manual?'':'selected'}>Automatikus besorolás</option><option value="main" ${b.manual&&type==='main'?'selected':''}>Fő alvás</option><option value="nap" ${b.manual&&type==='nap'?'selected':''}>Szundi</option><option value="short" ${b.manual&&type==='short'?'selected':''}>Rövid használat</option></select><button class="v522-save" type="button" data-save="${esc(b.id)}">Mentés</button><button class="v522-cancel" type="button" data-cancel="${esc(b.id)}">Mégse</button></div></article>`;
  }

  function renderJournal(){
    const box=document.getElementById('v522Journal');if(!box)return;const rows=[...(S.data?.rows||[])].reverse();
    if(!rows.length){box.innerHTML='<div class="v522-empty">Ebben az időszakban nincs alvás a naplóban.</div>';return}
    box.innerHTML=rows.map(r=>`<section class="v522-day" data-journal-day="${esc(r.date)}"><div class="v522-day-title"><strong>${esc(dayLabel(r.date))}</strong><span>ébredés napja · ${fmt(r.total_seconds)} összesen</span></div><div class="v522-cards">${[...(r.blocks||[])].sort((a,b)=>String(a.start).localeCompare(String(b.start))).map(cardHtml).join('')}</div></section>`).join('');
  }

  function scheduleChart(){cancelAnimationFrame(S.raf);S.raf=requestAnimationFrame(drawChart)}
  function drawChart(){
    const canvas=document.getElementById('v522Chart'),wrap=document.getElementById('v522ChartScroll');if(!canvas||!wrap||!S.data)return;const rows=S.data.rows||[],cssW=Math.max(wrap.clientWidth||320,rows.length*64+72),cssH=310,dpr=Math.max(1,window.devicePixelRatio||1);canvas.style.width=`${cssW}px`;canvas.style.height=`${cssH}px`;canvas.width=Math.round(cssW*dpr);canvas.height=Math.round(cssH*dpr);const x=canvas.getContext('2d');x.setTransform(dpr,0,0,dpr,0,0);x.clearRect(0,0,cssW,cssH);const pad={l:48,r:18,t:31,b:38},pw=cssW-pad.l-pad.r,ph=cssH-pad.t-pad.b,max=Math.max(3600,...rows.map(r=>Number(r.total_seconds)||0)),ceil=Math.ceil(max/3600)*3600;S.chartBars=[];x.font='10px system-ui,-apple-system,sans-serif';x.textBaseline='middle';x.strokeStyle='rgba(137,177,202,.12)';x.fillStyle='rgba(151,180,199,.7)';for(let i=0;i<=4;i++){const y=pad.t+ph-(ph*i/4),val=ceil*i/4;x.beginPath();x.moveTo(pad.l,y);x.lineTo(pad.l+pw,y);x.stroke();x.textAlign='right';x.fillText(`${(val/3600).toFixed(val%3600?1:0)}ó`,pad.l-8,y)}if(!rows.length){x.textAlign='center';x.fillText('Nincs adat',pad.l+pw/2,pad.t+ph/2);return}const step=pw/rows.length,bw=Math.min(38,Math.max(20,step*.62));rows.forEach((r,i)=>{const cx=pad.l+step*i+step/2;let y=pad.t+ph;const segs=[['main',Number(r.main_seconds)||0],['nap',Number(r.nap_seconds)||0],['short',Number(r.short_seconds)||0]];const bar={row:r,x1:cx-bw/2,x2:cx+bw/2,top:y};segs.forEach(([kind,val])=>{if(val<=0)return;const h=Math.max(1,ph*val/ceil);y-=h;x.fillStyle=TYPE_COLOR[kind];x.globalAlpha=.86;x.fillRect(cx-bw/2,y,bw,h);x.globalAlpha=1;if(h>=19&&bw>=28){x.fillStyle='#06111d';x.font='700 9px system-ui,-apple-system,sans-serif';x.textAlign='center';x.fillText(compact(val),cx,y+h/2)}});bar.top=y;S.chartBars.push(bar);x.fillStyle='#dbeaf2';x.font='700 10px system-ui,-apple-system,sans-serif';x.textAlign='center';x.fillText(compact(r.total_seconds),cx,Math.max(12,y-10));x.fillStyle='rgba(151,180,199,.78)';x.font='9px system-ui,-apple-system,sans-serif';x.fillText(shortDay(r.date),cx,pad.t+ph+20)})
  }
  function chartMove(e){
    const canvas=document.getElementById('v522Chart');if(!canvas||!S.chartBars.length)return;const rect=canvas.getBoundingClientRect(),px=e.clientX-rect.left,bar=S.chartBars.find(b=>px>=b.x1&&px<=b.x2);let tip=document.getElementById('v522Tooltip');if(!bar){tip?.classList.add('hidden');return}if(!tip){tip=document.createElement('div');tip.id='v522Tooltip';tip.className='v522-tooltip hidden';document.body.appendChild(tip)}const r=bar.row;tip.innerHTML=`<strong>${esc(dayLabel(r.date))} · ébredés napja</strong><br><b>Összes alvás: ${fmt(r.total_seconds)}</b><br>🌙 Fő: ${fmt(r.main_seconds)}<br>☁️ Szundi: ${fmt(r.nap_seconds)}<br>◷ Rövid: ${fmt(r.short_seconds)}`;tip.classList.remove('hidden');tip.style.left=`${Math.min(innerWidth-tip.offsetWidth-8,Math.max(8,e.clientX+12))}px`;tip.style.top=`${Math.min(innerHeight-tip.offsetHeight-8,Math.max(8,e.clientY+12))}px`;
  }

  async function saveBlock(id,select){
    if(!id||!select)return;select.disabled=true;setStatus('Besorolás mentése…');
    try{const j=await postJSON('/api/sleep-analysis/override',{block_id:id,type:select.value,period:periodValue()});S.data=j.analysis;render();setStatus(select.value==='auto'?'Automatikus besorolás visszaállítva.':'Kézi javítás elmentve.')}catch(e){setStatus(e.message||String(e),true)}finally{select.disabled=false}
  }

  function bind(root){
    document.getElementById('v522Period')?.addEventListener('change',e=>{S.period=e.target.value;const range=document.getElementById('v522Range');range?.classList.toggle('hidden',S.period!=='range');if(S.period==='range')initRange();else refresh()});
    document.getElementById('v522Apply')?.addEventListener('click',()=>{S.start=document.getElementById('v522Start')?.value||'';S.end=document.getElementById('v522End')?.value||'';if(!S.start||!S.end){setStatus('Add meg a kezdő és záró dátumot.',true);return}refresh()});
    root.addEventListener('click',e=>{
      const row=e.target.closest('[data-day]');if(row){root.querySelector(`[data-journal-day="${CSS.escape(row.dataset.day)}"]`)?.scrollIntoView({behavior:'smooth',block:'start'});return}
      const toggle=e.target.closest('[data-toggle]');if(toggle){const box=root.querySelector(`[data-sessions="${CSS.escape(toggle.dataset.toggle)}"]`);box?.classList.toggle('hidden');toggle.textContent=box?.classList.contains('hidden')?`${box?.children.length||0} szakasz`:'Szakaszok bezárása';return}
      const edit=e.target.closest('[data-edit]');if(edit){root.querySelector(`[data-editor="${CSS.escape(edit.dataset.edit)}"]`)?.classList.toggle('hidden');return}
      const cancel=e.target.closest('[data-cancel]');if(cancel){root.querySelector(`[data-editor="${CSS.escape(cancel.dataset.cancel)}"]`)?.classList.add('hidden');return}
      const save=e.target.closest('[data-save]');if(save){saveBlock(save.dataset.save,root.querySelector(`[data-select="${CSS.escape(save.dataset.save)}"]`));return}
      const open=e.target.closest('[data-open]');if(open&&open.dataset.open){const day=sourceDay(open.dataset.open);if(typeof window.navigate==='function')window.navigate('dashboard',day);else location.hash=`#dashboard/${day}`;}
    });
    const canvas=document.getElementById('v522Chart');canvas?.addEventListener('pointermove',chartMove);canvas?.addEventListener('pointerleave',()=>document.getElementById('v522Tooltip')?.classList.add('hidden'));canvas?.addEventListener('click',e=>{const rect=canvas.getBoundingClientRect(),px=e.clientX-rect.left,bar=S.chartBars.find(b=>px>=b.x1&&px<=b.x2);if(bar)root.querySelector(`[data-journal-day="${CSS.escape(bar.row.date)}"]`)?.scrollIntoView({behavior:'smooth',block:'start'})});window.addEventListener('resize',scheduleChart);document.addEventListener('click',e=>{if(e.target.closest('#refresh'))setTimeout(refresh,1700)},true);
  }

  function mount(){
    const root=document.getElementById('sleepmateSleepView');if(!root)return false;if(root.dataset.v522==='1')return true;root.dataset.v522='1';delete root.dataset.v521;installStyle();root.innerHTML=markup();bind(root);refresh();return true;
  }
  function wait(n=0){if(mount())return;if(n<1200)setTimeout(()=>wait(n+1),50)}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>wait(),{once:true});else wait();
})();
