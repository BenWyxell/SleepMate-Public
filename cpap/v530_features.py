from __future__ import annotations

import urllib.parse
import re

from .version import APP_VERSION


_installed = False
UI_VERSION = "5.3.4"


def _replace_required(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Hiányzik a v5.3.10 célzott frontend marker: {label}")
    return text.replace(old, new, 1)


def _patch_frontend_v534(text: str) -> str:
    """Keep the frozen UI marker from owning release-cache cleanup."""
    safe = """async function enforceFrontendGeneration(){
  // VERSION is the long-lived UI generation, not the application release.
  // Cache ownership and stale-generation cleanup belong exclusively to the
  // Service Worker after a matching client confirms the new build is alive.
  if('serviceWorker'in navigator){try{const reg=await navigator.serviceWorker.getRegistration();await reg?.update?.()}catch{}}
}"""
    if safe in text:
        return text
    old = """async function enforceFrontendGeneration(){
  const meta=q('meta[name=\"sleepmate-ui-version\"]')?.content||'';let backend='';try{backend=String((await api('/api/version')).version||'')}catch{}const expected=backend||VERSION;if(expected!==VERSION)return;
  try{const keys=await caches.keys();const stale=keys.filter(k=>k.startsWith('sleepmate-')&&!k.includes(`v${VERSION}`));if(stale.length)await Promise.all(stale.map(k=>caches.delete(k)))}catch{}
  if('serviceWorker'in navigator){try{const reg=await navigator.serviceWorker.getRegistration();await reg?.update?.()}catch{}}
  if(meta&&meta!==expected&&!sessionStorage.getItem('sm-v534-reloaded')){sessionStorage.setItem('sm-v534-reloaded','1');location.reload();return}sessionStorage.removeItem('sm-v534-reloaded');
}"""
    return _replace_required(text, old, safe, "frontend cache generation")

def _patch_sleepmate_v530(text: str) -> str:
    """Use one build generation and self-heal the complete O2 runtime."""
    version_marker = "const VERSION='5.3.4';"
    asset_marker = "const ASSET_VERSION=(()=>{try{return new URL(document.currentScript?.src||location.href,location.href).searchParams.get('v')||document.querySelector('meta[name=\\\"sleepmate-build-id\\\"]')?.content||VERSION}catch{return VERSION}})();"
    if asset_marker not in text:
        text = _replace_required(text, version_marker, version_marker + "\\n" + asset_marker, "O2 build asset generation")

    old_loader = """function loadScript(src,id){return new Promise((resolve,reject)=>{if(document.getElementById(id))return resolve();const s=document.createElement('script');s.id=id;s.src=src;s.async=false;s.onload=resolve;s.onerror=reject;document.head.appendChild(s)})}"""
    new_loader = """function loadScript(src,id,ready){return new Promise((resolve,reject)=>{const wanted=new URL(src,location.href).href,existing=document.getElementById(id);if(existing){if(existing.src===wanted&&(existing.dataset.smLoaded==='1'||ready?.()))return resolve();existing.remove()}const s=document.createElement('script');s.id=id;s.src=src;s.async=false;s.onload=()=>{s.dataset.smLoaded='1';resolve()};s.onerror=()=>{s.remove();reject(new Error(`Nem tölthető be: ${src}`))};document.head.appendChild(s)})}"""
    if new_loader not in text:
        text = _replace_required(text, old_loader, new_loader, "retryable O2 script loader")

    old_css = """function loadCss(href,id){if(document.getElementById(id))return;const l=document.createElement('link');l.id=id;l.rel='stylesheet';l.href=href;document.head.appendChild(l)}"""
    new_css = """function loadCss(href,id){const wanted=new URL(href,location.href).href,existing=document.getElementById(id);if(existing?.href===wanted)return;if(existing)existing.remove();const l=document.createElement('link');l.id=id;l.rel='stylesheet';l.href=href;l.onerror=()=>l.remove();document.head.appendChild(l)}"""
    if new_css not in text:
        text = _replace_required(text, old_css, new_css, "generation-aware O2 CSS loader")

    old_modules = """async function ensureO2Modules(){if(!activeO2())return;window.__sleepmateO2Bootstrap=o2;if(o2ScriptsLoaded){window.SleepMateO2Ring?.install?.();return}loadCss(`/o2ring.css?v=${VERSION}`,'smO2Css');await loadScript(`/o2ring.js?v=${VERSION}`,'smO2Js');await loadScript(`/o2ring-report-ui.js?v=${VERSION}`,'smO2ReportJs');o2ScriptsLoaded=true;window.SleepMateO2Ring?.install?.()}"""
    new_modules = """function o2RuntimeMissing(){return activeO2()&&(!window.SleepMateO2Ring||!document.querySelector('#sidebar [data-page=\\\"oximetry\\\"]')||!document.getElementById('page-oximetry')||!document.getElementById('smO2Master'))}
  async function ensureO2Modules(){if(!activeO2())return;window.__sleepmateO2Bootstrap=o2;loadCss(`/o2ring.css?v=${ASSET_VERSION}`,'smO2Css');if(!o2ScriptsLoaded||!window.SleepMateO2Ring){await loadScript(`/o2ring.js?v=${ASSET_VERSION}`,'smO2Js',()=>!!window.SleepMateO2Ring);if(!window.SleepMateO2Ring){document.getElementById('smO2Js')?.remove();throw new Error('Az O2Ring runtime nem inicializálódott.')}await loadScript(`/o2ring-report-ui.js?v=${ASSET_VERSION}`,'smO2ReportJs',()=>!!window.SleepMateO2RingReport);o2ScriptsLoaded=true}installO2MasterPanel();hydrateO2Master();await Promise.resolve(window.SleepMateO2Ring?.install?.());if(!document.querySelector('#sidebar [data-page=\\\"oximetry\\\"]')||!document.getElementById('page-oximetry')){window.SleepMateO2Ring?.uninstall?.();await Promise.resolve(window.SleepMateO2Ring?.install?.())}window.SleepMateO2RingReport?.install?.()}"""
    if new_modules not in text:
        text = _replace_required(text, old_modules, new_modules, "O2 module installation")

    old_apply = """async function applyO2Status(next){const enabled=next?.settings?.o2ring_enabled;if(typeof enabled!=='boolean')throw new Error('Az O2Ring master beállítás nem érkezett meg.');o2=next;o2State=enabled?O2_STATE.ENABLED:O2_STATE.DISABLED;setO2FeatureState();hydrateO2Master();if(activeO2()){await ensureO2Modules();Promise.resolve(window.SleepMateO2Ring?.refresh?.()).catch(e=>o2Msg(`O2Ring UI frissítési hiba: ${e.message}`))}else disableO2Ui();renderBottomNav();renderPwaEditor();window.dispatchEvent(new CustomEvent('sleepmate-o2-config-ready',{detail:{enabled,state:o2State}}));return o2}"""
    new_apply = """function resetO2Recovery(){clearTimeout(scheduleO2Recovery.timer);scheduleO2Recovery.timer=null;scheduleO2Recovery.attempt=0}
  function scheduleO2Recovery(){if(scheduleO2Recovery.timer||o2State===O2_STATE.DISABLED)return;const delays=[600,1500,3500,7000,12000],i=Math.min(Number(scheduleO2Recovery.attempt)||0,delays.length-1);scheduleO2Recovery.attempt=Math.min(i+1,delays.length-1);scheduleO2Recovery.timer=setTimeout(()=>{scheduleO2Recovery.timer=null;refreshO2State().catch(()=>scheduleO2Recovery())},delays[i])}
  async function applyO2Status(next){const enabled=next?.settings?.o2ring_enabled;if(typeof enabled!=='boolean')throw new Error('Az O2Ring master beállítás nem érkezett meg.');o2=next;o2State=enabled?O2_STATE.ENABLED:O2_STATE.DISABLED;setO2FeatureState();installO2MasterPanel();hydrateO2Master();if(activeO2()){await ensureO2Modules();resetO2Recovery();Promise.resolve(window.SleepMateO2Ring?.refresh?.()).catch(e=>o2Msg(`O2Ring UI frissítési hiba: ${e.message}`))}else{resetO2Recovery();disableO2Ui()}renderBottomNav();renderPwaEditor();window.dispatchEvent(new CustomEvent('sleepmate-o2-config-ready',{detail:{enabled,state:o2State}}));return o2}"""
    if new_apply not in text:
        text = _replace_required(text, old_apply, new_apply, "O2 status apply/retry")

    old_refresh = """async function refreshO2State(){if(o2RefreshPromise)return o2RefreshPromise;o2RefreshPromise=api('/api/o2ring/status').then(applyO2Status).catch(e=>{if(!resolvedO2()){setO2FeatureState();hydrateO2Master();o2Msg('Az O2Ring beállítás betöltése folyamatban van.')}throw e}).finally(()=>{o2RefreshPromise=null});return o2RefreshPromise}"""
    new_refresh = """async function refreshO2State(){if(o2RefreshPromise)return o2RefreshPromise;o2RefreshPromise=api('/api/o2ring/status').then(applyO2Status).catch(e=>{if(!resolvedO2()){setO2FeatureState();hydrateO2Master();o2Msg('Az O2Ring beállítás betöltése folyamatban van.')}if(o2State!==O2_STATE.DISABLED)scheduleO2Recovery();throw e}).finally(()=>{o2RefreshPromise=null});return o2RefreshPromise}"""
    if new_refresh not in text:
        text = _replace_required(text, old_refresh, new_refresh, "O2 refresh retry")

    old_recovery = """function bindO2HydrationRecovery(){const reconcile=()=>{if(!resolvedO2())refreshO2State().catch(()=>{})};window.addEventListener('online',reconcile);window.addEventListener('pageshow',reconcile);window.addEventListener('focus',reconcile);document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')reconcile()});navigator.serviceWorker?.addEventListener?.('message',event=>{if(event.data?.type==='SLEEPMATE_SHELL_READY')reconcile()})}"""
    new_recovery = """function bindO2HydrationRecovery(){const reconcile=()=>{installO2MasterPanel();resetO2Recovery();if(!resolvedO2()||o2RuntimeMissing())refreshO2State().catch(()=>scheduleO2Recovery());else{hydrateO2Master();window.SleepMateFrontendV534?.normalize?.()}};window.addEventListener('online',reconcile);window.addEventListener('pageshow',reconcile);window.addEventListener('focus',reconcile);document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')reconcile()});navigator.serviceWorker?.addEventListener?.('message',event=>{if(event.data?.type==='SLEEPMATE_SHELL_READY')reconcile()})}"""
    if new_recovery not in text:
        text = _replace_required(text, old_recovery, new_recovery, "PWA O2 hydration recovery")

    old_api = """window.SleepMateV530={ICONS,NAV,renderBottomNav,renderPwaEditor,preferences:()=>({...prefs}),o2State:()=>o2State,refreshO2:refreshO2State};"""
    new_api = """window.SleepMateV530={ICONS,NAV,renderBottomNav,renderPwaEditor,preferences:()=>({...prefs}),o2State:()=>o2State,refreshO2:refreshO2State,ensureO2:ensureO2Modules,installO2Master:installO2MasterPanel};"""
    if new_api not in text:
        text = _replace_required(text, old_api, new_api, "O2 recovery API")
    return text

def _patch_o2ring(text: str) -> str:
    """Render Dashboard O2 history with the same day-trend contract as AHI."""
    old_draw = """function drawDashboardO2Mini(){const rows=R.dashboardTrendRows||[],range=R.dashboardTrendZoom||bounds(rows),set=v=>R.dashboardTrendZoom=v,reset=()=>R.dashboardTrendZoom=null,redraw=drawDashboardO2Mini,defs=[['smDashO2Trend',[{key:'spo2',label:'SpO₂',unit:'%',color:COLORS.spo2,fixed:[75,100]}]],['smDashHrTrend',[{key:'heart_rate',label:'Pulzus',unit:' bpm',color:COLORS.hr}]]];for(const[cid,ss]of defs){const c=id(cid);chartDraw(c,rows,{range,series:ss,syncGroup:'dash-o2',rightAxis:false,smooth:true,points:true,connectGaps:true,lineWidth:2,xLabel:date,tooltipLabel:ts=>`${date(ts)} ${clock(ts)}`,redraw});bindChart(c,{setRange:set,resetRange:reset,redraw,syncGroup:'dash-o2'})}}"""
    new_draw = """function drawDashboardO2Mini(){const rows=R.dashboardTrendRows||[],draw=typeof window.drawTrendLine==='function'?window.drawTrendLine:(typeof drawTrendLine==='function'?drawTrendLine:null);if(!draw)return;draw(id('smDashO2Trend'),rows,[{name:'SpO₂',color:COLORS.spo2,get:r=>r.spo2,unit:'%',decimals:1}]);draw(id('smDashHrTrend'),rows,[{name:'Pulzus',color:COLORS.hr,get:r=>r.heart_rate,unit:' bpm',decimals:1}])}"""
    text = _replace_required(text, old_draw, new_draw, "Dashboard O2 AHI-style renderer")

    old_section = """function ensureDashboardO2Section(){const agg=q('#dashboardOverviewView .aggregate-cards');if(!agg)return null;let sec=id('smDashboardO2V534');if(!sec){sec=document.createElement('section');sec.id='smDashboardO2V534';sec.className='panel sm-dashboard-o2-v534';sec.dataset.o2ringFeature='1';sec.innerHTML='<div class="panel-head"><div><h3>Oximetriai összegzés</h3><span>CPAP-idővel átfedő O2Ring-adatok.</span></div><button id="smDashO2Open">Oximetria →</button></div><div class="sm-dashboard-o2-cards"><div><span>Medián SpO₂</span><b id="smDashO2Avg">—</b></div><div><span>Minimum SpO₂</span><b id="smDashO2Min">—</b></div><div><span>Medián pulzus</span><b id="smDashHrAvg">—</b></div><div><span>Átlag T90</span><b id="smDashT90">—</b></div></div><div class="sm-dashboard-o2-mini"><article><header>SpO₂ trend</header><div class="sm-o2-chart-wrap"><canvas id="smDashO2Trend"></canvas></div></article><article><header>Pulzus trend</header><div class="sm-o2-chart-wrap"><canvas id="smDashHrTrend"></canvas></div></article></div><div id="smDashO2Empty" class="o2r-empty hidden">Ebben az időszakban még nincs illesztett O2Ring adat.</div>';agg.insertAdjacentElement('afterend',sec);id('smDashO2Open').onclick=()=>openOximetry('recordings')}return sec}"""
    new_section = """function ensureDashboardO2Section(){const agg=q('#dashboardOverviewView .aggregate-cards');if(!agg)return null;let sec=id('smDashboardO2V534');if(!sec){sec=document.createElement('section');sec.id='smDashboardO2V534';sec.className='sm-dashboard-o2-v534';sec.dataset.o2ringFeature='1';sec.innerHTML=`<section class="panel sm-dashboard-o2-summary"><div class="panel-head"><div><h3>Oximetriai összegzés</h3><span>CPAP-idővel átfedő O2Ring-adatok.</span></div><button id="smDashO2Open">Oximetria →</button></div><div class="sm-dashboard-o2-cards"><div><span>Medián SpO₂</span><b id="smDashO2Avg">—</b></div><div><span>Minimum SpO₂</span><b id="smDashO2Min">—</b></div><div><span>Medián pulzus</span><b id="smDashHrAvg">—</b></div><div><span>Átlag T90</span><b id="smDashT90">—</b></div></div><div id="smDashO2Empty" class="o2r-empty hidden">Ebben az időszakban még nincs illesztett O2Ring adat.</div></section><section class="trend-grid sm-dashboard-o2-trends"><article class="panel trend-card"><div class="panel-head"><h3>SpO₂ trend</h3><span>medián</span></div><canvas id="smDashO2Trend"></canvas></article><article class="panel trend-card"><div class="panel-head"><h3>Pulzus trend</h3><span>medián bpm</span></div><canvas id="smDashHrTrend"></canvas></article></section>`;agg.insertAdjacentElement('afterend',sec);id('smDashO2Open').onclick=()=>openOximetry('recordings')}return sec}"""
    text = _replace_required(text, old_section, new_section, "Dashboard O2 AHI-style layout")

    old_refresh = """async function refreshDashboardO2(force=false){const sec=ensureDashboardO2Section();if(!sec)return;let rows=[];try{rows=state.dashboardOverview?.rows||[]}catch{}if(!rows.length){R.dashboardTrendRows=[];id('smDashO2Empty')?.classList.remove('hidden');drawDashboardO2Mini();return}const data=await getBatch(rows.map(r=>r.day),force),avail=data.filter(x=>x.available&&x.summary).sort((a,b)=>String(a.day).localeCompare(String(b.day))),av=key=>{const v=avail.map(x=>num(x.summary?.[key])).filter(x=>x!=null);return v.length?v.reduce((a,b)=>a+b,0)/v.length:null},mins=avail.map(x=>num(x.summary?.spo2_minimum)).filter(x=>x!=null),spo2Med=av('spo2_median')??av('spo2_average'),hrMed=av('heart_rate_median')??av('heart_rate_average');id('smDashO2Avg').textContent=spo2Med==null?'—':`${fmt(spo2Med,1)}%`;id('smDashO2Min').textContent=mins.length?`${Math.min(...mins)}%`:'—';id('smDashHrAvg').textContent=hrMed==null?'—':`${fmt(hrMed,1)} bpm`;id('smDashT90').textContent=av('t90_seconds')==null?'—':dur(av('t90_seconds'));id('smDashO2Empty').classList.toggle('hidden',avail.length>0);R.dashboardTrendRows=avail.map((x,i)=>({timestamp:num(x.matches?.[0]?.cpap_start)||dayTrendTs(x.day)||Date.now()/1000+i*86400,spo2:num(x.summary?.spo2_median)??num(x.summary?.spo2_average),heart_rate:num(x.summary?.heart_rate_median)??num(x.summary?.heart_rate_average)}));if(force)R.dashboardTrendZoom=null;drawDashboardO2Mini()}"""
    new_refresh = """async function refreshDashboardO2(force=false){const sec=ensureDashboardO2Section();if(!sec)return;let rows=[];try{rows=state.dashboardOverview?.rows||[]}catch{}if(!rows.length){R.dashboardTrendRows=[];id('smDashO2Empty')?.classList.remove('hidden');drawDashboardO2Mini();return}const data=await getBatch(rows.map(r=>r.day),force),key=v=>String(v||'').replace(/-/g,'').slice(0,8),byDay=new Map(data.map(x=>[key(x.day),x])),avail=data.filter(x=>x.available&&x.summary).sort((a,b)=>String(a.day).localeCompare(String(b.day))),av=field=>{const v=avail.map(x=>num(x.summary?.[field])).filter(x=>x!=null);return v.length?v.reduce((a,b)=>a+b,0)/v.length:null},mins=avail.map(x=>num(x.summary?.spo2_minimum)).filter(x=>x!=null),spo2Med=av('spo2_median')??av('spo2_average'),hrMed=av('heart_rate_median')??av('heart_rate_average');id('smDashO2Avg').textContent=spo2Med==null?'—':`${fmt(spo2Med,1)}%`;id('smDashO2Min').textContent=mins.length?`${Math.min(...mins)}%`:'—';id('smDashHrAvg').textContent=hrMed==null?'—':`${fmt(hrMed,1)} bpm`;id('smDashT90').textContent=av('t90_seconds')==null?'—':dur(av('t90_seconds'));id('smDashO2Empty').classList.toggle('hidden',avail.length>0);R.dashboardTrendRows=rows.map(r=>{const x=byDay.get(key(r.day)),s=x?.available?x.summary:null;return{...r,spo2:s?(num(s.spo2_median)??num(s.spo2_average)):null,heart_rate:s?(num(s.heart_rate_median)??num(s.heart_rate_average)):null}});R.dashboardTrendZoom=null;drawDashboardO2Mini()}"""
    return _replace_required(text, old_refresh, new_refresh, "Dashboard O2 historical rows")


def _send_javascript(handler, text: str) -> None:
    body = text.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/javascript; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
    handler.send_header("Pragma", "no-cache")
    handler.end_headers()
    handler.wfile.write(body)


def install_v530_features(app_module) -> None:
    """Install the v5.3.4 frontend shell over the stable SleepMate data core.

    v5.3.4 deliberately removes the layered v5.3.2/v5.3.3 O2 controllers from
    the active shell. The base ``o2ring.js`` is now the single O2 UI owner;
    ``frontend-v534.js`` owns general PWA/settings/cache normalization and is
    registered before the v5.3 navigation bootstrap so Dashboard load wrappers
    are deterministic before O2Ring is dynamically mounted.
    """
    global _installed
    if _installed:
        return

    from .o2ring_data_management import install_o2ring_data_management
    from .o2ring_ai import install_o2ring_ai
    from .o2ring_diagnostics import install_o2ring_diagnostics
    from .o2ring_restore import install_o2ring_restore
    from .o2ring_v532 import install_o2ring_v532
    from .o2ring_runtime_v534 import install_o2ring_runtime_v534

    install_o2ring_data_management(app_module)
    install_o2ring_ai(app_module)
    install_o2ring_diagnostics(app_module)
    install_o2ring_restore(app_module)
    install_o2ring_v532(app_module)
    install_o2ring_runtime_v534(app_module)

    handler_cls = app_module.Handler
    previous_get = handler_cls.do_GET

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/sleepmate-v530.js":
            try:
                source = (app_module.WEB / "sleepmate-v530.js").read_text(encoding="utf-8")
                _send_javascript(self, _patch_sleepmate_v530(source))
                return
            except Exception as exc:
                self.send_error(500, f"SleepMate frontend bootstrap failed: {type(exc).__name__}")
                return

        if parsed.path == "/o2ring.js":
            try:
                source = (app_module.WEB / "o2ring.js").read_text(encoding="utf-8")
                _send_javascript(self, _patch_o2ring(source))
                return
            except Exception as exc:
                self.send_error(500, f"SleepMate O2 frontend bootstrap failed: {type(exc).__name__}")
                return

        if parsed.path in {"/", "/index.html"}:
            try:
                index_path = app_module.WEB / "index.html"
                text = index_path.read_text(encoding="utf-8")
                release_match = re.search(r'<meta name="sleepmate-release-version" content="([^"]+)">', text)
                build_match = re.search(r'<meta name="sleepmate-build-id" content="([^"]+)">', text)
                release_version = release_match.group(1) if release_match else APP_VERSION
                asset_version = build_match.group(1) if build_match else release_version
                text = text.replace('/style.css?v=5.0.0', f'/style.css?v={UI_VERSION}')
                text = text.replace('/app.js?v=5.0.0', f'/app.js?v={UI_VERSION}')
                text = text.replace('<strong id="sidebarVersion">v2.7</strong>', f'<strong id="sidebarVersion">v{UI_VERSION}</strong>')
                text = text.replace('<strong id="sidebarVersion">v5.0.0</strong>', f'<strong id="sidebarVersion">v{UI_VERSION}</strong>')

                head_assets: list[str] = []
                if 'name="sleepmate-ui-version"' not in text:
                    head_assets.append(f'<meta name="sleepmate-ui-version" content="{UI_VERSION}">')
                if 'name="sleepmate-release-version"' not in text:
                    head_assets.append(f'<meta name="sleepmate-release-version" content="{release_version}">')
                if 'name="sleepmate-build-id"' not in text:
                    head_assets.append(f'<meta name="sleepmate-build-id" content="{asset_version}">')
                if 'name="sleepmate-o2ring-enabled"' not in text:
                    # The HTML shell is cached by the PWA and may outlive the
                    # configuration value that existed when it was fetched.
                    # Never bake a user setting into that shared shell: the
                    # no-store O2 status endpoint is the canonical state source.
                    head_assets.append('<meta name="sleepmate-o2ring-enabled" content="unknown">')
                if "sleepmate-aurora.css" not in text:
                    head_assets.append(f'<link rel="stylesheet" href="/sleepmate-aurora.css?v={asset_version}">')
                if "sleepmate-v530.css" not in text:
                    head_assets.append(f'<link rel="stylesheet" href="/sleepmate-v530.css?v={asset_version}">')
                if "o2ring-v534.css" not in text:
                    head_assets.append(f'<link rel="stylesheet" href="/o2ring-v534.css?v={asset_version}">')
                if "sm-o2-master-visibility" not in text:
                    head_assets.append(
                        '<style id="sm-o2-master-visibility">'
                        'body:has(#smO2Enabled:not(:checked)) .o2ring-report-option{display:none!important}'
                        '[data-settings-tab="pwa"]{display:none!important}'
                        '</style>'
                    )

                if head_assets:
                    marker = "</head>"
                    inject = "\n  " + "\n  ".join(head_assets) + "\n"
                    text = text.replace(marker, inject + marker, 1) if marker in text else inject + text

                scripts: list[str] = []
                if "sleepmate-sleep.js" not in text:
                    scripts.append('<script src="/sleepmate-sleep.js?v=5.2.6"></script>')
                if "sleepmate-sleep-v523.js" not in text:
                    scripts.append('<script src="/sleepmate-sleep-v523.js?v=5.2.6"></script>')
                if "sleepmate-chart-v523.js" not in text:
                    scripts.append('<script src="/sleepmate-chart-v523.js?v=5.2.14"></script>')
                if "sleepmate-sleep-v524.js" not in text:
                    scripts.append('<script src="/sleepmate-sleep-v524.js?v=5.2.6"></script>')
                if "sleepmate-sleep-refresh-v5212.js" not in text:
                    scripts.append('<script src="/sleepmate-sleep-refresh-v5212.js?v=5.2.12"></script>')

                # Frontend ownership is established before sleepmate-v530 starts
                # its asynchronous O2 module loader. This guarantees that the
                # Dashboard loading-state wrapper sits directly around the core
                # loader, so the temporary legacy value can never survive across
                # the later O2 network await and reach a painted frame.
                frontend_path = app_module.WEB / "frontend-v534.js"
                if frontend_path.is_file() and "sm-frontend-v534-inline" not in text:
                    feature_js = _patch_frontend_v534(frontend_path.read_text(encoding="utf-8"))
                    feature_js = feature_js.replace("</script", "<\\/script")
                    scripts.append(f'<script id="sm-frontend-v534-inline">{feature_js}</script>')

                if "sleepmate-v530.js" not in text:
                    scripts.append(f'<script src="/sleepmate-v530.js?v={asset_version}"></script>')

                data_management_path = app_module.WEB / "o2ring-data-management.js"
                if data_management_path.is_file() and "sm-o2-data-management-inline" not in text:
                    feature_js = data_management_path.read_text(encoding="utf-8").replace("</script", "<\\/script")
                    scripts.append(f'<script id="sm-o2-data-management-inline">{feature_js}</script>')

                # Historical v532/v533 files remain in the source tree for old
                # release reproducibility, but are intentionally not active here.
                if scripts:
                    marker = "</body>"
                    inject = "\n" + "\n".join(scripts) + "\n"
                    text = text.replace(marker, inject + marker, 1) if marker in text else text + inject

                body = text.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("X-SleepMate-UI-Version", UI_VERSION)
                self.send_header("X-SleepMate-Release-Version", release_version)
                self.send_header("X-SleepMate-Build-ID", asset_version)
                self.end_headers()
                self.wfile.write(body)
                return
            except Exception as exc:
                self.send_error(500, f"SleepMate shell generation failed: {type(exc).__name__}")
                return
        return previous_get(self)

    handler_cls.do_GET = do_GET
    _installed = True


__all__ = ["install_v530_features", "UI_VERSION"]
