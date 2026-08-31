(function(){
  'use strict';
  // v5.2.14 deliberately uses a new guard so a stale v5.2.6 overlay that was
  // already evaluated in the same PWA document cannot suppress this repair.
  if(window.__sleepmateChartV5214)return;
  window.__sleepmateChartV5214=true;

  function install(attempt=0){
    if(typeof traceSmooth!=='function'||typeof drawTooltip!=='function'||typeof syncTrendHover!=='function'){
      if(attempt<600)setTimeout(()=>install(attempt+1),50);
      return;
    }

    // Catmull-Rom -> cubic Bezier. Every data point is an actual curve endpoint,
    // so the visible line always passes through its marker.
    traceSmooth=function(ctx,pts,move=true){
      if(!pts?.length)return;
      if(move)ctx.moveTo(pts[0].x,pts[0].y);else ctx.lineTo(pts[0].x,pts[0].y);
      if(pts.length===1)return;
      if(pts.length===2){ctx.lineTo(pts[1].x,pts[1].y);return;}
      for(let i=0;i<pts.length-1;i++){
        const p0=pts[i-1]||pts[i],p1=pts[i],p2=pts[i+1],p3=pts[i+2]||p2;
        const cp1x=p1.x+(p2.x-p0.x)/6,cp1y=p1.y+(p2.y-p0.y)/6;
        const cp2x=p2.x-(p3.x-p1.x)/6,cp2y=p2.y-(p3.y-p1.y)/6;
        ctx.bezierCurveTo(cp1x,cp1y,cp2x,cp2y,p2.x,p2.y);
      }
    };

    // Detailed-signal canvas tooltip. On a coarse pointer (phone/tablet) there
    // is a real finger-sized exclusion zone below the label. If there is not
    // enough room above the finger, pin the label to the top of the canvas;
    // never move it below the finger.
    drawTooltip=function(ctx,w,h,x,y,lines,color){
      ctx.font='12px Segoe UI';
      const pad=8,lineH=17,width=Math.max(...lines.map(s=>ctx.measureText(s).width))+pad*2,height=lines.length*lineH+pad*2-3;
      const coarse=!!window.matchMedia?.('(pointer: coarse)').matches,gap=coarse?64:30;
      let bx=x-width/2,by=y-height-gap;
      bx=Math.max(4,Math.min(w-width-4,bx));
      by=Math.max(4,Math.min(h-height-4,by));
      ctx.fillStyle='rgba(8,13,19,.96)';ctx.strokeStyle=color;ctx.lineWidth=1;ctx.beginPath();ctx.roundRect(bx,by,width,height,7);ctx.fill();ctx.stroke();
      lines.forEach((s,i)=>{ctx.fillStyle=i===1?color:'#edf4fb';ctx.fillText(s,bx+pad,by+pad+12+i*lineH)});
    };

    // Dashboard trend tooltip: center above the pointer/finger. Touch uses a
    // larger exclusion zone and never falls back below the finger near the top
    // edge of the screen.
    syncTrendHover=function(idx,sourceCanvas,event){
      const sourceMeta=sourceCanvas?._trendMeta,row=sourceMeta?.rows?.[idx];if(!sourceMeta||!row)return;
      state.trendHoverIndex=idx;state.trendHoverCanvas=sourceCanvas;
      for(const c of $$('.trend-card canvas:not(.trend-hover-overlay)')){
        const m=c._trendMeta;if(!m?.rows?.length)continue;
        const target=m.rows.findIndex(r=>String(r.day)===String(row.day));
        drawTrendHoverLine(c,target>=0?target:null);
      }
      const m=sourceMeta,tip=$('#trendTooltip');if(!tip)return;
      let lines=[`<b>${formatDayCode(row.day)}</b>`];
      if(m.kind==='line')for(const ser of m.series){const v=ser.get(row);if(v!=null&&Number.isFinite(+v))lines.push(`<span><i style="background:${ser.color}"></i>${escapeHtml(ser.name)}: <strong>${num(v,ser.decimals??1)}${ser.unit?' '+escapeHtml(ser.unit):''}</strong></span>`)}
      else if(m.kind==='usage')lines.push(`<span><i style="background:#55b96f"></i>Használat: <strong>${num(row.usage_hours||0,2)} óra</strong></span>`);
      else if(m.kind==='events'){
        let total=0;for(const k of ['OA','CA','H','RERA']){const v=row.event_index?.[k]||0;total+=v;lines.push(`<span><i style="background:${TREND_EVENT_COLORS[k]}"></i>${k}: <strong>${num(v,2)} /óra</strong></span>`)}
        lines.push(`<span class="tip-total">Összesen: <strong>${num(total,2)} /óra</strong></span>`);
      }
      tip.innerHTML=lines.join('');tip.classList.remove('hidden');
      const rect=sourceCanvas.getBoundingClientRect();
      const cx=Number.isFinite(event?.clientX)?event.clientX:rect.left+rect.width/2;
      const cy=Number.isFinite(event?.clientY)?event.clientY:rect.top+rect.height/2;
      const coarse=event?.pointerType==='touch'||!!window.matchMedia?.('(pointer: coarse)').matches;
      const gap=coarse?64:28;
      let left=cx-tip.offsetWidth/2,top=cy-tip.offsetHeight-gap;
      left=Math.max(8,Math.min(window.innerWidth-tip.offsetWidth-8,left));
      top=Math.max(8,Math.min(window.innerHeight-tip.offsetHeight-8,top));
      tip.style.left=`${left}px`;tip.style.top=`${top}px`;
    };

    // Redraw already-open views immediately after the patch lands.
    try{if(typeof drawDashboardTrends==='function')drawDashboardTrends()}catch{}
    try{if(typeof drawHeroOverlay==='function')drawHeroOverlay()}catch{}
  }

  install();
})();