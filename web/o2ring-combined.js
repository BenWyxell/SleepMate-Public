(()=>{
  'use strict';

  const VERSION='5.3.0';
  const SIGNALS={
    flow:{label:'Légáramlás',unit:'L/perc'},
    pressure:{label:'Nyomás',unit:'cmH₂O'},
    leak:{label:'Szivárgás',unit:'L/perc'},
  };
  const EVENT_COLORS={OA:'#ff806f',CA:'#a995ff',H:'#57d6a8',RERA:'#5eb4ff',UA:'#f0c85b',CSR:'#e77cff',OTHER:'#aab7c4'};
  let currentDay='';
  let currentSignal='flow';
  let loadToken=0;
  let model=null;
  let hoverT=null;
  let hoverRaf=0;

  const api=async path=>{
    const sep=path.includes('?')?'&':'?';
    const r=await fetch(`${path}${sep}_o2combined=${Date.now()}`,{cache:'no-store'});
    const x=await r.json().catch(()=>({}));
    if(!r.ok||x.error)throw new Error(x.error||`HTTP ${r.status}`);
    return x;
  };
  const dayCode=()=>String(document.getElementById('day')?.value||'').replace(/-/g,'').slice(0,8);
  const num=(v,d=1)=>Number.isFinite(Number(v))?Number(v).toLocaleString('hu-HU',{minimumFractionDigits:d,maximumFractionDigits:d}):'–';
  const clock=epoch=>Number.isFinite(epoch)?new Date(epoch*1000).toLocaleTimeString('hu-HU',{hour:'2-digit',minute:'2-digit',second:'2-digit'}):'–';

  function css(){
    if(document.getElementById('smO2CombinedCss'))return;
    const s=document.createElement('style');
    s.id='smO2CombinedCss';
    s.textContent=`
      .o2r-combined{margin-top:16px;padding:0!important;overflow:hidden}
      .o2r-combined-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;padding:16px 16px 10px}
      .o2r-combined-head h3{margin:0 0 4px}.o2r-combined-head p{margin:0}
      .o2r-combined-controls{display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:flex-end}
      .o2r-combined-controls select{min-width:150px}
      .o2r-combined-readout{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;border-top:1px solid rgba(103,184,226,.14);border-bottom:1px solid rgba(103,184,226,.14);background:rgba(99,177,219,.12)}
      .o2r-combined-readout>div{padding:8px 12px;background:rgba(7,15,27,.82);min-width:0}
      .o2r-combined-readout span,.o2r-combined-readout b{display:block}.o2r-combined-readout span{font-size:10px;color:var(--muted,#9aacc0);text-transform:uppercase;letter-spacing:.45px}.o2r-combined-readout b{margin-top:2px;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .o2r-combined-stack{padding:10px 12px 14px;display:grid;gap:8px}
      .o2r-combined-row{border:1px solid rgba(99,177,219,.15);border-radius:14px;background:rgba(5,12,22,.34);overflow:hidden}
      .o2r-combined-row-head{height:30px;display:flex;align-items:center;justify-content:space-between;padding:0 10px;font-size:11px;color:var(--muted,#9aacc0)}
      .o2r-combined-row-head b{color:#eaf7ff;font-size:12px}
      .o2r-combined-stage{height:126px;position:relative;touch-action:pan-y;cursor:crosshair}
      .o2r-combined-stage canvas{position:absolute;inset:0;width:100%;height:100%;display:block}
      .o2r-combined-stage canvas:last-child{pointer-events:none}
      .o2r-combined-status{padding:10px 16px 14px;color:var(--muted,#9aacc0);font-size:12px}
      .o2r-combined-status.bad{color:#ff9aa7}
      @media(max-width:720px){.o2r-combined-head{flex-direction:column}.o2r-combined-controls{justify-content:flex-start;width:100%}.o2r-combined-readout{grid-template-columns:1fr 1fr}.o2r-combined-stage{height:112px}}
      @media(max-width:420px){.o2r-combined-readout{grid-template-columns:1fr}.o2r-combined-controls select{width:100%}}
    `;
    document.head.appendChild(s);
  }

  function installPanel(){
    const host=document.getElementById('o2rDailyPanel');
    if(!host||document.getElementById('o2rCombinedTimeline'))return;
    css();
    const panel=document.createElement('section');
    panel.id='o2rCombinedTimeline';
    panel.className='panel o2r-combined';
    panel.innerHTML=`
      <div class="o2r-combined-head">
        <div><h3>Közös CPAP + oximetria idővonal</h3><p class="muted">A CPAP-jel, SpO₂ és pulzus ugyanazon időtengelyen. Mozgasd a kurzort bármelyik grafikonon.</p></div>
        <div class="o2r-combined-controls"><label for="o2rCombinedSignal" class="muted">CPAP-jel</label><select id="o2rCombinedSignal"><option value="flow">Légáramlás</option><option value="pressure">Nyomás</option><option value="leak">Szivárgás</option></select></div>
      </div>
      <div class="o2r-combined-readout">
        <div><span>Időpont</span><b id="o2rCombinedTime">–</b></div>
        <div><span id="o2rCombinedCpapLabel">Légáramlás</span><b id="o2rCombinedCpapValue">–</b></div>
        <div><span>SpO₂</span><b id="o2rCombinedSpo2Value">–</b></div>
        <div><span>Pulzus</span><b id="o2rCombinedHrValue">–</b></div>
      </div>
      <div class="o2r-combined-stack">
        <article class="o2r-combined-row"><div class="o2r-combined-row-head"><b id="o2rCombinedCpapTitle">Légáramlás</b><span id="o2rCombinedCpapUnit">L/perc</span></div><div class="o2r-combined-stage" data-o2r-combined-stage><canvas id="o2rCombinedCpap"></canvas><canvas id="o2rCombinedCpapOverlay"></canvas></div></article>
        <article class="o2r-combined-row"><div class="o2r-combined-row-head"><b>SpO₂</b><span>% • referencia: <span id="o2rCombinedRef">90</span>%</span></div><div class="o2r-combined-stage" data-o2r-combined-stage><canvas id="o2rCombinedSpo2"></canvas><canvas id="o2rCombinedSpo2Overlay"></canvas></div></article>
        <article class="o2r-combined-row"><div class="o2r-combined-row-head"><b>Pulzus</b><span>bpm</span></div><div class="o2r-combined-stage" data-o2r-combined-stage><canvas id="o2rCombinedHr"></canvas><canvas id="o2rCombinedHrOverlay"></canvas></div></article>
      </div>
      <div id="o2rCombinedStatus" class="o2r-combined-status">Adatok előkészítése…</div>`;
    host.appendChild(panel);
    const select=document.getElementById('o2rCombinedSignal');
    select.value=currentSignal;
    select.addEventListener('change',()=>{currentSignal=select.value in SIGNALS?select.value:'flow';load(true)});
    panel.querySelectorAll('[data-o2r-combined-stage]').forEach(stage=>{
      stage.addEventListener('pointermove',event=>{
        if(!model)return;
        const r=stage.getBoundingClientRect();
        const frac=Math.max(0,Math.min(1,(event.clientX-r.left)/Math.max(1,r.width)));
        hoverT=model.xMin+frac*(model.xMax-model.xMin);
        scheduleHover();
      });
    });
    panel.addEventListener('pointerleave',()=>{hoverT=null;scheduleHover()});
    load(true);
  }

  function canvas(canvas){
    const dpr=window.devicePixelRatio||1;
    const r=canvas.getBoundingClientRect();
    const w=Math.max(260,r.width||300),h=Math.max(80,r.height||120);
    const pw=Math.round(w*dpr),ph=Math.round(h*dpr);
    if(canvas.width!==pw||canvas.height!==ph){canvas.width=pw;canvas.height=ph}
    const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);
    return{ctx,w,h};
  }

  function flattenSignal(payload,dayStart){
    const out=[];
    for(const series of payload?.series||[]){
      const start=new Date(series.start).getTime()/1000;
      if(!Number.isFinite(start))continue;
      const shift=start-dayStart;
      for(const p of series.points||[]){
        const t=shift+Number(p?.[0]),value=Number(p?.[1]);
        if(Number.isFinite(t)&&Number.isFinite(value))out.push({t,value});
      }
    }
    out.sort((a,b)=>a.t-b.t);
    return out;
  }

  function nearest(rows,t,getT=x=>x.t){
    if(!rows?.length||!Number.isFinite(t))return null;
    let lo=0,hi=rows.length-1;
    while(lo<hi){const mid=(lo+hi)>>1;if(getT(rows[mid])<t)lo=mid+1;else hi=mid}
    const a=rows[lo],b=lo>0?rows[lo-1]:null;
    return b&&Math.abs(getT(b)-t)<Math.abs(getT(a)-t)?b:a;
  }

  function niceRange(values,fallback){
    const finite=values.filter(Number.isFinite);
    if(!finite.length)return fallback;
    let lo=Math.min(...finite),hi=Math.max(...finite);
    if(lo===hi){lo-=1;hi+=1}
    const pad=Math.max((hi-lo)*.08,.5);
    return[lo-pad,hi+pad];
  }

  function drawGrid(ctx,w,h,pad,lo,hi){
    const iw=w-pad.l-pad.r,ih=h-pad.t-pad.b;
    ctx.save();ctx.strokeStyle='rgba(135,178,214,.15)';ctx.fillStyle='rgba(206,224,242,.58)';ctx.lineWidth=1;ctx.font='10px system-ui';
    for(let i=0;i<4;i++){
      const y=pad.t+ih*i/3,v=hi-(hi-lo)*i/3;
      ctx.beginPath();ctx.moveTo(pad.l,y);ctx.lineTo(w-pad.r,y);ctx.stroke();ctx.fillText(Math.abs(v)>=100?String(Math.round(v)):num(v,1),4,y+3);
    }
    ctx.restore();
  }

  function drawBase(canvasId,rows,getValue,range,kind){
    const el=document.getElementById(canvasId);if(!el||!model)return;
    const {ctx,w,h}=canvas(el);ctx.clearRect(0,0,w,h);
    const pad={l:42,r:12,t:8,b:22},iw=w-pad.l-pad.r,ih=h-pad.t-pad.b;
    const values=rows.map(getValue).filter(Number.isFinite),[lo,hi]=range||niceRange(values,[0,1]);
    drawGrid(ctx,w,h,pad,lo,hi);
    if(kind==='spo2'){
      for(const [v,color] of [[model.ref,'rgba(255,211,107,.56)'],[model.ref2,'rgba(255,142,122,.45)']]){
        if(!Number.isFinite(v)||v<lo||v>hi)continue;
        const y=pad.t+(hi-v)/(hi-lo)*ih;ctx.save();ctx.setLineDash([5,4]);ctx.strokeStyle=color;ctx.beginPath();ctx.moveTo(pad.l,y);ctx.lineTo(w-pad.r,y);ctx.stroke();ctx.restore();
      }
    }
    if(kind==='cpap'&&model.events.length){
      ctx.save();ctx.font='9px system-ui';let lastLabelX=-99;
      for(const ev of model.events){
        if(ev.t<model.xMin||ev.t>model.xMax)continue;
        const x=pad.l+(ev.t-model.xMin)/(model.xMax-model.xMin)*iw;
        ctx.strokeStyle=EVENT_COLORS[ev.type]||EVENT_COLORS.OTHER;ctx.globalAlpha=.42;ctx.beginPath();ctx.moveTo(x,pad.t);ctx.lineTo(x,h-pad.b);ctx.stroke();
        if(x-lastLabelX>18){ctx.globalAlpha=.85;ctx.fillStyle=EVENT_COLORS[ev.type]||EVENT_COLORS.OTHER;ctx.fillText(ev.type,x+2,pad.t+9);lastLabelX=x}
      }
      ctx.restore();
    }
    if(!values.length){ctx.fillStyle='rgba(206,224,242,.55)';ctx.font='12px system-ui';ctx.fillText('Nincs adat',pad.l+8,pad.t+24);return}
    const grad=ctx.createLinearGradient(pad.l,0,w-pad.r,0);
    if(kind==='spo2'){grad.addColorStop(0,'#4bdcff');grad.addColorStop(.55,'#49e3bd');grad.addColorStop(1,'#67a8ff')}
    else if(kind==='hr'){grad.addColorStop(0,'#9b7cff');grad.addColorStop(1,'#56c7ff')}
    else{grad.addColorStop(0,'#57c7ff');grad.addColorStop(.5,'#4ce8bd');grad.addColorStop(1,'#9b7cff')}
    ctx.save();ctx.strokeStyle=grad;ctx.lineWidth=1.8;ctx.shadowColor=kind==='hr'?'rgba(155,124,255,.28)':'rgba(75,220,255,.26)';ctx.shadowBlur=6;ctx.beginPath();let started=false,lastT=null;
    for(const row of rows){
      const t=Number(row.t),v=getValue(row);if(!Number.isFinite(t)||!Number.isFinite(v)||t<model.xMin||t>model.xMax){started=false;continue}
      if(lastT!=null&&t-lastT>45)started=false;
      const x=pad.l+(t-model.xMin)/(model.xMax-model.xMin)*iw,y=pad.t+(hi-v)/(hi-lo)*ih;
      if(!started){ctx.moveTo(x,y);started=true}else ctx.lineTo(x,y);lastT=t;
    }
    ctx.stroke();ctx.restore();
    ctx.save();ctx.fillStyle='rgba(206,224,242,.52)';ctx.font='9px system-ui';const steps=Math.max(2,Math.min(6,Math.floor(iw/110)));for(let i=0;i<=steps;i++){const t=model.xMin+(model.xMax-model.xMin)*i/steps,x=pad.l+iw*i/steps;ctx.fillText(clock(model.dayStart+t).slice(0,5),Math.max(pad.l,Math.min(w-pad.r-28,x-14)),h-6)}ctx.restore();
  }

  function drawAll(){
    if(!model)return;
    const cpapRange=currentSignal==='pressure'?[Math.max(0,Math.min(...model.cpap.map(x=>x.value).filter(Number.isFinite))-1),Math.max(5,Math.max(...model.cpap.map(x=>x.value).filter(Number.isFinite))+1)]:null;
    drawBase('o2rCombinedCpap',model.cpap,x=>x.value,cpapRange,'cpap');
    drawBase('o2rCombinedSpo2',model.o2,x=>Number(x.spo2),[75,100],'spo2');
    drawBase('o2rCombinedHr',model.o2,x=>Number(x.heart_rate),niceRange(model.o2.map(x=>Number(x.heart_rate)).filter(Number.isFinite),[35,130]),'hr');
    drawHover();
  }

  function drawHover(){
    if(!model)return;
    const ids=['o2rCombinedCpapOverlay','o2rCombinedSpo2Overlay','o2rCombinedHrOverlay'];
    for(const id of ids){
      const el=document.getElementById(id);if(!el)continue;const {ctx,w,h}=canvas(el);ctx.clearRect(0,0,w,h);
      if(!Number.isFinite(hoverT))continue;
      const pad={l:42,r:12,t:8,b:22},x=pad.l+(hoverT-model.xMin)/(model.xMax-model.xMin)*(w-pad.l-pad.r);
      ctx.save();ctx.strokeStyle='rgba(238,249,255,.72)';ctx.lineWidth=1;ctx.setLineDash([3,3]);ctx.beginPath();ctx.moveTo(x,pad.t);ctx.lineTo(x,h-pad.b);ctx.stroke();ctx.restore();
    }
    const t=Number.isFinite(hoverT)?hoverT:null;
    const cp=nearest(model.cpap,t),ox=nearest(model.o2,t);
    const set=(id,text)=>{const e=document.getElementById(id);if(e)e.textContent=text};
    set('o2rCombinedTime',t==null?'–':clock(model.dayStart+t));
    set('o2rCombinedCpapValue',cp?`${num(cp.value,currentSignal==='flow'?1:2)} ${SIGNALS[currentSignal].unit}`:'–');
    set('o2rCombinedSpo2Value',ox&&Number.isFinite(Number(ox.spo2))?`${Number(ox.spo2)}%`:'–');
    set('o2rCombinedHrValue',ox&&Number.isFinite(Number(ox.heart_rate))?`${Number(ox.heart_rate)} bpm`:'–');
  }

  function scheduleHover(){if(hoverRaf)return;hoverRaf=requestAnimationFrame(()=>{hoverRaf=0;drawHover()})}

  async function load(force=false){
    installPanel();
    const day=dayCode();
    if(!/^\d{8}$/.test(day))return;
    if(!force&&day===currentDay&&model)return;
    currentDay=day;hoverT=null;model=null;
    const token=++loadToken;
    const status=document.getElementById('o2rCombinedStatus');if(status){status.className='o2r-combined-status';status.textContent='CPAP és O2Ring adatok összeillesztése…'}
    try{
      const [summary,signal,o2,settings]=await Promise.all([
        api(`/api/day/${day}`),
        api(`/api/day/${day}/signal/${currentSignal}?max_points=5500`),
        api(`/api/o2ring/day?day=${day}&max_points=10000`),
        api('/api/o2ring/settings'),
      ]);
      if(token!==loadToken)return;
      const sessions=summary.sessions||[];
      if(!sessions.length)throw new Error('Ezen a napon nincs CPAP terápiás szakasz.');
      const dayStart=new Date(sessions[0].start).getTime()/1000;
      const end=Math.max(...sessions.map(s=>new Date(s.end).getTime()/1000-dayStart).filter(Number.isFinite),1);
      const cpap=flattenSignal(signal,dayStart);
      const oxygen=(o2.samples||[]).map(x=>({...x,t:Number(x.t)})).filter(x=>Number.isFinite(x.t)).sort((a,b)=>a.t-b.t);
      if(!o2.available||!oxygen.length)throw new Error('Ehhez a CPAP-éjszakához még nincs időben átfedő O2Ring felvétel.');
      const events=(summary.events||[]).map(e=>({type:String(e.type||'OTHER'),t:new Date(e.time).getTime()/1000-dayStart})).filter(e=>Number.isFinite(e.t));
      model={dayStart,xMin:0,xMax:Math.max(1,end),cpap,o2:oxygen,events,ref:Number(settings.o2ring_spo2_reference??90),ref2:Number(settings.o2ring_spo2_secondary_reference??88)};
      const meta=SIGNALS[currentSignal];
      const set=(id,text)=>{const e=document.getElementById(id);if(e)e.textContent=text};
      set('o2rCombinedCpapTitle',meta.label);set('o2rCombinedCpapLabel',meta.label);set('o2rCombinedCpapUnit',signal.unit||meta.unit);set('o2rCombinedRef',String(model.ref));
      if(status){const coverage=o2.summary?.coverage_percent;status.textContent=`${o2.matches?.length||0} CPAP–O2Ring átfedés • ${oxygen.length.toLocaleString('hu-HU')} oximetriai minta${coverage!=null?` • ${num(coverage,1)}% lefedettség`:''}`}
      drawAll();
    }catch(error){
      if(token!==loadToken)return;
      if(status){status.className='o2r-combined-status bad';status.textContent=error?.message||String(error)}
      clearCanvases();
    }
  }

  function clearCanvases(){for(const id of ['o2rCombinedCpap','o2rCombinedSpo2','o2rCombinedHr','o2rCombinedCpapOverlay','o2rCombinedSpo2Overlay','o2rCombinedHrOverlay']){const el=document.getElementById(id);if(!el)continue;const {ctx,w,h}=canvas(el);ctx.clearRect(0,0,w,h)}}
  function visible(){const p=document.getElementById('o2rDailyPanel');return !!p&&!p.classList.contains('hidden')}
  function maybe(){installPanel();if(visible())load(false)}

  const observer=new MutationObserver(()=>maybe());
  const start=()=>{
    css();
    observer.observe(document.documentElement,{childList:true,subtree:true});
    document.addEventListener('click',e=>{if(e.target?.closest?.('#o2rDailyBtn'))setTimeout(()=>load(true),0)});
    document.addEventListener('change',e=>{if(e.target?.id==='day'){currentDay='';setTimeout(()=>load(true),0)}});
    window.addEventListener('hashchange',()=>setTimeout(maybe,0));
    window.addEventListener('resize',()=>{if(model)requestAnimationFrame(drawAll)});
    maybe();
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
  window.SleepMateO2Combined={version:VERSION,refresh:()=>load(true)};
})();
