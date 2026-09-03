const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];

const CHARTS = [
  {key:'flow', title:'Légáramlás', color:'#57c7ff'},
  {key:'pressure', title:'Nyomás', color:'#ff7d8f'},
  {key:'mask_pressure', title:'Maszknyomás', color:'#b48cff'},
  {key:'leak', title:'Szivárgás', color:'#f4b85b'},
  {key:'flow_lim', title:'Áramláskorlátozás', color:'#ff9268'},
  {key:'snore', title:'Horkolás', color:'#f06f6f'},
  {key:'resp_rate', title:'Légzésszám', color:'#66d69e'},
  {key:'tidal_volume', title:'Légzéstérfogat', color:'#55d5d0'},
  {key:'minute_vent', title:'Perctérfogat', color:'#e7cd66'},
  {key:'epr_pressure', title:'EPR / EPAP nyomás', color:'#d19aff'},
];
const CHART_BY_KEY = Object.fromEntries(CHARTS.map(x=>[x.key,x]));
function eventTypeLabel(type,meta){return !meta?.name||meta.name===type?type:`${type} – ${meta.name}`}

const EVENT_TYPES = {
  OA:{name:'Obstruktív apnoe',color:'#ff806f',short:'A légút elzáródása miatt megszűnő vagy csaknem megszűnő légáramlás.',info:'A felső légút fizikailag beszűkül vagy elzáródik. A ResMed AutoSet algoritmus az obstruktív eseményekre szükség esetén nyomásemeléssel reagálhat.'},
  CA:{name:'Centrális apnoe',color:'#a995ff',short:'Nyitott légút mellett jelentkező légzéskimaradás.',info:'A ResMed centrális apnoénál nyitott légutat érzékel, de nincs légáramlás. AutoSet módban a készülék nem kezeli egyszerű obstruktív eseményként.'},
  H:{name:'Hipopnoe',color:'#57d6a8',short:'Részleges légáramlás-csökkenéssel járó légzési esemény.',info:'Nem teljes légzéskimaradás, hanem a légáramlás jelentős csökkenése. A hipopnoék az apnoékkal együtt alkotják az AHI-t.'},
  UA:{name:'Nem besorolható apnoe',color:'#f0c85b',short:'Az apnoe típusa nem sorolható be megbízhatóan.',info:'Jelentős szivárgás vagy bizonytalan légúti jel mellett a rendszer nem mindig tudja centrálisnak vagy obstruktívnak besorolni az eseményt.'},
  RERA:{name:'RERA',color:'#5eb4ff',short:'Fokozott légzési erőfeszítéshez kapcsolódó alvásmegszakítás.',info:'Olyan légzési periódus, amely nem feltétlenül teljesíti az apnoe vagy hipopnoe feltételeit, de fokozódó légzési erőfeszítés után mikroébredéshez vezethet.'},
  CSR:{name:'Cheyne–Stokes-légzés',color:'#e77cff',short:'Jellegzetesen hullámzó, periodikus légzésminta.',info:'A légzés mélysége fokozatosan növekszik, majd csökken, és ezt légzésszünetek kísérhetik. A ResMed algoritmus CSR-mintázatot is képes naplózni.'},
  OTHER:{name:'Egyéb esemény',color:'#aab7c4',short:'Egyéb vagy nem szabványos eseményjelölés.',info:'Az adatforrásban szereplő olyan esemény, amelyhez a program nem rendelt külön CPAP eseménytípust.'},
};

const state = {
  days:[], dayRows:[], currentDay:null, summary:null,
  full:[0,1], view:[0,1], selectedSignal:'flow',
  overviewSignals:new Map(), mainSignal:null, stackSignals:new Map(),
  chartMode:'focus', hoverTime:null, hoverPointY:0, chartDrag:null, stackDrag:null, navDrag:null, navPreview:null,
  overlayRaf:0, dayToken:0, mainToken:0, stackToken:0, resizeTimer:0, wheelReloadTimer:0,
  logs:[], reportRows:[], patient:null, patientTab:'overview', patientEdit:null, confirmAction:null,
  dashboardPeriod:'30', dashboardOverview:null, latestDay:null, overviewToken:0, detectedEquipment:null,
  settings:{show_spo2:false,show_hr:false,auto_scan_enabled:true,auto_scan_mode:'interval',auto_scan_interval_minutes:30,auto_scan_time:'06:00',auto_scan_days:[0,1,2,3,4,5,6],data_dir:''}, trendHoverIndex:null, trendHoverCanvas:null, trendHoverRaf:0,
  diagnostics:null, dailyAssessmentTimer:0, dashboardCalendarMonth:null, glossary:[], faqLoaded:false, equipmentCatalog:null, equipmentCatalogLoaded:false, pendingEventFocus:null,lastAutoScanSeen:null,
  ai:{provider:'gemini',status:null,config:null,result:null,analysisId:null,history:[],detail:'short',analysisType:null,month:null,streamTimer:0,chatBusy:false},
  systemStatus:null, comparison:null, remote:null, pwaPrompt:null, pendingReportPdf:null,
  connectionOffline:false,lastApiOnlineAt:null,pullRefreshing:false,touchPointers:new Map(),touchPinch:null,touchTapAt:0,notificationEnabled:false,pushStatus:null,
};

function sleep(ms){return new Promise(r=>setTimeout(r,ms))}
function setConnectionState(offline,stamp=null){
  state.connectionOffline=!!offline;
  if(!offline){state.lastApiOnlineAt=stamp||new Date().toISOString();try{localStorage.setItem('sleepmate-last-online-at',state.lastApiOnlineAt)}catch{}}
  const badge=$('#connectionBadge');
  if(badge){
    if(offline){let last=state.lastApiOnlineAt;try{last=last||localStorage.getItem('sleepmate-last-online-at')}catch{}badge.textContent=`Offline adat${last?' • utolsó kapcsolat: '+new Date(last).toLocaleTimeString('hu-HU',{hour:'2-digit',minute:'2-digit'}):''}`;badge.classList.remove('hidden')}
    else badge.classList.add('hidden');
  }
  updatePwaStatus();
}
function friendlyApiError(status,raw=''){if([502,503,504].includes(Number(status)))return'A SleepMate szerver átmenetileg nem érhető el.';if(Number(status)===0)return'A SleepMate szerverrel megszakadt a kapcsolat.';return raw||`A szerver hibát jelzett (HTTP ${status}).`}
async function api(url){
  const sep=url.includes('?')?'&':'?';let last=null;for(let attempt=0;attempt<3;attempt++){try{const r=await fetch(`${url}${sep}_=${Date.now()}`,{cache:'no-store'}),offline=r.headers.get('X-SleepMate-Offline')==='1',ct=(r.headers.get('content-type')||'').toLowerCase();if(!ct.includes('application/json')){const text=await r.text(),html=text.trimStart().toLowerCase().startsWith('<!doctype')||text.trimStart().toLowerCase().startsWith('<html');if(html&&r.ok)throw new Error('A webfelület és a háttérprogram verziója nem egyezik. Zárd be a régi SleepMate ablakát, majd indítsd újra ezt a verziót.');const err=new Error(friendlyApiError(r.status,`A szerver nem JSON választ adott (${r.status}).`));err.technical=`HTTP ${r.status} • nem JSON válasz`;err.retryable=[502,503,504].includes(r.status);throw err}const j=await r.json();if(!r.ok||j.error){const err=new Error(j.error||friendlyApiError(r.status));err.technical=`HTTP ${r.status}${j.error?' • '+j.error:''}`;err.retryable=[502,503,504].includes(r.status);throw err}setConnectionState(offline);return j}catch(e){last=e;if(e?.message?.includes('verziója nem egyezik'))throw e;const retryable=e?.retryable||e instanceof TypeError;if(attempt<2&&retryable){await sleep(220*(attempt+1));continue}if(e instanceof TypeError){const err=new Error(friendlyApiError(0));err.technical=String(e.message||e);throw err}throw e}}throw last||new Error('Ismeretlen hálózati hiba.')
}
async function apiWrite(url,method='POST',data=null){const opt={method,headers:{},cache:'no-store'};if(data!==null){opt.headers['Content-Type']='application/json';opt.body=JSON.stringify(data)}try{const r=await fetch(url,opt),ct=(r.headers.get('content-type')||'').toLowerCase(),j=ct.includes('application/json')?await r.json():{};if(!r.ok||j.error){const e=new Error(j.error||friendlyApiError(r.status));e.technical=`HTTP ${r.status}${j.error?' • '+j.error:''}`;throw e}setConnectionState(false);return j}catch(e){if(e instanceof TypeError){const x=new Error(friendlyApiError(0));x.technical=String(e.message||e);throw x}throw e}}
function showError(e){const el=$('#error'),raw=e?.message||String(e),technical=e?.technical||raw;let title='Hiba történt',msg=raw;if(/átmenetileg nem érhető el|megszakadt a kapcsolat|HTTP 50[234]|nem JSON választ adott \(50[234]\)/i.test(raw+' '+technical)){title='A SleepMate szerver átmenetileg nem érhető el';msg='A már betöltött adatok megmaradnak. Próbáld újra; ha van korábbi offline példány, a PWA automatikusan azt használja.'}$('#errorTitle').textContent=title;$('#errorMessage').textContent=msg;$('#errorTechnical').textContent=technical;el.classList.remove('hidden');clearTimeout(el._hideTimer);el._hideTimer=setTimeout(()=>el.classList.add('hidden'),12000);addLog('HIBA',technical)}
function clearError(){$('#error').classList.add('hidden')}
function addLog(type,msg){state.logs.unshift({time:new Date(),type,msg,source:'client'});state.logs=state.logs.slice(0,500);renderLogs()}
function renderLogs(){const box=$('#logList');if(!box)return;box.innerHTML=state.logs.length?state.logs.map(x=>`<div class="log-row"><time>${x.time.toLocaleTimeString('hu-HU')}</time><b class="log-${x.type.toLowerCase()}">${x.type}</b><span>${escapeHtml(x.msg)}</span></div>`).join(''):'<div class="empty-state">Még nincs naplóbejegyzés ebben a munkamenetben.</div>'}
function escapeHtml(s){return String(s).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}

function richTextHtml(text){
  const safe=escapeHtml(text||'');
  return safe
    .replace(/\*\*(.+?)\*\*/gs,'<strong>$1</strong>')
    .replace(/__(.+?)__/gs,'<strong>$1</strong>')
    .replace(/`([^`]+)`/g,'<code>$1</code>')
    .replace(/\n/g,'<br>');
}
function prepareStartupSplash(){
  const splash=$('#startupSplash'), img=splash?.querySelector('.startup-splash-image');
  if(!splash)return;
  const ready=()=>splash.classList.add('image-ready');
  if(!img){ready();return}
  if(img.complete&&img.naturalWidth){img.decode?.().catch(()=>{}).finally(ready);return}
  img.addEventListener('load',()=>{img.decode?.().catch(()=>{}).finally(ready)},{once:true});
  img.addEventListener('error',ready,{once:true});
}
function hideStartupSplash(){
  const splash=$('#startupSplash'), shell=document.querySelector('.hidden-until-ready');
  if(shell) shell.classList.add('ready');
  if(!splash) return;
  const finish=()=>setTimeout(()=>splash.classList.add('hidden'),360);
  if(splash.classList.contains('image-ready'))finish();
  else{const img=splash.querySelector('.startup-splash-image');img?.addEventListener('load',finish,{once:true});setTimeout(finish,1100)}
}
function mobileNavMode(){return window.matchMedia('(max-width:900px)').matches}
function setMobileSidebar(open){
  const sidebar=$('#sidebar'),scrim=$('#sidebarScrim'),toggle=$('#mobileMenuToggle');
  if(!sidebar||!scrim||!toggle)return;
  const show=Boolean(open&&mobileNavMode());
  document.documentElement.classList.toggle('mobile-nav-open',show);
  document.body.classList.toggle('mobile-nav-open',show);
  sidebar.classList.toggle('mobile-open',show);
  sidebar.setAttribute('aria-hidden',show?'false':(mobileNavMode()?'true':'false'));
  scrim.classList.toggle('active',show);
  scrim.setAttribute('aria-hidden',show?'false':'true');
  toggle.setAttribute('aria-expanded',show?'true':'false');
}
function closeMobileSidebar(){setMobileSidebar(false)}
function bindMobileDrawerGestures(){
  let tracking=false,startX=0,startY=0,startedOpen=false,horizontal=false;
  document.addEventListener('touchstart',e=>{
    if(!mobileNavMode()||!e.touches?.length)return;
    const t=e.touches[0],isOpen=document.body.classList.contains('mobile-nav-open');
    const inSidebar=!!e.target.closest?.('#sidebar');
    if(!isOpen&&t.clientX>48)return;
    if(isOpen&&!inSidebar)return;
    tracking=true;horizontal=false;startX=t.clientX;startY=t.clientY;startedOpen=isOpen;
  },{passive:true});
  // Claim a genuine horizontal edge gesture before WebKit can interpret it as
  // browser history navigation. Vertical scrolling from the edge stays normal.
  document.addEventListener('touchmove',e=>{
    if(!tracking||!mobileNavMode()||e.touches.length!==1)return;
    const t=e.touches[0],dx=t.clientX-startX,dy=t.clientY-startY;
    if(!horizontal){
      if(Math.abs(dy)>Math.abs(dx)&&Math.abs(dy)>9){tracking=false;return}
      if(Math.abs(dx)<9)return;
      horizontal=true;
    }
    const intended=startedOpen?dx<0:dx>0;
    if(intended&&e.cancelable)e.preventDefault();
  },{passive:false});
  document.addEventListener('touchend',e=>{
    if(!tracking||!mobileNavMode())return;tracking=false;
    const t=e.changedTouches?.[0];if(!t)return;
    const dx=t.clientX-startX,dy=Math.abs(t.clientY-startY);
    if(!horizontal||dy>80||Math.abs(dx)<52)return;
    if(startedOpen&&dx<0)closeMobileSidebar();
    else if(!startedOpen&&dx>0)setMobileSidebar(true);
    horizontal=false;
  },{passive:true});
  document.addEventListener('touchcancel',()=>{tracking=false;horizontal=false},{passive:true});
}
function openAIPrintModal(){ if(!state.ai.result)return; $('#aiPrintModal').classList.remove('hidden'); }
function closeAIPrintModal(){ $('#aiPrintModal').classList.add('hidden'); }

function fmtClock(v,seconds=true){return new Date(v).toLocaleTimeString('hu-HU',seconds?{hour:'2-digit',minute:'2-digit',second:'2-digit'}:{hour:'2-digit',minute:'2-digit'})}
function fmtDateTime(ms){return new Date(ms).toLocaleString('hu-HU',{month:'short',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit'})}
function formatDayCode(code){if(!code)return'–';const y=+code.slice(0,4),m=+code.slice(4,6),d=+code.slice(6,8);return new Intl.DateTimeFormat('hu-HU',{year:'numeric',month:'short',day:'numeric'}).format(new Date(y,m-1,d))}
function isoToDayCode(iso){return iso?.replaceAll('-','')||''}
function dayCodeToIso(code){return code?`${code.slice(0,4)}-${code.slice(4,6)}-${code.slice(6,8)}`:''}
function formatSpan(ms){let s=Math.max(0,Math.round(ms/1000));const h=Math.floor(s/3600);s%=3600;const m=Math.floor(s/60),sec=s%60;if(h)return`${h} óra ${String(m).padStart(2,'0')} perc`;if(m)return`${m} perc ${String(sec).padStart(2,'0')} mp`;return`${sec} mp`}
function formatUsageShort(hms){return hms?.slice(0,5)||'00:00'}
function unitText(unit,key){if(key==='resp_rate'&&unit==='bpm')return'légzés/perc';if(unit==='cmH2O')return'cmH₂O';return unit||''}
function decimalsFor(key){return ['flow','leak','pressure','mask_pressure','minute_vent','epr_pressure'].includes(key)?2:key==='tidal_volume'?0:2}
function formatStat(v,key,unit){if(v==null)return'–';return `${Number(v).toFixed(decimalsFor(key))}${unit?' '+unitText(unit,key):''}`}
function avg(arr){return arr.length?arr.reduce((a,b)=>a+b,0)/arr.length:0}
function secondsToHM(sec){const m=Math.round(sec/60);return `${Math.floor(m/60)}:${String(m%60).padStart(2,'0')}`}

async function init(){
  applyPwaPresentationMode();
  bindUi();
  registerPwa();
  setupMobilePwaFeatures();
  try{
    const [ver]=await Promise.all([api('/api/version'),loadDays(),loadConfig()]);
    if(ver.api!==19)throw new Error(`Nem támogatott háttérprogram-verzió: ${ver.version||'ismeretlen'}`);
    addLog('INFO',`SleepMate ${ver.version} elindult.`);
    route();
    warmOfflineRecentDays();
  }catch(e){
    showError(e);setConnectionState(true);
    try{route()}catch{}
  }finally{
    setInterval(checkBackgroundRefresh,60000);
    hideStartupSplash();
  }
}

function bindUi(){
  const nav=$('#sidebar .nav');
  if(nav)nav.addEventListener('click',e=>{const b=e.target.closest?.('.nav-item');if(!b)return;closeMobileSidebar();navigate(b.dataset.page)});
  $('#mobileMenuToggle').addEventListener('click',e=>{e.preventDefault();e.stopPropagation();setMobileSidebar(!document.body.classList.contains('mobile-nav-open'))});
  $('#mobileMenuClose').addEventListener('click',e=>{e.preventDefault();e.stopPropagation();closeMobileSidebar()});
  $('#sidebarScrim').addEventListener('click',e=>{e.preventDefault();closeMobileSidebar()});
  document.addEventListener('keydown',e=>{if(e.key==='Escape')closeMobileSidebar()});
  window.matchMedia('(max-width:900px)').addEventListener?.('change',()=>closeMobileSidebar());
  window.addEventListener('pageshow',()=>closeMobileSidebar());
  window.addEventListener('orientationchange',()=>closeMobileSidebar());
  bindMobileDrawerGestures();
  closeMobileSidebar();
  $('#refresh').onclick=refreshData;
  $('#errorRetry').onclick=()=>{clearError();route()};$('#errorDiagnostics').onclick=()=>navigate('logs');$('#shareDaily').onclick=shareCurrentDay;$('#pwaNotificationButton').onclick=()=>{navigate('settings');setTimeout(()=>setSettingsTab('push'),50)};
  $('#day').onchange=()=>navigate('dashboard',$('#day').value);
  $('#prevDay').onclick=()=>adjacentDay(1);
  $('#nextDay').onclick=()=>adjacentDay(-1);
  $('#resetZoom').onclick=()=>setView(state.full[0],state.full[1],true);
  $('#backToDashboardOverview').onclick=()=>navigate('dashboard');
  $('#openLatestSleep').onclick=()=>{if(state.latestDay)navigate('dashboard',state.latestDay)};
  $$('#dashboardPeriodSwitch [data-period]').forEach(b=>b.onclick=()=>loadDashboardOverview(b.dataset.period));
  $('#focusViewBtn').onclick=()=>setChartMode('focus');
  $('#stackViewBtn').onclick=()=>setChartMode('stack');
  $('#eventsDay').onchange=()=>loadEventsPage($('#eventsDay').value);
  $('#reportDay').onchange=()=>loadReportStats($('#reportDay').value);
  $('#applyReportRange').onclick=applyReportRange;
  $('#openReportPdf').onclick=openReportPdfModal;
  $('#reportPdfClose').onclick=closeReportPdfModal;
  $('#reportPdfCancel').onclick=closeReportPdfModal;
  $('#reportPdfPreview').onclick=()=>generateReportPdf(true);
  $('#reportPdfGenerate').onclick=()=>generateReportPdf(false);
  $('#reportPdfSave').onclick=saveGeneratedReportPdf;
  $('#reportIncludePatient').onchange=updateReportPatientOptions;
  $('#reportAnonymize').onclick=applyReportAnonymizedPreset;
  $$('input[name="reportMode"]').forEach(x=>x.onchange=applyReportModePreset);
  $$('input[name="reportTheme"]').forEach(x=>x.onchange=updateReportOptionCards);
  $('#clearLogs').onclick=clearAllLogs;
  $('#refreshLogs').onclick=loadDiagnostics;
  $('#refreshDashboardCalendar').onclick=()=>renderDashboardCalendar(true);
  $('#dashboardCalendarMonth').onchange=()=>{state.dashboardCalendarMonth=$('#dashboardCalendarMonth').value;renderDashboardCalendar(false)};
  $('#faqSearch').oninput=renderFaqResults;
  $('#faqCategory').onchange=renderFaqResults;
  $$('input[name="faqScope"]').forEach(x=>x.onchange=renderFaqResults);
  $$('.patient-tab').forEach(b=>b.onclick=()=>setPatientTab(b.dataset.patientTab));
  $('#patientEditButton').onclick=()=>editPatientCurrent();
  $('#createPatientButton').onclick=()=>openProfileEditor();
  $('#restorePatientButton').onclick=()=>setPatientTab('backup');
  $('#patientTherapyPeriod').onchange=()=>loadPatientTherapy($('#patientTherapyPeriod').value);
  $('#deletePatientButton').onclick=()=>confirmAction('A kezelt személy törlésével a személyhez tartozó személyes, diagnosztikai és terápiás metaadatok eltávolításra kerülnek. A CPAP EDF mérési adatok NEM törlődnek. Biztosan folytatod?',deletePatientOnly);
  $('#patientModalClose').onclick=closePatientModal;$('#patientCancel').onclick=closePatientModal;
  $('#confirmNo').onclick=closeConfirm;$('#confirmYes').onclick=async()=>{const fn=state.confirmAction;closeConfirm();if(fn)await fn()};
  $('#patientForm').onsubmit=savePatientForm;
  $('#exportPatientBackup').onclick=exportPatientBackup;
  $('#importPatientBackup').onclick=importPatientBackup;
  $('#assignDetectedDevice').onclick=assignDetectedDevice;
  $('#saveDisplaySettings').onclick=saveDisplaySettings;
  $('#saveDataSourceSettings').onclick=saveDataSourceSettings;
  $('#savePortSettings').onclick=savePortSettings;
  $('#browseSettingDataDir').onclick=()=>pickFolderInto('#settingDataDirInput');
  $('#saveRemoteSettings').onclick=saveRemoteSettings;
  $('#tailscaleInstall').onclick=()=>installRemoteComponent('tailscale');
  $('#tailscaleEnable').onclick=()=>setTailscaleAccess('enable');
  $('#tailscaleDisable').onclick=()=>setTailscaleAccess('disable');
  $('#tailscaleOpen').onclick=()=>openRemoteUrl(state.remote?.tailscale?.url||state.remote?.tailscale?.setup_url||'');
  $('#tailscaleQr').onclick=openTailscaleQr;
  $('#tailscaleQrClose').onclick=closeTailscaleQr;
  $('#tailscaleQrDone').onclick=closeTailscaleQr;
  $('#cloudflareInstall').onclick=()=>installRemoteComponent('cloudflare');
  $('#cloudflareStart').onclick=()=>setCloudflareTunnel('start');
  $('#cloudflareStop').onclick=()=>setCloudflareTunnel('stop');
  $('#cloudflareOpen').onclick=()=>openRemoteUrl(state.remote?.cloudflare?.url||'');
  $('#pwaInstallButton').onclick=installPwa;
  $('#pushEnableButton').onclick=enablePwaNotifications;
  $('#pushSaveButton').onclick=savePushPreferences;
  $('#pushTestButton').onclick=testPushNotification;
  $('#pushDisableButton').onclick=disablePushNotifications;
  $('#saveAutoScanSettings').onclick=saveAutoScanSettings;
  $('#saveAutoBackupSettings').onclick=saveAutoBackupSettings;
  $('#settingAutoBackupMode').onchange=updateAutoBackupUi;
  $('#browseAutoBackupDir').onclick=()=>pickFolderInto('#settingAutoBackupDir');
  $('#systemStatusToggle').onclick=()=>$('#systemStatusDetails').classList.toggle('hidden');
  $('#openComparison').onclick=openComparisonModal;
  $('#editComparison').onclick=openComparisonModal;
  $('#clearComparison').onclick=clearComparison;
  $('#comparisonModalClose').onclick=closeComparisonModal;
  $('#comparisonCancel').onclick=closeComparisonModal;
  $('#runComparison').onclick=runComparison;
  $('#addTimelineEvent').onclick=()=>openRecordEditor('timeline_event');
  $('#settingAutoScanMode').onchange=updateScheduleUi;
  $('#browseManualImportFolder').onclick=()=>pickFolderInto('#manualImportFolder');
  $('#startFolderImport').onclick=startFolderImport;
  $('#startSdSearch').onclick=startSdSearch;
  $('#startZipImport').onclick=startZipImport;
  $('#startInstantRefresh').onclick=startInstantRefresh;
  $('#createFullBackup').onclick=createFullBackup;
  $('#restoreFullBackup').onclick=restoreFullBackup;
  if($('#saveUpdateSettings'))$('#saveUpdateSettings').onclick=saveUpdateSettings;
  if($('#checkForUpdates'))$('#checkForUpdates').onclick=checkForUpdates;
  if($('#installUpdate'))$('#installUpdate').onclick=installAvailableUpdate;
  if($('#rollbackUpdate'))$('#rollbackUpdate').onclick=rollbackSleepMate;
  if($('#runSelfCheck'))$('#runSelfCheck').onclick=runSelfCheck;
  if($('#createSupportBundle'))$('#createSupportBundle').onclick=createSupportBundle;
  $('#deleteSelectedData').onclick=deleteSelectedData;
  $('#dataDeleteModalClose').onclick=closeDataDeleteModal;
  $('#dataDeleteCancel').onclick=closeDataDeleteModal;
  $('#dataDeleteConfirmInput').oninput=()=>{$('#dataDeleteExecute').disabled=$('#dataDeleteConfirmInput').value!=='TÖRLÉS'};
  $('#dataDeleteExecute').onclick=executeSelectedDataDelete;
  $('#openDailyAssessment').onclick=openDailyAssessmentModal;
  $('#deleteDailyAssessment').onclick=deleteDailyAssessment;

  $('#dailyAssessmentModalClose').onclick=closeDailyAssessmentModal;
  $('#dailyAssessmentCancel').onclick=closeDailyAssessmentModal;
  $('#dailyAssessmentForm').onsubmit=saveDailyAssessment;
  $$('[data-add-record]').forEach(b=>b.onclick=()=>openRecordEditor(b.dataset.addRecord));
  $$('.patient-summary-card[data-jump]').forEach(c=>c.onclick=()=>setPatientTab(c.dataset.jump));
  $$('.ai-provider-card').forEach(b=>b.onclick=()=>selectAIProvider(b.dataset.aiProvider));
  $$('[data-ai-analysis]').forEach(b=>b.onclick=()=>startAIAnalysisWithFeatures(b.dataset.aiAnalysis,b));
  $('#aiAnalysisPickerButton').onclick=openAIAnalysisSheet;
  $('#aiAnalysisSheetClose').onclick=closeAIAnalysisSheet;
  $('#aiAnalysisSheetScrim').onclick=closeAIAnalysisSheet;
  $$('[data-ai-mobile-choice]').forEach(b=>b.onclick=()=>chooseMobileAIAnalysis(b.dataset.aiMobileChoice));
  $('#aiMobileMonthRun').onclick=runMobileAIMonth;
  $('#aiMobileComparisonRun').onclick=runMobileAIComparison;
  for(const id of ['aiCompareAStart','aiCompareAEnd','aiCompareBStart','aiCompareBEnd'])document.getElementById(id)?.addEventListener('change',updateAIAnalysisLocks);
  $$('.ai-detail-switch [data-ai-detail]').forEach(b=>b.onclick=()=>setAIDetailView(b.dataset.aiDetail));
  $('#aiChatForm').onsubmit=sendAIChat;
  if($('#aiChatInput')){
    $('#aiChatInput').addEventListener('input',resizeAIChatInput);
    $('#aiChatInput').addEventListener('focus',resizeAIChatInput);
    resizeAIChatInput();
  }
  $('#aiPrintPdf').onclick=openAIPrintModal;
  $('#aiPrintModalClose').onclick=closeAIPrintModal;
  $('#aiPrintOnlyResult').onclick=()=>{closeAIPrintModal();printAIResult(false)};
  $('#aiPrintWithChat').onclick=()=>{closeAIPrintModal();printAIResult(true)};
  $('#aiPromptClose').onclick=closeAIPromptModal;
  $('#aiPromptModal').addEventListener('click',e=>{if(e.target===$('#aiPromptModal'))closeAIPromptModal()});
  $('#aiPromptCopy').onclick=copyAIPrompt;
  $('#aiPromptDownload').onclick=downloadAIPrompt;
  $('#aiPromptChatGpt').onclick=()=>openExternalAi('https://chatgpt.com/');
  $('#aiPromptGemini').onclick=()=>openExternalAi('https://gemini.google.com/app');
  $('#saveAISettings').onclick=saveAISettings;$('#refreshAIHistory').onclick=loadAIHistory;$$('[data-settings-tab]').forEach(b=>b.onclick=()=>setSettingsTab(b.dataset.settingsTab));
  if($('#settingsCategorySelect'))$('#settingsCategorySelect').onchange=e=>setSettingsTab(e.target.value);
  $$('.secret-toggle').forEach(b=>b.onclick=()=>toggleSecretInput(b));
  $$('[data-ai-test]').forEach(b=>b.onclick=()=>testAIProvider(b.dataset.aiTest,b));
  if($('#refreshAiLogs')) $('#refreshAiLogs').onclick=loadAiDiagnosticLog;
  if($('#copyAiFullLog')) $('#copyAiFullLog').onclick=()=>copyLogToClipboard('ai');
  if($('#exportAiFullLog')) $('#exportAiFullLog').onclick=()=>exportLogTxt('ai');
  if($('#copyFullLog')) $('#copyFullLog').onclick=()=>copyLogToClipboard('full');
  if($('#exportFullLog')) $('#exportFullLog').onclick=()=>exportLogTxt('full');
  $$('#mobileBottomNav button').forEach(b=>b.onclick=()=>handleMobileBottomNav(b));
  setupHeroInteraction(); setupNavigatorInteraction(); setupEventsInteraction();
  window.addEventListener('hashchange',route);
  window.addEventListener('sleepmate-ai-preferences',applyAiFeatureAvailability);
  window.addEventListener('resize',()=>{clearTimeout(state.resizeTimer);state.resizeTimer=setTimeout(()=>{drawAll();drawDashboardTrends()},120)});
}

function navigate(page,day=null){
  clearTrendHover();
  state.hoverTime=null;state.touchPointers.clear();state.touchPinch=null;
  scheduleOverlayRender();
  const next=page==='dashboard'&&day?`#dashboard/${day}`:`#${page}`;
  // Installed PWA navigation must not build a browser history stack. On iOS a
  // left-edge drawer gesture otherwise also triggers WebKit's Back navigation
  // first (e.g. AI -> Dashboard) and only then opens our hamburger drawer.
  if(standalonePwa()){
    history.replaceState({sleepmate:true},'',next);
    route();
  }else{
    location.hash=next;
  }
}
function route(){
  const raw=(location.hash||'#dashboard').slice(1);const [pageRaw,day]=raw.split('/');
  const page=['dashboard','patient','sessions','events','reports','ai','faq','equipment','upload','logs','settings'].includes(pageRaw)?pageRaw:'dashboard';
  showPage(page);
  if(page==='dashboard'){if(day&&state.days.includes(day))loadDashboard(day);else loadDashboardOverview(state.dashboardPeriod)}
  else if(page==='patient')loadPatientPage();
  else if(page==='sessions')loadSessionsPage();
  else if(page==='events')loadEventsPage(state.currentDay||state.days[0]);
  else if(page==='reports')prepareReports();
  else if(page==='ai')loadAIPage();
  else if(page==='faq')loadFaqPage();
  else if(page==='equipment')loadEquipmentPage();
  else if(page==='upload')loadUploadPage();
  else if(page==='logs')loadDiagnostics();
  else if(page==='settings'){setSettingsTab('source');loadConfig();loadAIConfig();}
}
function showPage(page){
  $$('.page').forEach(x=>x.classList.toggle('active',x.id===`page-${page}`));
  $$('.nav-item').forEach(x=>x.classList.toggle('active',x.dataset.page===page));
  const titles={dashboard:'Dashboard',patient:'Kezelt személy',sessions:'Szekciók',events:'Események',reports:'Jelentések',ai:'AI összegzés',faq:'GYIK',equipment:'Felszerelés',upload:'Feltöltés',logs:'Naplók',settings:'Beállítások'};
  if($('#sidebarVersion')) $('#sidebarVersion').textContent='v5.0.0';
  $('#pageTitle').textContent=titles[page];
  const subs={dashboard:'Legutóbbi alvás • trendek • OSCAR-referencia',patient:'Személyes, diagnosztikai és terápiás előzmények',sessions:'ResMed napok és terápiás idő',events:'Felismert légzési események',reports:'Statisztikák és prémium PDF jelentés',ai:'Luna és Milo • anonim terápiás elemzés • chat',faq:'CPAP / PAP fogalomtár és rövidítések',equipment:'Kezelt személyhez rendelt készülékek és maszkok',upload:'Import és szinkronizálás',logs:'Rendszerállapot • diagnosztika • munkamenet eseményei',settings:'Helyi szerver és elérés'};
  $('#pageSubtitle').textContent=subs[page]||'SleepMate';
  updateMeasurementEmptyStates();updateMobileBottomNav(page);
}
const DATA_REQUIRED_PAGES=['dashboard','sessions','events','reports'];
function emptySleepSvg(){return `<svg viewBox="0 0 360 220" role="img" aria-label="Alvó személy CPAP készülékkel és holddal">
      <path d="M107 49c-28 11-43 42-32 70 12 30 47 44 77 31 14-6 24-17 30-30-37 11-74-24-63-62-4-4-8-7-12-9Z" fill="#83b7ff"/>
      <circle cx="113" cy="87" r="4" fill="#173247"/><path d="M101 104c8 7 18 7 26 0" fill="none" stroke="#173247" stroke-width="4" stroke-linecap="round"/>
      <path d="M155 155h129a17 17 0 0 1 17 17v15H139v-16a16 16 0 0 1 16-16Z" fill="#20394c"/>
      <path d="M166 137h69c16 0 29 8 36 18H150c2-10 7-18 16-18Z" fill="#edf7fb"/>
      <circle cx="180" cy="137" r="18" fill="#ffd1b6"/><path d="M166 136c3-18 25-21 32-5-9-4-17-4-32 5Z" fill="#3f5365"/>
      <path d="M195 142c10 0 17 2 22 8" fill="none" stroke="#57c7ff" stroke-width="5" stroke-linecap="round"/>
      <path d="M216 150c21 0 18-29 42-29" fill="none" stroke="#57c7ff" stroke-width="4" stroke-linecap="round" stroke-dasharray="5 6"/>
      <rect x="251" y="98" width="48" height="43" rx="9" fill="#e8f1f5" stroke="#658195" stroke-width="3"/><rect x="260" y="107" width="24" height="15" rx="3" fill="#64cdf3"/>
      <circle cx="290" cy="127" r="4" fill="#657b8b"/>
      <path d="M57 170c27-13 49-7 66 17" fill="none" stroke="#294b62" stroke-width="5" stroke-linecap="round"/><circle cx="64" cy="168" r="4" fill="#f4c95d"/>
      <circle cx="310" cy="69" r="5" fill="#f4c95d"/><path d="M303 47l3 7 7 3-7 3-3 7-3-7-7-3 7-3Z" fill="#f4c95d"/>
    </svg>`}
function measurementEmptyHtml(){return `<section class="measurement-empty-state" aria-live="polite">
  <div class="empty-sleep-art" aria-hidden="true">${emptySleepSvg()}</div>
  <h2>Még nem töltöttél el éjszakát.</h2>
  <p>Vagy igen? Akkor töltsd fel az SD/ZIP adatokat, vagy szinkronizáld az alapértelmezett ResMed mappát. 🌙</p>
  <div class="empty-sleep-actions"><button type="button" data-empty-upload>Adatok feltöltése</button><button type="button" class="primary-action" data-empty-sync>Szinkronizálás most</button></div>
  <small>A forrásmappáidhoz a program csak olvasási céllal fér hozzá.</small>
</section>`}
function updateMeasurementEmptyStates(){
  const empty=!state.days.length;
  DATA_REQUIRED_PAGES.forEach(name=>{const page=document.getElementById(`page-${name}`);if(!page)return;page.classList.toggle('measurement-empty-mode',empty);let box=page.querySelector('.measurement-empty-state');if(empty&&!box){page.insertAdjacentHTML('afterbegin',measurementEmptyHtml());box=page.querySelector('.measurement-empty-state');box.querySelector('[data-empty-upload]').onclick=()=>navigate('upload');box.querySelector('[data-empty-sync]').onclick=async()=>{navigate('upload');setTimeout(startInstantRefresh,120)}}else if(!empty&&box)box.remove()})
}

async function loadDays(selected=null){
  const d=await api('/api/days');state.days=d.days;
  const selects=['#day','#eventsDay'];
  for(const q of selects){const el=$(q);el.innerHTML='';d.days.forEach(x=>el.add(new Option(formatDayCode(x),x)));if(selected&&d.days.includes(selected))el.value=selected}
  if(!state.currentDay&&d.days.length)state.currentDay=d.days[0];
  if(!d.days.length)state.currentDay=null;
  updateMeasurementEmptyStates();
  return d.days;
}
async function loadDayRows(force=false){
  if(!state.dayRows.length||force){const d=await api('/api/day-table');state.dayRows=d.rows}
  if(window.SleepMateO2Ring?.hydrateDayRows)await window.SleepMateO2Ring.hydrateDayRows(state.dayRows,force);
  applyOximetryVisibility();return state.dayRows;
}
async function loadConfig(){
  try{
    const c=await api('/api/config');
    state.settings={
      show_spo2:!!c.show_spo2,show_hr:!!c.show_hr,data_dir:c.data_dir||'',port_mode:c.port_mode||'auto',port_preferred:Number(c.port_preferred||c.port||8895),runtime_port:Number(c.port||8895),
      auto_scan_enabled:!!c.auto_scan_enabled,auto_scan_mode:c.auto_scan_mode||'interval',
      auto_scan_interval_minutes:Number(c.auto_scan_interval_minutes||30),auto_scan_time:c.auto_scan_time||'06:00',
      auto_scan_days:Array.isArray(c.auto_scan_days)?c.auto_scan_days:[0,1,2,3,4,5,6],
      tray_notifications:c.tray_notifications!==false,start_with_windows:!!c.start_with_windows,
      auto_backup_enabled:!!c.auto_backup_enabled,auto_backup_mode:c.auto_backup_mode||'weekly',auto_backup_time:c.auto_backup_time||'03:00',
      auto_backup_weekday:Number(c.auto_backup_weekday??6),auto_backup_monthday:Number(c.auto_backup_monthday??1),auto_backup_dir:c.auto_backup_dir||'',
      auto_backup_keep:Number(c.auto_backup_keep||5),auto_backup_last_run:c.auto_backup_last_run||null,auto_backup_next_run:c.auto_backup_next_run||null,auto_backup_last_file:c.auto_backup_last_file||'',
      cloudflare_hostname:c.cloudflare_hostname||'',cloudflare_access_confirmed:!!c.cloudflare_access_confirmed,
      update_github_repo:c.update_github_repo||'',update_channel:c.update_channel||'stable',update_auto_check:c.update_auto_check!==false
    };
    if($('#settingDataDirInput'))$('#settingDataDirInput').value=c.data_dir||'';
    if($('#instantRefreshPath'))$('#instantRefreshPath').textContent=c.data_dir||'–';
    $('#settingPort').textContent=c.port;$('#settingHost').textContent=c.host;
    if($('#settingPortMode'))$('#settingPortMode').value=state.settings.port_mode;
    if($('#settingPreferredPort'))$('#settingPreferredPort').value=state.settings.port_preferred;
    if($('#settingPortHint'))$('#settingPortHint').textContent=state.settings.port_mode==='auto'?(c.port===state.settings.port_preferred?'Az elsődleges port szabad volt.':`Az elsődleges ${state.settings.port_preferred} foglalt volt; automatikusan ezt választotta.`):'Fix port mód.';
    if($('#cloudflareOriginHint'))$('#cloudflareOriginHint').textContent=`http://127.0.0.1:${c.port}`;
    $('#settingShowSpO2').checked=state.settings.show_spo2;$('#settingShowHR').checked=state.settings.show_hr;
    if($('#settingAutoScanEnabled'))$('#settingAutoScanEnabled').checked=state.settings.auto_scan_enabled;
    if($('#settingAutoScanMode'))$('#settingAutoScanMode').value=state.settings.auto_scan_mode;
    if($('#settingAutoScanInterval'))$('#settingAutoScanInterval').value=String(state.settings.auto_scan_interval_minutes);
    if($('#settingAutoScanTime'))$('#settingAutoScanTime').value=state.settings.auto_scan_time;
    if($('#settingTrayNotifications'))$('#settingTrayNotifications').checked=state.settings.tray_notifications;
    if($('#settingStartWithWindows'))$('#settingStartWithWindows').checked=state.settings.start_with_windows;
    if($('#settingAutoBackupEnabled'))$('#settingAutoBackupEnabled').checked=state.settings.auto_backup_enabled;
    if($('#settingAutoBackupMode'))$('#settingAutoBackupMode').value=state.settings.auto_backup_mode;
    if($('#settingAutoBackupTime'))$('#settingAutoBackupTime').value=state.settings.auto_backup_time;
    if($('#settingAutoBackupWeekday'))$('#settingAutoBackupWeekday').value=String(state.settings.auto_backup_weekday);
    if($('#settingAutoBackupMonthday'))$('#settingAutoBackupMonthday').value=state.settings.auto_backup_monthday;
    if($('#settingAutoBackupDir'))$('#settingAutoBackupDir').value=state.settings.auto_backup_dir;
    if($('#settingAutoBackupKeep'))$('#settingAutoBackupKeep').value=state.settings.auto_backup_keep;
    if($('#autoBackupLast'))$('#autoBackupLast').textContent=state.settings.auto_backup_last_run?humanDateTime(state.settings.auto_backup_last_run):'Még nem futott';
    if($('#autoBackupNext'))$('#autoBackupNext').textContent=state.settings.auto_backup_next_run?humanDateTime(state.settings.auto_backup_next_run):'Nincs ütemezve';
    if($('#autoBackupLastFile'))$('#autoBackupLastFile').textContent=state.settings.auto_backup_last_file||'Még nincs mentés';
    if($('#cloudflareHostname'))$('#cloudflareHostname').value=state.settings.cloudflare_hostname||'';
    if($('#cloudflareAccessConfirmed'))$('#cloudflareAccessConfirmed').checked=state.settings.cloudflare_access_confirmed;
    if($('#updateAutoCheck'))$('#updateAutoCheck').checked=state.settings.update_auto_check!==false;
    if($('#remoteBackendUrl'))$('#remoteBackendUrl').textContent=`http://127.0.0.1:${c.port}`;
    if(document.querySelector('[data-settings-panel="remote"]')) loadRemoteStatus();
    updateAutoBackupUi();
    $$('.weekday-picker input[type="checkbox"]').forEach(x=>x.checked=state.settings.auto_scan_days.includes(Number(x.value)));
    if($('#autoScanLast'))$('#autoScanLast').textContent=c.auto_scan_last_run?new Date(c.auto_scan_last_run).toLocaleString('hu-HU'):'Még nem futott';
    if($('#autoScanNext'))$('#autoScanNext').textContent=c.auto_scan_next_run?new Date(c.auto_scan_next_run).toLocaleString('hu-HU'):'Nincs ütemezve';
    if(state.lastAutoScanSeen===null)state.lastAutoScanSeen=c.auto_scan_last_run||'';
    updateScheduleUi();applyOximetryVisibility();
  }catch(e){addLog('WARN',`Beállítások nem olvashatók: ${e.message}`)}
}
function updateScheduleUi(){
  const mode=$('#settingAutoScanMode')?.value||'interval';
  $$('.schedule-interval').forEach(x=>x.classList.toggle('hidden',mode!=='interval'));
  $$('.schedule-time').forEach(x=>x.classList.toggle('hidden',mode==='interval'));
  $$('.schedule-weekly').forEach(x=>x.classList.toggle('hidden',mode!=='weekly'));
}
async function pickFolderInto(selector){
  try{const current=$(selector)?.value?.trim()||'';const r=await apiWrite('/api/system/pick-folder','POST',{user_initiated:true,initial_dir:current});if(r.folder)$(selector).value=r.folder}catch(e){showError(e)}
}
function flashInlineStatus(el,text,ms=4500){if(!el)return;el.textContent=text;clearTimeout(el._hideTimer);el._hideTimer=setTimeout(()=>{el.textContent=''},ms)}
async function saveDataSourceSettings(){
  const status=$('#dataSourceSettingsStatus'),btn=$('#saveDataSourceSettings');btn.disabled=true;status.textContent='Mentés…';
  try{const r=await apiWrite('/api/settings','POST',{data_dir:$('#settingDataDirInput').value.trim()});state.dayRows=[];await loadConfig();await loadDays();flashInlineStatus(status,'Mentve. Ez lett az automatikus és azonnali frissítés alapmappája.');addLog('INFO',`Alapértelmezett adatmappa: ${r.data_dir}`)}catch(e){showError(e);flashInlineStatus(status,'Hiba.',6000)}finally{btn.disabled=false}
}
async function savePortSettings(){
  const status=$('#portSettingsStatus'),btn=$('#savePortSettings');btn.disabled=true;status.textContent='Mentés…';
  try{
    const mode=$('#settingPortMode').value,port=Number($('#settingPreferredPort').value);
    if(!Number.isInteger(port)||port<1024||port>65435)throw new Error('A port 1024 és 65435 közötti egész szám legyen.');
    await apiWrite('/api/settings','POST',{port_mode:mode,port});
    state.settings.port_mode=mode;state.settings.port_preferred=port;
    flashInlineStatus(status,'Mentve. A portbeállítás a SleepMate következő újraindításakor lép életbe.',7000);
    addLog('INFO',`Portbeállítás mentve: ${mode==='auto'?'automatikus':'fix'} • ${port}.`);
  }catch(e){showError(e);flashInlineStatus(status,'Hiba.',7000)}finally{btn.disabled=false}
}
async function saveAutoScanSettings(){
  const status=$('#autoScanSettingsStatus'),btn=$('#saveAutoScanSettings');btn.disabled=true;status.textContent='Mentés…';
  try{const days=$$('.weekday-picker input:checked').map(x=>Number(x.value));const r=await apiWrite('/api/settings','POST',{auto_scan_enabled:$('#settingAutoScanEnabled').checked,auto_scan_mode:$('#settingAutoScanMode').value,auto_scan_interval_minutes:Number($('#settingAutoScanInterval').value),auto_scan_time:$('#settingAutoScanTime').value,auto_scan_days:days,tray_notifications:$('#settingTrayNotifications')?.checked!==false,start_with_windows:!!$('#settingStartWithWindows')?.checked});await loadConfig();const msg=r.auto_scan_enabled?'Automatikus beállítások mentve.':'Automatikus könyvtárfelülvizsgálat kikapcsolva.';flashInlineStatus(status,msg);addLog('INFO',msg)}catch(e){showError(e);flashInlineStatus(status,'Hiba.',6000)}finally{btn.disabled=false}
}
function updateAutoBackupUi(){const mode=$('#settingAutoBackupMode')?.value||'weekly';document.querySelector('.auto-backup-weekly')?.classList.toggle('hidden',mode!=='weekly');document.querySelector('.auto-backup-monthly')?.classList.toggle('hidden',mode!=='monthly')}

async function saveAutoBackupSettings(){const btn=$('#saveAutoBackupSettings'),status=$('#autoBackupSettingsStatus');if(!btn)return;btn.disabled=true;status.textContent='Mentés…';try{const r=await apiWrite('/api/settings','POST',{auto_backup_enabled:$('#settingAutoBackupEnabled').checked,auto_backup_mode:$('#settingAutoBackupMode').value,auto_backup_time:$('#settingAutoBackupTime').value,auto_backup_weekday:Number($('#settingAutoBackupWeekday').value),auto_backup_monthday:Number($('#settingAutoBackupMonthday').value),auto_backup_dir:$('#settingAutoBackupDir').value.trim(),auto_backup_keep:Number($('#settingAutoBackupKeep').value)});await loadConfig();flashInlineStatus(status,'Automatikus biztonsági mentés beállítva.');addLog('INFO','Automatikus backup beállítások mentve.')}catch(e){showError(e);flashInlineStatus(status,'Hiba.',7000)}finally{btn.disabled=false}}


async function loadRemoteStatus(){
  try{
    const r=await api('/api/remote/status');state.remote=r;
    const t=r.tailscale||{},c=r.cloudflare||{};
    $('#tailscaleInstalled').textContent=t.installed?'igen':'nincs';$('#tailscaleOnline').textContent=t.online?'igen':'nem';$('#tailscaleServe').textContent=t.serve_active?'aktív':'kikapcsolva';$('#tailscaleUrl').value=t.url||'';
    const detail=$('#tailscaleDetail');if(detail)detail.textContent=t.message||(t.serve_active&&t.url?'A privát HTTPS cím használatra kész.':t.online?'A Serve bekapcsolása után itt jelenik meg a HTTPS cím.':'');
    const ts=$('#tailscaleState');ts.textContent=!t.installed?'Nincs telepítve':t.serve_active&&t.url?'Elérhető':t.setup_url?'Jóváhagyás kell':t.online?'Készen áll':'Nincs kapcsolat';ts.className='remote-status '+(t.serve_active&&t.url?'ok':t.online?'warn':'neutral');
    $('#tailscaleInstall').classList.toggle('hidden',!!t.installed);$('#tailscaleInstall').disabled=!!t.installed;
    $('#tailscaleEnable').disabled=!t.installed||!t.online||t.serve_active;$('#tailscaleDisable').disabled=!t.serve_active;$('#tailscaleOpen').disabled=!(t.url||t.setup_url);$('#tailscaleOpen').textContent=t.url?'Megnyitás':t.setup_url?'Tailscale beállítás':'Megnyitás';$('#tailscaleQr').disabled=!(t.serve_active&&t.url);
    $('#cloudflareInstalled').textContent=c.installed?(c.version||'igen'):'nincs';$('#cloudflareRunning').textContent=c.running?'fut':'áll';$('#cloudflareAccessState').textContent=c.access_confirmed?'beállítva':'nincs visszaigazolva';
    if($('#cloudflareMode'))$('#cloudflareMode').textContent=c.mode_label||'–';
    if($('#cloudflareServiceHint'))$('#cloudflareServiceHint').textContent=c.message||'';
    $('#cloudflareHostname').value=c.hostname||state.settings.cloudflare_hostname||'';$('#cloudflareAccessConfirmed').checked=!!c.access_confirmed;$('#cloudflareTokenHint').textContent=c.external_running?'Nem szükséges: a meglévő cloudflared szolgáltatás kezeli a tunnelt.':c.token_configured?`Mentett token: ${c.token_hint||'••••'}`:'Nincs mentett token — csak SleepMate által indított tunnelhez kell.';
    const adv=$('#cloudflareTokenAdvanced');if(adv&&c.external_running)adv.open=false;
    const cs=$('#cloudflareState');cs.textContent=!c.installed?'Nincs telepítve':c.running?'Tunnel fut':c.service_installed?'Szolgáltatás áll':c.token_configured?'Készen áll':'Nincs tunnel';cs.className='remote-status '+(c.running?'ok':(c.service_installed||c.token_configured)?'warn':'neutral');
    $('#cloudflareInstall').classList.toggle('hidden',!!c.installed);$('#cloudflareInstall').disabled=!!c.installed;
    $('#cloudflareStart').disabled=!c.installed||!c.hostname||!c.access_confirmed||(c.running&&!c.external_running);$('#cloudflareStop').disabled=!c.managed_running;$('#cloudflareOpen').disabled=!c.url;
  }catch(e){showError(e)}
}
async function installRemoteComponent(component){
  const btn=component==='tailscale'?$('#tailscaleInstall'):$('#cloudflareInstall');
  if(btn)btn.disabled=true;
  try{
    const r=await apiWrite('/api/remote/install','POST',{component});
    const result=r.result||{};
    if(result.manual_required&&result.url){
      if(confirm((result.message||'Automatikus telepítés nem érhető el.')+'\n\nMegnyissam a hivatalos letöltési oldalt?'))window.open(result.url,'_blank','noopener');
    }else if(!result.ok){
      throw new Error(result.message||'A komponens telepítése nem sikerült.');
    }else{
      addLog('INFO',component==='tailscale'?'Tailscale telepítése kész.':'cloudflared telepítése kész.');
    }
    await loadRemoteStatus();
  }catch(e){showError(e)}finally{if(btn)btn.disabled=false}
}

async function saveRemoteSettings(){
  const btn=$('#saveRemoteSettings');btn.disabled=true;
  try{
    const r=await apiWrite('/api/remote/config','POST',{cloudflare_hostname:$('#cloudflareHostname').value.trim(),cloudflare_access_confirmed:$('#cloudflareAccessConfirmed').checked,cloudflare_token:$('#cloudflareToken').value.trim(),cloudflare_clear_token:$('#cloudflareClearToken').checked});
    $('#cloudflareToken').value='';$('#cloudflareClearToken').checked=false;await loadConfig();state.remote=r.status;await loadRemoteStatus();addLog('INFO','Távoli elérés beállításai mentve.');
  }catch(e){showError(e)}finally{btn.disabled=false}
}
async function setTailscaleAccess(action){
  const a=$('#tailscaleEnable'),b=$('#tailscaleDisable');a.disabled=b.disabled=true;
  try{await apiWrite('/api/remote/tailscale','POST',{action});await loadRemoteStatus();addLog('INFO',action==='enable'?'Tailscale elérés bekapcsolva.':'Tailscale elérés kikapcsolva.')}catch(e){showError(e)}finally{await loadRemoteStatus()}
}
async function setCloudflareTunnel(action){
  const a=$('#cloudflareStart'),b=$('#cloudflareStop');a.disabled=b.disabled=true;
  try{if(action==='start'&&!state.settings.cloudflare_hostname){await saveRemoteSettings()}await apiWrite('/api/remote/cloudflare','POST',{action});await loadRemoteStatus();addLog('INFO',action==='start'?'Cloudflare Tunnel ellenőrizve / elindítva.':'SleepMate által indított Cloudflare Tunnel leállítva.')}catch(e){showError(e)}finally{await loadRemoteStatus()}
}
function openRemoteUrl(url){if(url)window.open(url,'_blank','noopener')}
function openTailscaleQr(){
  const url=state.remote?.tailscale?.url||'';
  if(!url){showError(new Error('A QR-kódhoz előbb működő Tailscale Serve HTTPS cím szükséges.'));return}
  const modal=$('#tailscaleQrModal'),img=$('#tailscaleQrImage'),label=$('#tailscaleQrUrl');
  label.textContent=url;
  img.removeAttribute('src');
  img.src=`/api/remote/tailscale/qr?_=${Date.now()}`;
  img.onerror=()=>{closeTailscaleQr();showError(new Error('Nem sikerült elkészíteni a QR-kódot. Futtasd a függőségtelepítőt, majd próbáld újra.'))};
  modal.classList.remove('hidden');
}
function closeTailscaleQr(){const modal=$('#tailscaleQrModal');if(modal)modal.classList.add('hidden')}
function applyPwaPresentationMode(){
  const yes=standalonePwa();
  document.documentElement.classList.toggle('pwa-standalone',yes);
  document.body.classList.toggle('pwa-standalone',yes);
}
function registerPwa(){
  if('serviceWorker' in navigator){
    const hadController=!!navigator.serviceWorker.controller;
    navigator.serviceWorker.register('/service-worker.js',{updateViaCache:'none'}).then(reg=>reg.update().catch(()=>{})).catch(()=>{});
    navigator.serviceWorker.addEventListener('controllerchange',()=>{
      // iOS standalone PWA already has a native launch screen. Do not force a
      // second full page reload/splash when a new service worker takes control.
      if(hadController&&!standalonePwa()&&!sessionStorage.getItem('sleepmate-sw-reloaded')){sessionStorage.setItem('sleepmate-sw-reloaded','1');location.reload()}
    });
  }
  window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();state.pwaPrompt=e;const b=$('#pwaInstallButton');if(b){b.disabled=false;$('#pwaInstallHint').textContent='A SleepMate telepíthető ezen az eszközön.'}});
  window.addEventListener('appinstalled',()=>{state.pwaPrompt=null;const b=$('#pwaInstallButton');if(b)b.disabled=true;if($('#pwaInstallHint'))$('#pwaInstallHint').textContent='A SleepMate telepítve van ezen az eszközön.';updatePwaStatus()});
  const standalone=window.matchMedia?.('(display-mode: standalone)').matches||window.navigator.standalone===true;
  if(standalone&&$('#pwaInstallHint')){$('#pwaInstallHint').textContent='A SleepMate már alkalmazásnézetben fut.';$('#pwaInstallButton').disabled=true}
  else if(!state.pwaPrompt&&$('#pwaInstallHint')){const ios=/iPhone|iPad|iPod/.test(navigator.userAgent);$('#pwaInstallHint').textContent=ios?'iPhone/iPad: Safari → Megosztás → Főképernyőhöz adás.':'HTTPS-es Tailscale vagy Cloudflare címen a böngésző felajánlja a telepítést.'}
}
async function installPwa(){if(!state.pwaPrompt){const hint=$('#pwaInstallHint');if(hint)hint.textContent='Ha nincs telepítési ablak: Chrome/Edge menü → Alkalmazás telepítése, iPhone-on Safari → Főképernyőhöz adás.';return}state.pwaPrompt.prompt();try{await state.pwaPrompt.userChoice}catch{}state.pwaPrompt=null}
function standalonePwa(){return window.navigator.standalone===true||window.matchMedia?.('(display-mode: standalone)').matches}
function notificationPreference(){try{return localStorage.getItem('sleepmate-notifications-enabled')==='1'}catch{return false}}
function urlBase64ToUint8Array(base64String){const padding='='.repeat((4-base64String.length%4)%4),base64=(base64String+padding).replace(/-/g,'+').replace(/_/g,'/'),raw=atob(base64);return Uint8Array.from([...raw].map(c=>c.charCodeAt(0)))}
function bytesEqual(a,b){if(!a||!b)return false;const x=new Uint8Array(a),y=b instanceof Uint8Array?b:new Uint8Array(b);if(x.length!==y.length)return false;for(let i=0;i<x.length;i++)if(x[i]!==y[i])return false;return true}
function pushSubscriptionKeyMatches(sub,publicKey){try{const existing=sub?.options?.applicationServerKey;if(!existing)return true;return bytesEqual(existing,urlBase64ToUint8Array(publicKey))}catch{return true}}
async function alignPushSubscription(status,sub,{force=false}={}){if(!status?.available||!status.public_key||Notification.permission!=='granted')return sub;const reg=await navigator.serviceWorker.ready;let current=sub||await reg.pushManager.getSubscription();const mismatch=!!current&&!pushSubscriptionKeyMatches(current,status.public_key);if(force||mismatch){if(current){try{await apiWrite('/api/push/unsubscribe','POST',{endpoint:current.endpoint})}catch{}try{await current.unsubscribe()}catch{}}current=null}if(!current)current=await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:urlBase64ToUint8Array(status.public_key)});const prefs=currentPushPreferences();await apiWrite('/api/push/subscribe','POST',{subscription:current.toJSON(),preferences:prefs,origin:location.origin});return current}
function currentPushPreferences(){return{new_night:!!$('#pushPrefNewNight')?.checked,data_update:!!$('#pushPrefDataUpdate')?.checked,warning:!!$('#pushPrefWarning')?.checked,backup_error:!!$('#pushPrefBackupError')?.checked}}
function applyPushPreferences(p={}){if($('#pushPrefNewNight'))$('#pushPrefNewNight').checked=p.new_night!==false;if($('#pushPrefDataUpdate'))$('#pushPrefDataUpdate').checked=!!p.data_update;if($('#pushPrefWarning'))$('#pushPrefWarning').checked=p.warning!==false;if($('#pushPrefBackupError'))$('#pushPrefBackupError').checked=p.backup_error!==false}
async function currentPushSubscription(){if(!('serviceWorker'in navigator)||!('PushManager'in window))return null;try{const reg=await navigator.serviceWorker.ready;return await reg.pushManager.getSubscription()}catch{return null}}
async function loadPushStatus(showErrors=false){
  const badge=$('#pushCapabilityBadge'),stateEl=$('#pushDeviceState'),detail=$('#pushDeviceDetail'),count=$('#pushSubscriptionCount'),txt=$('#pushStatusText');
  try{
    const status=await api('/api/push/status');state.pushStatus=status;
    let sub=await currentPushSubscription();const permission=('Notification'in window)?Notification.permission:'unsupported',secure=window.isSecureContext;
    const canSync=!!(status.available&&secure&&permission==='granted'&&'serviceWorker'in navigator&&'PushManager'in window);
    if(canSync&&sub){try{sub=await alignPushSubscription(status,sub)}catch(e){if(showErrors)throw e}}
    if(count)count.textContent=String(status.subscriptions||0);
    const supported=!!(status.available&&secure&&'serviceWorker'in navigator&&'PushManager'in window&&'Notification'in window);
    if(badge){badge.textContent=supported?'Web Push kész ✓':status.dependency_error?'Függőség hiányzik':'Nem érhető el';badge.classList.toggle('warn',!supported)}
    if(stateEl)stateEl.textContent=sub?'Feliratkozva ✓':permission==='denied'?'Értesítések letiltva':'Nincs feliratkozva';
    if(detail)detail.textContent=!secure?'A Web Push HTTPS-t igényel.':permission==='denied'?'A böngésző/iOS beállításaiban engedélyezd újra.':sub?'Ez a PWA valódi háttér-push értesítéseket fogadhat.':'Kapcsold be ezen az eszközön.';
    if(txt)txt.textContent=status.dependency_error||'A VAPID kulcspárt a SleepMate automatikusan, helyben kezeli. A privát kulcs nem hagyja el a szervert.';
    state.notificationEnabled=!!sub&&permission==='granted';try{localStorage.setItem('sleepmate-notifications-enabled',state.notificationEnabled?'1':'0')}catch{}
    updatePwaStatus();return{status,sub};
  }catch(e){state.pushStatus=null;if(badge){badge.textContent='Nem elérhető';badge.classList.add('warn')}if(txt)txt.textContent=e.message;if(showErrors)showError(e);updatePwaStatus();return{status:null,sub:null}}
}
async function enablePwaNotifications(){
  try{
    if(!window.isSecureContext)throw new Error('A valódi PWA értesítésekhez HTTPS kapcsolat szükséges.');
    if(!('Notification'in window)||!('serviceWorker'in navigator)||!('PushManager'in window))throw new Error('Ezen az eszközön a Web Push nem támogatott.');
    const {status}=await loadPushStatus(true);if(!status?.available||!status.public_key)throw new Error(status?.dependency_error||'A SleepMate Web Push backend még nem áll készen.');
    const permission=await Notification.requestPermission();if(permission!=='granted')throw new Error('Az értesítési engedély nem lett megadva.');
    let sub=await currentPushSubscription();sub=await alignPushSubscription(status,sub);
    const prefs=currentPushPreferences();
    try{localStorage.setItem('sleepmate-push-prefs',JSON.stringify(prefs));localStorage.setItem('sleepmate-notifications-enabled','1')}catch{}
    await loadPushStatus(false);await apiWrite('/api/push/test','POST',{endpoint:sub.endpoint,origin:location.origin});
  }catch(e){showError(e)}
}
async function savePushPreferences(){try{const sub=await currentPushSubscription();if(!sub)throw new Error('Ez az eszköz még nincs feliratkozva push értesítésekre.');const prefs=currentPushPreferences();await apiWrite('/api/push/preferences','POST',{endpoint:sub.endpoint,preferences:prefs});try{localStorage.setItem('sleepmate-push-prefs',JSON.stringify(prefs))}catch{}if($('#pushStatusText'))$('#pushStatusText').textContent='Értesítési beállítások mentve.'}catch(e){showError(e)}}
async function disablePushNotifications(){try{const sub=await currentPushSubscription();if(sub){try{await apiWrite('/api/push/unsubscribe','POST',{endpoint:sub.endpoint})}catch{}await sub.unsubscribe()}state.notificationEnabled=false;try{localStorage.setItem('sleepmate-notifications-enabled','0')}catch{}await loadPushStatus(false)}catch(e){showError(e)}}
async function testPushNotification(){
  const btn=$('#pushTestButton'),txt=$('#pushStatusText');
  try{
    let {status}=await loadPushStatus(true);let sub=await currentPushSubscription();
    if(!sub)throw new Error('Előbb kapcsold be az értesítéseket ezen az eszközön.');
    if(Notification.permission!=='granted')throw new Error('Az értesítési jogosultság nincs engedélyezve ezen az eszközön.');
    if(btn)btn.disabled=true;if(txt)txt.textContent='Próbaértesítés küldése erre az eszközre…';
    sub=await alignPushSubscription(status,sub);
    let r=await apiWrite('/api/push/test','POST',{endpoint:sub.endpoint,origin:location.origin});
    const badJwt=!r.sent&&(r.errors||[]).some(x=>/BadJwtToken|korábbi VAPID kulccsal/i.test(String(x)));
    if(badJwt){
      if(txt)txt.textContent='VAPID kapcsolat javítása és újrafeliratkozás…';
      sub=await alignPushSubscription(status,sub,{force:true});
      r=await apiWrite('/api/push/test','POST',{endpoint:sub.endpoint,origin:location.origin});
    }
    if(!r.sent){const detail=(r.errors||[])[0]||((r.failed||0)?'A push szolgáltató visszautasította a küldést.':'A telefon feliratkozása nincs a SleepMate szerverén.');throw new Error(detail)}
    if(txt)txt.textContent='Próbaértesítés elküldve ✓ • Nézd meg az iPhone értesítési sávját / zárolási képernyőjét.';
    addLog('INFO','PWA próbaértesítés sikeresen elküldve erre az eszközre.');
  }catch(e){if(txt)txt.textContent=`Próbaértesítés sikertelen: ${e.message}`;showError(e)}finally{if(btn)btn.disabled=false}
}

async function notifyAfterRefresh(){await loadPushStatus(false)}
function updatePwaStatus(){
  const installed=standalonePwa(),server=!state.connectionOffline,notif=('Notification'in window)?Notification.permission:'unsupported';
  if($('#pwaStatusInstall'))$('#pwaStatusInstall').textContent=installed?'Telepítve ✓':'Böngészőben';
  if($('#pwaStatusServer')){$('#pwaStatusServer').textContent=server?'Elérhető ✓':'Offline';$('#pwaStatusServer').className=server?'ok':'warn'}
  if($('#pwaStatusOffline'))$('#pwaStatusOffline').textContent='Aktív ✓';
  if($('#pwaStatusNotifications'))$('#pwaStatusNotifications').textContent=state.notificationEnabled?'Web Push aktív ✓':notif==='denied'?'Letiltva':state.pushStatus?.available?'Bekapcsolható':'Nincs beállítva';
  const b=$('#pwaNotificationButton');if(b){b.textContent=state.notificationEnabled?'PWA értesítések beállításai':'PWA értesítések';b.disabled=false}
}
function handleMobileBottomNav(btn){const page=btn.dataset.mobilePage,action=btn.dataset.mobileAction;if(page){navigate(page);return}if(action==='more'){setMobileSidebar(true);return}if(action==='charts'){const day=state.currentDay||state.latestDay||state.days[0];if(!day)return;if(location.hash!==`#dashboard/${day}`){navigate('dashboard',day);setTimeout(()=>document.querySelector('.hero-panel')?.scrollIntoView({behavior:'smooth',block:'start'}),550)}else document.querySelector('.hero-panel')?.scrollIntoView({behavior:'smooth',block:'start'})}}
function updateMobileBottomNav(page){const daily=page==='dashboard'&&location.hash.includes('/');$$('#mobileBottomNav button').forEach(b=>{let active=false;if(b.dataset.mobileAction==='charts')active=daily;else if(b.dataset.mobilePage==='dashboard')active=page==='dashboard'&&!daily;else active=b.dataset.mobilePage===page;b.classList.toggle('active',active)})}
function resetPullRefreshUi(){const el=$('#pullRefreshIndicator');if(!el)return;el.classList.remove('ready','visible','refreshing');el.style.setProperty('--pull','0px');el.querySelector('b').textContent='Húzd le a frissítéshez'}
function setupPullToRefresh(){const scroller=$('.content-shell'),ind=$('#pullRefreshIndicator');if(!scroller||!ind)return;let active=false,startY=0,pull=0;scroller.addEventListener('touchstart',e=>{if(!mobileNavMode()||scroller.scrollTop>1||state.pullRefreshing||e.touches.length!==1)return;if(e.target.closest('canvas,input,select,textarea,button,.table-wrap,.modal'))return;active=true;startY=e.touches[0].clientY;pull=0},{passive:true});scroller.addEventListener('touchmove',e=>{if(!active||e.touches.length!==1)return;const dy=e.touches[0].clientY-startY;if(dy<=0){resetPullRefreshUi();return}pull=Math.min(105,dy*.55);ind.style.setProperty('--pull',`${pull}px`);ind.classList.add('visible');ind.classList.toggle('ready',pull>=68);ind.querySelector('b').textContent=pull>=68?'Engedd el a frissítéshez':'Húzd le a frissítéshez'},{passive:true});scroller.addEventListener('touchend',()=>{if(!active)return;active=false;if(pull>=68){ind.classList.add('refreshing');ind.querySelector('b').textContent='Adatok ellenőrzése…';refreshData()}else resetPullRefreshUi()},{passive:true})}
function setupDailySwipe(){
  const view=$('#dashboardDailyView'),cue=$('#daySwipeCue');if(!view||!cue)return;
  if(cue.parentElement!==document.body)document.body.appendChild(cue);
  let sx=0,sy=0,dx=0,active=false,horizontal=false,targetDay=null;
  const reset=(animate=true)=>{view.style.transition=animate?'transform .26s cubic-bezier(.22,.8,.28,1),opacity .22s ease':'';view.style.transform='';view.style.opacity='';cue.classList.remove('visible','prev','next');if(animate)setTimeout(()=>view.style.transition='',280)};
  const targetFor=delta=>{if(!state.currentDay)return null;const i=state.days.indexOf(state.currentDay),ni=i+delta;return ni>=0&&ni<state.days.length?state.days[ni]:null};
  const isDailyRoute=()=>/^#?dashboard\/[0-9]{8}/.test((location.hash||'').replace(/^#/,''));
  view.addEventListener('touchstart',e=>{
    if(!mobileNavMode()||!isDailyRoute()||view.classList.contains('hidden')||document.body.classList.contains('mobile-nav-open')||e.touches.length!==1)return;
    const t=e.touches[0];
    // The left edge belongs exclusively to the hamburger drawer. A right swipe
    // starting there must never be interpreted as night switching.
    if(t.clientX<=48)return;
    // Charts own their own pinch/pan/cursor gestures; form controls and scrolling
    // regions must never accidentally switch the night either.
    if(e.target.closest('canvas,input,select,textarea,button,.table-wrap,.event-list,.navigator,.ai-chat-messages,.modal,#sidebar'))return;
    sx=t.clientX;sy=t.clientY;dx=0;active=true;horizontal=false;targetDay=null;view.style.transition='none';
  },{passive:true});
  view.addEventListener('touchmove',e=>{if(!active||e.touches.length!==1)return;const t=e.touches[0],x=t.clientX-sx,y=t.clientY-sy;if(!horizontal){if(Math.abs(y)>Math.abs(x)&&Math.abs(y)>9){active=false;reset(false);return}if(Math.abs(x)<10)return;horizontal=true}dx=x;targetDay=targetFor(dx<0?-1:1);const limited=Math.sign(dx)*Math.min(Math.abs(dx),Math.max(145,innerWidth*.42));view.style.transform=`translate3d(${limited}px,0,0) rotate(${limited/innerWidth*5}deg)`;view.style.opacity=String(Math.max(.68,1-Math.abs(limited)/innerWidth*.42));cue.classList.toggle('prev',dx>0);cue.classList.toggle('next',dx<0);cue.classList.add('visible');$('#daySwipeCueIcon').textContent=dx>0?'‹':'›';$('#daySwipeCueLabel').textContent=dx>0?'Korábbi éjszaka':'Újabb éjszaka';$('#daySwipeCueDate').textContent=targetDay?dayCodeToIso(targetDay):'Nincs több nap'},{passive:true});
  view.addEventListener('touchend',()=>{if(!active&&!horizontal){reset();return}active=false;const threshold=Math.min(125,innerWidth*.28),go=horizontal&&Math.abs(dx)>=threshold&&targetDay;if(!go){reset();return}const out=Math.sign(dx)*(innerWidth+80);view.style.transition='transform .19s ease-in,opacity .17s ease';view.style.transform=`translate3d(${out}px,0,0) rotate(${Math.sign(dx)*7}deg)`;view.style.opacity='0';cue.classList.remove('visible');const day=targetDay;setTimeout(()=>{view.style.transition='none';view.style.transform=`translate3d(${-Math.sign(dx)*45}px,0,0)`;view.style.opacity='0';navigate('dashboard',day);setTimeout(()=>{view.style.transition='transform .24s cubic-bezier(.22,.8,.28,1),opacity .2s';view.style.transform='';view.style.opacity='';setTimeout(()=>view.style.transition='',260)},30)},190)},{passive:true});
  view.addEventListener('touchcancel',()=>{active=false;horizontal=false;reset()},{passive:true});
}

function setupMobilePwaFeatures(){
  applyPwaPresentationMode();
  try{state.lastApiOnlineAt=localStorage.getItem('sleepmate-last-online-at')||null;const saved=JSON.parse(localStorage.getItem('sleepmate-push-prefs')||'null');if(saved)applyPushPreferences(saved)}catch{}
  updatePwaStatus();setupPullToRefresh();setupDailySwipe();loadPushStatus(false);warmOfflineRecentDays();
  window.addEventListener('online',()=>{setConnectionState(false);route();loadPushStatus(false);warmOfflineRecentDays()});
  window.addEventListener('offline',()=>setConnectionState(true));
  const mq=window.matchMedia?.('(display-mode: standalone)');mq?.addEventListener?.('change',applyPwaPresentationMode);
  $('.content-shell')?.addEventListener('scroll',()=>{clearTrendHover();if(!$('#dashboardDailyView')?.classList.contains('hidden')){state.hoverTime=null;scheduleOverlayRender()}},{passive:true});
  if(!navigator.onLine)setConnectionState(true);
}
async function warmOfflineRecentDays(){
  if(!navigator.onLine||!('serviceWorker'in navigator))return;try{await navigator.serviceWorker.ready}catch{return}
  const urls=['/api/version','/api/config','/api/days','/api/patient','/api/system/status',`/api/dashboard/overview?period=${encodeURIComponent(state.dashboardPeriod||'30')}`];
  for(const day of state.days.slice(0,3)){urls.push(`/api/day/${day}`);urls.push(`/api/day/${day}/stats`)}
  for(const url of urls){try{const sep=url.includes('?')?'&':'?';await fetch(`${url}${sep}_=${Date.now()}`,{cache:'no-store'})}catch{}}
}
function dailyO2ShareValues(){const s=state.o2Daily?.available?state.o2Daily.summary:null;if(!s)return null;const spo2=s.spo2_median??s.spo2_average,hr=s.heart_rate_median??s.heart_rate_average;if(spo2==null&&hr==null)return null;return{spo2,hr,min:s.spo2_minimum,t90:Number(s.t90_seconds)||0}}
function formatO2ShareDuration(seconds){const mins=Math.round((Number(seconds)||0)/60);return mins>=60?`${Math.floor(mins/60)} ó ${String(mins%60).padStart(2,'0')} p`:`${mins} perc`}
async function createDailyShareCard(){const s=state.summary;if(!s)throw new Error('Nincs megosztható napi adat.');const o2=dailyO2ShareValues(),c=document.createElement('canvas');c.width=1080;c.height=o2?1580:1350;const x=c.getContext('2d');x.fillStyle='#08111f';x.fillRect(0,0,c.width,c.height);x.fillStyle='#edf4fb';x.font='700 70px system-ui';x.fillText('SleepMate',70,115);x.fillStyle='#95aabe';x.font='38px system-ui';x.fillText(formatDayCode(s.day),70,175);x.fillStyle='#152434';x.fillRect(60,230,960,o2?1130:900);const stats=[['Használati idő',formatUsageShort(s.usage),''],['AHI',Number(s.ahi||0).toFixed(2),'esemény/óra'],['Szivárgás 95%',String($('#dailyLeakP95')?.textContent||'–'),'L/perc'],['Nyomás 95%',String($('#dailyPressureP95')?.textContent||'–'),'cmH₂O'],['Események',String($('#eventCount')?.textContent||'–'),`OA ${s.counts?.OA||0} • CA ${s.counts?.CA||0} • H ${s.counts?.H||0} • RERA ${s.counts?.RERA||0}`]];if(o2){stats.push(['SpO₂',o2.spo2==null?'–':`${Number(o2.spo2).toLocaleString('hu-HU',{maximumFractionDigits:1})}%`,`${o2.min==null?'':`minimum ${Number(o2.min).toLocaleString('hu-HU',{maximumFractionDigits:1})}% • `}T90 ${formatO2ShareDuration(o2.t90)}`],['Pulzus',o2.hr==null?'–':Number(o2.hr).toLocaleString('hu-HU',{maximumFractionDigits:1}),'ütés/perc • O2Ring']);}const spacing=o2?145:160;stats.forEach((a,i)=>{const y=315+i*spacing;x.fillStyle='#91a8bd';x.font='32px system-ui';x.fillText(a[0],105,y);x.fillStyle='#f4f8fb';x.font='700 64px system-ui';x.fillText(a[1],105,y+72);if(a[2]){x.fillStyle='#91a8bd';x.font='27px system-ui';x.fillText(a[2],430,y+65)}});x.fillStyle='#91a8bd';x.font='26px system-ui';x.fillText('PAP-terápiás összefoglaló • SleepMate',70,c.height-110);return await new Promise((res,rej)=>c.toBlob(b=>b?res(b):rej(new Error('A megosztási kép nem készíthető el.')),'image/png',.94))}
async function shareCurrentDay(){if(!state.summary){showError(new Error('Nincs megosztható napi adat.'));return}const s=state.summary;try{if(window.SleepMateO2Ring?.getDailySummary){state.o2DailyLoading=true;state.o2Daily=await window.SleepMateO2Ring.getDailySummary(s.day);state.o2DailyLoading=false}const o2=dailyO2ShareValues(),o2Text=o2?`\nSpO₂: ${o2.spo2==null?'–':Number(o2.spo2).toLocaleString('hu-HU',{maximumFractionDigits:1})+'%'} (minimum: ${o2.min==null?'–':Number(o2.min).toLocaleString('hu-HU',{maximumFractionDigits:1})+'%'})\nPulzus: ${o2.hr==null?'–':Number(o2.hr).toLocaleString('hu-HU',{maximumFractionDigits:1})+' /perc'}\nT90: ${formatO2ShareDuration(o2.t90)}`:'',text=`SleepMate • ${formatDayCode(s.day)}\nHasználat: ${formatUsageShort(s.usage)}\nAHI: ${Number(s.ahi||0).toFixed(2)} /óra\nSzivárgás P95: ${$('#dailyLeakP95')?.textContent||'–'} L/perc\nNyomás P95: ${$('#dailyPressureP95')?.textContent||'–'} cmH₂O\nEsemények: OA ${s.counts?.OA||0}, CA ${s.counts?.CA||0}, H ${s.counts?.H||0}, RERA ${s.counts?.RERA||0}${o2Text}`;if(navigator.share){const blob=await createDailyShareCard(),file=new File([blob],`SleepMate_${s.day}.png`,{type:'image/png'});if(!navigator.canShare||navigator.canShare({files:[file]})){await navigator.share({title:`SleepMate – ${formatDayCode(s.day)}`,text,files:[file]});return}await navigator.share({title:`SleepMate – ${formatDayCode(s.day)}`,text});return}await navigator.clipboard.writeText(text);addLog('INFO','Napi összefoglaló a vágólapra másolva.')}catch(e){state.o2DailyLoading=false;if(e?.name!=='AbortError')showError(e)}}


async function saveDisplaySettings(){
  const btn=$('#saveDisplaySettings'),status=$('#displaySettingsStatus');btn.disabled=true;status.textContent='Mentés…';
  try{
    const r=await apiWrite('/api/settings','POST',{show_spo2:$('#settingShowSpO2').checked,show_hr:$('#settingShowHR').checked});
    state.settings={...state.settings,show_spo2:!!r.show_spo2,show_hr:!!r.show_hr};applyOximetryVisibility();if(location.hash.startsWith('#dashboard')){if(state.currentDay&&location.hash.includes('/'))await loadDashboard(state.currentDay);else await loadDashboardOverview(state.dashboardPeriod)}flashInlineStatus(status,(state.settings.show_spo2||state.settings.show_hr)?'Mentve. A bekapcsolt kártyák adat nélkül is láthatók.':'Mentve.');addLog('INFO','Oximetria megjelenítési beállítások mentve.');
  }catch(e){showError(e);flashInlineStatus(status,'Hiba.',6000)}finally{btn.disabled=false}
}
function applyOximetryVisibility(summary=state.summary){
  const showSpo2=!!state.settings.show_spo2,showHr=!!state.settings.show_hr;
  $('#spo2Metric')?.classList.toggle('hidden',!showSpo2);
  $('#hrMetric')?.classList.toggle('hidden',!showHr);
  $$('.col-spo2').forEach(x=>x.classList.toggle('hidden',!showSpo2));
  $$('.col-hr').forEach(x=>x.classList.toggle('hidden',!showHr));
  const daily=state.o2Daily?.summary||{},spo2Value=daily.spo2_median??daily.spo2_average??summary?.oximetry?.spo2_median,hrValue=daily.heart_rate_median??daily.heart_rate_average??summary?.oximetry?.pulse_median,loading=state.o2DailyLoading===true;
  if($('#spo2')){$('#spo2').textContent=spo2Value!=null?`${Number(spo2Value).toLocaleString('hu-HU',{maximumFractionDigits:1})}%`:loading?'Betöltés…':'Nincs adat';$('#spo2').classList.toggle('no-data',spo2Value==null&&!loading)}
  if($('#hr')){$('#hr').textContent=hrValue!=null?`${Number(hrValue).toLocaleString('hu-HU',{maximumFractionDigits:1})}`:loading?'Betöltés…':'Nincs adat';$('#hr').classList.toggle('no-data',hrValue==null&&!loading)}
}



function aiProviderMeta(provider=state.ai.provider){
  const cfg=state.ai.config?.providers?.[provider]||{};
  return {provider,name:cfg.display_name||(provider==='gemini'?'Luna':'Milo'),label:cfg.provider_label||(provider==='gemini'?'Google Gemini':'Groq'),configured:!!cfg.configured,model:cfg.model||''};
}
function aiAvatarInner(provider){return provider==='gemini'?'<img src="/assets/luna-avatar.svg" alt="Luna">':'<img src="/assets/milo-avatar.svg" alt="Milo">'}
function setAIAvatar(el,provider){if(!el)return;el.classList.toggle('gemini-avatar',provider==='gemini');el.classList.toggle('groq-avatar',provider==='groq');el.innerHTML=aiAvatarInner(provider)}
function selectAIProvider(provider){if(!['gemini','groq'].includes(provider))return;state.ai.provider=provider;$$('.ai-provider-card').forEach(x=>x.classList.toggle('selected',x.dataset.aiProvider===provider));updateAIAnalysisLocks();updateAIChatCounter()}
async function loadAIPage(){
  try{await Promise.all([loadAIStatus(),loadAIConfig(),loadDayRows(),loadAIHistory()]);populateAIMonths();presetComparisonDates();selectAIProvider(state.ai.provider)}catch(e){showError(e)}
}
async function loadAIStatus(){
  const r=await api('/api/ai/status');state.ai.status=r;state.ai.config={providers:r.providers,protection:r.protection,encrypted_at_rest:r.encrypted_at_rest};updateAIProviderUi();updateAIAnalysisLocks();return r
}
async function loadAIConfig(){
  try{
    const r=await api('/api/ai/config');state.ai.config=r;updateAIProviderUi();const g=r.providers?.gemini||{},q=r.providers?.groq||{};
    if($('#settingGeminiName'))$('#settingGeminiName').value=g.display_name||'Luna';if($('#settingGroqName'))$('#settingGroqName').value=q.display_name||'Milo';
    if($('#settingGeminiModel'))$('#settingGeminiModel').value=g.model||'gemini-3.6-flash';if($('#settingGroqModel'))$('#settingGroqModel').value=q.model||'openai/gpt-oss-120b';
    if($('#settingGeminiKeyHint'))$('#settingGeminiKeyHint').textContent=g.configured?`Aktív kulcs: ${g.key_hint||'••••'} • SleepMate titkosított beállítás`:'Nincs mentett kulcs';
    if($('#settingGroqKeyHint'))$('#settingGroqKeyHint').textContent=q.configured?`Aktív kulcs: ${q.key_hint||'••••'} • SleepMate titkosított beállítás`:'Nincs mentett kulcs';
    $('#geminiConfiguredBadge')?.classList.toggle('configured',!!g.configured);if($('#geminiConfiguredBadge'))$('#geminiConfiguredBadge').textContent=g.configured?'Élő API kész':'Nincs API-kulcs';
    $('#groqConfiguredBadge')?.classList.toggle('configured',!!q.configured);if($('#groqConfiguredBadge'))$('#groqConfiguredBadge').textContent=q.configured?'Élő API kész':'Nincs API-kulcs';return r
  }catch(e){addLog('WARN',`AI beállítások nem olvashatók: ${e.message}`)}
}
function updateAIProviderUi(){
  const cfg=state.ai.config?.providers||state.ai.status?.providers||{},gem=cfg.gemini||{},groq=cfg.groq||{};
  if($('#aiGeminiName'))$('#aiGeminiName').textContent=gem.display_name||'Luna';if($('#aiGroqName'))$('#aiGroqName').textContent=groq.display_name||'Milo';
  if($('#aiGeminiStatus'))$('#aiGeminiStatus').textContent=gem.configured?`${gem.model||'gemini-3.6-flash'} • élő API`:'Nincs API-kulcs';
  if($('#aiGroqStatus'))$('#aiGroqStatus').textContent=groq.configured?`${groq.model||'openai/gpt-oss-120b'} • élő API`:'Nincs API-kulcs';
  const usage=state.ai.status?.chat||{};if($('#aiGeminiRemaining'))$('#aiGeminiRemaining').textContent=usage.gemini?.remaining??10;if($('#aiGroqRemaining'))$('#aiGroqRemaining').textContent=usage.groq?.remaining??10;
  if($('#aiDatasetBadge'))$('#aiDatasetBadge').textContent=state.ai.status?.dataset_signature?`Adatverzió ${state.ai.status.dataset_signature.slice(0,8)}`:'Nincs adatverzió'
}
function populateAIMonths(){const sel=$('#aiMonthSelect');if(!sel)return;const months=[...new Set((state.dayRows||[]).map(r=>String(r.date||'').slice(0,7)).filter(Boolean))].sort().reverse();sel.innerHTML=months.length?months.map(m=>{const [y,mo]=m.split('-');const label=new Intl.DateTimeFormat('hu-HU',{year:'numeric',month:'long'}).format(new Date(+y,+mo-1,1));return`<option value="${m}">${label}</option>`}).join(''):'<option value="">Nincs terápiás hónap</option>';const mobile=$('#aiMobileMonthSelect');if(mobile){mobile.innerHTML=sel.innerHTML;mobile.value=sel.value}}
const AI_MOBILE_ANALYSIS_LABELS={night:'Előző alvás',week:'Előző hét',month:'Hónap',full_period:'Teljes terápiás időszak',comparison:'Időszakok összehasonlítása'};
function openAIAnalysisSheet(){
  const sheet=$('#aiAnalysisSheet');if(!sheet)return;
  if($('#aiMobileMonthSelect')&&$('#aiMonthSelect')){$('#aiMobileMonthSelect').innerHTML=$('#aiMonthSelect').innerHTML;$('#aiMobileMonthSelect').value=$('#aiMonthSelect').value}
  for(const [mobile,desktop] of [['aiMobileCompareAStart','aiCompareAStart'],['aiMobileCompareAEnd','aiCompareAEnd'],['aiMobileCompareBStart','aiCompareBStart'],['aiMobileCompareBEnd','aiCompareBEnd']])if($(mobile)&&$(desktop))$(mobile).value=$(desktop).value;
  $('#aiMobileMonthControls')?.classList.add('hidden');$('#aiMobileComparisonControls')?.classList.add('hidden');$$('#aiAnalysisSheet [data-ai-mobile-choice]').forEach(b=>b.classList.remove('selected'));
  sheet.classList.remove('hidden');sheet.setAttribute('aria-hidden','false');document.body.classList.add('ai-sheet-open');
}
function closeAIAnalysisSheet(){const sheet=$('#aiAnalysisSheet');if(!sheet)return;sheet.classList.add('hidden');sheet.setAttribute('aria-hidden','true');document.body.classList.remove('ai-sheet-open')}
function setAIMobilePickerLabel(type){const el=$('#aiAnalysisPickerLabel');if(el)el.textContent=AI_MOBILE_ANALYSIS_LABELS[type]||'Válassz kiértékelést'}
function chooseMobileAIAnalysis(type){
  $$('[data-ai-mobile-choice]').forEach(b=>b.classList.toggle('selected',b.dataset.aiMobileChoice===type));setAIMobilePickerLabel(type);
  $('#aiMobileMonthControls')?.classList.toggle('hidden',type!=='month');$('#aiMobileComparisonControls')?.classList.toggle('hidden',type!=='comparison');
  if(type==='month'||type==='comparison')return;
  closeAIAnalysisSheet();const btn=document.querySelector(`[data-ai-analysis="${type}"]`);if(btn)startAIAnalysisWithFeatures(type,btn);
}
function runMobileAIMonth(){const mobile=$('#aiMobileMonthSelect'),desktop=$('#aiMonthSelect');if(desktop&&mobile)desktop.value=mobile.value;updateAIAnalysisLocks();closeAIAnalysisSheet();const btn=document.querySelector('[data-ai-analysis="month"]');if(btn)startAIAnalysisWithFeatures('month',btn)}
function runMobileAIComparison(){for(const [mobile,desktop] of [['aiMobileCompareAStart','aiCompareAStart'],['aiMobileCompareAEnd','aiCompareAEnd'],['aiMobileCompareBStart','aiCompareBStart'],['aiMobileCompareBEnd','aiCompareBEnd']])if($(mobile)&&$(desktop))$(desktop).value=$(mobile).value;updateAIAnalysisLocks();closeAIAnalysisSheet();const btn=document.querySelector('[data-ai-analysis="comparison"]');if(btn)startAIAnalysisWithFeatures('comparison',btn)}

function currentAIAnalysisKey(type){if(type==='month')return`${type}:${$('#aiMonthSelect')?.value||''}`;if(type==='comparison')return`comparison:${$('#aiCompareAStart')?.value||''}:${$('#aiCompareAEnd')?.value||''}:${$('#aiCompareBStart')?.value||''}:${$('#aiCompareBEnd')?.value||''}`;return type}
function updateAIAnalysisLocks(){const rows=state.ai.status?.current_dataset_analyses||{},features=aiFeaturePreferences(),modeCount=availableAIAnalysisModes().length;$$('[data-ai-analysis]').forEach(btn=>{const key=currentAIAnalysisKey(btn.dataset.aiAnalysis),lock=features.assistantsVisible?rows[key]:null;btn.classList.toggle('locked',!!lock);btn.classList.toggle('has-ai-mode-menu',modeCount>1);btn.dataset.savedAnalysisId=lock?.analysis_id||'';btn.textContent='Elemzés indítása';btn.setAttribute('aria-haspopup',modeCount>1?'menu':'false');btn.setAttribute('aria-expanded','false');btn.title=lock?'Ehhez az adatverzióhoz mentett kiértékelés is tartozik; a belső AI mód ezt nyitja meg.':'Válassz a bekapcsolt elemzési módok közül.'})}
function toggleSecretInput(btn){const input=document.getElementById(btn.dataset.secretTarget);if(!input)return;input.type=input.type==='password'?'text':'password';btn.textContent=input.type==='password'?'Mutat':'Elrejt'}
function aiKeySourceLabel(v){return v==='encrypted_settings'?'SleepMate titkosított beállítás':'nincs kulcs'}
async function testAIProvider(provider,button){
  const status=$(provider==='gemini'?'#aiGeminiTestStatus':'#aiGroqTestStatus');button.disabled=true;status.textContent='Tesztelés…';status.className='ai-test-status';
  try{const r=await apiWrite('/api/ai/test','POST',{provider});status.textContent=`✓ Siker • ${r.model} • ${r.response_ms} ms • kulcs ${r.key_fingerprint}`;status.className='ai-test-status ok';await Promise.all([loadAIStatus(),loadAiDiagnosticLog()]);}
  catch(e){status.textContent=`✕ ${e.message}`;status.className='ai-test-status bad';await loadAiDiagnosticLog();}
  finally{button.disabled=false}
}
function renderAiLogDetails(details){
  const d=details||{};
  const preferred=['event','request_id','provider','provider_label','display_name','model','operation','analysis_type','analysis_key','analysis_id','dataset_signature','key_source','key_hint','key_fingerprint','endpoint','json_mode','reasoning_effort','timeout_s','http_status','transient','provider_error_type','provider_error_code','provider_error_detail','chunks','response_chars','response_ms','fallback_used','prompt_version','system_prompt_chars','user_prompt_chars','safe_payload_bytes','question_chars','history_messages','remaining_before','remaining_after','error_type','error','response_preview'];
  const keys=[...preferred.filter(k=>d[k]!==undefined&&d[k]!==null&&d[k]!==''),...Object.keys(d).filter(k=>!preferred.includes(k)&&d[k]!==undefined&&d[k]!==null&&d[k]!=='')];
  return keys.map(k=>{let v=d[k];if(typeof v==='object')v=JSON.stringify(v);if(k==='key_source')v=aiKeySourceLabel(v);return `<div><b>${escapeHtml(k)}</b><span>${escapeHtml(String(v))}</span></div>`}).join('');
}

function formatPersistentLogRow(x){
  const details=x.details&&Object.keys(x.details).length?`\n  részletek: ${JSON.stringify(x.details,null,2).replace(/\n/g,'\n  ')}`:'';
  return `[${x.time||''}] [${x.level||'INFO'}] [${x.kind||'system'}] ${x.message||''}${details}`;
}
function formatClientLogRow(x){
  const t=x.time instanceof Date?x.time.toISOString():String(x.time||'');
  return `[${t}] [${x.type||'INFO'}] [browser] ${x.msg||''}`;
}
async function buildFullLogText(kind='full'){
  const h=await api('/api/logs/history?limit=100000');
  const persistent=(h.rows||[]);
  const header=`SleepMate teljes ${kind==='ai'?'AI diagnosztikai ':''}napló\nExport ideje: ${new Date().toISOString()}\n`;
  if(kind==='ai'){
    const ai=persistent.filter(x=>x.kind==='ai').slice().reverse();
    return header+'\n'+(ai.length?ai.map(formatPersistentLogRow).join('\n\n'):'Nincs AI naplóbejegyzés.');
  }
  const all=persistent.slice().reverse();
  const client=(state.logs||[]).filter(x=>x.source==='client').slice().reverse();
  return header+'\n--- TARTÓS HÁTTÉRNAPLÓ ---\n'+(all.length?all.map(formatPersistentLogRow).join('\n\n'):'Nincs tartós naplóbejegyzés.')+'\n\n--- AKTUÁLIS BÖNGÉSZŐ-MUNKAMENET ---\n'+(client.length?client.map(formatClientLogRow).join('\n'):'Nincs külön kliensoldali naplóbejegyzés.');
}
async function copyTextRobust(text){
  if(navigator.clipboard?.writeText){try{await navigator.clipboard.writeText(text);return}catch{}}
  const ta=document.createElement('textarea');ta.value=text;ta.style.position='fixed';ta.style.opacity='0';document.body.appendChild(ta);ta.select();document.execCommand('copy');ta.remove();
}
async function copyLogToClipboard(kind){
  try{const text=await buildFullLogText(kind);await copyTextRobust(text);addLog('INFO',`${kind==='ai'?'AI diagnosztikai':'Teljes program'} napló vágólapra másolva.`);}
  catch(e){showError(e)}
}
function downloadTextFile(text,name){const blob=new Blob([text],{type:'text/plain;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)}
async function exportLogTxt(kind){
  try{const text=await buildFullLogText(kind),stamp=new Date().toISOString().replace(/[:.]/g,'-');downloadTextFile(text,`SleepMate_${kind==='ai'?'AI_naplo':'teljes_naplo'}_${stamp}.txt`);addLog('INFO',`${kind==='ai'?'AI diagnosztikai':'Teljes program'} napló exportálva.`);}
  catch(e){showError(e)}
}

async function loadAiDiagnosticLog(){
  const box=$('#aiDiagnosticLog'),providerBox=$('#aiProviderDiagnostic');if(!box)return;
  try{
    const [h,cfg]=await Promise.all([api('/api/logs/history?limit=300'),api('/api/ai/config')]);
    const ps=cfg.providers||{};
    providerBox.innerHTML=['gemini','groq'].map(p=>{const x=ps[p]||{};return `<article class="ai-provider-diag ${p}"><strong>${p==='gemini'?'Luna / Gemini':'Milo / Groq'}</strong><span>Modell: <b>${escapeHtml(x.model||'—')}</b></span><span>Kulcs forrása: <b>${escapeHtml(aiKeySourceLabel(x.key_source))}</b></span><span>Maszkolt kulcs: <code>${escapeHtml(x.key_hint||'—')}</code></span><span>Fingerprint: <code>${escapeHtml(x.key_fingerprint||'—')}</code></span></article>`}).join('');
    const rows=(h.rows||[]).filter(x=>x.kind==='ai');
    box.innerHTML=rows.length?rows.map(x=>`<details class="ai-log-row ${String(x.level).toLowerCase()}"><summary><time>${new Date(x.time).toLocaleString('hu-HU')}</time><b>${escapeHtml(x.level)}</b><span>${escapeHtml(x.message)}</span><em>${escapeHtml(x.details?.provider||x.details?.selected_provider||'AI')} • ${escapeHtml(x.details?.model||x.details?.operation||x.details?.event||'')}</em></summary><div class="ai-log-details">${renderAiLogDetails(x.details)}</div></details>`).join(''):'<div class="empty-state">Még nincs AI naplóbejegyzés.</div>';
  }catch(e){box.innerHTML=`<div class="empty-state">AI napló nem tölthető be: ${escapeHtml(e.message)}</div>`}
}
async function saveAISettings(){const btn=$('#saveAISettings'),status=$('#aiSettingsStatus');btn.disabled=true;status.textContent='Titkosított mentés…';try{const payload={gemini_display_name:$('#settingGeminiName').value.trim()||'Luna',groq_display_name:$('#settingGroqName').value.trim()||'Milo',gemini_model:$('#settingGeminiModel').value.trim()||'gemini-3.6-flash',groq_model:$('#settingGroqModel').value.trim()||'openai/gpt-oss-120b',gemini_api_key:$('#settingGeminiKey').value.trim(),groq_api_key:$('#settingGroqKey').value.trim(),gemini_clear_key:$('#settingGeminiClear').checked,groq_clear_key:$('#settingGroqClear').checked};await apiWrite('/api/ai/config','POST',payload);$('#settingGeminiKey').value='';$('#settingGroqKey').value='';$('#settingGeminiClear').checked=false;$('#settingGroqClear').checked=false;await Promise.all([loadAIConfig(),loadAIStatus()]);flashInlineStatus(status,'Mentve és titkosítva.');addLog('INFO','AI szolgáltatói beállítások mentve.')}catch(e){showError(e);flashInlineStatus(status,'Hiba.',7000)}finally{btn.disabled=false}}
async function readNdjson(url,payload,onEvent){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),cache:'no-store'});if(!r.ok){let msg=`HTTP ${r.status}`;try{const j=await r.json();msg=j.error||msg}catch{}throw new Error(msg)}if(!r.body)throw new Error('A böngésző nem támogatja a streamelt választ.');const reader=r.body.getReader(),dec=new TextDecoder(),parts=[];let buf='';for(;;){const {done,value}=await reader.read();if(done)break;buf+=dec.decode(value,{stream:true});const lines=buf.split('\n');buf=lines.pop()||'';for(const line of lines){if(!line.trim())continue;let ev;try{ev=JSON.parse(line)}catch{continue}parts.push(ev);await onEvent(ev)}}if(buf.trim()){try{await onEvent(JSON.parse(buf))}catch{}}return parts}
function extractPartialJsonString(text,key){const mark=`"${key}"`,i=text.indexOf(mark);if(i<0)return'';let p=text.indexOf(':',i+mark.length);if(p<0)return'';p++;while(/\s/.test(text[p]||''))p++;if(text[p]!=='"')return'';p++;let out='',esc=false;for(;p<text.length;p++){const c=text[p];if(esc){out+=c==='n'?'\n':c==='t'?'\t':c==='r'?'\r':c;esc=false;continue}if(c==='\\'){esc=true;continue}if(c==='"')break;out+=c}return out}
async function loadAIHistory(){try{const r=await api('/api/ai/history?limit=100');state.ai.history=r.rows||[];renderAIHistory()}catch(e){addLog('WARN',`AI előzmények nem tölthetők be: ${e.message}`)}}
function analysisTypeLabel(key=''){if(key.startsWith('night'))return'Előző alvás';if(key.startsWith('week'))return'Előző hét';if(key.startsWith('month'))return'Havi kiértékelés';if(key.startsWith('comparison'))return'Időszakok összehasonlítása';return'Teljes terápiás időszak'}
function renderAIHistory(){const box=$('#aiHistoryList');if(!box)return;const features=aiFeaturePreferences(),rows=(state.ai.history||[]).filter(r=>r.provider==='groq'?features.miloVisible:features.lunaVisible);box.innerHTML=rows.length?rows.map(r=>{const m=aiProviderMeta(r.provider);const p=r.period||{},title=friendlyAiTitle(r.title||analysisTypeLabel(r.analysis_key),r.status);return`<button class="ai-history-card" type="button" data-ai-history-id="${escapeHtml(r.id)}" data-ai-provider="${escapeHtml(r.provider||'gemini')}"><span class="ai-avatar mini ${r.provider==='gemini'?'gemini-avatar':'groq-avatar'}">${aiAvatarInner(r.provider)}</span><span class="ai-history-copy"><b>${escapeHtml(title)}</b><small>${escapeHtml(m.name)} • ${escapeHtml(analysisTypeLabel(r.analysis_key))} • ${escapeHtml(formatAiDate(p.start))} – ${escapeHtml(formatAiDate(p.end))}</small><em>${escapeHtml((r.summary||'').slice(0,180))}${(r.summary||'').length>180?'…':''}</em></span><span class="ai-history-meta">${r.message_count||0} chat<br>${humanDateTime(r.created_at)}</span></button>`}).join(''):'<div class="empty-state">A bekapcsolt AI-asszisztenshez még nincs mentett kiértékelés.</div>';$$('[data-ai-history-id]').forEach(b=>b.onclick=()=>openAIHistory(b.dataset.aiHistoryId))}
function formatAiDate(v){if(!v)return'—';const s=String(v);const m=s.match(/^(\d{4})-(\d{2})-(\d{2})/);if(m)return`${m[1]}.${m[2]}.${m[3]}.`;return s}
function humanDateTime(v){if(!v)return'—';try{const d=new Date(v),y=d.getFullYear(),m=String(d.getMonth()+1).padStart(2,'0'),day=String(d.getDate()).padStart(2,'0'),h=String(d.getHours()).padStart(2,'0'),mi=String(d.getMinutes()).padStart(2,'0');return`${y}.${m}.${day}. ${h}:${mi}`}catch{return v}}
function friendlyAiTitle(title,status='acceptable'){const t=String(title||'').trim(),low=t.toLowerCase();if(t&&!['therapy','performance','summary','analysis','assessment','treatment','effectiveness','for 20','cpap therapy','pap therapy'].some(x=>low.includes(x)))return t;const map={very_good:'A terápia stabil és eredményes',good:'A terápia összességében eredményes',acceptable:'A terápia megfelelő, néhány érték figyelmet érdemel',attention:'Több terápiás érték is figyelmet érdemel',unfavorable:'A terápiás eredmények felülvizsgálatra érdemesek'};return map[status]||'A terápia aktuális összképe'}
async function openAIHistory(id){try{const row=await api(`/api/ai/history/${encodeURIComponent(id)}`);state.ai.analysisId=id;state.ai.result=row.result;state.ai.provider=row.provider||row.result?.provider||'gemini';selectAIProvider(state.ai.provider);renderAIResult(row.result,false);renderAIChatHistory(row);$('#aiResultArea').classList.remove('hidden');$('#aiResultArea').scrollIntoView({behavior:'smooth',block:'start'});updateAIChatCounter()}catch(e){showError(e)}}
function aiFeaturePreferences(){const p=window.SleepMateV530?.preferences?.()||{},lunaVisible=p.ai_luna_visible!==false,miloVisible=p.ai_milo_visible!==false;return{lunaVisible,miloVisible,assistantsVisible:lunaVisible||miloVisible,promptingEnabled:p.ai_prompting_enabled===true}}
function applyAiFeatureAvailability(){const f=aiFeaturePreferences();if(state.ai.provider==='gemini'&&!f.lunaVisible&&f.miloVisible)selectAIProvider('groq');else if(state.ai.provider==='groq'&&!f.miloVisible&&f.lunaVisible)selectAIProvider('gemini');const resultProvider=state.ai.result?.provider;if((resultProvider==='gemini'&&!f.lunaVisible)||(resultProvider==='groq'&&!f.miloVisible))$('#aiResultArea')?.classList.add('hidden');renderAIHistory();updateAIAnalysisLocks()}
function aiSelection(type){const month=type==='month'?$('#aiMonthSelect')?.value||'':'',comparison=type==='comparison'?{a_start:$('#aiCompareAStart')?.value||'',a_end:$('#aiCompareAEnd')?.value||'',b_start:$('#aiCompareBStart')?.value||'',b_end:$('#aiCompareBEnd')?.value||''}:null;if(type==='comparison'&&!Object.values(comparison).every(Boolean))throw new Error('Add meg mindkét összehasonlítási időszakot.');return{provider:state.ai.provider,analysis_type:type,month,comparison}}
function closeAIPromptModal(){$('#aiPromptModal')?.classList.add('hidden');document.body.classList.remove('ai-prompt-open')}
function showAIPromptModal(){const modal=$('#aiPromptModal');if(!modal)return;modal.classList.remove('hidden');document.body.classList.add('ai-prompt-open');$('#aiPromptContent').textContent='A teljes prompt összeállítása…';$('#aiPromptStatus').textContent='A SleepMate a kiértékelés kanonikus adatcsomagját készíti elő.';$('#aiPromptCopy').disabled=true;$('#aiPromptDownload').disabled=true}
async function requestAIPrompt(selection){showAIPromptModal();try{const r=await apiWrite('/api/ai/prompt','POST',selection);state.ai.exportPrompt=r;$('#aiPromptContent').textContent=r.prompt||'';const p=r.period||{};$('#aiPromptMeta').textContent=`${analysisTypeLabel(r.analysis_key||r.analysis_type)} • ${formatAiDate(p.period_start)} – ${formatAiDate(p.period_end)} • prompt v${r.prompt_version}`;$('#aiPromptStatus').textContent=r.prompt?'A teljes prompt elkészült és kijelölhető.':'A prompt üres.';$('#aiPromptCopy').disabled=!r.prompt;$('#aiPromptDownload').disabled=!r.prompt;return r}catch(e){state.ai.exportPrompt=null;$('#aiPromptContent').textContent='';$('#aiPromptStatus').textContent=e.message||String(e);throw e}}
async function copyAIPrompt(){const text=state.ai.exportPrompt?.prompt||'';if(!text)return;try{await copyTextRobust(text);$('#aiPromptStatus').textContent='Prompt a vágólapra másolva.'}catch(e){$('#aiPromptStatus').textContent=e.message||'A másolás nem sikerült.'}}
function downloadAIPrompt(){const x=state.ai.exportPrompt;if(!x?.prompt)return;downloadTextFile(x.prompt,x.filename||`SleepMate_AI_prompt_${new Date().toISOString().slice(0,10)}.txt`);$('#aiPromptStatus').textContent='A prompt TXT fájl letöltése elindult.'}
function openExternalAi(url){const opened=window.open(url,'_blank','noopener,noreferrer');if(opened)opened.opener=null;else $('#aiPromptStatus').textContent='A böngésző letiltotta az új ablakot. Engedélyezd a felugró ablakokat ehhez a művelethez.'}
function availableAIAnalysisModes(){const f=aiFeaturePreferences(),modes=[];if(f.lunaVisible&&aiProviderMeta('gemini').configured)modes.push({id:'gemini',label:'Luna értékelje'});if(f.miloVisible&&aiProviderMeta('groq').configured)modes.push({id:'groq',label:'Milo értékelje'});if(f.promptingEnabled)modes.push({id:'external',label:'Prompt külső AI-hoz'});return modes}
let aiModeOutsideHandler=null;
function closeAIAnalysisModeMenu(){document.querySelector('.ai-mode-menu')?.remove();$$('[data-ai-analysis]').forEach(btn=>btn.setAttribute('aria-expanded','false'));if(aiModeOutsideHandler){document.removeEventListener('click',aiModeOutsideHandler);aiModeOutsideHandler=null}}
async function runAIAnalysisMode(mode,type,button){closeAIAnalysisModeMenu();if(mode.id==='external'){let selection;try{selection=aiSelection(type)}catch(e){showError(e);return}button.disabled=true;try{await requestAIPrompt(selection)}catch(e){showError(e)}finally{button.disabled=false}return}selectAIProvider(mode.id);return startAIAnalysis(type,button)}
function showAIAnalysisModeMenu(modes,type,button){closeAIAnalysisModeMenu();const menu=document.createElement('div');menu.className='ai-mode-menu';menu.setAttribute('role','menu');menu.setAttribute('aria-label','Elemzési mód');menu.innerHTML=modes.map(mode=>`<button type="button" role="menuitem" data-ai-mode="${mode.id}">${escapeHtml(mode.label)}</button>`).join('');document.body.appendChild(menu);button.setAttribute('aria-expanded','true');const anchor=button.offsetParent?button:$('#aiAnalysisPickerButton')||button,r=anchor.getBoundingClientRect(),mw=Math.min(280,Math.max(220,r.width));menu.style.width=`${mw}px`;const top=r.bottom+8+menu.offsetHeight>innerHeight?Math.max(8,r.top-menu.offsetHeight-8):r.bottom+8;menu.style.left=`${Math.max(8,Math.min(innerWidth-mw-8,r.left))}px`;menu.style.top=`${top}px`;menu.querySelectorAll('[data-ai-mode]').forEach(item=>item.onclick=e=>{e.stopPropagation();const mode=modes.find(x=>x.id===item.dataset.aiMode);if(mode)runAIAnalysisMode(mode,type,button)});aiModeOutsideHandler=e=>{if(!menu.contains(e.target)&&e.target!==button)closeAIAnalysisModeMenu()};setTimeout(()=>document.addEventListener('click',aiModeOutsideHandler),0)}
async function startAIAnalysisWithFeatures(type,button){if(!state.days.length){showError(new Error('Még nincs kiértékelhető terápiás adat.'));return}const modes=availableAIAnalysisModes();if(!modes.length){showError(new Error('Nincs bekapcsolt és használható elemzési mód. Kapcsold be a promptolást, vagy állíts be API-kulcsot Lunához vagy Milóhoz.'));return}if(modes.length===1)return runAIAnalysisMode(modes[0],type,button);showAIAnalysisModeMenu(modes,type,button)}
async function startAIAnalysis(type,button){if(!state.days.length){showError(new Error('Még nincs kiértékelhető terápiás adat.'));return}const key=currentAIAnalysisKey(type),lock=state.ai.status?.current_dataset_analyses?.[key];if(lock?.analysis_id){await openAIHistory(lock.analysis_id);return}const provider=state.ai.provider,meta=aiProviderMeta(provider);if(!meta.configured){showError(new Error(`${meta.name} API-kulcsa nincs beállítva. Nyisd meg: Beállítások → AI.`));return}button.disabled=true;state.ai.analysisType=type;state.ai.month=type==='month'?$('#aiMonthSelect').value:'';const comparison=type==='comparison'?{a_start:$('#aiCompareAStart').value,a_end:$('#aiCompareAEnd').value,b_start:$('#aiCompareBStart').value,b_end:$('#aiCompareBEnd').value}:null;if(type==='comparison'&&!Object.values(comparison).every(Boolean)){showError(new Error('Add meg mindkét összehasonlítási időszakot.'));button.disabled=false;return}const work=$('#aiWorkArea'),result=$('#aiResultArea');work.classList.remove('hidden');result.classList.add('hidden');setAIAvatar($('#aiStreamAvatar'),provider);$('#aiStreamName').textContent=`${meta.name} elemzi az adatokat…`;$('#aiStreamMeta').textContent='Anonim adatcsomag előkészítése';$('#aiStreamingText').textContent='Kapcsolódás az AI szolgáltatóhoz…';$('#aiStreamProgress').style.width='8%';let raw='',actualProvider=provider;try{await readNdjson('/api/ai/analysis-stream',{provider,analysis_type:type,month:state.ai.month,comparison},async ev=>{if(ev.type==='provider'){actualProvider=ev.provider;const m=aiProviderMeta(actualProvider);setAIAvatar($('#aiStreamAvatar'),actualProvider);$('#aiStreamName').textContent=`${m.name} írja a kiértékelést…`;$('#aiStreamMeta').textContent=`${m.label} • ${ev.model}`;$('#aiStreamProgress').style.width='20%'}else if(ev.type==='fallback'){raw='';actualProvider=ev.provider;setAIAvatar($('#aiStreamAvatar'),actualProvider);$('#aiStreamName').textContent='Milo átvette a kiértékelést';$('#aiStreamMeta').textContent=ev.message;$('#aiStreamingText').textContent='';$('#aiStreamProgress').style.width='18%'}else if(ev.type==='delta'){raw+=ev.text;const live=extractPartialJsonString(raw,'live_text');if(live)$('#aiStreamingText').textContent=live;$('#aiStreamProgress').style.width=`${Math.min(92,28+Math.log10(Math.max(10,raw.length))*16)}%`}else if(ev.type==='error')throw new Error(ev.message);else if(ev.type==='final'){state.ai.analysisId=ev.analysis_id;state.ai.result=ev.result;actualProvider=ev.result.provider||actualProvider;$('#aiStreamProgress').style.width='100%';$('#aiStreamMeta').textContent='Kiértékelés mentve';renderAIResult(ev.result,true)}});work.classList.add('hidden');result.classList.remove('hidden');await Promise.all([loadAIStatus(),loadAIHistory()]);result.scrollIntoView({behavior:'smooth',block:'start'})}catch(e){work.classList.add('hidden');showError(e)}finally{button.disabled=false}}
function confidenceLabel(v){return v==='high'?'Magas bizonyosság':v==='medium'?'Közepes bizonyosság':'Alacsony bizonyosság'}
function renderAIResult(r,resetChat=true){const meta=aiProviderMeta(r.provider);state.ai.provider=r.provider;selectAIProvider(r.provider);setAIAvatar($('#aiResultAvatar'),r.provider);setAIAvatar($('#aiChatAvatar'),r.provider);$('#aiResultProvider').textContent=`${meta.name} • ${meta.label} • ${r.model||meta.model||''}${r.fallback_used?' • fallback':''}`;$('#aiResultTitle').textContent=friendlyAiTitle(r.overall?.title,r.overall?.status);$('#aiResultPeriod').textContent=`${formatAiDate(r.period?.start)} – ${formatAiDate(r.period?.end)} • ${r.period?.days||0} terápiás nap`;if($('#aiOverallTitle')) $('#aiOverallTitle').textContent=r.overall?.title||'Összegzés';$('#aiOverallSummary').textContent=r.overall?.summary||r.live_text||'';$('#aiOverallMark').textContent=['attention','unfavorable'].includes(r.overall?.status)?'!':'✓';$('#aiShortEffect').textContent=r.therapy_effectiveness?.text||'—';$('#aiShortPositive').textContent=r.positives?.[0]||'—';$('#aiShortAttention').textContent=r.attention_points?.[0]||'—';const sections=[['Terápia hatékonysága','♥',r.therapy_effectiveness],['Események','⌁',r.events],['Nyomás','↕',r.pressure],['Szivárgás','≋',r.leak]];if(r.oxygen)sections.push(['Oxigén és pulzus','O₂',r.oxygen]);const html=sections.map(([title,icon,obj])=>`<article class="panel ai-detail-card"><div class="ai-detail-card-head"><span>${icon}</span><h3>${title}</h3><em>${confidenceLabel(obj?.confidence)}</em></div><p>${escapeHtml(obj?.text||'Nincs adat.')}</p></article>`).join('')+`<article class="panel ai-detail-card wide"><div class="ai-detail-card-head"><span>↗</span><h3>Trendek és mintázatok</h3></div>${(r.trends||[]).map(x=>`<div class="ai-trend-item"><b>${escapeHtml(x.title)}</b><p>${escapeHtml(x.text)}</p><small>${confidenceLabel(x.confidence)}</small></div>`).join('')||'<p>Nincs trendadat.</p>'}</article>`+`<article class="panel ai-list-card positive"><h3>Pozitívumok</h3><ul>${(r.positives||[]).map(x=>`<li>${escapeHtml(x)}</li>`).join('')}</ul></article>`+`<article class="panel ai-list-card attention"><h3>Figyelmet érdemlő pontok</h3><ul>${(r.attention_points||[]).map(x=>`<li>${escapeHtml(x)}</li>`).join('')}</ul></article>`+`<article class="panel ai-list-card wide"><h3>Javaslatok</h3><ul>${(r.recommendations||[]).map(x=>`<li>${escapeHtml(x.text)}</li>`).join('')}</ul><div class="ai-data-quality">Adatminőség: ${r.data_quality?.sufficient?'elegendő':'korlátozott'}${r.data_quality?.missing_useful_data?.length?` • Hasznos lenne: ${r.data_quality.missing_useful_data.map(escapeHtml).join(', ')}`:''}</div></article>`;$('#aiDetailedSections').innerHTML=html;setAIDetailView('short');if(resetChat)renderAIChatHistory({provider:r.provider,messages:[]});updateAIChatCounter()}
function renderAIChatHistory(row){const provider=row.provider||state.ai.provider,meta=aiProviderMeta(provider),box=$('#aiChatMessages');state.ai.provider=provider;selectAIProvider(provider);box.innerHTML=`<div class="chat-row ai-side ${provider==='gemini'?'luna':'milo'}"><div class="ai-avatar chat-avatar ${provider==='gemini'?'gemini-avatar':'groq-avatar'}">${aiAvatarInner(provider)}</div><div class="chat-bubble"><b>${escapeHtml(meta.name)}</b><p>Megvan a kiértékelés. Itt folytathatod ugyanazt a beszélgetést, amikor csak szeretnéd.</p></div></div>`;for(const m of row.messages||[]){if(m.role==='user')appendUserChat(m.content);else appendAIChat(m.content,false,m.provider||provider,aiProviderMeta(m.provider||provider).name)}box.scrollTop=box.scrollHeight}
function setAIDetailView(view){state.ai.detail=view;$('#aiShortView')?.classList.toggle('active',view==='short');$('#aiDetailedView')?.classList.toggle('active',view==='detailed');$$('.ai-detail-switch [data-ai-detail]').forEach(b=>b.classList.toggle('active',b.dataset.aiDetail===view))}
function updateAIChatCounter(){const u=state.ai.status?.chat?.[state.ai.provider];if($('#aiChatCounter'))$('#aiChatCounter').textContent=`${u?.used||0} / ${u?.limit||10} kérdés ma`}
function resizeAIChatInput(){const el=$('#aiChatInput');if(!el)return;const min=42,max=118;el.style.height='auto';const next=Math.max(min,Math.min(max,el.scrollHeight));el.style.height=`${next}px`;el.style.overflowY=el.scrollHeight>max?'auto':'hidden'}
async function sendAIChat(ev){ev.preventDefault();if(state.ai.chatBusy||!state.ai.result||!state.ai.analysisId)return;const input=$('#aiChatInput'),q=input.value.trim();if(!q)return;const provider=state.ai.provider,u=state.ai.status?.chat?.[provider];if((u?.remaining??10)<=0){showError(new Error('Ennél az AI-nál elfogyott a napi 10 kérdéses keret.'));return}const meta=aiProviderMeta(provider);appendUserChat(q);input.value='';resizeAIChatInput();state.ai.chatBusy=true;const typing=appendAIChat('',true,provider,meta.name),p=typing.querySelector('p');try{let actual=provider;await readNdjson('/api/ai/chat-stream',{analysis_id:state.ai.analysisId,question:q},async ev=>{if(ev.type==='delta'){typing.querySelector('.chat-typing')?.remove();typing.dataset.rawText=(typing.dataset.rawText||'')+ev.text;p.innerHTML=richTextHtml(typing.dataset.rawText);typing.parentElement.scrollTop=typing.parentElement.scrollHeight}else if(ev.type==='fallback'){actual=ev.provider;typing.classList.toggle('luna',actual==='gemini');typing.classList.toggle('milo',actual!=='gemini');setAIAvatar(typing.querySelector('.ai-avatar'),actual);typing.querySelector('b').textContent=aiProviderMeta(actual).name;typing.dataset.rawText='';p.innerHTML='';}else if(ev.type==='error')throw new Error(ev.message)});await Promise.all([loadAIStatus(),loadAIHistory()]);updateAIChatCounter()}catch(e){typing.remove();showError(e)}finally{state.ai.chatBusy=false}}
function patientPhotoUrl(patient=state.patient){const v=patient?.photo_version?encodeURIComponent(patient.photo_version):'current';return `/api/patient/photo?v=${v}`}
function userAvatarHtml(){return `<div class="user-chat-avatar"><img src="${patientPhotoUrl()}" onerror="this.style.display='none';this.nextElementSibling.style.display='grid'" alt="Profilkép"><span>👤</span></div>`}
function appendUserChat(text){const box=$('#aiChatMessages');box.insertAdjacentHTML('beforeend',`<div class="chat-row user-side"><div class="chat-bubble"><p>${escapeHtml(text)}</p></div>${userAvatarHtml()}</div>`);box.scrollTop=box.scrollHeight}
function appendAIChat(text,typing,provider,name){const box=$('#aiChatMessages'),row=document.createElement('div');row.className=`chat-row ai-side ${provider==='gemini'?'luna':'milo'}`;row.innerHTML=`<div class="ai-avatar chat-avatar ${provider==='gemini'?'gemini-avatar':'groq-avatar'}">${aiAvatarInner(provider)}</div><div class="chat-bubble"><b>${escapeHtml(name)}</b><p>${richTextHtml(text)}</p>${typing?'<span class="chat-typing">● ● ●</span>':''}</div>`;row.dataset.rawText=text||'';box.appendChild(row);box.scrollTop=box.scrollHeight;return row}
function printAIResult(includeChat=false){if(!state.ai.result)return;const r=state.ai.result,meta=aiProviderMeta(r.provider),w=window.open('','_blank','width=980,height=900');if(!w)return;const details=$('#aiDetailedSections').innerHTML;let chatHtml='';if(includeChat){const rows=[...document.querySelectorAll('#aiChatMessages .chat-row')].map(row=>{const who=row.classList.contains('user-side')?'Te':row.querySelector('.chat-bubble b')?.textContent||'AI';const body=row.querySelector('.chat-bubble p')?.innerHTML||'';return `<div class="chat-export-row"><h4>${escapeHtml(who)}</h4><div class="chat-export-bubble">${body}</div></div>`}).join('');chatHtml=`<section class="chat-export"><h2>Beszélgetés</h2>${rows}</section>`}w.document.write(`<!doctype html><html lang="hu"><head><meta charset="utf-8"><title>SleepMate AI kiértékelés</title><style>body{font:15px/1.6 Arial;color:#18212b;max-width:980px;margin:40px auto;padding:0 28px;background:#fff}h1,h2,h3,h4{color:#0c4a6e}.meta{color:#64748b;margin-bottom:24px}.box{border:1px solid #d7e1ea;border-radius:14px;padding:18px;margin:14px 0}.ai-detail-card,.ai-list-card{border:1px solid #d7e1ea;border-radius:14px;padding:16px;margin:12px 0}.ai-detail-card-head{display:flex;gap:12px;align-items:center}.ai-detail-card-head em{margin-left:auto;color:#64748b}ul{padding-left:22px}.chat-export{margin-top:26px}.chat-export-row{margin:0 0 14px}.chat-export-row h4{margin:0 0 6px}.chat-export-bubble{border:1px solid #d7e1ea;border-radius:14px;padding:14px;background:#f7fafc}</style></head><body><h1>${escapeHtml(friendlyAiTitle(r.overall.title,r.overall.status))}</h1><div class="meta">${escapeHtml(meta.name)} • ${escapeHtml(meta.label)} • ${escapeHtml(formatAiDate(r.period.start))} – ${escapeHtml(formatAiDate(r.period.end))}</div><div class="box"><h2>Rövid összefoglaló</h2><p>${escapeHtml(r.overall.summary)}</p></div>${details}${chatHtml}<p class="meta">SleepMate v5.0.0</p><script>window.onload=()=>setTimeout(()=>window.print(),200)<\/script></body></html>`);w.document.close()}
function setSettingsTab(name){
  $$('[data-settings-tab]').forEach(b=>b.classList.toggle('active',b.dataset.settingsTab===name));
  $$('[data-settings-panel]').forEach(p=>p.classList.toggle('active',p.dataset.settingsPanel===name));
  if($('#settingsCategorySelect'))$('#settingsCategorySelect').value=name;
  if(name==='push')loadPushStatus(false);
  if(name==='system')loadMaintenanceStatus();
}

function updateLevelClass(level='neutral'){const l=String(level||'').toLowerCase();return l==='ok'?'ok':l==='warn'?'warn':l==='error'?'error':'neutral'}
function renderUpdateStatus(r={}){
  const badge=$('#updateStateBadge');if(badge){const failed=!!r.last_error;badge.className=`remote-status ${r.update_available?'warn':failed?'neutral':'ok'}`;badge.textContent=r.update_available?'Frissítés elérhető':failed?'Ellenőrzési hiba':'Naprakész'}
  if($('#updateCurrentVersion'))$('#updateCurrentVersion').textContent=r.current_version||'—';
  if($('#updateLatestVersion'))$('#updateLatestVersion').textContent=r.latest_version||'—';
  if($('#updateLastCheck'))$('#updateLastCheck').textContent=r.last_check?humanDateTime(r.last_check):'—';
  if($('#updateAutoCheck'))$('#updateAutoCheck').checked=r.auto_check!==false;
  if($('#installUpdate'))$('#installUpdate').disabled=!r.update_available;
  if($('#rollbackUpdate'))$('#rollbackUpdate').disabled=!r.rollback_available;
  const status=$('#updateStatusText');if(status){status.textContent=r.last_error?`Hiba: ${r.last_error}`:r.update_available?`SleepMate ${r.latest_version} telepíthető. Telepítés előtt teljes backup és rollback-pont készül.`:'A SleepMate a hivatalos publikus kiadási csatornát használja.'}
}
async function loadMaintenanceStatus(){
  try{const [u,c]=await Promise.all([api('/api/update/status'),api('/api/self-check')]);renderUpdateStatus(u);renderSelfCheck(c)}catch(e){addLog('WARN',`Rendszerkarbantartási állapot nem tölthető be: ${e.message}`)}
}
async function saveUpdateSettings(){
  const btn=$('#saveUpdateSettings');if(!btn)return;btn.disabled=true;
  try{const payload={update_channel:'stable',update_auto_check:$('#updateAutoCheck').checked};const r=await apiWrite('/api/update/config','POST',payload);state.settings.update_auto_check=r.auto_check!==false;renderUpdateStatus(r);addLog('INFO','Frissítési beállítás mentve.')}catch(e){showError(e)}finally{btn.disabled=false}
}
async function checkForUpdates(){
  const btn=$('#checkForUpdates');if(!btn)return;btn.disabled=true;const text=$('#updateStatusText');if(text)text.textContent='GitHub release ellenőrzése…';
  try{const r=await apiWrite('/api/update/check','POST',{});renderUpdateStatus(r)}catch(e){showError(e);try{renderUpdateStatus(await api('/api/update/status'))}catch{}}finally{btn.disabled=false}
}
async function waitForSleepMateRestart(expectedVersion='',timeoutMs=150000){
  const start=Date.now();while(Date.now()-start<timeoutMs){try{const r=await fetch('/api/version',{cache:'no-store'});if(r.ok){const v=await r.json();if(!expectedVersion||v.version===expectedVersion){location.reload();return true}}}catch{}await new Promise(r=>setTimeout(r,1200))}return false
}
async function installAvailableUpdate(){
  try{clearError();const r=await apiWrite('/api/update/install','POST',{});setProgressBox('update',{progress:1,phase:'Indítás',message:'Biztonságos frissítés előkészítése…'});let expected='';try{const j=await pollJob(r.job,'update');expected=j.result?.target_version||'';setProgressBox('update',{status:'done',progress:100,phase:'Újraindítás',message:`SleepMate ${expected||'új verzió'} indul…`})}catch(e){/* az újraindítás közben megszakadó HTTP kapcsolat itt normális */}const ok=await waitForSleepMateRestart(expected);if(!ok)showError(new Error('A SleepMate újraindítása a várt időn belül nem igazolható. Nézd meg az update_worker naplót vagy indítsd el a programot.'))}catch(e){showError(e);setProgressBox('update',{status:'error',phase:'Frissítési hiba',message:e.message})}
}
async function rollbackSleepMate(){
  confirmAction('Az előző eltett programverzió kerül visszaállításra. A terápiás és kézi adatok nem kerülnek vissza egy korábbi állapotra. Folytatod?',async()=>{
    try{const r=await apiWrite('/api/update/rollback','POST',{});setProgressBox('update',{progress:5,phase:'Rollback',message:'Előző programverzió előkészítése…'});let expected='';try{const j=await pollJob(r.job,'update');expected=j.result?.target_version||''}catch{}await waitForSleepMateRestart(expected)}catch(e){showError(e)}
  },'Rollback')
}
function renderSelfCheck(r={}){
  const badge=$('#selfCheckBadge');if(badge){badge.className=`remote-status ${updateLevelClass(r.overall)}`;badge.textContent=r.overall==='OK'?'Rendben':r.overall==='WARN'?'Figyelmeztetés':r.overall==='ERROR'?'Hiba':'Még nem futott'}
  const box=$('#selfCheckSummary');if(!box)return;const rows=r.checks||[];box.innerHTML=rows.length?rows.map(x=>`<article class="self-check-row ${String(x.level||'').toLowerCase()}"><span class="self-check-dot">${x.level==='OK'?'✓':x.level==='ERROR'?'×':'!'}</span><div><b>${escapeHtml(x.title)}</b><small>${escapeHtml(x.message)}</small></div></article>`).join(''):'<div class="empty-state">Még nincs önellenőrzési eredmény.</div>'
}
async function runSelfCheck(){const btn=$('#runSelfCheck');if(btn)btn.disabled=true;try{const r=await apiWrite('/api/self-check/run','POST',{});renderSelfCheck(r);addLog(r.overall==='OK'?'INFO':'WARN',`SleepMate önellenőrzés: ${r.overall}.`)}catch(e){showError(e)}finally{if(btn)btn.disabled=false}}
async function createSupportBundle(){
  const btn=$('#createSupportBundle');if(btn)btn.disabled=true;
  try{const r=await apiWrite('/api/support/create','POST',{});const j=await pollJob(r.job,'support');if(j.result?.download_url){const a=document.createElement('a');a.href=j.result.download_url;a.download='';document.body.appendChild(a);a.click();a.remove()}addLog('INFO','SleepMate szervizcsomag elkészült.')}catch(e){showError(e);setProgressBox('support',{status:'error',phase:'Hiba',message:e.message})}finally{if(btn)btn.disabled=false}
}

async function checkBackgroundRefresh(){
  try{const c=await api('/api/config'),stamp=c.auto_scan_last_run||'';if(stamp&&state.lastAutoScanSeen!==null&&stamp!==state.lastAutoScanSeen){const before=state.days[0]||null;state.lastAutoScanSeen=stamp;state.dayRows=[];await loadDays(state.currentDay);addLog('INFO','Automatikus könyvtárfelülvizsgálat új adatállapotot töltött be.');const raw=(location.hash||'#dashboard').slice(1);if(raw==='#dashboard'||raw==='dashboard')await loadDashboardOverview(state.dashboardPeriod);else if(raw.startsWith('dashboard/')&&state.currentDay)await loadDashboard(state.currentDay);if(raw==='sessions')await loadSessionsPage();if(raw==='logs')await loadDiagnostics();await notifyAfterRefresh(before,{source:'scheduled'})}else if(state.lastAutoScanSeen===null)state.lastAutoScanSeen=stamp}catch(e){/* háttérellenőrzésnél nem zavarjuk a felhasználót */}}
const progressHideTimers=new Map();
function progressBox(name){return document.querySelector(`[data-progress-card="${name}"]`)}
function setProgressBox(name,job,uploadPct=null){
  const box=progressBox(name);if(!box)return;box.classList.remove('hidden');
  const pct=uploadPct!=null?uploadPct:Number(job?.progress||0),bar=box.querySelector('.progress-track i'),strong=box.querySelector('strong'),span=box.querySelector('span');
  bar.style.width=`${Math.max(0,Math.min(100,pct))}%`;strong.textContent=job?.phase||'Folyamatban…';span.textContent=job?.message||`${pct}%`;
  box.classList.toggle('done',job?.status==='done');box.classList.toggle('error',job?.status==='error');
  const oldTimer=progressHideTimers.get(name);if(oldTimer)clearTimeout(oldTimer);
  if(job?.status==='done'||job?.status==='error'){progressHideTimers.set(name,setTimeout(()=>{box.classList.add('hidden');box.classList.remove('done','error');progressHideTimers.delete(name)},job.status==='done'?4500:7500))}
}
async function pollJob(jid,name,onDone){
  let last=null;for(;;){const j=await api(`/api/job/${jid}`);last=j;setProgressBox(name,j);if(j.status==='done'){if(onDone)await onDone(j);return j}if(j.status==='error')throw new Error(j.message||j.error||'A művelet sikertelen.');await new Promise(r=>setTimeout(r,350))}
}
async function startJsonJob(url,name,payload={}){
  clearError();const r=await apiWrite(url,'POST',payload);setProgressBox(name,{progress:1,phase:'Indítás',message:'A művelet elindult.'});return pollJob(r.job,name,async j=>{state.dayRows=[];await loadDays(state.currentDay);addLog('INFO',`${j.label||'Művelet'} kész.`)})
}
async function uploadFileToJob(createUrl,file,name,onDone){
  if(!file)throw new Error('Válassz ki egy fájlt.');const meta=await apiWrite(createUrl,'POST',{});const jid=meta.job;setProgressBox(name,{progress:0,phase:'Feltöltés',message:file.name});
  await new Promise((resolve,reject)=>{const xhr=new XMLHttpRequest();xhr.open('PUT',meta.upload_url);xhr.setRequestHeader('Content-Type','application/zip');xhr.upload.onprogress=e=>{if(e.lengthComputable)setProgressBox(name,{phase:'Feltöltés',message:`${(e.loaded/1048576).toFixed(1)} / ${(e.total/1048576).toFixed(1)} MB`},Math.round(e.loaded/e.total*35))};xhr.onload=()=>{if(xhr.status>=200&&xhr.status<300)resolve();else{try{reject(new Error(JSON.parse(xhr.responseText).error||`HTTP ${xhr.status}`))}catch{reject(new Error(`HTTP ${xhr.status}`))}}};xhr.onerror=()=>reject(new Error('A feltöltés megszakadt.'));xhr.send(file)});
  return pollJob(jid,name,onDone);
}
async function startFolderImport(){try{await startJsonJob('/api/import/folder','folder',{source:$('#manualImportFolder').value.trim()});await loadUploadHistory()}catch(e){showError(e);setProgressBox('folder',{status:'error',phase:'Hiba',message:e.message})}}
async function startSdSearch(){try{await startJsonJob('/api/import/sd-search','sd');await loadUploadHistory()}catch(e){showError(e);setProgressBox('sd',{status:'error',phase:'Nem található SD-kártya',message:String(e.message||e).replace(/^FileNotFoundError:\s*/,'')})}}
async function startZipImport(){try{await uploadFileToJob('/api/import/zip/create',$('#zipImportFile').files?.[0],'zip',async()=>{state.dayRows=[];await loadDays(state.currentDay)});await loadUploadHistory()}catch(e){showError(e);setProgressBox('zip',{status:'error',phase:'Hiba',message:e.message})}}
async function startInstantRefresh(){try{await startJsonJob('/api/import/refresh','refresh');await loadUploadHistory()}catch(e){showError(e);setProgressBox('refresh',{status:'error',phase:'Hiba',message:e.message})}}
async function loadUploadHistory(){try{const h=await api('/api/logs/history?limit=12'),box=$('#uploadHistory');if(!box)return;box.innerHTML=h.rows.length?h.rows.map(x=>`<div class="history-row"><time>${new Date(x.time).toLocaleString('hu-HU')}</time><b class="history-${String(x.level).toLowerCase()}">${escapeHtml(x.level)}</b><span>${escapeHtml(x.message)}</span></div>`).join(''):'<div class="empty-state">Még nincs import/frissítési előzmény.</div>'}catch(e){addLog('WARN',e.message)}}
async function loadUploadPage(){await loadConfig();await loadUploadHistory()}
function fullBackupSuggestedName(){const d=new Date(),pad=n=>String(n).padStart(2,'0');return `SleepMate_teljes_backup_${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}_${pad(d.getHours())}-${pad(d.getMinutes())}.zip`}
async function saveBackupResponse(downloadUrl,fileHandle){
  if(fileHandle){
    const response=await fetch(downloadUrl,{cache:'no-store'});if(!response.ok)throw new Error(`A backup letöltése sikertelen (HTTP ${response.status}).`);
    const writable=await fileHandle.createWritable();
    try{
      if(response.body?.getReader){const reader=response.body.getReader();for(;;){const {done,value}=await reader.read();if(done)break;if(value)await writable.write(value)}}
      else await writable.write(await response.blob());
      await writable.close();
    }catch(e){try{await writable.abort()}catch{}throw e}
    return;
  }
  const a=document.createElement('a');a.href=downloadUrl;a.download=fullBackupSuggestedName();document.body.appendChild(a);a.click();a.remove();
}
async function createFullBackup(){
  let fileHandle=null;
  try{
    // Chromium/Edge desktop: ask for the destination BEFORE creating the backup.
    // This must run directly from the user's click while transient activation is active.
    if(typeof window.showSaveFilePicker==='function'){
      try{fileHandle=await window.showSaveFilePicker({suggestedName:fullBackupSuggestedName(),types:[{description:'SleepMate teljes backup',accept:{'application/zip':['.zip']}}],excludeAcceptAllOption:false})}
      catch(e){if(e?.name==='AbortError'){setProgressBox('backup',{status:'idle',phase:'Megszakítva',message:'A mentési hely kiválasztása megszakítva.'});return}throw e}
    }
    const r=await apiWrite('/api/backup/create','POST',{}),j=await pollJob(r.job,'backup');
    if(j.result?.download_url)await saveBackupResponse(j.result.download_url,fileHandle);
    setProgressBox('backup',{status:'done',progress:100,phase:'Kész',message:fileHandle?'A teljes backup a kiválasztott helyre mentve.':'A teljes backup elkészült; a böngésző letöltésként mentette.'});
    addLog('INFO','Teljes backup elkészült.');
  }catch(e){showError(e);setProgressBox('backup',{status:'error',phase:'Hiba',message:e.message})}
}
async function restoreFullBackup(){const file=$('#restoreFullBackupFile').files?.[0];if(!file){showError(new Error('Válassz ki egy teljes backup ZIP-et.'));return}confirmAction('A teljes backup visszatöltése a SleepMate teljes mentett belső állapotát állítja vissza: kezelt személy, felszerelések, profilkép, AI-adatok, beállítások és a belső CPAP mérési tár. A külső ResMed/SD forrásmappát nem módosítja. Biztosan folytatod?',async()=>{try{await uploadFileToJob('/api/backup/restore/create',file,'restore',async()=>{state.dayRows=[];state.patient=null;const [, , patient]=await Promise.all([loadConfig(),loadDays(),api('/api/patient')]);state.patient=patient;try{renderPatient()}catch{};try{await renderDashboardCalendar(true)}catch{}});addLog('INFO','Teljes rendszerbackup visszatöltve: személy, felszerelések, mérési adatok és beállítások frissítve.')}catch(e){showError(e);setProgressBox('restore',{status:'error',phase:'Hiba',message:e.message})}},'Teljes visszatöltés')}
async function deleteSelectedData(){
  const options={measurement:$('#deleteMeasurementData').checked,patient:$('#deletePatientData').checked,logs:$('#deleteSystemLogs').checked};
  if(!Object.values(options).some(Boolean)){showError(new Error('Jelölj ki legalább egy törlendő adattípust.'));return}
  state.pendingDataDeleteOptions=options;
  const labels=[];
  if(options.measurement)labels.push('CPAP mérési adatok a programból');
  if(options.patient)labels.push('Kezelt személy, felszerelés és napi értékelések');
  if(options.logs)labels.push('Rendszernapló');
  $('#dataDeleteSelection').innerHTML=labels.map(x=>`<span>${escapeHtml(x)}</span>`).join('');
  $('#dataDeleteAutoScanBlock').classList.toggle('hidden',!state.settings.auto_scan_enabled);
  const disableRadio=document.querySelector('input[name="dataDeleteAutoScan"][value="disable"]');if(disableRadio)disableRadio.checked=true;
  $('#dataDeleteConfirmInput').value='';$('#dataDeleteExecute').disabled=true;
  $('#dataDeleteModal').classList.remove('hidden');
  setTimeout(()=>$('#dataDeleteConfirmInput').focus(),50);
}
function closeDataDeleteModal(){
  $('#dataDeleteModal').classList.add('hidden');
  $('#dataDeleteConfirmInput').value='';$('#dataDeleteExecute').disabled=true;state.pendingDataDeleteOptions=null;
}
async function executeSelectedDataDelete(){
  if($('#dataDeleteConfirmInput').value!=='TÖRLÉS')return;
  const options=state.pendingDataDeleteOptions;if(!options)return;
  const keepAuto=(document.querySelector('input[name="dataDeleteAutoScan"]:checked')?.value||'disable')==='keep';
  $('#dataDeleteExecute').disabled=true;
  try{
    if(state.settings.auto_scan_enabled&&!keepAuto){await apiWrite('/api/settings','POST',{auto_scan_enabled:false});await loadConfig()}
    closeDataDeleteModal();
    const r=await apiWrite('/api/data/delete','POST',options);
    await pollJob(r.job,'restore',async()=>{state.dayRows=[];state.patient=null;await loadDays()});
    addLog('INFO','Kiválasztott programadatok törölve. A külső forrásmappa változatlan maradt.');
    route();
  }catch(e){showError(e);$('#dataDeleteExecute').disabled=false}
}

async function refreshData(){
  if(state.pullRefreshing)return;state.pullRefreshing=true;const btn=$('#refresh'),old=btn.textContent;btn.disabled=true;btn.textContent='Frissítés…';clearError();const before=state.days[0]||null;
  try{const result=await api('/api/refresh');state.dayRows=[];const current=state.currentDay;await loadDays(current);addLog('INFO','EDF-adatok frissítve.');await notifyAfterRefresh(before,result);route()}
  catch(e){showError(e)}finally{state.pullRefreshing=false;btn.disabled=false;btn.textContent=old;resetPullRefreshUi()}
}
function adjacentDay(delta){if(!state.currentDay)return;const i=state.days.indexOf(state.currentDay);const ni=i+delta;if(ni>=0&&ni<state.days.length)navigate('dashboard',state.days[ni])}

async function loadDashboardOverview(period='30'){
  clearError();updateMeasurementEmptyStates();if(!state.days.length)return;$('#dashboardDailyView').classList.add('hidden');$('#dashboardOverviewView').classList.remove('hidden');
  state.dashboardPeriod=String(period||'30');
  $$('#dashboardPeriodSwitch [data-period]').forEach(b=>b.classList.toggle('active',b.dataset.period===state.dashboardPeriod));
  try{
    const [d,patient]=await Promise.all([api(`/api/dashboard/overview?period=${encodeURIComponent(state.dashboardPeriod)}`),api('/api/patient')]);state.dashboardOverview=d;state.patient=patient;
    const latest=d.latest?.summary,ks=d.latest?.key_stats||{};state.latestDay=latest?.day||null;
    if(latest){
      state.currentDay=latest.day;
      $('#latestSleepDate').textContent=`${formatDayCode(latest.day)} • ${latest.sessions?.length||0} terápiás szakasz`;
      $('#latestAhi').textContent=Number(latest.ahi||0).toFixed(2);$('#latestUsage').textContent=formatUsageShort(latest.usage);
      $('#latestCompliance').textContent=(latest.therapy_seconds||0)>=14400?'4+ órás cél elérve':'4+ órás cél nincs elérve';
      $('#latestLeakP95').textContent=ks.leak_p95==null?'–':num(ks.leak_p95,1);
      const ev=['OA','CA','H','UA','RERA'].reduce((n,k)=>n+(latest.counts?.[k]||0),0),hrs=(latest.therapy_seconds||0)/3600;
      $('#latestEvents').textContent=ev;$('#latestEventIndex').textContent=hrs?`${num(ev/hrs,2)} esemény/óra`:'–';
      $('#latestPressureP95').textContent=ks.pressure_p95==null?'–':num(ks.pressure_p95,1);
      $('#latestStatus').textContent=secondsToHM(latest.therapy_seconds||0);$('#latestSessions').textContent=`${latest.sessions?.length||0} szakasz`;
      $('#latestEventBadges').innerHTML=['OA','CA','H','RERA'].map(k=>{const m=EVENT_TYPES[k];return`<span style="--badge:${m.color}">${k}: <b>${latest.counts?.[k]||0}</b></span>`}).join('');
      $('#openLatestSleep').disabled=false;
    }else{$('#latestSleepDate').textContent='Nincs terápiás adat';$('#openLatestSleep').disabled=true}
    const a=d.aggregate||{};$('#aggAhi').textContent=a.ahi==null?'–':num(a.ahi,2);$('#aggUsage').textContent=secondsToHM(a.average_usage_seconds||0);$('#aggCompliance').textContent=`${num(a.four_hour_percent||0,1)}%`;$('#aggComplianceCount').textContent=`${a.four_hour_days||0}/${a.days||0} nap`;$('#aggDays').textContent=a.days??0;$('#aggRange').textContent=d.from&&d.to?`${formatDayCode(d.from)} – ${formatDayCode(d.to)}`:'–';
    await renderPreviousNightDelta();presetComparisonDates();requestAnimationFrame(drawDashboardTrends);addLog('INFO',`Dashboard összesítő betöltve (${state.dashboardPeriod} nap/időszak).`);
  }catch(e){showError(e)}
}
function renderSystemStatus(s){const card=$('#systemStatusCenter');if(!card||!s)return;card.classList.remove('status-loading','status-ok','status-warning','status-error');card.classList.add(`status-${s.overall||'warning'}`);const title=s.overall==='ok'?'SleepMate rendben működik ✓':s.overall==='error'?'A SleepMate beavatkozást igényel':'A SleepMate működik, de van mire figyelni';$('#systemStatusTitle').textContent=title;const issues=Object.values(s.components||{}).filter(x=>x.warning||(!x.ok&&!x.optional));const prefix=s.overall==='error'?'Beavatkozás szükséges: ':s.overall==='warning'?'Figyelmeztetés: ':'';$('#systemStatusSummary').textContent=issues.length?prefix+issues.map(x=>x.label).join(' • '):'Adatforrás, EDF, diagnosztika, szinkron és biztonsági mentés rendben.';$('#systemStatusDetails').innerHTML=Object.values(s.components||{}).map(x=>{const cls=x.warning?'warn':x.ok?'ok':x.optional?'optional':'bad',icon=x.warning?'!':x.ok?'✓':x.optional?'○':'×';return`<article class="system-component ${cls}"><span>${icon}</span><div><b>${escapeHtml(x.label)}</b><small>${escapeHtml(String(x.value??'—').replace('T',' '))}</small></div></article>`}).join('')}
function isoFromCode(c){return c?`${c.slice(0,4)}-${c.slice(4,6)}-${c.slice(6,8)}`:''}
function deltaTone(v,lowerBetter=true){if(v==null||Math.abs(v)<.0001)return'flat';return (lowerBetter?(v<0):(v>0))?'good':'bad'}
function deltaText(v,dec=2,suffix=''){if(v==null)return'—';const sign=v>0?'+':'';return `${sign}${num(v,dec)}${suffix}`}
async function renderPreviousNightDelta(){const box=$('#previousNightDelta');if(!box||state.days.length<2){box?.classList.add('hidden');return}const b=state.days[0],a=state.days[1];try{const c=await api(`/api/comparison?a_start=${isoFromCode(a)}&a_end=${isoFromCode(a)}&b_start=${isoFromCode(b)}&b_end=${isoFromCode(b)}`),d=c.delta||{};box.classList.remove('hidden');$('#previousNightDeltaPeriod').textContent=`${formatDayCode(a)} → ${formatDayCode(b)}`;const items=[['AHI',d.ahi,2,' /óra',true],['Használat',d.average_usage_seconds?d.average_usage_seconds/60:null,0,' perc',false],['Szivárgás P95',d.leak_p95,1,' L/perc',true],['Nyomás P95',d.pressure_p95,1,' cmH₂O',null]];$('#previousNightDeltaGrid').innerHTML=items.map(([n,v,dec,u,better])=>`<article class="delta-item ${better===null?'neutral':deltaTone(v,better)}"><label>${n}</label><strong>${deltaText(v,dec,u)}</strong><small>${v==null?'Nincs elég adat':Math.abs(v)<.0001?'Nem változott':v>0?'Nőtt':'Csökkent'}</small></article>`).join('')}catch(e){box.classList.add('hidden')}}
function openComparisonModal(){presetComparisonDates();$('#comparisonModal').classList.remove('hidden')}
function closeComparisonModal(){$('#comparisonModal').classList.add('hidden')}
function clearComparison(){
  state.comparison=null;
  const panel=$('#comparisonSummaryPanel'),box=$('#comparisonResult'),label=$('#comparisonSummaryLabel');
  if(box)box.innerHTML='';
  if(label)label.textContent='Két kiválasztott időszak eredménye';
  panel?.classList.add('hidden');
  for(const id of ['compareAStart','compareAEnd','compareBStart','compareBEnd']){const el=document.getElementById(id);if(el)el.value=''}
}
function presetComparisonDates(){if(state.days.length<2)return;const newest=isoFromCode(state.days[0]),oldest=isoFromCode(state.days[Math.min(state.days.length-1,29)]),mid=isoFromCode(state.days[Math.min(state.days.length-1,14)]);if(!$('#compareAStart').value)$('#compareAStart').value=oldest;if(!$('#compareAEnd').value)$('#compareAEnd').value=mid;if(!$('#compareBStart').value)$('#compareBStart').value=mid;if(!$('#compareBEnd').value)$('#compareBEnd').value=newest;for(const [id,val] of [['aiCompareAStart',$('#compareAStart').value],['aiCompareAEnd',$('#compareAEnd').value],['aiCompareBStart',$('#compareBStart').value],['aiCompareBEnd',$('#compareBEnd').value]])if(document.getElementById(id)&&!document.getElementById(id).value)document.getElementById(id).value=val}
async function runComparison(){const q={a_start:$('#compareAStart').value,a_end:$('#compareAEnd').value,b_start:$('#compareBStart').value,b_end:$('#compareBEnd').value};if(!Object.values(q).every(Boolean)){showError(new Error('Add meg mindkét időszak kezdő és záró dátumát.'));return}try{const c=await api(`/api/comparison?${new URLSearchParams(q)}`);state.comparison=c;renderComparison(c);closeComparisonModal()}catch(e){showError(e)}}
function renderComparison(c){const box=$('#comparisonResult');if(!box)return;$('#comparisonSummaryPanel')?.classList.remove('hidden');const a=c.period_a||{},b=c.period_b||{},d=c.delta||{};if($('#comparisonSummaryLabel'))$('#comparisonSummaryLabel').textContent=`${formatDayCode(a.from)} – ${formatDayCode(a.to)}  ↔  ${formatDayCode(b.from)} – ${formatDayCode(b.to)}`;const rows=[['AHI',a.ahi,b.ahi,d.ahi,2,' /óra',true],['Átlagos használat',(a.average_usage_seconds||0)/3600,(b.average_usage_seconds||0)/3600,(d.average_usage_seconds||0)/3600,2,' óra',false],['Nyomás P95',a.pressure_p95,b.pressure_p95,d.pressure_p95,1,' cmH₂O',null],['Szivárgás P95',a.leak_p95,b.leak_p95,d.leak_p95,1,' L/perc',true]];box.innerHTML=`<div class="comparison-summary-head"><span>A: ${formatDayCode(a.from)} – ${formatDayCode(a.to)} • ${a.days} nap</span><span>B: ${formatDayCode(b.from)} – ${formatDayCode(b.to)} • ${b.days} nap</span></div><div class="comparison-metrics">${rows.map(([n,av,bv,dv,dec,u,better])=>`<article><label>${n}</label><div><span>${num(av,dec)}${u}</span><b>→</b><span>${num(bv,dec)}${u}</span></div><strong class="${better===null?'neutral':deltaTone(dv,better)}">${deltaText(dv,dec,u)}</strong></article>`).join('')}</div><div class="comparison-events">${['OA','CA','H','RERA'].map(k=>`<span>${k}: <b class="${deltaTone(d.event_index?.[k],true)}">${deltaText(d.event_index?.[k],2,' /óra')}</b></span>`).join('')}</div>`}

function trendRect(w,h){return{l:48,r:18,t:30,b:32,w:Math.max(1,w-66),h:Math.max(1,h-62)}}
function trendDateLabel(row){return row?.day?`${row.day.slice(4,6)}.${row.day.slice(6,8)}.`:'–'}
function trendX(i,n,pr){return n<=1?pr.l+pr.w/2:pr.l+pr.w*i/(n-1)}
function trendBarX(i,n,pr){const bw=pr.w/Math.max(1,n);return pr.l+(i+.5)*bw}
function traceSmooth(ctx,pts,move=true){
  if(!pts.length)return;if(move)ctx.moveTo(pts[0].x,pts[0].y);else ctx.lineTo(pts[0].x,pts[0].y);
  if(pts.length===1)return;
  for(let i=1;i<pts.length-1;i++){const p=pts[i],n=pts[i+1],mx=(p.x+n.x)/2,my=(p.y+n.y)/2;ctx.quadraticCurveTo(p.x,p.y,mx,my)}
  const last=pts.at(-1);ctx.quadraticCurveTo(last.x,last.y,last.x,last.y)
}
function smoothPath(ctx,pts){if(!pts.length)return;ctx.beginPath();traceSmooth(ctx,pts,true)}
function drawPointLabels(ctx,pts,sp,seriesIndex,seriesCount){if(!pts.length)return;const n=pts.length,showAll=n<=8&&seriesCount<=2,step=showAll?1:Math.max(1,Math.ceil(n/5));ctx.save();ctx.font='9px Segoe UI';ctx.textAlign='center';ctx.fillStyle=sp.color;for(let i=0;i<n;i++){if(!showAll&&i%step&&i!==n-1)continue;const p=pts[i],txt=num(p.v,sp.decimals??1);const dy=seriesCount>1?(seriesIndex===0?-7:13):-7;ctx.fillText(txt,p.x,p.y+dy)}ctx.restore()}
function trendOverlayFor(canvas){
  let ov=canvas._trendOverlay;if(ov&&ov.isConnected)return ov;
  // A hover réteg a body-ba kerül és viewport-koordinátákkal illeszkedik a
  // forrás canvasra. Így a panel padding/border/eltérő grid-szélesség nem tud
  // plusz X/Y eltolást hozzáadni.
  ov=document.createElement('canvas');ov.className='trend-hover-overlay';ov.setAttribute('aria-hidden','true');document.body.appendChild(ov);canvas._trendOverlay=ov;return ov
}
function sizeTrendOverlay(canvas){
  const ov=trendOverlayFor(canvas),r=canvas.getBoundingClientRect(),dpr=window.devicePixelRatio||1;
  ov.style.left=`${r.left}px`;ov.style.top=`${r.top}px`;ov.style.width=`${r.width}px`;ov.style.height=`${r.height}px`;
  const pw=Math.max(1,Math.round(r.width*dpr)),ph=Math.max(1,Math.round(r.height*dpr));if(ov.width!==pw||ov.height!==ph){ov.width=pw;ov.height=ph}
  const ctx=ov.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);return{ov,ctx,w:r.width,h:r.height}
}
function trendMetaX(m,idx,pr){
  const x=Number(m?.xPositions?.[idx]);if(Number.isFinite(x))return x;
  return m?.kind==='line'?trendX(idx,m.rows.length,pr):trendBarX(idx,m.rows.length,pr)
}
function trendIndexAtX(canvas,x,pr){
  const m=canvas?._trendMeta;if(!m?.rows?.length)return 0;
  const xs=m.xPositions||m.rows.map((_,i)=>trendMetaX(m,i,pr));let best=0,dist=Infinity;
  for(let i=0;i<xs.length;i++){const d=Math.abs(x-xs[i]);if(d<dist){dist=d;best=i}}
  return best
}
function clearTrendHover(){state.trendHoverIndex=null;state.trendHoverCanvas=null;$('#trendTooltip')?.classList.add('hidden');for(const c of $$('.trend-card canvas:not(.trend-hover-overlay)')){if(c._trendOverlay){const {ctx,w,h}=sizeTrendOverlay(c);ctx.clearRect(0,0,w,h)}}}
function drawTrendHoverLine(canvas,idx){
  if(!canvas?._trendMeta)return;const m=canvas._trendMeta,{ctx,w,h}=sizeTrendOverlay(canvas),pr=trendRect(w,h);ctx.clearRect(0,0,w,h);if(idx==null||idx<0||idx>=m.rows.length)return;
  const x=trendMetaX(m,idx,pr);ctx.save();ctx.setLineDash([5,5]);ctx.strokeStyle='rgba(225,238,250,.72)';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(x,pr.t);ctx.lineTo(x,pr.t+pr.h);ctx.stroke();ctx.restore();
  if(m.kind==='line')for(const ser of m.series||[]){const v=ser.get(m.rows[idx]);if(v==null||!Number.isFinite(+v))continue;const sc=m.scales?.get(ser.name)||m.scale;if(!sc)continue;const y=pr.t+(sc.hi-(+v))/(sc.hi-sc.lo||1)*pr.h;ctx.fillStyle=ser.color;ctx.beginPath();ctx.arc(x,y,4,0,Math.PI*2);ctx.fill();ctx.strokeStyle='#0d151e';ctx.lineWidth=1.5;ctx.stroke()}
}
function syncTrendHover(idx,sourceCanvas,event){
  const sourceMeta=sourceCanvas?._trendMeta,row=sourceMeta?.rows?.[idx];if(!sourceMeta||!row)return;
  state.trendHoverIndex=idx;state.trendHoverCanvas=sourceCanvas;
  // Dátum alapján szinkronizálunk, nem pusztán index alapján. Minden kártya a
  // saját xPositions geometriáját használja: vonal = adatpont, oszlop = közép.
  for(const c of $$('.trend-card canvas:not(.trend-hover-overlay)')){const m=c._trendMeta;if(!m?.rows?.length)continue;const target=m.rows.findIndex(r=>String(r.day)===String(row.day));drawTrendHoverLine(c,target>=0?target:null)}
  const m=sourceMeta,tip=$('#trendTooltip');if(!tip)return;
  let lines=[`<b>${formatDayCode(row.day)}</b>`];
  if(m.kind==='line')for(const ser of m.series){const v=ser.get(row);if(v!=null&&Number.isFinite(+v))lines.push(`<span><i style="background:${ser.color}"></i>${escapeHtml(ser.name)}: <strong>${num(v,ser.decimals??1)}${ser.unit?' '+escapeHtml(ser.unit):''}</strong></span>`)}
  else if(m.kind==='usage'){lines.push(`<span><i style="background:#55b96f"></i>Használat: <strong>${num(row.usage_hours||0,2)} óra</strong></span>`)}
  else if(m.kind==='events'){let total=0;for(const k of ['OA','CA','H','RERA']){const v=row.event_index?.[k]||0;total+=v;lines.push(`<span><i style="background:${TREND_EVENT_COLORS[k]}"></i>${k}: <strong>${num(v,2)} /óra</strong></span>`)}lines.push(`<span class="tip-total">Összesen: <strong>${num(total,2)} /óra</strong></span>`)}
  tip.innerHTML=lines.join('');tip.classList.remove('hidden');const rr=sourceCanvas.getBoundingClientRect(),x=event.clientX+14,y=event.clientY+14;tip.style.left=`${Math.min(window.innerWidth-tip.offsetWidth-10,x)}px`;tip.style.top=`${Math.min(window.innerHeight-tip.offsetHeight-10,y)}px`;
}
function wireTrendCanvas(canvas,rows,kind='line'){
  const point=e=>{if(!rows.length)return null;const r=canvas.getBoundingClientRect(),pr=trendRect(r.width,r.height),x=e.clientX-r.left,idx=trendIndexAtX(canvas,x,pr);cancelAnimationFrame(state.trendHoverRaf);state.trendHoverRaf=requestAnimationFrame(()=>syncTrendHover(idx,canvas,e));return idx};
  let touch=null;
  canvas.onmousemove=point;canvas.onmouseleave=()=>clearTrendHover();
  canvas.onpointerdown=e=>{if(e.pointerType!=='touch')return;touch={id:e.pointerId,x:e.clientX,y:e.clientY,moved:false,vertical:false};point(e)};
  canvas.onpointermove=e=>{if(e.pointerType!=='touch'||!touch||touch.id!==e.pointerId)return;const dx=e.clientX-touch.x,dy=e.clientY-touch.y;if(!touch.moved&&Math.hypot(dx,dy)>5){touch.moved=true;touch.vertical=Math.abs(dy)>Math.abs(dx)*1.05}if(touch.vertical){clearTrendHover();return}point(e)};
  const end=e=>{if(e.pointerType!=='touch'||!touch||touch.id!==e.pointerId)return;const wasTap=!touch.moved&&!touch.vertical;touch=null;if(wasTap){const idx=point(e);if(idx!=null)navigate('dashboard',rows[idx].day)}setTimeout(clearTrendHover,80)};
  canvas.onpointerup=end;canvas.onpointercancel=()=>{touch=null;clearTrendHover()};
  canvas.onclick=e=>{if(e.pointerType==='touch')return;const idx=point(e);if(idx!=null)navigate('dashboard',rows[idx].day)};
}
function drawLegend(ctx,pr,series){ctx.font='10px Segoe UI';let x=pr.l,y=15;for(const sp of series){const label=sp.name,w=ctx.measureText(label).width+28;if(x+w>pr.l+pr.w){x=pr.l;y+=12}ctx.strokeStyle=sp.color;ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(x,y-3);ctx.lineTo(x+14,y-3);ctx.stroke();ctx.fillStyle='#b9c6d2';ctx.fillText(label,x+19,y);x+=w+12}}
function drawTrendLine(canvas,rows,series,{zero=false,normalized=false,band=false,bandColor='rgba(200,120,220,.10)'}={}){
  if(!canvas)return;const{ctx,w,h}=setupCanvas(canvas),pr=trendRect(w,h);ctx.clearRect(0,0,w,h);ctx.fillStyle='#101722';ctx.fillRect(0,0,w,h);ctx.strokeStyle='#273747';ctx.lineWidth=1;
  for(let i=0;i<=4;i++){const y=pr.t+pr.h*i/4;ctx.beginPath();ctx.moveTo(pr.l,y);ctx.lineTo(pr.l+pr.w,y);ctx.stroke()}
  let all=[];if(!normalized)for(const sp of series)for(const r of rows){const v=sp.get(r);if(v!=null&&Number.isFinite(+v))all.push(+v)}let lo=zero?0:(all.length?Math.min(...all):0),hi=all.length?Math.max(...all):1;if(hi===lo)hi=lo+1;const pad=zero?Math.max(.02,hi*.05):(hi-lo)*.10;lo=zero?0:lo-pad;hi+=pad;
  const scales=new Map(),pointSets=[];
  for(const sp of series){const vals=rows.map(r=>{const v=sp.get(r);return v==null||!Number.isFinite(+v)?null:+v});let slo=lo,shi=hi;if(normalized){const av=vals.filter(v=>v!=null);slo=av.length?Math.min(...av):0;shi=av.length?Math.max(...av):1;const pd=(shi-slo||1)*.08;slo-=pd;shi+=pd}scales.set(sp.name,{lo:slo,hi:shi});pointSets.push(vals.map((v,i)=>v==null?null:{x:trendX(i,rows.length,pr),y:pr.t+(shi-v)/(shi-slo||1)*pr.h,v}))}
  if(band&&pointSets.length===2&&!normalized){const a=pointSets[0],b=pointSets[1],pairs=a.map((p,i)=>p&&b[i]?[p,b[i]]:null).filter(Boolean);if(pairs.length>1){const upper=pairs.map(x=>x[0]),lower=[...pairs].reverse().map(x=>x[1]);ctx.fillStyle=bandColor;ctx.beginPath();traceSmooth(ctx,upper,true);traceSmooth(ctx,lower,false);ctx.closePath();ctx.fill()}}
  series.forEach((sp,si)=>{const pts=pointSets[si].filter(Boolean);if(!pts.length)return;ctx.strokeStyle=sp.color;ctx.lineWidth=si===series.length-1&&series.length>1?2.7:2;ctx.lineJoin='round';ctx.lineCap='round';smoothPath(ctx,pts);ctx.stroke();for(const p of pts){ctx.fillStyle=sp.color;ctx.beginPath();ctx.arc(p.x,p.y,2.3,0,Math.PI*2);ctx.fill()}});
  ctx.font='9px Segoe UI';ctx.fillStyle='#899db0';const step=Math.max(1,Math.ceil(rows.length/6));rows.forEach((r,i)=>{if(i%step&&i!==rows.length-1)return;const x=trendX(i,rows.length,pr),txt=trendDateLabel(r),tw=ctx.measureText(txt).width;ctx.fillText(txt,Math.max(pr.l,Math.min(pr.l+pr.w-tw,x-tw/2)),h-8)});
  if(!normalized){ctx.fillText(hi.toFixed(1),4,pr.t+4);ctx.fillText(lo.toFixed(1),4,pr.t+pr.h)}drawLegend(ctx,pr,series);
  canvas._trendMeta={kind:'line',rows,series,scale:{lo,hi},scales,xPositions:rows.map((_,i)=>trendX(i,rows.length,pr))};wireTrendCanvas(canvas,rows,'line');if(state.trendHoverIndex!=null)drawTrendHoverLine(canvas,state.trendHoverIndex)
}
function drawUsageBars(canvas,rows){if(!canvas)return;const{ctx,w,h}=setupCanvas(canvas),pr=trendRect(w,h);ctx.clearRect(0,0,w,h);ctx.fillStyle='#101722';ctx.fillRect(0,0,w,h);const max=Math.max(4,...rows.map(r=>r.usage_hours||0));ctx.strokeStyle='#273747';for(let i=0;i<=4;i++){const y=pr.t+pr.h*i/4;ctx.beginPath();ctx.moveTo(pr.l,y);ctx.lineTo(pr.l+pr.w,y);ctx.stroke()}const bw=pr.w/Math.max(1,rows.length);rows.forEach((r,i)=>{const v=r.usage_hours||0,x=pr.l+i*bw+bw*.16,y=pr.t+(max-v)/max*pr.h;ctx.fillStyle=v>=4?'#54b86f':'#d28a18';ctx.fillRect(x,y,bw*.68,pr.t+pr.h-y)});ctx.fillStyle='#899db0';ctx.font='9px Segoe UI';const step=Math.max(1,Math.ceil(rows.length/6));rows.forEach((r,i)=>{if(i%step&&i!==rows.length-1)return;const txt=trendDateLabel(r),tw=ctx.measureText(txt).width,x=trendBarX(i,rows.length,pr);ctx.fillText(txt,Math.max(pr.l,Math.min(pr.l+pr.w-tw,x-tw/2)),h-8)});canvas._trendMeta={kind:'usage',rows,xPositions:rows.map((_,i)=>trendBarX(i,rows.length,pr))};wireTrendCanvas(canvas,rows,'usage');if(state.trendHoverIndex!=null)drawTrendHoverLine(canvas,state.trendHoverIndex)}
const TREND_EVENT_COLORS={OA:'#d7636b',CA:'#e88943',H:'#dfb536',RERA:'#45b978'};
function drawEventBars(canvas,rows){if(!canvas)return;const{ctx,w,h}=setupCanvas(canvas),pr=trendRect(w,h),types=['OA','CA','H','RERA'];ctx.clearRect(0,0,w,h);ctx.fillStyle='#101722';ctx.fillRect(0,0,w,h);const totals=rows.map(r=>types.reduce((n,k)=>n+(r.event_index?.[k]||0),0)),max=Math.max(.1,...totals);const bw=pr.w/Math.max(1,rows.length);ctx.strokeStyle='#273747';for(let i=0;i<=4;i++){const y=pr.t+pr.h*i/4;ctx.beginPath();ctx.moveTo(pr.l,y);ctx.lineTo(pr.l+pr.w,y);ctx.stroke()}rows.forEach((r,i)=>{let y0=pr.t+pr.h;for(const k of types){const v=r.event_index?.[k]||0,hh=v/max*pr.h;if(!hh)continue;ctx.fillStyle=TREND_EVENT_COLORS[k];ctx.fillRect(pr.l+i*bw+bw*.14,y0-hh,bw*.72,hh);y0-=hh}});ctx.font='10px Segoe UI';drawLegend(ctx,pr,types.map(k=>({name:k,color:TREND_EVENT_COLORS[k]})));const step=Math.max(1,Math.ceil(rows.length/6));ctx.fillStyle='#899db0';rows.forEach((r,i)=>{if(i%step&&i!==rows.length-1)return;const txt=trendDateLabel(r),tw=ctx.measureText(txt).width,x=trendBarX(i,rows.length,pr);ctx.fillText(txt,Math.max(pr.l,Math.min(pr.l+pr.w-tw,x-tw/2)),h-8)});canvas._trendMeta={kind:'events',rows,xPositions:rows.map((_,i)=>trendBarX(i,rows.length,pr))};wireTrendCanvas(canvas,rows,'events');if(state.trendHoverIndex!=null)drawTrendHoverLine(canvas,state.trendHoverIndex)}
function drawDashboardTrends(){
  const rows=state.dashboardOverview?.rows||[];if(!rows.length)return;
  drawTrendLine($('#trendAhi'),rows,[{name:'AHI',color:'#63bdff',get:r=>r.ahi,unit:'/óra',decimals:2}],{zero:true});
  drawUsageBars($('#trendUsage'),rows);
  drawTrendLine($('#trendPressure'),rows,[{name:'Medián',color:'#f0b0ff',get:r=>r.pressure_median,unit:'cmH₂O',decimals:2},{name:'95%',color:'#b14bd3',get:r=>r.pressure_p95,unit:'cmH₂O',decimals:2}],{band:true,bandColor:'rgba(190,85,215,.13)'});
  drawTrendLine($('#trendLeak'),rows,[{name:'Medián',color:'#ffd06f',get:r=>r.leak_median,unit:'L/perc',decimals:1},{name:'95%',color:'#ff8a1f',get:r=>r.leak_p95,unit:'L/perc',decimals:1}],{zero:true,band:true,bandColor:'rgba(255,153,37,.12)'});
  drawEventBars($('#trendEvents'),rows);
  drawTrendLine($('#trendResp'),rows,[{name:'Légzésszám',color:'#77cf8f',get:r=>r.resp_rate_median,unit:'/perc',decimals:1},{name:'Légzéstérfogat',color:'#3fc9e3',get:r=>r.tidal_volume_median,unit:'ml',decimals:0},{name:'Perctérfogat',color:'#b5d861',get:r=>r.minute_vent_median,unit:'L/perc',decimals:1}],{normalized:true});
}

async function loadDashboard(day){
  if(!day||!state.days.length){updateMeasurementEmptyStates();return;}clearError();$('#dashboardOverviewView').classList.add('hidden');$('#dashboardDailyView').classList.remove('hidden');
  try{
    const o2Promise=window.SleepMateO2Ring?.getDailySummary?.(day)||null;state.o2DailyLoading=!!o2Promise;state.o2Daily=null;const s=await api(`/api/day/${day}`);const extras=await Promise.allSettled([api(`/api/day/${day}/stats`),api('/api/patient'),api('/api/patient/therapy?period=30'),o2Promise||Promise.resolve(null)]);const st=extras[0].status==='fulfilled'?extras[0].value:{rows:[],apnea_duration:'–'},patient=extras[1].status==='fulfilled'?extras[1].value:(state.patient||{}),therapy30=extras[2].status==='fulfilled'?extras[2].value:{},o2Day=extras[3].status==='fulfilled'?extras[3].value:null;state.o2Daily=o2Day;state.o2DailyLoading=false;extras.slice(0,3).forEach((r,i)=>{if(r.status==='rejected')addLog('WARN',`Napi kiegészítő adat ${i+1}: ${r.reason?.message||r.reason}`)});state.currentDay=day;state.patient=patient;state.summary=s;state.full=fullBounds(s);state.view=[...state.full];state.hoverTime=null;state.overviewSignals.clear();state.stackSignals.clear();state.mainSignal=null;state.selectedSignal=state.selectedSignal||'flow';state.dayToken++;state.mainToken++;state.stackToken++;
    $('#day').value=day;$('#dashboardDate').textContent=dayCodeToIso(day);updateDayArrows();
    $('#usage').textContent=formatUsageShort(s.usage);$('#ahi').textContent=Number(s.ahi).toFixed(2);
    const eventCount=['OA','CA','H','UA','RERA'].reduce((n,k)=>n+(s.counts[k]||0),0);$('#eventCount').textContent=eventCount;
    applyOximetryVisibility(s);
    const integ=$('#integrity');integ.textContent=s.integrity.complete?`✓ ${s.integrity.edf_files} EDF-fájl ép`:`⚠ ${s.integrity.problems.length} EDF-fájl problémás`;integ.className=s.integrity.complete?'ok':'bad';
    $('#sessions').innerHTML=s.sessions.map((x,i)=>`<div class="session"><b>#${i+1}</b> ${fmtClock(x.start)} → ${fmtClock(x.end)} <strong>${x.duration_hms.slice(0,5)}</strong></div>`).join('');
    $('#sessionTotal').textContent=`${s.sessions.length} szakasz`;$('#dailySessionCount').textContent=s.sessions.length;
    const sm=Object.fromEntries((st.rows||[]).map(r=>[r.key,r]));$('#dailyLeakP95').textContent=sm.leak?num(sm.leak.p95,1):'–';$('#dailyPressureMedian').textContent=sm.pressure?num(sm.pressure.median,1):'–';$('#dailyPressureP95').textContent=sm.pressure?num(sm.pressure.p95,1):'–';$('#dailyPressureMax').textContent=sm.pressure?num(sm.pressure.max,1):'–';$('#dailyApneaTime').textContent=st.apnea_duration||'–';const rx=currentPrescription(patient.prescriptions||[]);$('#dailyPrescription').textContent=therapyLabel(rx);$('#dailyPrescriptionSince').textContent=rx?.effective_from?`${humanDate(rx.effective_from)}-tól`:'Nincs rögzített előírás';$('#dailyCompareMedian').textContent=sm.pressure?num(sm.pressure.median,1):'–';$('#dailyCompareP95').textContent=sm.pressure?num(sm.pressure.p95,1):'–';$('#dailyCompareMax').textContent=sm.pressure?num(sm.pressure.max,1):'–';$('#dailyCompare30P95').textContent=therapy30.pressure?num(therapy30.pressure.p95,1):'–';$('#dailyCompare30Ahi').textContent=`Terápiás AHI: ${therapy30.ahi==null?'–':num(therapy30.ahi,2)+' /óra'}`;renderNightEvaluation(s,st,patient);loadDailyAssessment(day,patient);
    buildEventBadges(s);buildEventLegend(s.events);buildEventList(s.events);buildOverviewGrid();buildStackedGrid();setChartMode(state.chartMode,false);drawAll();
    addLog('INFO',`${dayCodeToIso(day)} betöltve: ${formatUsageShort(s.usage)}, AHI ${Number(s.ahi).toFixed(2)}.`);
    await Promise.all([loadOverviewSignals(),loadMainSignal()]);if(state.chartMode==='stack')await loadStackSignals();
    if(state.pendingEventFocus?.day===day){const focus=state.pendingEventFocus.event;state.pendingEventFocus=null;zoomEvent(focus);requestAnimationFrame(()=>document.querySelector('.hero-panel')?.scrollIntoView({behavior:'smooth',block:'start'}));}
  }catch(e){showError(e)}
}
function updateDayArrows(){const i=state.days.indexOf(state.currentDay);$('#prevDay').disabled=i<0||i===state.days.length-1;$('#nextDay').disabled=i<=0}
function fullBounds(s){if(!s?.sessions?.length)return[Date.now(),Date.now()+1];return[new Date(s.sessions[0].start).getTime(),new Date(s.sessions.at(-1).end).getTime()]}
function clampRange(a,b){const[f0,f1]=state.full;if(a>b)[a,b]=[b,a];const minSpan=Math.min(30000,Math.max(1000,f1-f0));let span=Math.max(minSpan,b-a);if(span>f1-f0)return[f0,f1];if(a<f0){a=f0;b=a+span}if(b>f1){b=f1;a=b-span}return[a,b]}
function setView(a,b,reload=true){state.view=clampRange(a,b);state.hoverTime=null;drawAll();if(reload){loadMainSignal();loadOverviewSignals();if(state.chartMode==='stack')loadStackSignals()}}

function buildEventBadges(s){
  const items=['OA','CA','H','RERA'].map(k=>({k,n:s.counts[k]||0,m:EVENT_TYPES[k]}));
  $('#eventBadges').innerHTML=items.map(x=>`<span style="--badge:${x.m.color}">${x.k}: <b>${x.n}</b></span>`).join('');
}
function buildEventLegend(events){const present=new Set(events.map(e=>e.type));$('#eventLegend').innerHTML=Object.entries(EVENT_TYPES).filter(([k])=>present.has(k)).map(([k,v])=>`<span class="legend-item"><span class="legend-dot" style="background:${v.color}"></span>${eventTypeLabel(k,v)}</span>`).join('')}
function buildEventList(events){
  const box=$('#eventList');box.innerHTML='';
  for(const e of events){const meta=EVENT_TYPES[e.type]||EVENT_TYPES.OTHER,b=document.createElement('button');b.type='button';b.className='event-chip';b.innerHTML=`<span class="legend-dot" style="background:${meta.color}"></span><span class="event-code">${e.type}</span><span class="event-time">${fmtClock(e.time)}</span>`;b.onclick=()=>zoomEvent(e);box.appendChild(b)}
}
function zoomEvent(e){const t=new Date(e.time).getTime();setView(t-120000,t+120000,true);state.hoverTime=t;scheduleOverlayRender()}

function buildOverviewGrid(){
  const box=$('#overviewGrid');box.innerHTML='';
  for(const c of CHARTS){const b=document.createElement('button');b.type='button';b.className=`overview-card ${c.key===state.selectedSignal?'selected':''}`;b.dataset.key=c.key;b.innerHTML=`<div class="mini-head"><span>${c.title}</span><small id="mini-unit-${c.key}">–</small></div><canvas id="mini-${c.key}"></canvas>`;b.onclick=()=>selectSignal(c.key);box.appendChild(b)}
}
function selectSignal(key){state.selectedSignal=key;$$('.overview-card').forEach(x=>x.classList.toggle('selected',x.dataset.key===key));state.mainSignal=null;updateHeroHeader();drawHeroBase();drawHeroOverlay();loadMainSignal()}
function buildStackedGrid(){
  const box=$('#stackedCharts');if(!box)return;box.innerHTML='';
  for(const c of CHARTS){
    const card=document.createElement('section');card.className='stack-chart';card.dataset.key=c.key;
    card.innerHTML=`<div class="stack-head"><span><i style="background:${c.color}"></i>${c.title}</span><small id="stack-unit-${c.key}">–</small></div><div class="canvas-stack stack-canvas"><canvas id="stack-base-${c.key}"></canvas><canvas id="stack-overlay-${c.key}" class="canvas-overlay"></canvas></div>`;
    box.appendChild(card);setupStackInteraction(c.key);
  }
}
function setChartMode(mode,reload=true){
  state.chartMode=mode==='stack'?'stack':'focus';
  $('#focusViewBtn')?.classList.toggle('active',state.chartMode==='focus');
  $('#stackViewBtn')?.classList.toggle('active',state.chartMode==='stack');
  $('#overviewBlock')?.classList.toggle('hidden',state.chartMode==='stack');
  $('#stackedBlock')?.classList.toggle('hidden',state.chartMode!=='stack');
  $('.hero-panel')?.classList.toggle('stack-mode',state.chartMode==='stack');
  if(state.chartMode==='focus')state.stackSignals.clear();
  updateHeroHeader();
  if(state.chartMode==='stack'){
    drawStackedAll();
    if(reload)loadStackSignals();
  }
}
function updateHeroHeader(){if(state.chartMode==='stack'){$('#heroTitle').textContent='Összes grafikon – közös nézet';$('#heroSwatch').style.background='#65c6ff';$('#heroUnit').textContent='';return}const c=CHART_BY_KEY[state.selectedSignal];$('#heroTitle').textContent=c.title;$('#heroSwatch').style.background=c.color;const data=state.mainSignal||state.overviewSignals.get(c.key);$('#heroUnit').textContent=data?unitText(data.unit,c.key):'Betöltés…'}

async function loadOverviewSignals(){
  if(!state.summary)return;const day=state.summary.day,dayToken=state.dayToken,token=++state.overviewToken;
  const startS=(state.view[0]-state.full[0])/1000,endS=(state.view[1]-state.full[0])/1000;
  const full=Math.abs(state.view[0]-state.full[0])<1000&&Math.abs(state.view[1]-state.full[1])<1000;
  await Promise.all(CHARTS.map(async c=>{try{const q=new URLSearchParams({max_points:full?'1800':'1200'});if(!full){q.set('range_start_s',String(startS));q.set('range_end_s',String(endS))}const data=await api(`/api/day/${day}/signal/${c.key}?${q}`);if(dayToken!==state.dayToken||token!==state.overviewToken)return;state.overviewSignals.set(c.key,data);const u=$(`#mini-unit-${c.key}`);if(u)u.textContent=unitText(data.unit,c.key);drawMini(c.key)}catch(e){if(token===state.overviewToken)addLog('WARN',`${c.title}: ${e.message}`)}}));
  updateHeroHeader();
}
function maxPointsForMain(){const sec=(state.view[1]-state.view[0])/1000;const width=Math.max(800,$('.hero-stack')?.clientWidth||1200);let factor=2.5,cap=5000;if(sec<=5*60){factor=12;cap=18000}else if(sec<=20*60){factor=8;cap=15000}else if(sec<=60*60){factor=5;cap=11000}else if(sec<=4*3600){factor=3.5;cap=8000}return Math.max(1800,Math.min(cap,Math.round(width*factor)))}
async function loadStackSignals(){
  if(!state.summary||state.chartMode!=='stack')return;
  const day=state.summary.day,token=++state.stackToken;
  const startS=(state.view[0]-state.full[0])/1000,endS=(state.view[1]-state.full[0])/1000;
  const width=Math.max(700,$('#stackedCharts')?.clientWidth||1100);
  const sec=(state.view[1]-state.view[0])/1000;
  const maxPoints=sec<=20*60?Math.min(7000,Math.round(width*4)):Math.min(3600,Math.round(width*2));
  await Promise.all(CHARTS.map(async c=>{
    try{
      const q=new URLSearchParams({max_points:String(maxPoints),range_start_s:String(startS),range_end_s:String(endS)});
      const data=await api(`/api/day/${day}/signal/${c.key}?${q}`);
      if(token!==state.stackToken)return;
      state.stackSignals.set(c.key,data);
      const u=$(`#stack-unit-${c.key}`);if(u)u.textContent=unitText(data.unit,c.key);
      drawStackChart(c.key);drawStackOverlay(c.key);
    }catch(e){if(token===state.stackToken)addLog('WARN',`${c.title} (összes grafikon): ${e.message}`)}
  }));
}

async function loadMainSignal(){
  if(!state.summary)return;const day=state.summary.day,key=state.selectedSignal,token=++state.mainToken;updateHeroHeader();
  const startS=(state.view[0]-state.full[0])/1000,endS=(state.view[1]-state.full[0])/1000;
  try{const q=new URLSearchParams({max_points:String(maxPointsForMain()),range_start_s:String(startS),range_end_s:String(endS)});const data=await api(`/api/day/${day}/signal/${key}?${q}`);if(token!==state.mainToken)return;state.mainSignal=data;updateHeroHeader();drawHeroBase();drawHeroOverlay()}
  catch(e){if(token===state.mainToken){addLog('WARN',`${CHART_BY_KEY[key]?.title||key}: ${e.message}`);$('#heroUnit').textContent='Átmeneti adatkapcsolati hiba'}}
}

function setupCanvas(canvas){const dpr=window.devicePixelRatio||1,r=canvas.getBoundingClientRect(),cssW=Math.max(220,r.width||220),cssH=Math.max(40,r.height||120),pxW=Math.floor(cssW*dpr),pxH=Math.floor(cssH*dpr);if(canvas.width!==pxW||canvas.height!==pxH){canvas.width=pxW;canvas.height=pxH}const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);return{ctx,w:cssW,h:cssH}}
function reuseCanvas(canvas){const dpr=window.devicePixelRatio||1,ctx=canvas.getContext('2d'),w=Math.max(1,canvas.width/dpr),h=Math.max(1,canvas.height/dpr);ctx.setTransform(dpr,0,0,dpr,0,0);return{ctx,w,h}}
function plotRect(w,h,mini=false){return mini?{l:6,r:6,t:5,b:5,w:w-12,h:h-10}:{l:54,r:12,t:9,b:25,w:w-66,h:h-34}}
function xForTime(t,pr,bounds=state.view){return pr.l+(t-bounds[0])/(bounds[1]-bounds[0]||1)*pr.w}
function timeForX(x,pr,bounds=state.view){const p=Math.max(0,Math.min(1,(x-pr.l)/(pr.w||1)));return bounds[0]+p*(bounds[1]-bounds[0])}
function canvasX(e,canvas){const r=canvas.getBoundingClientRect();return e.clientX-r.left}
function drawGrid(ctx,pr,mini=false){ctx.strokeStyle=mini?'rgba(38,54,71,.42)':'#263647';ctx.lineWidth=1;const hy=mini?2:4,vx=mini?3:5;for(let i=0;i<=hy;i++){const y=pr.t+pr.h*i/hy;ctx.beginPath();ctx.moveTo(pr.l,y);ctx.lineTo(pr.l+pr.w,y);ctx.stroke()}for(let i=0;i<=vx;i++){const x=pr.l+pr.w*i/vx;ctx.beginPath();ctx.moveTo(x,pr.t);ctx.lineTo(x,pr.t+pr.h);ctx.stroke()}}
function drawXAxis(ctx,pr,bounds=state.view){const span=bounds[1]-bounds[0];ctx.fillStyle='#91a5b9';ctx.font='10px Segoe UI';for(let i=0;i<=5;i++){const x=pr.l+pr.w*i/5,t=bounds[0]+span*i/5,txt=fmtClock(t,span<15*60*1000),tw=ctx.measureText(txt).width;ctx.fillText(txt,Math.max(2,Math.min(pr.l+pr.w-tw,x-tw/2)),pr.t+pr.h+18)}}
function drawSessions(ctx,pr,bounds=state.view,alpha=.08){if(!state.summary)return;for(const sess of state.summary.sessions){const a=Math.max(bounds[0],new Date(sess.start).getTime()),b=Math.min(bounds[1],new Date(sess.end).getTime());if(b<=a)continue;ctx.fillStyle=`rgba(87,199,255,${alpha})`;ctx.fillRect(xForTime(a,pr,bounds),pr.t,xForTime(b,pr,bounds)-xForTime(a,pr,bounds),pr.h)}}
function yRange(data,key,bounds=state.view){if(!data)return null;let lo=Infinity,hi=-Infinity,count=0;for(const s of data.series||[]){const start=new Date(s.start).getTime();for(const p of s.points){const t=start+p[0]*1000;if(t<bounds[0]||t>bounds[1])continue;const v=p[1];if(v<lo)lo=v;if(v>hi)hi=v;count++}}if(!count)return null;if(key==='flow'){const m=Math.max(Math.abs(lo),Math.abs(hi),1);lo=-m;hi=m}if(hi===lo){const d=Math.abs(hi||1)*.1||1;lo-=d;hi+=d}const pad=(hi-lo)*.06;return[lo-pad,hi+pad]}
function yForValue(v,pr,yr){return pr.t+(yr[1]-v)/(yr[1]-yr[0]||1)*pr.h}
function drawYAxis(ctx,pr,yr,key){if(!yr)return;ctx.fillStyle='#91a5b9';ctx.font='10px Segoe UI';const dec=decimalsFor(key);for(let i=0;i<=4;i++){const v=yr[1]-(yr[1]-yr[0])*i/4;ctx.fillText(v.toFixed(dec),4,pr.t+pr.h*i/4+3)}}
function drawSeries(ctx,data,key,pr,yr,bounds,color,width=1.15){ctx.strokeStyle=color;ctx.lineWidth=width;ctx.lineJoin='round';ctx.lineCap='round';for(const s of data?.series||[]){const start=new Date(s.start).getTime();let begun=false;ctx.beginPath();for(const[offset,v]of s.points){const t=start+offset*1000;if(t<bounds[0]||t>bounds[1])continue;const x=xForTime(t,pr,bounds),y=yForValue(v,pr,yr);if(!begun){ctx.moveTo(x,y);begun=true}else ctx.lineTo(x,y)}if(begun)ctx.stroke()}}

function drawMini(key){
  const canvas=$(`#mini-${key}`);if(!canvas||!state.summary)return;
  const data=(state.chartMode==='stack'?state.stackSignals.get(key):null)||state.overviewSignals.get(key),{ctx,w,h}=setupCanvas(canvas);
  ctx.clearRect(0,0,w,h);ctx.fillStyle='#101722';ctx.fillRect(0,0,w,h);
  const pr=plotRect(w,h,true),yr=yRange(data,key,state.view);drawGrid(ctx,pr,true);
  if(!yr||!data)return;
  drawSeries(ctx,data,key,pr,yr,state.view,CHART_BY_KEY[key].color,1);
}
function drawHeroBase(){const canvas=$('#heroBase');if(!canvas||!state.summary)return;const{ctx,w,h}=setupCanvas(canvas),key=state.selectedSignal,data=state.mainSignal;ctx.clearRect(0,0,w,h);ctx.fillStyle='#0e1620';ctx.fillRect(0,0,w,h);const pr=plotRect(w,h);drawSessions(ctx,pr,state.view,.05);drawGrid(ctx,pr);const yr=yRange(data,key,state.view);if(!data||!yr){ctx.fillStyle='#93a7bb';ctx.font='12px Segoe UI';ctx.fillText('Adatok betöltése…',pr.l+10,pr.t+24);drawXAxis(ctx,pr);return}drawYAxis(ctx,pr,yr,key);drawSeries(ctx,data,key,pr,yr,state.view,CHART_BY_KEY[key].color,1.2);drawEventMarkers(ctx,pr,state.view,false);drawXAxis(ctx,pr)}
function drawEventMarkers(ctx,pr,bounds,labels=false){if(!state.summary)return;for(const e of state.summary.events){const t=new Date(e.time).getTime();if(t<bounds[0]||t>bounds[1])continue;const x=xForTime(t,pr,bounds),m=EVENT_TYPES[e.type]||EVENT_TYPES.OTHER;ctx.save();ctx.strokeStyle=m.color;ctx.globalAlpha=.82;ctx.lineWidth=1.5;ctx.beginPath();ctx.moveTo(x,pr.t);ctx.lineTo(x,pr.t+pr.h);ctx.stroke();if(labels){ctx.globalAlpha=1;ctx.fillStyle=m.color;ctx.font='10px Segoe UI';ctx.fillText(e.type,x+3,pr.t+11)}ctx.restore()}}
function nearestPoint(data,targetMs){if(!data)return null;let best=null,bestDiff=Infinity;for(const s of data.series||[]){const start=new Date(s.start).getTime(),pts=s.points;if(!pts.length)continue;const target=(targetMs-start)/1000;let lo=0,hi=pts.length-1;while(lo<hi){const mid=(lo+hi)>>1;if(pts[mid][0]<target)lo=mid+1;else hi=mid}for(const idx of[lo-1,lo,lo+1]){if(idx<0||idx>=pts.length)continue;const t=start+pts[idx][0]*1000,d=Math.abs(t-targetMs);if(d<bestDiff){bestDiff=d;best={time:t,value:pts[idx][1]}}}}const maxGap=Math.max(2500,(state.view[1]-state.view[0])/650);return bestDiff<=maxGap?best:null}
function drawTooltip(ctx,w,h,x,y,lines,color){ctx.font='12px Segoe UI';const pad=8,lineH=17,width=Math.max(...lines.map(s=>ctx.measureText(s).width))+pad*2,height=lines.length*lineH+pad*2-3;let bx=x+13,by=Math.max(6,y-height/2);if(bx+width>w-4)bx=x-width-13;if(by+height>h-4)by=h-height-4;ctx.fillStyle='rgba(8,13,19,.96)';ctx.strokeStyle=color;ctx.lineWidth=1;ctx.beginPath();ctx.roundRect(bx,by,width,height,7);ctx.fill();ctx.stroke();lines.forEach((s,i)=>{ctx.fillStyle=i===1?color:'#edf4fb';ctx.fillText(s,bx+pad,by+pad+12+i*lineH)})}
function drawHeroOverlay(){const canvas=$('#heroOverlay');if(!canvas||!state.summary)return;const{ctx,w,h}=setupCanvas(canvas);ctx.clearRect(0,0,w,h);const pr=plotRect(w,h),key=state.selectedSignal,data=state.mainSignal,yr=yRange(data,key,state.view);if(state.chartDrag){const x1=Math.min(state.chartDrag.startX,state.chartDrag.currentX),x2=Math.max(state.chartDrag.startX,state.chartDrag.currentX);ctx.fillStyle='rgba(85,183,255,.16)';ctx.fillRect(x1,pr.t,x2-x1,pr.h);ctx.strokeStyle='#55b7ff';ctx.strokeRect(x1,pr.t,x2-x1,pr.h)}if(state.hoverTime==null||state.hoverTime<state.view[0]||state.hoverTime>state.view[1])return;const x=xForTime(state.hoverTime,pr);ctx.save();ctx.strokeStyle='rgba(235,244,252,.78)';ctx.setLineDash([4,3]);ctx.beginPath();ctx.moveTo(x,pr.t);ctx.lineTo(x,pr.t+pr.h);ctx.stroke();ctx.restore();const p=nearestPoint(data,state.hoverTime),color=CHART_BY_KEY[key].color;if(p&&yr){const py=yForValue(p.value,pr,yr);ctx.fillStyle=color;ctx.beginPath();ctx.arc(x,py,3.5,0,Math.PI*2);ctx.fill();drawTooltip(ctx,w,h,x,state.hoverPointY||pr.t+30,[fmtDateTime(p.time),`${p.value.toFixed(decimalsFor(key))}${data?.unit?' '+unitText(data.unit,key):''}`],color)}else drawTooltip(ctx,w,h,x,state.hoverPointY||pr.t+30,[fmtDateTime(state.hoverTime),'Nincs adat – a készülék nem rögzített itt'],'#91a5b9')}

function drawStackChart(key){
  const canvas=$(`#stack-base-${key}`);if(!canvas||!state.summary)return;
  const data=(state.chartMode==='stack'?state.stackSignals.get(key):null)||state.overviewSignals.get(key),{ctx,w,h}=setupCanvas(canvas),pr=plotRect(w,h),yr=yRange(data,key,state.view);
  ctx.clearRect(0,0,w,h);ctx.fillStyle='#0e1620';ctx.fillRect(0,0,w,h);drawSessions(ctx,pr,state.view,.04);drawGrid(ctx,pr);
  if(yr&&data){drawYAxis(ctx,pr,yr,key);drawSeries(ctx,data,key,pr,yr,state.view,CHART_BY_KEY[key].color,1.05)}
  drawEventMarkers(ctx,pr,state.view,false);drawXAxis(ctx,pr);
}
function drawStackOverlay(key){
  const canvas=$(`#stack-overlay-${key}`);if(!canvas||!state.summary)return;
  const data=(state.chartMode==='stack'?state.stackSignals.get(key):null)||state.overviewSignals.get(key),{ctx,w,h}=setupCanvas(canvas),pr=plotRect(w,h),yr=yRange(data,key,state.view);
  ctx.clearRect(0,0,w,h);
  if(state.stackDrag?.key===key){const x1=Math.min(state.stackDrag.startX,state.stackDrag.currentX),x2=Math.max(state.stackDrag.startX,state.stackDrag.currentX);ctx.fillStyle='rgba(85,183,255,.14)';ctx.fillRect(x1,pr.t,x2-x1,pr.h);ctx.strokeStyle='#55b7ff';ctx.strokeRect(x1,pr.t,x2-x1,pr.h)}
  if(state.hoverTime==null||state.hoverTime<state.view[0]||state.hoverTime>state.view[1])return;
  const x=xForTime(state.hoverTime,pr);ctx.save();ctx.strokeStyle='rgba(235,244,252,.72)';ctx.setLineDash([4,3]);ctx.beginPath();ctx.moveTo(x,pr.t);ctx.lineTo(x,pr.t+pr.h);ctx.stroke();ctx.restore();
  const point=nearestPoint(data,state.hoverTime);if(point&&yr){const y=yForValue(point.value,pr,yr),color=CHART_BY_KEY[key].color;ctx.fillStyle=color;ctx.beginPath();ctx.arc(x,y,3,0,Math.PI*2);ctx.fill();const unit=data?.unit?' '+unitText(data.unit,key):'';ctx.font='10px Segoe UI';const txt=`${point.value.toFixed(decimalsFor(key))}${unit}`;const tw=ctx.measureText(txt).width;ctx.fillStyle='rgba(8,13,19,.88)';ctx.fillRect(Math.min(w-tw-10,x+6),Math.max(2,y-17),tw+8,15);ctx.fillStyle=color;ctx.fillText(txt,Math.min(w-tw-6,x+10),Math.max(12,y-6))}
}
function drawStackedAll(){if(state.chartMode!=='stack')return;for(const c of CHARTS){drawStackChart(c.key);drawStackOverlay(c.key)}}
function chartZoomed(){const full=state.full[1]-state.full[0],span=state.view[1]-state.view[0];return full>0&&span<full-1000}
function panChartTouch(startView,dx,width){if(!chartZoomed()||!width)return false;const span=startView[1]-startView[0],shift=-(dx/width)*span,stateNext=clampRange(startView[0]+shift,startView[1]+shift);state.view=stateNext;state.hoverTime=null;state.navPreview=null;drawAll();return true}
function beginTouchPinch(canvas,pointers,pr){const pts=[...pointers.values()];if(pts.length<2)return null;const r=canvas.getBoundingClientRect(),dist=Math.hypot(pts[1].x-pts[0].x,pts[1].y-pts[0].y)||1,center=((pts[0].x+pts[1].x)/2)-r.left;return{dist,view:[...state.view],centerTime:timeForX(center,pr)}}
function moveTouchPinch(canvas,pointers,pinch,pr){if(!pinch)return pinch;const pts=[...pointers.values()];if(pts.length<2)return pinch;const dist=Math.hypot(pts[1].x-pts[0].x,pts[1].y-pts[0].y)||1,scale=pinch.dist/dist,span=Math.max(15000,(pinch.view[1]-pinch.view[0])*scale),ratio=(pinch.centerTime-pinch.view[0])/(pinch.view[1]-pinch.view[0]||1);state.view=clampRange(pinch.centerTime-span*ratio,pinch.centerTime+span*(1-ratio));state.hoverTime=pinch.centerTime;drawAll();return pinch}
function setupStackInteraction(key){
  const canvas=$(`#stack-overlay-${key}`);if(!canvas)return;const pointers=new Map();let pinch=null,touchStart=null,touchMoved=false,panned=false;
  const update=e=>{if(!state.summary)return;const r=canvas.getBoundingClientRect(),pr=plotRect(r.width,r.height),x=canvasX(e,canvas);if(x<pr.l||x>pr.l+pr.w)return;state.hoverTime=timeForX(x,pr);state.hoverPointY=e.clientY-r.top;if(state.stackDrag?.key===key)state.stackDrag.currentX=Math.max(pr.l,Math.min(pr.l+pr.w,x));scheduleOverlayRender()};
  canvas.addEventListener('pointerdown',e=>{if(e.button!==0||!state.summary)return;const r=canvas.getBoundingClientRect(),pr=plotRect(r.width,r.height),x=canvasX(e,canvas);if(x<pr.l||x>pr.l+pr.w)return;try{canvas.setPointerCapture(e.pointerId)}catch{};if(e.pointerType==='touch'){pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});if(pointers.size===1){touchStart={x:e.clientX,y:e.clientY,view:[...state.view],width:pr.w};touchMoved=false;panned=false;update(e)}else if(pointers.size===2){pinch=beginTouchPinch(canvas,pointers,pr);touchMoved=true}return}update(e);state.stackDrag={key,startX:x,currentX:x,pr,pointerId:e.pointerId}});
  canvas.addEventListener('pointermove',e=>{if(e.pointerType==='touch'){if(!pointers.has(e.pointerId))return;pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});const r=canvas.getBoundingClientRect(),pr=plotRect(r.width,r.height);if(pointers.size>=2){pinch=moveTouchPinch(canvas,pointers,pinch||beginTouchPinch(canvas,pointers,pr),pr);touchMoved=true;return}if(touchStart){const dx=e.clientX-touchStart.x,dy=e.clientY-touchStart.y;if(Math.hypot(dx,dy)>7)touchMoved=true;if(chartZoomed()&&Math.abs(dx)>Math.abs(dy)*.75&&Math.abs(dx)>5){panned=panChartTouch(touchStart.view,dx,touchStart.width);return}}update(e);return}update(e)});
  const endTouch=e=>{pointers.delete(e.pointerId);try{canvas.releasePointerCapture(e.pointerId)}catch{};if(pointers.size<2)pinch=null};
  canvas.addEventListener('pointerup',e=>{if(e.pointerType==='touch'){const hadPinch=!!pinch||pointers.size>1;endTouch(e);if(!hadPinch&&!touchMoved)handleChartDoubleTap(()=>setView(state.full[0],state.full[1],true));if(panned)scheduleWheelSignalReload();if(!pointers.size){touchStart=null;pinch=null}return}const d=state.stackDrag;if(!d||d.key!==key)return;state.stackDrag=null;try{canvas.releasePointerCapture(e.pointerId)}catch{}if(Math.abs(d.currentX-d.startX)>=8){const a=timeForX(Math.min(d.startX,d.currentX),d.pr),b=timeForX(Math.max(d.startX,d.currentX),d.pr);setView(a,b,true)}else scheduleOverlayRender()});
  canvas.addEventListener('pointercancel',e=>{if(e.pointerType==='touch'){endTouch(e);touchStart=null;state.hoverTime=null;scheduleOverlayRender()}});canvas.addEventListener('pointerleave',e=>{if(e.pointerType!=='touch'&&!state.stackDrag){state.hoverTime=null;scheduleOverlayRender()}});canvas.addEventListener('dblclick',()=>setView(state.full[0],state.full[1],true));
}

function drawNavigator(){const canvas=$('#navigator');if(!canvas||!state.summary)return;const{ctx,w,h}=setupCanvas(canvas),pr={l:54,r:12,t:8,b:21,w:w-66,h:h-29};ctx.clearRect(0,0,w,h);ctx.fillStyle='#0b121a';ctx.fillRect(pr.l,pr.t,pr.w,pr.h);drawGrid(ctx,pr);drawSessions(ctx,pr,state.full,.18);drawEventMarkers(ctx,pr,state.full,false);const selection=state.navPreview||state.view,x1=xForTime(selection[0],pr,state.full),x2=xForTime(selection[1],pr,state.full);ctx.fillStyle='rgba(85,183,255,.12)';ctx.fillRect(x1,pr.t,x2-x1,pr.h);ctx.strokeStyle='#55b7ff';ctx.lineWidth=2;ctx.strokeRect(x1,pr.t,x2-x1,pr.h);ctx.fillStyle='#55b7ff';ctx.fillRect(x1-3,pr.t,6,pr.h);ctx.fillRect(x2-3,pr.t,6,pr.h);drawXAxis(ctx,pr,state.full)}
function eventLaneTypes(){const present=new Set((state.summary?.events||[]).map(e=>e.type));const order=['OA','CA','H','UA','RERA','CSR','OTHER'];const lanes=order.filter(k=>present.has(k));return lanes.length?lanes:['OA','CA','H','RERA']}
function eventPlotRect(w,h){return{l:82,r:12,t:8,b:25,w:w-94,h:h-33}}
function drawEventsBase(){
  const canvas=$('#eventsBase');if(!canvas||!state.summary)return;const{ctx,w,h}=setupCanvas(canvas),pr=eventPlotRect(w,h),lanes=eventLaneTypes();
  ctx.clearRect(0,0,w,h);ctx.fillStyle='#0e1620';ctx.fillRect(0,0,w,h);drawSessions(ctx,pr,state.view,.055);
  const rowH=pr.h/lanes.length;ctx.font='10px Segoe UI';
  lanes.forEach((type,i)=>{const y=pr.t+i*rowH;ctx.fillStyle=i%2?'rgba(255,255,255,.012)':'rgba(255,255,255,.028)';ctx.fillRect(pr.l,y,pr.w,rowH);ctx.strokeStyle='#263647';ctx.beginPath();ctx.moveTo(pr.l,y+rowH);ctx.lineTo(pr.l+pr.w,y+rowH);ctx.stroke();const m=EVENT_TYPES[type]||EVENT_TYPES.OTHER;ctx.fillStyle=m.color;ctx.fillText(type,10,y+rowH/2+3);const typeW=ctx.measureText(type).width;ctx.fillStyle='#8498ab';ctx.font='9px Segoe UI';const maxNameW=Math.max(18,pr.l-(20+typeW));let nm=m.name;while(nm.length>4&&ctx.measureText(nm).width>maxNameW)nm=nm.slice(0,-2);if(nm!==m.name)nm=nm.replace(/\s+$/,'')+'…';ctx.fillText(nm,18+typeW,y+rowH/2+3);ctx.font='10px Segoe UI'});
  for(const e of state.summary.events){const t=new Date(e.time).getTime();if(t<state.view[0]||t>state.view[1])continue;const lane=lanes.indexOf(e.type);if(lane<0)continue;const m=EVENT_TYPES[e.type]||EVENT_TYPES.OTHER,x=xForTime(t,pr),y=pr.t+(lane+.5)*rowH;ctx.strokeStyle=m.color;ctx.fillStyle=m.color;ctx.lineWidth=2;const dur=Math.max(0,Number(e.duration_s)||0)*1000;if(dur>0){const x2=xForTime(Math.min(state.view[1],t+dur),pr);ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(Math.max(x+2,x2),y);ctx.stroke()}ctx.beginPath();ctx.arc(x,y,4,0,Math.PI*2);ctx.fill()}
  drawXAxis(ctx,pr);
}
function drawEventsOverlay(){const canvas=$('#eventsOverlay');if(!canvas||!state.summary)return;const{ctx,w,h}=setupCanvas(canvas);ctx.clearRect(0,0,w,h);if(state.hoverTime==null||state.hoverTime<state.view[0]||state.hoverTime>state.view[1])return;const pr=eventPlotRect(w,h),x=xForTime(state.hoverTime,pr);ctx.save();ctx.strokeStyle='rgba(235,244,252,.72)';ctx.setLineDash([4,3]);ctx.beginPath();ctx.moveTo(x,pr.t);ctx.lineTo(x,pr.t+pr.h);ctx.stroke();ctx.restore()}
function updateViewInfo(){const[a,b]=state.view,full=Math.abs(a-state.full[0])<1000&&Math.abs(b-state.full[1])<1000;$('#viewInfo').textContent=full?`Teljes időtartomány • ${fmtClock(a,false)} – ${fmtClock(b,false)} • ${formatSpan(b-a)}`:`Nagyított nézet • ${fmtClock(a)} – ${fmtClock(b)} • ${formatSpan(b-a)}`;$('#cursorInfo').textContent=state.hoverTime==null?'Kurzor: –':`Kurzor: ${fmtClock(state.hoverTime)}`}
function drawAll(){if(!state.summary)return;updateHeroHeader();updateViewInfo();drawHeroBase();drawHeroOverlay();drawNavigator();drawEventsBase();drawEventsOverlay();for(const c of CHARTS)drawMini(c.key);drawStackedAll()}
function renderOverlays(){updateViewInfo();drawHeroOverlay();drawEventsOverlay();if(state.chartMode==='stack')for(const c of CHARTS)drawStackOverlay(c.key)}
function scheduleOverlayRender(){if(state.overlayRaf)return;state.overlayRaf=requestAnimationFrame(()=>{state.overlayRaf=0;renderOverlays()})}

function scheduleWheelSignalReload(){clearTimeout(state.wheelReloadTimer);state.wheelReloadTimer=setTimeout(()=>{state.wheelReloadTimer=0;loadMainSignal();loadOverviewSignals();if(state.chartMode==='stack')loadStackSignals()},110)}
function panHeroWithWheel(e,canvas){
  if(!state.summary)return;
  const r=canvas.getBoundingClientRect(),pr=plotRect(r.width,r.height),x=e.clientX-r.left,y=e.clientY-r.top;
  // The wheel is captured only inside the actual large plot area. Everywhere else the page scrolls normally.
  if(x<pr.l||x>pr.l+pr.w||y<pr.t||y>pr.t+pr.h)return;
  const fullSpan=state.full[1]-state.full[0],span=state.view[1]-state.view[0];
  // When the whole night already fits on screen there is nowhere to pan, so keep normal page scrolling.
  if(fullSpan<=0||span>=fullSpan-1000)return;
  let delta=Math.abs(e.deltaX)>Math.abs(e.deltaY)?e.deltaX:e.deltaY;
  if(!delta)return;
  if(e.deltaMode===1)delta*=16;else if(e.deltaMode===2)delta*=Math.max(240,r.height);
  e.preventDefault();
  const strength=Math.max(-2.5,Math.min(2.5,delta/100));
  const shift=span*.08*strength; // wheel down -> later/right, wheel up -> earlier/left
  const next=clampRange(state.view[0]+shift,state.view[1]+shift);
  if(Math.abs(next[0]-state.view[0])<1&&Math.abs(next[1]-state.view[1])<1)return;
  state.view=next;state.hoverTime=null;state.navPreview=null;drawAll();scheduleWheelSignalReload();
}
function handleChartDoubleTap(fn){const now=Date.now();if(now-state.touchTapAt<330){state.touchTapAt=0;fn()}else state.touchTapAt=now}
function setupHeroInteraction(){
  const canvas=$('#heroOverlay');const pointers=new Map();let pinch=null,touchStart=null,touchMoved=false,panned=false;
  canvas.addEventListener('wheel',e=>panHeroWithWheel(e,canvas),{passive:false});
  const update=e=>{if(!state.summary)return;const r=canvas.getBoundingClientRect(),pr=plotRect(r.width,r.height),x=canvasX(e,canvas);if(x<pr.l||x>pr.l+pr.w)return;state.hoverTime=timeForX(x,pr);state.hoverPointY=e.clientY-r.top;if(state.chartDrag)state.chartDrag.currentX=Math.max(pr.l,Math.min(pr.l+pr.w,x));scheduleOverlayRender()};
  canvas.addEventListener('pointerdown',e=>{if(e.button!==0||!state.summary)return;try{canvas.setPointerCapture(e.pointerId)}catch{};const r=canvas.getBoundingClientRect(),pr=plotRect(r.width,r.height),x=canvasX(e,canvas);if(x<pr.l||x>pr.l+pr.w)return;if(e.pointerType==='touch'){pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});state.touchPointers=pointers;if(pointers.size===1){touchStart={x:e.clientX,y:e.clientY,view:[...state.view],width:pr.w};touchMoved=false;panned=false;update(e)}else if(pointers.size===2){pinch=beginTouchPinch(canvas,pointers,pr);state.touchPinch=pinch;touchMoved=true}return}state.chartDrag={startX:x,currentX:x,pr,pointerId:e.pointerId}});
  canvas.addEventListener('pointermove',e=>{if(e.pointerType==='touch'){if(!pointers.has(e.pointerId))return;pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});const r=canvas.getBoundingClientRect(),pr=plotRect(r.width,r.height);if(pointers.size>=2){pinch=moveTouchPinch(canvas,pointers,pinch||beginTouchPinch(canvas,pointers,pr),pr);state.touchPinch=pinch;touchMoved=true;return}if(touchStart){const dx=e.clientX-touchStart.x,dy=e.clientY-touchStart.y;if(Math.hypot(dx,dy)>7)touchMoved=true;if(chartZoomed()&&Math.abs(dx)>Math.abs(dy)*.75&&Math.abs(dx)>5){panned=panChartTouch(touchStart.view,dx,touchStart.width);return}}update(e);return}update(e)});
  const endTouch=e=>{pointers.delete(e.pointerId);try{canvas.releasePointerCapture(e.pointerId)}catch{};if(pointers.size<2){pinch=null;state.touchPinch=null}};
  canvas.addEventListener('pointerup',e=>{if(e.pointerType==='touch'){const hadPinch=!!pinch||pointers.size>1;endTouch(e);if(!hadPinch&&!touchMoved)handleChartDoubleTap(()=>setView(state.full[0],state.full[1],true));if(panned)scheduleWheelSignalReload();if(!pointers.size)touchStart=null;return}const d=state.chartDrag;if(!d)return;state.chartDrag=null;try{canvas.releasePointerCapture(e.pointerId)}catch{}if(Math.abs(d.currentX-d.startX)>=8){const a=timeForX(Math.min(d.startX,d.currentX),d.pr),b=timeForX(Math.max(d.startX,d.currentX),d.pr);setView(a,b,true)}else scheduleOverlayRender()});
  canvas.addEventListener('pointercancel',e=>{if(e.pointerType==='touch'){endTouch(e);touchStart=null;state.hoverTime=null;scheduleOverlayRender()}});canvas.addEventListener('pointerleave',e=>{if(e.pointerType!=='touch'&&!state.chartDrag){state.hoverTime=null;scheduleOverlayRender()}});canvas.addEventListener('dblclick',()=>setView(state.full[0],state.full[1],true));
}
function beginHeroPinch(canvas){const pts=[...state.touchPointers.values()];if(pts.length<2)return;const r=canvas.getBoundingClientRect(),pr=plotRect(r.width,r.height),dist=Math.hypot(pts[1].x-pts[0].x,pts[1].y-pts[0].y)||1,center=((pts[0].x+pts[1].x)/2)-r.left;state.touchPinch={dist,view:[...state.view],centerTime:timeForX(center,pr)}}
function handleHeroPinch(canvas){const p=state.touchPinch;if(!p){beginHeroPinch(canvas);return}const pts=[...state.touchPointers.values()];if(pts.length<2)return;const dist=Math.hypot(pts[1].x-pts[0].x,pts[1].y-pts[0].y)||1,scale=p.dist/dist,span=(p.view[1]-p.view[0])*scale,ratio=(p.centerTime-p.view[0])/(p.view[1]-p.view[0]||1);state.view=clampRange(p.centerTime-span*ratio,p.centerTime+span*(1-ratio));state.hoverTime=p.centerTime;drawAll()}

function setupEventsInteraction(){const canvas=$('#eventsOverlay');const update=e=>{if(!state.summary)return;const r=canvas.getBoundingClientRect(),pr=eventPlotRect(r.width,r.height),x=canvasX(e,canvas);if(x<pr.l||x>pr.l+pr.w)return;state.hoverTime=timeForX(x,pr);scheduleOverlayRender()};canvas.addEventListener('pointermove',update);canvas.addEventListener('pointerdown',e=>{if(e.pointerType==='touch'){try{canvas.setPointerCapture(e.pointerId)}catch{};update(e)}});canvas.addEventListener('pointerleave',e=>{if(e.pointerType!=='touch'){state.hoverTime=null;scheduleOverlayRender()}});canvas.addEventListener('click',e=>{if(!state.summary?.events?.length)return;const r=canvas.getBoundingClientRect(),pr=eventPlotRect(r.width,r.height),x=canvasX(e,canvas);if(x<pr.l||x>pr.l+pr.w)return;const t=timeForX(x,pr);let best=null,diff=Infinity;for(const ev of state.summary.events){const et=new Date(ev.time).getTime();if(et<state.view[0]||et>state.view[1])continue;const d=Math.abs(et-t);if(d<diff){diff=d;best=ev}}if(best&&diff<(state.view[1]-state.view[0])/40)zoomEvent(best)})}
function navPlot(canvas){const r=canvas.getBoundingClientRect();return{l:54,r:12,t:8,b:21,w:r.width-66,h:r.height-29}}
function setupNavigatorInteraction(){const canvas=$('#navigator');canvas.addEventListener('pointerdown',e=>{if(!state.summary||e.button!==0)return;const pr=navPlot(canvas),x=canvasX(e,canvas);if(x<pr.l||x>pr.l+pr.w)return;const sx1=xForTime(state.view[0],pr,state.full),sx2=xForTime(state.view[1],pr,state.full);let mode='new';if(Math.abs(x-sx1)<10)mode='left';else if(Math.abs(x-sx2)<10)mode='right';else if(x>sx1&&x<sx2)mode='pan';canvas.setPointerCapture(e.pointerId);state.navDrag={mode,startX:x,startView:[...state.view],pr,pointerId:e.pointerId};state.navPreview=[...state.view]});canvas.addEventListener('pointermove',e=>{const d=state.navDrag;if(!d)return;const x=Math.max(d.pr.l,Math.min(d.pr.l+d.pr.w,canvasX(e,canvas))),t=timeForX(x,d.pr,state.full);let a=d.startView[0],b=d.startView[1];if(d.mode==='left')a=t;else if(d.mode==='right')b=t;else if(d.mode==='pan'){const t0=timeForX(d.startX,d.pr,state.full),delta=t-t0;a+=delta;b+=delta}else{const t0=timeForX(d.startX,d.pr,state.full);a=Math.min(t0,t);b=Math.max(t0,t)}state.navPreview=clampRange(a,b);requestAnimationFrame(drawNavigator)});canvas.addEventListener('pointerup',e=>{if(!state.navDrag)return;try{canvas.releasePointerCapture(e.pointerId)}catch{}const p=state.navPreview;state.navDrag=null;state.navPreview=null;if(p)setView(p[0],p[1],true)});canvas.addEventListener('dblclick',()=>setView(state.full[0],state.full[1],true))}

async function loadSessionsPage(){
  clearError();updateMeasurementEmptyStates();if(!state.days.length)return;try{const rows=await loadDayRows();renderSessionsTable(rows);$('#daysCount').textContent=rows.length;$('#avgUsage').textContent=secondsToHM(avg(rows.map(x=>x.therapy_seconds)));$('#avgAhi').textContent=avg(rows.map(x=>Number(x.ahi)||0)).toFixed(2);$('#healthyDays').textContent=`${rows.filter(x=>x.integrity?.complete).length}/${rows.length}`;await renderDashboardCalendar(false)}
  catch(e){showError(e)}
}
function renderSessionsTable(rows){const body=$('#sessionsTableBody');body.innerHTML=rows.length?rows.map(r=>`<tr class="click-row" data-day="${r.day}"><td><strong>${dayCodeToIso(r.day)}</strong>${r.integrity?.complete?'':' <span class="warn-dot">●</span>'}</td><td>${formatUsageShort(r.usage)}</td><td>${Number(r.ahi).toFixed(2)}</td><td>${r.events}</td><td>${r.counts.OA||0}</td><td>${r.counts.CA||0}</td><td>${r.counts.H||0}</td><td>${r.counts.RERA||0}</td><td class="col-spo2">${r.spo2!=null?r.spo2+'%':'—'}</td><td class="col-hr">${r.hr!=null?r.hr:'—'}</td><td><button class="row-action" data-open="${r.day}">Megnyitás</button></td></tr>`).join(''):'<tr><td colspan="11">Nincs adat.</td></tr>';body.querySelectorAll('tr[data-day]').forEach(tr=>tr.onclick=e=>{if(e.target.closest('button'))return;navigate('dashboard',tr.dataset.day)});body.querySelectorAll('[data-open]').forEach(b=>b.onclick=e=>{e.stopPropagation();navigate('dashboard',b.dataset.open)});applyOximetryVisibility()}

async function loadEventsPage(day){
  if(!day||!state.days.length){updateMeasurementEmptyStates();return;}$('#eventsDay').value=day;try{const s=await api(`/api/day/${day}`);const body=$('#eventsTableBody');body.innerHTML=s.events.length?s.events.map((e,i)=>{const m=EVENT_TYPES[e.type]||EVENT_TYPES.OTHER;return`<tr><td>${fmtClock(e.time)}</td><td><span class="type-pill" style="--type:${m.color}">${eventTypeLabel(e.type,m)}</span></td><td>${e.duration_s?Number(e.duration_s).toFixed(0)+' mp':'—'}</td><td><div class="event-description-cell"><span>${escapeHtml(m.short||e.description||'—')}</span><button class="info-dot" type="button" aria-label="Információ: ${escapeHtml(m.name)}" data-info="${escapeHtml(m.info||m.short||'')}">i</button></div></td><td><button class="row-action event-open" data-i="${i}">Dashboard</button></td></tr>`}).join(''):'<tr><td colspan="5">Nincs esemény ezen a napon.</td></tr>';body.querySelectorAll('.event-open').forEach(b=>b.onclick=()=>{const ev=s.events[+b.dataset.i];state.pendingEventFocus={day,event:ev};state.currentDay=day;navigate('dashboard',day)});wireInfoDots(body)}catch(e){showError(e)}
}
function wireInfoDots(root=document){root.querySelectorAll('.info-dot').forEach(b=>{b.onmouseenter=()=>showInfoBubble(b,b.dataset.info||'');b.onfocus=()=>showInfoBubble(b,b.dataset.info||'');b.onmouseleave=hideInfoBubble;b.onblur=hideInfoBubble;b.onclick=e=>{e.stopPropagation();showInfoBubble(b,b.dataset.info||'',true)}})}
function showInfoBubble(anchor,text,persist=false){let el=$('#globalInfoBubble');if(!el){el=document.createElement('div');el.id='globalInfoBubble';el.className='info-bubble hidden';document.body.appendChild(el)}el.textContent=text;const r=anchor.getBoundingClientRect();el.style.left=`${Math.min(window.innerWidth-330,Math.max(10,r.left-280))}px`;el.style.top=`${Math.min(window.innerHeight-120,r.bottom+7)}px`;el.classList.remove('hidden');el.dataset.persist=persist?'1':'0'}
function hideInfoBubble(){const el=$('#globalInfoBubble');if(el&&el.dataset.persist!=='1')el.classList.add('hidden')}
document.addEventListener('click',e=>{const el=$('#globalInfoBubble');if(el&&!e.target.closest('.info-dot')){el.dataset.persist='0';el.classList.add('hidden')}});

async function prepareReports(){
  updateMeasurementEmptyStates();if(!state.days.length)return;try{const rows=await loadDayRows();if(!rows.length)return;const dates=rows.map(r=>r.day).sort();const from=$('#reportFrom'),to=$('#reportTo');if(!from.value)from.value=dayCodeToIso(dates[0]);if(!to.value)to.value=dayCodeToIso(dates.at(-1));applyReportRange()}catch(e){showError(e)}
}
function applyReportRange(){const a=isoToDayCode($('#reportFrom').value),b=isoToDayCode($('#reportTo').value);const lo=a&&b&&a>b?b:a,hi=a&&b&&a>b?a:b;state.reportRows=state.dayRows.filter(r=>(!lo||r.day>=lo)&&(!hi||r.day<=hi));$('#reportRangeInfo').textContent=`${state.reportRows.length} nap a kiválasztott időszakban.`;$('#reportCount').textContent=`${state.reportRows.length} nap`;$('#reportDaysBody').innerHTML=state.reportRows.map(r=>`<tr class="click-row report-row" data-day="${r.day}"><td>${dayCodeToIso(r.day)}</td><td>${formatUsageShort(r.usage)}</td><td>${Number(r.ahi).toFixed(2)}</td><td>${r.events}</td><td>${r.counts.OA||0}</td><td>${r.counts.CA||0}</td><td>${r.counts.H||0}</td><td>${r.counts.RERA||0}</td></tr>`).join('')||'<tr><td colspan="8">Nincs nap a tartományban.</td></tr>';const sel=$('#reportDay');sel.innerHTML='';state.reportRows.forEach(r=>sel.add(new Option(dayCodeToIso(r.day),r.day)));$('#reportDaysBody').querySelectorAll('.report-row').forEach(tr=>tr.onclick=()=>{sel.value=tr.dataset.day;loadReportStats(tr.dataset.day)});if(state.reportRows.length){const preferred=state.reportRows.some(r=>r.day===state.currentDay)?state.currentDay:state.reportRows[0].day;sel.value=preferred;loadReportStats(preferred)}else{$('#statsBody').innerHTML='<tr><td colspan="6">Nincs kiválasztott nap.</td></tr>';$('#apneaTime').textContent='–'}}
async function loadReportStats(day){if(!day)return;try{const st=await api(`/api/day/${day}/stats`);$('#apneaTime').textContent=`Teljes apnoe-idő: ${st.apnea_duration}`;$('#statsBody').innerHTML=st.rows.length?st.rows.map(r=>`<tr><td>${r.title}</td><td>${formatStat(r.min,r.key,r.unit)}</td><td>${formatStat(r.median,r.key,r.unit)}</td><td>${formatStat(r.p95,r.key,r.unit)}</td><td>${formatStat(r.p995,r.key,r.unit)}</td><td>${formatStat(r.max,r.key,r.unit)}</td></tr>`).join(''):'<tr><td colspan="6">Nincs statisztikai adat.</td></tr>'}catch(e){showError(e)}}


const REPORT_PRESETS={
  standard:['summary','usage','events','pressure_leak','timeline','calendar','data_quality','glossary'],
  detailed:['summary','usage','events','pressure_leak','comparison','timeline','calendar','assessments','equipment','diagnosis','data_quality','daily_table','glossary']
};
function updateReportOptionCards(){
  $$('.report-mode-card').forEach(x=>x.classList.toggle('selected',!!x.querySelector('input:checked')));
  $$('.report-theme-options label').forEach(x=>x.classList.toggle('selected',!!x.querySelector('input:checked')));
}
async function openReportPdfModal(){
  state.pendingReportPdf=null;const save=$('#reportPdfSave');if(save){save.classList.add('hidden');save.disabled=true}
  if(!state.reportRows?.length){showError(new Error('A kiválasztott időszakban nincs PDF-be foglalható terápiás adat.'));return}
  $('#reportPdfFrom').value=$('#reportFrom').value;
  $('#reportPdfTo').value=$('#reportTo').value;
  if(!state.patient)try{state.patient=await api('/api/patient')}catch{}
  const hasPatient=!!state.patient?.profile;
  $('#reportIncludePatient').disabled=!hasPatient;
  $('#reportPatientStatus').textContent=hasPatient?'A közvetlen azonosítók kikapcsolhatók egy kattintással.':'Még nincs létrehozva kezelt személy.';
  if(!hasPatient)$('#reportIncludePatient').checked=false;
  updateReportPatientOptions();
  updateReportOptionCards();
  setReportPdfStatus('ready','Készen áll a generálásra.');
  $('#reportPdfModal').classList.remove('hidden');
}
function closeReportPdfModal(){$('#reportPdfModal').classList.add('hidden')}
function updateReportPatientOptions(){$('#reportPatientOptions').classList.toggle('hidden',!$('#reportIncludePatient').checked)}
function applyReportAnonymizedPreset(){
  $('#reportIncludePatient').checked=true;updateReportPatientOptions();
  const direct=new Set(['name','birth_date','taj','doctor','institution']);
  $$('[data-patient-field]').forEach(x=>{x.checked=!direct.has(x.dataset.patientField)});
  $('#reportPatientStatus').textContent='Anonimizált: név, születési dátum, TAJ, orvos és intézmény kikapcsolva.';
}
function applyReportModePreset(){
  updateReportOptionCards();
  const mode=document.querySelector('input[name="reportMode"]:checked')?.value||'standard';
  if(mode==='custom')return;
  const enabled=new Set(REPORT_PRESETS[mode]||[]);
  $$('[data-report-section]').forEach(x=>x.checked=enabled.has(x.dataset.reportSection));
  if(mode==='detailed')$('#reportComparePrevious').checked=true;
}
function collectReportConfig(){
  const sections=$$('[data-report-section]:checked').map(x=>x.dataset.reportSection);
  if($('#reportComparePrevious').checked&&!sections.includes('comparison'))sections.push('comparison');
  return{
    mode:document.querySelector('input[name="reportMode"]:checked')?.value||'standard',
    theme:document.querySelector('input[name="reportTheme"]:checked')?.value||'sleepmate',
    include_patient:$('#reportIncludePatient').checked,
    patient_fields:$$('[data-patient-field]:checked').map(x=>x.dataset.patientField),
    compare_previous:$('#reportComparePrevious').checked,
    sections
  };
}
function setReportPdfStatus(kind,text){const el=$('#reportPdfStatus');el.classList.remove('busy','error');if(kind==='busy')el.classList.add('busy');if(kind==='error')el.classList.add('error');el.querySelector('span:last-child').textContent=text}
function isApplePwa(){return /iPad|iPhone|iPod/.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1)||window.navigator.standalone===true||window.matchMedia?.('(display-mode: standalone)').matches}
async function saveGeneratedReportPdf(){
  const file=state.pendingReportPdf,btn=$('#reportPdfSave');
  if(!file){setReportPdfStatus('error','Nincs mentésre váró PDF. Generáld újra a jelentést.');return}
  try{
    btn.disabled=true;
    if(navigator.share&&(!navigator.canShare||navigator.canShare({files:[file]}))){
      await navigator.share({files:[file],title:file.name,text:'SleepMate PAP-terápiás jelentés'});
      setReportPdfStatus('ready','A PDF átadva az iOS mentési/megosztási ablakának.');
      addLog('INFO',`PDF jelentés mentési lap megnyitva: ${file.name}.`);
      return;
    }
    const url=URL.createObjectURL(file),a=document.createElement('a');a.href=url;a.download=file.name;a.target='_blank';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
    setReportPdfStatus('ready','A PDF megnyitva. A böngésző menüjéből mentsd a fájlt.');
  }catch(e){
    if(e?.name==='AbortError'){setReportPdfStatus('ready','A mentést megszakítottad. A PDF továbbra is készen áll.');return}
    setReportPdfStatus('error',e.message||'A PDF mentési ablak nem nyitható meg.');showError(e)
  }finally{btn.disabled=false}
}
async function generateReportPdf(preview=false){
  const start=$('#reportPdfFrom').value,end=$('#reportPdfTo').value;
  if(!start||!end){setReportPdfStatus('error','Add meg a jelentés időszakát.');return}
  const config=collectReportConfig();
  if(!config.sections.length){setReportPdfStatus('error','Válassz legalább egy jelentésblokkot.');return}
  const btns=[$('#reportPdfPreview'),$('#reportPdfGenerate')];btns.forEach(b=>b.disabled=true);
  let win=null;if(preview)win=window.open('about:blank','_blank');
  setReportPdfStatus('busy',preview?'PDF előnézet készítése…':'PDF generálása…');
  try{
    const r=await fetch('/api/report/pdf',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({start,end,config,preview}),cache:'no-store'});
    if(!r.ok){let msg=`HTTP ${r.status}`;try{const j=await r.json();msg=j.error||msg}catch{}throw new Error(msg)}
    const blob=await r.blob(),url=URL.createObjectURL(blob);
    if(preview){if(win)win.location=url;else window.open(url,'_blank');setTimeout(()=>URL.revokeObjectURL(url),60000);setReportPdfStatus('ready','Előnézet elkészült.');}
    else{
      const cd=r.headers.get('content-disposition')||'',m=cd.match(/filename="([^"]+)"/),name=m?.[1]||`SleepMate_PAP_jelentes_${start}-${end}.pdf`;
      const file=new File([blob],name,{type:'application/pdf'});
      if(isApplePwa()){
        URL.revokeObjectURL(url);
        state.pendingReportPdf=file;
        const save=$('#reportPdfSave');save.classList.remove('hidden');save.disabled=false;
        setReportPdfStatus('ready','PDF elkészült. Koppints a „Mentés a Fájlokba” gombra.');
        addLog('INFO',`PDF jelentés elkészült, iOS mentésre vár: ${start} – ${end}.`);
      }else{
        const a=document.createElement('a');a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),2000);
        setReportPdfStatus('ready','PDF elkészült és letöltve.');addLog('INFO',`PDF jelentés elkészült: ${start} – ${end}.`)
      }
    }
  }catch(e){if(win)try{win.close()}catch{}setReportPdfStatus('error',e.message||'A PDF generálása sikertelen.');showError(e)}
  finally{btns.forEach(b=>b.disabled=false)}
}



async function loadEquipmentCatalog(){
  if(state.equipmentCatalogLoaded)return state.equipmentCatalog;
  try{
    const r=await fetch(`/equipment_catalog.json?_=${Date.now()}`,{cache:'no-store'});
    if(!r.ok)throw new Error('A felszerelési adatbázis nem tölthető be.');
    state.equipmentCatalog=await r.json();state.equipmentCatalogLoaded=true;
  }catch(e){
    state.equipmentCatalog={machines:[],accessories:[],masks:[],lists:{}};state.equipmentCatalogLoaded=true;addLog('WARN',e.message||String(e));
  }
  return state.equipmentCatalog;
}
function catalogRows(kind){
  const c=state.equipmentCatalog||{};
  return kind==='device'?(c.machines||[]):kind==='mask'?(c.masks||[]):kind==='accessory'?(c.accessories||[]):[];
}
function catalogManufacturer(row){return row?.manufacturer||''}
function catalogModel(row,kind){return kind==='accessory'?(row?.accessory_model||''):(row?.model||'')}
function splitCatalogSizes(v){
  return String(v||'').split('/').map(x=>x.trim()).filter(Boolean).map(x=>x.replace(/\s*\([^)]*\)\s*/g,'').trim()).filter(Boolean);
}
function maskSizeOptions(row=null,manufacturer=''){
  const mf=String(manufacturer||row?.manufacturer||'').trim();
  const exact=splitCatalogSizes(row?.sizes||'');
  // ResMed: az SW mindig választható. A modell-specifikus katalóguslista ezt többé nem írhatja felül.
  if(normalizeFaqText(mf)===normalizeFaqText('ResMed'))return uniqueSorted(['SW',...exact]);
  return uniqueSorted(exact);
}
function uniqueSorted(values){return [...new Set(values.filter(Boolean))].sort((a,b)=>String(a).localeCompare(String(b),'hu'))}
function catalogOptions(kind,field,manufacturer=''){
  let rows=catalogRows(kind);
  if(manufacturer)rows=rows.filter(r=>normalizeFaqText(catalogManufacturer(r))===normalizeFaqText(manufacturer));
  if(field==='manufacturer')return uniqueSorted(rows.map(catalogManufacturer));
  if(field==='model')return uniqueSorted(rows.map(r=>catalogModel(r,kind)));
  if(kind==='mask'&&field==='category')return uniqueSorted(rows.map(r=>r.mask_category));
  if(kind==='mask'&&field==='size'){const sizes=rows.flatMap(r=>splitCatalogSizes(r.sizes));if(normalizeFaqText(manufacturer)===normalizeFaqText('ResMed'))sizes.unshift('SW');return uniqueSorted(sizes)}
  if(kind==='accessory'&&field==='category')return uniqueSorted(rows.map(r=>r.category));
  return[];
}
function setDatalistOptions(id,values){const dl=document.getElementById(id);if(dl)dl.innerHTML=uniqueSorted(values).map(v=>`<option value="${escapeHtml(v)}"></option>`).join('')}
function exactCatalogMatch(kind,manufacturer,model){
  const nm=normalizeFaqText(model),mf=normalizeFaqText(manufacturer);
  if(!nm)return null;
  return catalogRows(kind).find(r=>normalizeFaqText(catalogModel(r,kind))===nm&&(!mf||normalizeFaqText(catalogManufacturer(r))===mf))
      || catalogRows(kind).find(r=>normalizeFaqText(catalogModel(r,kind))===nm)
      || null;
}
function catalogPreviewHtml(kind,row){
  if(!row)return'';
  const cells=[];
  let note=row.notes||row.compatibility_notes||'';
  if(kind==='device'){
    cells.push(['Család',row.family],['Terápiás mód',row.therapy_mode],['Párásítás',row.humidification],['Víztartály / párásító',row.humidifier_or_water_tub],['Fűtött cső',row.heated_tube],['Normál cső',row.standard_tube]);
  }else if(kind==='mask'){
    cells.push(['Kategória',row.mask_category],['Interfész',row.interface],['Cső helye',row.hose_connection_position],['Méretek',row.sizes],['Párna anyaga',row.cushion_material],['PAP kompatibilitás',row.general_pap_compatibility]);
    note=[row.notes,row.airmini_compatibility?`AirMini: ${row.airmini_compatibility}`:''].filter(Boolean).join(' • ');
  }else if(kind==='accessory'){
    cells.push(['Kategória',row.category],['Kompatibilis készülékek',row.compatible_devices],['Fűtött',row.heated],['Méret / átmérő',row.size_or_diameter],['Csatlakozás',row.connection]);
  }
  return`<div class="catalog-preview-head"><strong>Adatbázis-találat: ${escapeHtml(catalogManufacturer(row))} ${escapeHtml(catalogModel(row,kind))}</strong><span>ajánlott kitöltés</span></div><div class="catalog-preview-grid">${cells.filter(x=>x[1]).map(([k,v])=>`<div><label>${escapeHtml(k)}</label><b>${escapeHtml(v)}</b></div>`).join('')}</div>${note?`<div class="catalog-preview-note"><label>Kompatibilitási megjegyzés</label>${escapeHtml(note)}</div>`:''}`;
}
function updateCatalogPreview(kind){
  const form=$('#patientForm'),preview=$('#equipmentCatalogPreview');if(!form||!preview)return;
  const row=exactCatalogMatch(kind,form.elements.manufacturer?.value||'',form.elements.model?.value||'');
  if(!row){preview.innerHTML='';preview.classList.add('hidden');return}
  preview.innerHTML=catalogPreviewHtml(kind,row);preview.classList.remove('hidden');
  if(!form.elements.manufacturer.value)form.elements.manufacturer.value=catalogManufacturer(row);
  if(kind==='mask'){
    if(form.elements.mask_type&&!form.elements.mask_type.value)form.elements.mask_type.value=row.mask_category||'';
    if(form.elements.size)setDatalistOptions(form.elements.size.getAttribute('list'),maskSizeOptions(row,form.elements.manufacturer?.value||row.manufacturer));
  }else if(kind==='accessory'){
    if(form.elements.category&&!form.elements.category.value)form.elements.category.value=row.category||'';
  }
}
function wireCatalogEditor(kind){
  if(!['device','mask','accessory'].includes(kind))return;
  const form=$('#patientForm'),man=form?.elements.manufacturer,model=form?.elements.model;if(!form||!man||!model)return;
  const updateModels=()=>{setDatalistOptions(model.getAttribute('list'),catalogOptions(kind,'model',man.value));updateCatalogPreview(kind)};
  man.addEventListener('input',updateModels);
  model.addEventListener('input',()=>updateCatalogPreview(kind));
  model.addEventListener('change',()=>updateCatalogPreview(kind));
  if(kind==='mask'){
    const cat=form.elements.mask_type,size=form.elements.size;
    if(cat)setDatalistOptions(cat.getAttribute('list'),catalogOptions('mask','category',man.value));
    if(size)setDatalistOptions(size.getAttribute('list'),catalogOptions('mask','size',man.value));
    man.addEventListener('input',()=>{if(cat)setDatalistOptions(cat.getAttribute('list'),catalogOptions('mask','category',man.value));if(size)setDatalistOptions(size.getAttribute('list'),catalogOptions('mask','size',man.value))});
  }
  if(kind==='accessory'){
    const cat=form.elements.category;if(cat)setDatalistOptions(cat.getAttribute('list'),catalogOptions('accessory','category',man.value));man.addEventListener('input',()=>cat&&setDatalistOptions(cat.getAttribute('list'),catalogOptions('accessory','category',man.value)));
  }
  updateModels();updateCatalogPreview(kind);
}

function equipmentEmptyHtml(hasProfile=false){return `<section class="measurement-empty-state equipment-empty-state" aria-live="polite">
  <div class="empty-sleep-art" aria-hidden="true">${emptySleepSvg()}</div>
  <h2>Még nincs felszerelési adat.</h2>
  <p>${hasProfile?'Még nem tartozik készülék, maszk vagy kiegészítő a kezelt személyhez. Szinkronizálj egy ResMed mentést, vagy rögzíts felszerelést kézzel.':'Előbb hozz létre vagy tölts vissza egy kezelt személyt, majd szinkronizálj ResMed adatokat vagy rögzíts felszerelést.'}</p>
  <div class="empty-sleep-actions">
    ${hasProfile?'<button type="button" data-equipment-add>Készülék rögzítése</button>':'<button type="button" data-equipment-patient>Kezelt személy</button>'}
    <button type="button" data-equipment-upload>Adatok feltöltése</button>
    <button type="button" class="primary-action" data-equipment-sync>Szinkronizálás most</button>
  </div>
  <small>Az SD-kártyát és a forrásmappát a SleepMate csak olvassa.</small>
</section>`}
async function loadEquipmentPage(){
  clearError();
  try{
    const [eq,patient]=await Promise.all([api('/api/equipment'),api('/api/patient'),loadEquipmentCatalog()]);
    state.detectedEquipment=eq;state.patient=patient;
    const hasProfile=!!patient.profile;
    const storedCount=(patient.devices||[]).length+(patient.masks||[]).length+(patient.accessories||[]).length+(patient.setups||[]).length;
    // Felszerelési szempontból az oldal akkor üres, ha nincs automatikusan felismert
    // eszköz ÉS nincs egyetlen nyilvántartott felszerelési rekord sem. A kezelt
    // személy vagy a korábbi CPAP napok léte önmagában nem indok a placeholder kártyákra.
    const fullyEmpty=!eq.available&&storedCount===0;
    const emptyBox=$('#equipmentEmptyState');
    if(fullyEmpty){
      clearError();
      emptyBox.innerHTML=equipmentEmptyHtml(hasProfile);emptyBox.classList.remove('hidden');
      $('#equipmentNeedsPatient').classList.add('hidden');$('#equipmentContent').classList.add('hidden');
      emptyBox.querySelector('[data-equipment-upload]').onclick=()=>navigate('upload');
      emptyBox.querySelector('[data-equipment-sync]').onclick=()=>{navigate('upload');setTimeout(startInstantRefresh,120)};
      const add=emptyBox.querySelector('[data-equipment-add]');if(add)add.onclick=()=>openRecordEditor('device');
      const pp=emptyBox.querySelector('[data-equipment-patient]');if(pp)pp.onclick=()=>navigate('patient');
      return;
    }
    emptyBox.classList.add('hidden');emptyBox.innerHTML='';
    $('#equipmentNeedsPatient').classList.toggle('hidden',hasProfile);$('#equipmentContent').classList.toggle('hidden',!hasProfile);if(!hasProfile)return;
    const detectedPanel=$('#detectedEquipmentPanel');
    if(!eq.available){
      detectedPanel.classList.add('hidden');
      $('#assignDetectedDevice').disabled=true;
    }else{
      detectedPanel.classList.remove('hidden');
      $('#equipmentManufacturer').textContent=eq.manufacturer||'ResMed';$('#equipmentName').textContent=eq.product_name||'Ismeretlen CPAP készülék';$('#equipmentProductCode').textContent=eq.product_code||'–';$('#equipmentRegion').textContent=eq.geographic_identifier||'–';$('#equipmentDataModel').textContent=eq.data_model_version||'–';$('#equipmentDataVersion').textContent=eq.data_version??'–';$('#equipmentSoftware').textContent=eq.application_identifier||'–';$('#equipmentSource').textContent=eq.source||'Identification.json';const duplicate=(patient.devices||[]).some(d=>(eq.serial_number&&d.serial_number===eq.serial_number)||(!eq.serial_number&&eq.product_code&&d.product_code===eq.product_code&&d.model===eq.product_name));$('#assignDetectedDevice').disabled=duplicate;$('#assignDetectedDevice').textContent=duplicate?'Már a nyilvántartásban':'Hozzárendelés a kezelt személyhez';const ds=$('#detectedDeviceState');ds.textContent=duplicate?'Hozzárendelve':'Észlelt';ds.className=`status-pill ${duplicate?'active':'past'}`;$('#equipmentNote').textContent=duplicate?'Ez az SD-ről felismert készülék már a kezelt személy felszerelései között szerepel. A felső blokk csak az aktuálisan beolvasott SD-forrást mutatja.':'Az SD-kártyáról felismert eszköz még csak észlelt forrás. A gombbal kerül be egyszer a kezelt személy titkosított felszerelési nyilvántartásába.';const img=$('#equipmentImage');if(img)img.src=`/equipment-image?_=${Date.now()}`;
    }
    renderEquipmentRecords();
  }catch(e){showError(e)}
}
function equipmentRecordName(r,kind){
  if(kind==='device')return`${r.manufacturer||''} ${r.model||r.product_name||'Készülék'}`.trim();
  if(kind==='accessory')return`${r.manufacturer||''} ${r.model||r.category||'Kiegészítő'}`.trim();
  return`${r.manufacturer||''} ${r.model||'Maszk'}${r.size?` • ${r.size}`:''}`.trim()
}
function latestActiveSetup(rows){return [...(rows||[])].filter(r=>r.active!==false&&!r.end_date).sort((a,b)=>(b.start_date||'').localeCompare(a.start_date||''))[0]||[...(rows||[])].sort((a,b)=>(b.start_date||'').localeCompare(a.start_date||''))[0]||null}
function setupAccessories(r,p=state.patient){const ids=Array.isArray(r?.accessory_ids)?r.accessory_ids:[];return ids.map(id=>(p?.accessories||[]).find(x=>x.id===id)).filter(Boolean)}
function equipmentSetupLabel(r,p=state.patient){if(!r)return'—';const d=(p?.devices||[]).find(x=>x.id===r.device_id),m=(p?.masks||[]).find(x=>x.id===r.mask_id);return`${d?equipmentRecordName(d,'device'):'Készülék'} + ${m?equipmentRecordName(m,'mask'):'Maszk'}`}
const REPLACEMENT_INTERVALS={
  '2 hét':{days:14,label:'2 hét'},
  '1 hónap':{months:1,label:'1 hónap'},
  '3 hónap':{months:3,label:'3 hónap'},
  '6 hónap':{months:6,label:'6 hónap'},
  '1 év':{years:1,label:'1 év'}
};
function parseLocalDate(iso){if(!iso)return null;const d=new Date(`${iso}T12:00:00`);return Number.isNaN(d.getTime())?null:d}
function addReplacementInterval(start,interval){
  const d=parseLocalDate(start),cfg=REPLACEMENT_INTERVALS[interval];if(!d||!cfg)return null;
  const out=new Date(d);if(cfg.days)out.setDate(out.getDate()+cfg.days);if(cfg.months)out.setMonth(out.getMonth()+cfg.months);if(cfg.years)out.setFullYear(out.getFullYear()+cfg.years);return out
}
function replacementInfo(r){
  const interval=r?.replacement_interval||'Nincs szükség időzítésre',due=addReplacementInterval(r?.start_date,interval);
  if(!REPLACEMENT_INTERVALS[interval])return{scheduled:false,interval,label:'Nincs időzített csere',tone:'none',percent:0};
  if(!due)return{scheduled:false,hidden:true,interval,label:'',tone:'none',percent:0};
  const start=parseLocalDate(r.start_date),now=new Date(),total=Math.max(1,due-start),used=Math.max(0,now-start),left=Math.ceil((due-now)/86400000),percent=Math.max(0,Math.min(100,used/total*100));
  let tone=left<0?'overdue':left<=7?'danger':percent>=75?'warn':percent>=50?'mid':'good';
  const label=left<0?`${Math.abs(left)} napja esedékes`:left===0?'Ma esedékes':`${left} nap van hátra`;
  return{scheduled:true,interval,due,left,percent,tone,label}
}
function equipmentIcon(kind,r={}){
  const cat=String(r.category||'').toLowerCase();
  if(kind==='mask')return`<span class="equipment-type-icon mask-icon" title="Maszk"><svg viewBox="0 0 24 24"><path d="M5 8c2.2-1.8 4.5-2.7 7-2.7S16.8 6.2 19 8v6.2c-1.8 2.3-4.1 3.5-7 3.5s-5.2-1.2-7-3.5V8Z"/><path d="M8 10v3.7M16 10v3.7M9 18v2M15 18v2"/></svg></span>`;
  if(cat.includes('párás'))return`<span class="equipment-type-icon humidifier-icon" title="Párásító"><svg viewBox="0 0 24 24"><path d="M12 3s5 5.4 5 9a5 5 0 1 1-10 0c0-3.6 5-9 5-9Z"/><path d="M9.5 13.5c.5 1.4 1.4 2.1 2.7 2.3"/></svg></span>`;
  if(cat.includes('szűr'))return`<span class="equipment-type-icon filter-icon" title="Szűrő"><svg viewBox="0 0 24 24"><path d="M4 6h16M6 10h12M8 14h8M10 18h4"/></svg></span>`;
  if(cat.includes('cső')||cat.includes('gégecső'))return`<span class="equipment-type-icon tube-icon" title="Cső"><svg viewBox="0 0 24 24"><path d="M4 7c7 0 5 10 12 10h4"/><path d="M4 4v6M20 14v6"/></svg></span>`;
  if(kind==='device')return`<span class="equipment-type-icon device-icon" title="PAP-készülék"><svg viewBox="0 0 24 24"><rect x="3" y="6" width="18" height="12" rx="3"/><rect x="6" y="9" width="6" height="5" rx="1"/><path d="M15 10h3M15 13h3"/></svg></span>`;
  return`<span class="equipment-type-icon generic-icon" title="Kiegészítő"><svg viewBox="0 0 24 24"><path d="M8 4h8v4h4v8h-4v4H8v-4H4V8h4V4Z"/></svg></span>`
}
function replacementBar(r){
  const inf=replacementInfo(r);
  if(inf.hidden)return'';
  if(!inf.scheduled)return`<div class="replacement-bar none"><span style="width:0"></span></div><div class="replacement-meta"><span>Nincs időzített csere</span></div>`;
  return`<div class="replacement-bar ${inf.tone}" title="${escapeHtml(inf.label)}"><span style="width:${inf.percent.toFixed(1)}%"></span></div><div class="replacement-meta"><span>${escapeHtml(inf.interval)}</span><b>${escapeHtml(inf.label)}</b>${inf.due?`<small>${humanDate(inf.due.toISOString().slice(0,10))}</small>`:''}</div>`
}
function renderReplacementSummary(masks,accessories){
  const rows=[...masks.map(r=>({kind:'mask',r})),...accessories.map(r=>({kind:'accessory',r}))].filter(x=>x.r.active!==false&&!x.r.end_date&&replacementInfo(x.r).scheduled);
  rows.sort((a,b)=>(replacementInfo(a.r).left??99999)-(replacementInfo(b.r).left??99999));
  const box=$('#replacementSummary');if(!box)return;
  box.innerHTML=rows.length?rows.slice(0,5).map(({kind,r})=>{const inf=replacementInfo(r);return`<div class="replacement-summary-row ${inf.tone}">${equipmentIcon(kind,r)}<div><strong>${escapeHtml(equipmentRecordName(r,kind))}</strong><span>${escapeHtml(inf.label)}</span></div></div>`}).join(''):'<div class="empty-state">Nincs időzített csere az aktív maszkokhoz vagy kiegészítőkhöz.</div>'
}
function equipmentRecordCard(r,kind,devices=[]){
  const active=r.active!==false&&!r.end_date,inf=replacementInfo(r),device=kind==='accessory'?devices.find(x=>x.id===r.device_id):null;
  const facts=kind==='device'
    ?`<span>Termékkód <b>${escapeHtml(r.product_code||'—')}</b></span><span>Kezdés <b>${humanDate(r.start_date)}</b></span>`
    :kind==='mask'
      ?`<span>Kialakítás <b>${escapeHtml(r.mask_type||'—')}</b></span><span>Kezdés <b>${humanDate(r.start_date)}</b></span>`
      :`<span>Típus <b>${escapeHtml(r.category||'—')}</b></span><span>Készülék <b>${escapeHtml(device?equipmentRecordName(device,'device'):'Nincs kötve')}</b></span><span>Kezdés <b>${humanDate(r.start_date)}</b></span>`;
  return`<article class="record-card equipment-record ${inf.tone}">
    ${replacementBar(r)}
    <div class="equipment-record-main">${equipmentIcon(kind,r)}<div class="equipment-record-copy"><span class="status-pill ${active?'active':'past'}">${active?'Aktív':'Korábbi'}</span><h3>${escapeHtml(equipmentRecordName(r,kind))}</h3><div class="record-facts">${facts}</div></div></div>
    ${recButtons(kind,r)}
  </article>`
}
function renderEquipmentRecords(){
  const p=state.patient||{},sorter=(a,b)=>Number(b.active!==false&&!b.end_date)-Number(a.active!==false&&!a.end_date)||(b.start_date||'').localeCompare(a.start_date||'');
  const devices=[...(p.devices||[])].sort(sorter),masks=[...(p.masks||[])].sort(sorter),accessories=[...(p.accessories||[])].sort(sorter),setups=[...(p.setups||[])].sort(sorter);
  const dbox=$('#deviceRecords'),mbox=$('#maskRecords'),abox=$('#accessoryRecords'),sbox=$('#setupRecords');
  dbox.innerHTML=devices.length?devices.map(r=>equipmentRecordCard(r,'device',devices)).join(''):'<div class="empty-state">Még nincs a kezelt személyhez rendelt készülék.</div>';
  mbox.innerHTML=masks.length?masks.map(r=>equipmentRecordCard(r,'mask',devices)).join(''):'<div class="empty-state">Még nincs maszk rögzítve.</div>';
  abox.innerHTML=accessories.length?accessories.map(r=>equipmentRecordCard(r,'accessory',devices)).join(''):'<div class="empty-state">Még nincs kiegészítő. Itt rögzíthető például párásító, szűrő, fűtött gégecső vagy EzShare.</div>';
  sbox.innerHTML=setups.length?setups.map(r=>{const acc=setupAccessories(r,p),legacy=[];if(r.heated_tube)legacy.push('Fűtött cső');if(r.humidifier)legacy.push('Párásító');const names=acc.map(a=>equipmentRecordName(a,'accessory'));const extras=[...names,...legacy.filter(x=>!names.some(n=>n.toLowerCase().includes(x.toLowerCase().split(' ')[0])))];return`<article class="record-card setup-record ${r.active!==false&&!r.end_date?'current-record':''}"><div><span class="status-pill ${r.active!==false&&!r.end_date?'active':'past'}">${r.active!==false&&!r.end_date?'Aktív':'Korábbi'}</span><h3>${escapeHtml(equipmentSetupLabel(r,p))}</h3><div class="record-facts"><span>Időszak <b>${humanDate(r.start_date)}${r.end_date?' – '+humanDate(r.end_date):' – jelenleg'}</b></span><span>Kiegészítők <b>${escapeHtml(extras.length?extras.join(' • '):'—')}</b></span></div>${r.note?`<p>${escapeHtml(r.note)}</p>`:''}</div>${recButtons('setup',r)}</article>`}).join(''):'<div class="empty-state">Nincs használati konfiguráció. Előbb rögzíts legalább egy készüléket és egy maszkot.</div>';
  renderReplacementSummary(masks,accessories);
  wireRecordButtons(dbox);wireRecordButtons(mbox);wireRecordButtons(abox);wireRecordButtons(sbox)
}
async function assignDetectedDevice(){
  const eq=state.detectedEquipment;if(!eq?.available||!state.patient?.profile)return;
  try{await apiWrite('/api/patient/record/device','POST',{manufacturer:eq.manufacturer||'ResMed',model:eq.product_name||'AirSense 11',product_code:eq.product_code||'',serial_number:eq.serial_number||'',start_date:state.patient.profile.therapy_start_date||'',replacement_interval:'Nincs szükség időzítésre',end_date:'',active:true,note:'Az SD-kártya Identification.json fájljából hozzárendelve.'});addLog('INFO','Az SD-kártyáról felismert készülék hozzárendelve a kezelt személyhez.');await loadEquipmentPage();renderPatient()}catch(e){showError(e)}
}



const PATIENT_SCHEMAS={
  profile:{title:'Személyes adatok szerkesztése',fields:[
    ['name','Név','text'],['birth_date','Születési idő','date'],['taj','TAJ-szám','text'],['taj_validate','TAJ ellenőrzőszám ellenőrzése','checkbox'],
    ['diagnosis_date','Diagnózis felállításának dátuma','date'],['therapy_start_date','PAP-terápia megkezdésének dátuma','date'],
    ['doctor_name','Kezelőorvos neve','text'],['institution','Kezelőintézmény','text'],['next_control_date','Következő kontroll','date'],
    ['notes','Saját megjegyzések','textarea'],
    ['profile_photo','Profilkép','file']
  ]},
  diagnosis:{title:'Diagnózis / vizsgálat',fields:[
    ['date','Diagnózis / vizsgálat dátuma','date'],['diagnosis_type','Diagnózis típusa','select:OSA|CSA|Kevert|Egyéb'],['ahi','Diagnosztikai AHI (/óra)','number'],['odi','ODI (/óra)','number'],
    ['spo2_min','Legalacsonyabb SpO₂ (%)','number'],['spo2_avg','Átlagos SpO₂ (%)','number'],['diagnosis','Diagnózis / megjegyzés','textarea']
  ]},
  titration:{title:'Titrálás',fields:[
    ['date','Titrálás dátuma','date'],['type','Titrálás típusa','select:Alváslaboros|Otthoni|Automata PAP|Manuális|Egyéb'],['pressure_type','Javasolt nyomás típusa','select:Fix CPAP|APAP'],
    ['fixed_pressure','Fix nyomás (cmH₂O)','number'],['min_pressure','APAP minimum (cmH₂O)','number'],['max_pressure','APAP maximum (cmH₂O)','number'],
    ['ahi','AHI a titrálás során (/óra)','number'],['central_ahi','Centrális AHI (/óra)','number'],['spo2_min','SpO₂ minimum (%)','number'],['note','Megjegyzés','textarea']
  ]},
  prescription:{title:'Terápiás előírás',fields:[
    ['effective_from','Érvényes ettől','date'],['effective_to','Érvényes eddig (opcionális)','date'],['mode','Terápiás mód','select:Fix CPAP|APAP / AutoCPAP'],
    ['fixed_pressure','Előírt fix nyomás (cmH₂O)','number'],['min_pressure','Előírt minimum (cmH₂O)','number'],['max_pressure','Előírt maximum (cmH₂O)','number'],['note','Megjegyzés','textarea']
  ]},
  medication:{title:'Gyógyszer',fields:[
    ['name','Gyógyszer neve','text'],['strength','Hatáserősség','text'],['dosage','Adagolás','text'],['time','Szedés időpontja','text'],
    ['start_date','Kezdés dátuma','date'],['end_date','Befejezés dátuma','date'],['active','Aktív','checkbox'],['note','Megjegyzés','textarea']
  ]},
  device:{title:'PAP-készülék',fields:[
    ['manufacturer','Gyártó','catalog-device-manufacturer'],['model','Típus / modell','catalog-device-model'],['product_code','Termékkód','text'],['serial_number','Sorozatszám (opcionális)','text'],['start_date','Használat kezdete','date'],['replacement_interval','Csere / felülvizsgálat gyakorisága','select:Nincs szükség időzítésre|2 hét|1 hónap|3 hónap|6 hónap|1 év'],['end_date','Használat vége','date'],['active','Aktív készülék','checkbox'],['note','Megjegyzés','textarea']
  ]},
  mask:{title:'CPAP maszk',fields:[
    ['manufacturer','Gyártó','catalog-mask-manufacturer'],['model','Maszk típusa / modell','catalog-mask-model'],['mask_type','Kialakítás','catalog-mask-category'],['size','Méret','catalog-mask-size'],['start_date','Használat kezdete','date'],['replacement_interval','Csere gyakorisága','select:Nincs szükség időzítésre|2 hét|1 hónap|3 hónap|6 hónap|1 év'],['end_date','Használat vége','date'],['active','Aktív maszk','checkbox'],['note','Megjegyzés','textarea']
  ]},
  accessory:{title:'CPAP kiegészítő',fields:[
    ['category','Kiegészítő típusa','catalog-accessory-category'],['manufacturer','Gyártó','catalog-accessory-manufacturer'],['model','Típus / modell','catalog-accessory-model'],['device_id','Kapcsolódó készülék (opcionális)','select-device'],['start_date','Használat kezdete','date'],['replacement_interval','Csere gyakorisága','select:Nincs szükség időzítésre|2 hét|1 hónap|3 hónap|6 hónap|1 év'],['end_date','Használat vége','date'],['active','Aktív kiegészítő','checkbox'],['note','Megjegyzés','textarea']
  ]},
  setup:{title:'Használati konfiguráció',fields:[
    ['device_id','Készülék','select-device'],['mask_id','Maszk','select-mask'],['accessory_ids','Kiegészítők','select-accessories'],['start_date','Konfiguráció kezdete','date'],['end_date','Konfiguráció vége','date'],['active','Aktív konfiguráció','checkbox'],['note','Megjegyzés','textarea']
  ]},
  timeline_event:{title:'Saját terápiás esemény',fields:[['date','Dátum','date'],['event_type','Típus','select:Egyéb|Maszkváltás|Készülékváltás|Beállításváltozás|Kontroll|Életmódbeli változás'],['title','Esemény rövid neve','text'],['note','Megjegyzés','textarea']]}
};

function humanDate(iso){if(!iso)return'—';try{return new Intl.DateTimeFormat('hu-HU',{year:'numeric',month:'long',day:'numeric'}).format(new Date(`${iso}T12:00:00`))}catch{return iso}}
function ageFromDob(iso){if(!iso)return null;const d=new Date(`${iso}T12:00:00`),n=new Date();let a=n.getFullYear()-d.getFullYear();const m=n.getMonth()-d.getMonth();if(m<0||(m===0&&n.getDate()<d.getDate()))a--;return a>=0?a:null}
function daysSince(iso){if(!iso)return null;const d=new Date(`${iso}T00:00:00`),n=new Date();return Math.max(0,Math.floor((n-d)/86400000)+1)}
function tajDigits(v){return String(v||'').replace(/\D/g,'').slice(0,9)}
function formatTaj(v){const d=tajDigits(v);return d.length===9?`${d.slice(0,3)} ${d.slice(3,6)} ${d.slice(6)}`:(d||'—')}
function validTaj(v){const d=tajDigits(v);if(d.length!==9)return false;let sum=0;for(let i=0;i<8;i++)sum+=(+d[i])*(i%2===0?3:7);return sum%10===+d[8]}
function num(v,d=1){return v===null||v===undefined||v===''?'—':Number(v).toLocaleString('hu-HU',{minimumFractionDigits:d,maximumFractionDigits:d})}
function therapyLabel(r){if(!r)return'—';const mode=r.mode||r.pressure_type||'';if(mode.includes('Fix'))return`Fix CPAP ${num(r.fixed_pressure,1)} cmH₂O`;if(mode.includes('APAP'))return`APAP ${num(r.min_pressure,1)}–${num(r.max_pressure,1)} cmH₂O`;return mode||'—'}
function currentPrescription(records){if(!records?.length)return null;const today=new Date().toISOString().slice(0,10),sorted=[...records].sort((a,b)=>(b.effective_from||'').localeCompare(a.effective_from||''));return sorted.find(r=>(!r.effective_from||r.effective_from<=today)&&(!r.effective_to||r.effective_to>=today))||sorted[0]||null}
function latestByDate(records,key='date'){return [...(records||[])].sort((a,b)=>(b[key]||'').localeCompare(a[key]||''))[0]||null}

function therapyTimelineEvents(){const p=state.patient||{},rows=[];const push=(date,type,title,detail,source,id=null)=>{if(date)rows.push({date,type,title,detail,source,id})};push(p.profile?.therapy_start_date,'start','PAP-terápia kezdete','A terápia megkezdésének rögzített dátuma.','profile');for(const r of p.prescriptions||[])push(r.effective_from,'prescription','Terápiás előírás módosítása',therapyLabel(r),'prescription',r.id);for(const r of p.titrations||[])push(r.date,'titration','Titrálás',therapyLabel(r),'titration',r.id);for(const r of p.devices||[])push(r.start_date,'device','Készülék használatba véve',equipmentRecordName(r,'device'),'device',r.id);for(const r of p.masks||[])push(r.start_date,'mask','Maszk használatba véve',equipmentRecordName(r,'mask'),'mask',r.id);for(const r of p.accessories||[])push(r.start_date,'accessory','Kiegészítő használatba véve',equipmentRecordName(r,'accessory'),'accessory',r.id);for(const r of p.medications||[]){push(r.start_date,'medication','Gyógyszer kezdete',`${r.name||'Gyógyszer'} ${r.strength||''}`.trim(),'medication',r.id);push(r.end_date,'medication','Gyógyszer befejezése',`${r.name||'Gyógyszer'} ${r.strength||''}`.trim(),'medication',r.id)}for(const r of p.weights||[])push(r.date,'weight','Testsúly / BMI változás',[r.weight?`${r.weight} kg`:'',r.bmi?`BMI ${r.bmi}`:''].filter(Boolean).join(' • '),'weight',r.id);for(const r of p.controls||[])push(r.date,'control','Kontrollvizsgálat',r.note||r.institution||'Kontroll','control',r.id);for(const r of p.timeline_events||[])push(r.date,'custom',r.title||r.event_type||'Saját terápiás esemény',[r.event_type&&r.title?r.event_type:'',r.note||''].filter(Boolean).join(' • '), 'timeline_event',r.id);return rows.sort((a,b)=>String(b.date).localeCompare(String(a.date)))}
function timelineIcon(t){return({start:'☾',prescription:'⚙',titration:'↕',device:'▣',mask:'◉',accessory:'＋',medication:'✚',weight:'⚖',control:'⌂',custom:'✦'}[t]||'•')}
function renderTherapyTimeline(){const box=$('#therapyTimeline');if(!box)return;const rows=therapyTimelineEvents();box.innerHTML=rows.length?rows.map(r=>`<article class="timeline-row type-${escapeHtml(r.type)}"><div class="timeline-marker">${timelineIcon(r.type)}</div><div class="timeline-content"><time>${humanDate(r.date)}</time><h3>${escapeHtml(r.title)}</h3><p>${escapeHtml(r.detail||'')}</p></div>${r.source==='timeline_event'?recButtons('timeline_event',{id:r.id}):''}</article>`).join(''):'<div class="empty-state">Még nincs terápiás változás rögzítve.</div>';wireRecordButtons(box)}

async function loadPatientPage(){
  clearError();
  try{state.patient=await api('/api/patient');renderPatient();setPatientTab(state.patientTab);await loadPatientTherapy($('#patientTherapyPeriod')?.value||'30')}catch(e){showError(e)}
}
function setPatientTab(tab){
  const hasProfile=!!state.patient?.profile;
  if(!hasProfile&&tab!=='backup')tab='overview';
  state.patientTab=tab;
  $$('.patient-tab').forEach(x=>x.classList.toggle('active',x.dataset.patientTab===tab));
  $$('.patient-view').forEach(x=>x.classList.toggle('active',x.dataset.patientView===tab));
  if(!hasProfile){
    $('#patientEmpty').classList.toggle('hidden',tab==='backup');
    $('#patientContent').classList.toggle('hidden',tab!=='backup');
  }else{
    $('#patientEmpty').classList.add('hidden');$('#patientContent').classList.remove('hidden');
  }
  $('#backupExportCard')?.classList.toggle('hidden',!hasProfile);
  $('#patientEditButton').classList.toggle('hidden',tab==='backup'||!hasProfile);$('#patientEditButton').textContent='Szerkesztés'
}
function renderPatient(){
  const p=state.patient||{},profile=p.profile,empty=!profile;
  $('#patientEmpty').classList.toggle('hidden',!empty);$('#patientContent').classList.toggle('hidden',empty);$('#patientEditButton').classList.toggle('hidden',empty);
  if(empty){return;}
  $('#patientName').textContent=profile.name||'Névtelen kezelt személy';const age=ageFromDob(profile.birth_date);$('#patientAge').textContent=age==null?'Életkor: —':`${age} éves`;
  $('#patientTherapyStart').textContent=`PAP-terápia kezdete: ${humanDate(profile.therapy_start_date)}`;const td=daysSince(profile.therapy_start_date);$('#patientTherapyDays').textContent=`Terápiában eltöltött idő: ${td==null?'—':td+' nap'}`;
  const img=$('#patientPhoto'),fb=$('#patientPhotoFallback');if(p.has_photo){img.src=patientPhotoUrl(p);img.classList.remove('hidden');fb.classList.add('hidden')}else{img.removeAttribute('src');img.classList.add('hidden');fb.classList.remove('hidden')}
  $('#patientSecurityChip').textContent=p.security?.encrypted_at_rest?'🔒 Titkosított helyi tárolás':'⚠ Tárolás ellenőrzendő';
  const dx=latestByDate(p.diagnoses);$('#patientDiagnosisTitle').textContent=dx?.diagnosis||dx?.diagnosis_type||'—';$('#patientDiagnosisAhi').textContent=`Diagnosztikai AHI: ${dx?.ahi!==undefined&&dx?.ahi!==''?num(dx.ahi,1)+' /óra':'—'}`;
  const rx=currentPrescription(p.prescriptions);$('#patientPrescription').textContent=therapyLabel(rx);$('#patientPrescriptionSince').textContent=rx?.effective_from?`${humanDate(rx.effective_from)}-tól`:'—';$('#comparePrescription').textContent=therapyLabel(rx);
  const tit=latestByDate(p.titrations);$('#patientLastTitrationDate').textContent=tit?humanDate(tit.date):'—';$('#patientLastTitration').textContent=therapyLabel(tit);
  const active=(p.medications||[]).filter(m=>m.active!==false&&!m.end_date);$('#patientActiveMeds').textContent=active.length;
  $('#patientPersonalDetails').innerHTML=detailRows([['Név',profile.name],['Születési idő',humanDate(profile.birth_date)],['Életkor',age==null?'—':`${age} év`],['TAJ-szám',formatTaj(profile.taj)+(profile.taj_validate&&profile.taj?` ${validTaj(profile.taj)?'✓':'⚠ hibás ellenőrzőszám'}`:'')],['Diagnózis dátuma',humanDate(profile.diagnosis_date)],['Terápia kezdete',humanDate(profile.therapy_start_date)]]);
  const activeSetup=latestActiveSetup(p.setups||[]),setupText=activeSetup?equipmentSetupLabel(activeSetup,p):'—';$('#patientCareDetails').innerHTML=detailRows([['Kezelőorvos',profile.doctor_name||'—'],['Kezelőintézmény',profile.institution||'—'],['Következő kontroll',humanDate(profile.next_control_date)],['Aktuális felszerelési konfiguráció',setupText],['Saját megjegyzések',profile.notes||'—']]);
  renderDiagnosisRecords();renderTitrations();renderPrescriptions();renderMedications();renderTherapyTimeline();
}
function detailRows(rows){return rows.map(([k,v])=>`<div><label>${escapeHtml(k)}</label><strong>${escapeHtml(v??'—')}</strong></div>`).join('')}
function recButtons(kind,r){return `<div class="record-actions"><button type="button" data-edit-kind="${kind}" data-edit-id="${r.id}">Szerkesztés</button><button type="button" class="danger-link" data-delete-kind="${kind}" data-delete-id="${r.id}">Törlés</button></div>`}
function wireRecordButtons(box){box.querySelectorAll('[data-edit-kind]').forEach(b=>b.onclick=()=>openRecordEditor(b.dataset.editKind,b.dataset.editId));box.querySelectorAll('[data-delete-kind]').forEach(b=>b.onclick=()=>confirmAction('Biztosan törlöd ezt a rekordot? A CPAP mérési adatok ettől nem változnak.',()=>deleteRecord(b.dataset.deleteKind,b.dataset.deleteId)))}
function renderDiagnosisRecords(){const box=$('#diagnosisRecords');const rows=[...(state.patient?.diagnoses||[])].sort((a,b)=>(b.date||'').localeCompare(a.date||''));box.innerHTML=rows.length?rows.map(r=>`<article class="panel record-card"><div><span class="record-date">${humanDate(r.date)}</span><h3>${escapeHtml(r.diagnosis||r.diagnosis_type||'Diagnózis')}</h3><div class="record-facts"><span>AHI <b>${r.ahi!==''&&r.ahi!=null?num(r.ahi,1)+' /óra':'—'}</b></span><span>ODI <b>${r.odi!==''&&r.odi!=null?num(r.odi,1)+' /óra':'—'}</b></span><span>SpO₂ min. <b>${r.spo2_min!==''&&r.spo2_min!=null?num(r.spo2_min,0)+'%':'—'}</b></span></div></div>${recButtons('diagnosis',r)}</article>`).join(''):'<div class="empty-state">Nincs rögzített diagnosztikai vizsgálat.</div>';wireRecordButtons(box)}
function renderTitrations(){const box=$('#titrationRecords');const rows=[...(state.patient?.titrations||[])].sort((a,b)=>(b.date||'').localeCompare(a.date||''));box.innerHTML=rows.length?rows.map(r=>`<article class="panel record-card"><div><span class="record-date">${humanDate(r.date)}</span><h3>${therapyLabel(r)}</h3><div class="record-facts"><span>Típus <b>${escapeHtml(r.type||'—')}</b></span><span>Titrálási AHI <b>${r.ahi!==''&&r.ahi!=null?num(r.ahi,1)+' /óra':'—'}</b></span><span>CAHI <b>${r.central_ahi!==''&&r.central_ahi!=null?num(r.central_ahi,1)+' /óra':'—'}</b></span><span>SpO₂ min. <b>${r.spo2_min!==''&&r.spo2_min!=null?num(r.spo2_min,0)+'%':'—'}</b></span></div>${r.note?`<p>${escapeHtml(r.note)}</p>`:''}</div>${recButtons('titration',r)}</article>`).join(''):'<div class="empty-state">Nincs rögzített titrálás.</div>';wireRecordButtons(box)}
function renderPrescriptions(){const box=$('#prescriptionRecords');const rows=[...(state.patient?.prescriptions||[])].sort((a,b)=>(b.effective_from||'').localeCompare(a.effective_from||''));box.innerHTML=rows.length?rows.map((r,i)=>`<article class="panel record-card ${i===0?'current-record':''}"><div><span class="record-date">${humanDate(r.effective_from)}${r.effective_to?' – '+humanDate(r.effective_to):' – jelenleg'}</span><h3>${therapyLabel(r)}</h3>${r.note?`<p>${escapeHtml(r.note)}</p>`:''}</div>${recButtons('prescription',r)}</article>`).join(''):'<div class="empty-state">Nincs rögzített terápiás előírás.</div>';wireRecordButtons(box)}
function renderMedications(){const box=$('#medicationRecords');const rows=[...(state.patient?.medications||[])].sort((a,b)=>Number(b.active!==false&&!b.end_date)-Number(a.active!==false&&!a.end_date)||(b.start_date||'').localeCompare(a.start_date||''));box.innerHTML=rows.length?rows.map(r=>{const active=r.active!==false&&!r.end_date;return`<article class="panel record-card"><div><span class="status-pill ${active?'active':'past'}">${active?'Aktív':'Korábbi'}</span><h3>${escapeHtml(r.name||'Gyógyszer')} ${r.strength?`<small>${escapeHtml(r.strength)}</small>`:''}</h3><div class="record-facts"><span>Adagolás <b>${escapeHtml(r.dosage||'—')}</b></span><span>Időpont <b>${escapeHtml(r.time||'—')}</b></span><span>Kezdés <b>${humanDate(r.start_date)}</b></span>${r.end_date?`<span>Befejezés <b>${humanDate(r.end_date)}</b></span>`:''}</div>${r.note?`<p>${escapeHtml(r.note)}</p>`:''}</div>${recButtons('medication',r)}</article>`}).join(''):'<div class="empty-state">Nincs rögzített gyógyszer.</div>';wireRecordButtons(box)}

async function loadPatientTherapy(period){
  if(!state.patient?.profile)return;try{const d=await api(`/api/patient/therapy?period=${encodeURIComponent(period)}`),p=d.pressure;const names={7:'elmúlt 7 nap',30:'elmúlt 30 nap',90:'elmúlt 90 nap',all:'teljes időszak'};$('#patientActualPeriodLabel').textContent=names[period]||period;$('#patientActualP95').textContent=p?`${num(p.p95,1)} cmH₂O`:'—';$('#patientActualAhi').textContent=`Terápiás AHI: ${d.ahi==null?'—':num(d.ahi,2)+' /óra'}`;$('#compareAvg').textContent=p?`${num(p.average,1)} cmH₂O`:'—';$('#compareMedian').textContent=p?`${num(p.median,1)} cmH₂O`:'—';$('#compareP95').textContent=p?`${num(p.p95,1)} cmH₂O`:'—';$('#compareMax').textContent=p?`${num(p.max,1)} cmH₂O`:'—'}catch(e){showError(e)}
}
function editPatientCurrent(){const t=state.patientTab;if(t==='overview'||t==='personal')openProfileEditor();else if(t==='diagnosis')openRecordEditor('diagnosis');else if(t==='titrations')openRecordEditor('titration');else if(t==='prescription')openRecordEditor('prescription');else if(t==='medications')openRecordEditor('medication');else if(t==='timeline')openRecordEditor('timeline_event');else if(t==='backup')return}
function openProfileEditor(){openEditor('profile',state.patient?.profile||{})}
function findRecord(kind,id){const map={diagnosis:'diagnoses',titration:'titrations',prescription:'prescriptions',medication:'medications',device:'devices',mask:'masks',accessory:'accessories',setup:'setups',daily_assessment:'daily_assessments',timeline_event:'timeline_events'};return (state.patient?.[map[kind]]||[]).find(x=>x.id===id)||{}}
async function openRecordEditor(kind,id=null){
  if(['device','mask','accessory'].includes(kind))await loadEquipmentCatalog();
  openEditor(kind,id?findRecord(kind,id):{})
}
function openEditor(kind,data){const schema=PATIENT_SCHEMAS[kind];if(!schema)return;state.patientEdit={kind,data};$('#patientModalTitle').textContent=schema.title;$('#patientFormFields').innerHTML=schema.fields.map(f=>fieldHtml(f,data)).join('')+(['device','mask','accessory'].includes(kind)?'<div id="equipmentCatalogPreview" class="catalog-preview hidden"></div>':'');$('#patientModal').classList.remove('hidden');const pressure=$('[name="pressure_type"]'),mode=$('[name="mode"]');if(pressure)pressure.onchange=togglePressureFields;if(mode)mode.onchange=togglePressureFields;togglePressureFields();wireCatalogEditor(kind)}
function fieldHtml([name,label,type],data){
  const value=data?.[name]??'';
  if(type==='textarea')return`<label class="form-field wide"><span>${label}</span><textarea name="${name}" rows="3">${escapeHtml(value)}</textarea></label>`;
  if(type==='checkbox')return`<label class="form-field checkbox-field"><input name="${name}" type="checkbox" ${value?'checked':''}><span>${label}</span></label>`;
  if(type==='file')return`<label class="form-field wide"><span>${label}</span><input name="${name}" type="file" accept="image/*"><small>A kép a böngészőben legfeljebb 512×512 képpontra lesz átméretezve és tömörített WEBP formátumba kerül a gyorsabb betöltéshez.</small>${state.patient?.has_photo?'<button id="deletePhotoInline" type="button" class="danger-link">Jelenlegi profilkép törlése</button>':''}</label>`;
  if(type.startsWith('catalog-')){
    const [,kind,field]=type.split('-'),id=`catalog-${kind}-${field}-${name}`,manufacturer=data?.manufacturer||'';
    const values=catalogOptions(kind,field,field==='manufacturer'?'':manufacturer);
    return`<label class="form-field"><span>${label}</span><input name="${name}" type="text" list="${id}" value="${escapeHtml(value)}" data-catalog-kind="${kind}" data-catalog-field="${field}" autocomplete="off"><datalist id="${id}">${values.map(v=>`<option value="${escapeHtml(v)}"></option>`).join('')}</datalist><small class="catalog-field-note">Válassz az adatbázisból, vagy írj be saját értéket.</small></label>`;
  }
  if(type==='select-accessories'){const rows=state.patient?.accessories||[],selected=new Set(Array.isArray(value)?value:[]);return`<label class="form-field wide"><span>${label}</span><select name="${name}" multiple size="${Math.min(6,Math.max(3,rows.length||3))}">${rows.map(r=>`<option value="${escapeHtml(r.id)}" ${selected.has(r.id)?'selected':''}>${escapeHtml(equipmentRecordName(r,'accessory'))}</option>`).join('')}</select><small>Ctrl+kattintással több elem választható. Ha nincs kiegészítő, hagyd üresen.</small></label>`}
  if(type==='select-device'||type==='select-mask'){const rows=type==='select-device'?(state.patient?.devices||[]):(state.patient?.masks||[]);const opts=rows.map(r=>({value:r.id,label:type==='select-device'?`${r.manufacturer||''} ${r.model||r.product_name||'Készülék'}`.trim():`${r.manufacturer||''} ${r.model||'Maszk'} ${r.size?`(${r.size})`:''}`.trim()}));return`<label class="form-field"><span>${label}</span><select name="${name}"><option value="">— válassz —</option>${opts.map(o=>`<option value="${escapeHtml(o.value)}" ${o.value===value?'selected':''}>${escapeHtml(o.label)}</option>`).join('')}</select></label>`}
  if(type.startsWith('select:')){const opts=type.slice(7).split('|');return`<label class="form-field"><span>${label}</span><select name="${name}">${opts.map(o=>`<option ${o===value?'selected':''}>${escapeHtml(o)}</option>`).join('')}</select></label>`}
  const step=type==='number'?' step="0.1"':'';
  return`<label class="form-field"><span>${label}</span><input name="${name}" type="${type}" value="${escapeHtml(value)}"${step}></label>`
}
function togglePressureFields(){const form=$('#patientForm'),kind=state.patientEdit?.kind;if(!form)return;let mode=form.elements.pressure_type?.value||form.elements.mode?.value||'';for(const name of['fixed_pressure','min_pressure','max_pressure']){const el=form.elements[name];if(!el)continue;const wrap=el.closest('.form-field');wrap.classList.toggle('conditional-hidden',mode.includes('Fix')?name!=='fixed_pressure':mode.includes('APAP')?name==='fixed_pressure':false)}}
function closePatientModal(){$('#patientModal').classList.add('hidden');state.patientEdit=null}
async function savePatientForm(e){e.preventDefault();const edit=state.patientEdit;if(!edit)return;const form=e.currentTarget,data={...(edit.data||{})};for(const [name,,type] of PATIENT_SCHEMAS[edit.kind].fields){const el=form.elements[name];if(!el||type==='file')continue;if(type==='checkbox')data[name]=el.checked;else if(type==='select-accessories')data[name]=[...el.selectedOptions].map(o=>o.value);else if(type==='number')data[name]=el.value===''?'':Number(el.value);else data[name]=el.value.trim?el.value.trim():el.value}if(edit.kind==='profile'){const taj=tajDigits(data.taj);data.taj=taj;if(data.taj_validate&&taj&& !validTaj(taj)){showError(new Error('A megadott TAJ-szám ellenőrző számjegye hibás. Kapcsold ki az ellenőrzést, ha mégis így szeretnéd tárolni.'));return}await apiWrite('/api/patient/profile','POST',data);const file=form.elements.profile_photo?.files?.[0];if(file){const url=await resizeImageToDataUrl(file,512);await apiWrite('/api/patient/photo','POST',{data_url:url})}}else await apiWrite(`/api/patient/record/${edit.kind}`,'POST',data);closePatientModal();state.patient=await api('/api/patient');renderPatient();setPatientTab(state.patientTab);await loadPatientTherapy($('#patientTherapyPeriod').value);if(['device','mask','accessory','setup'].includes(edit.kind))await loadEquipmentPage();addLog('INFO','Kezelt személy adatai mentve.')}
async function resizeImageToDataUrl(file,max){const img=await new Promise((res,rej)=>{const i=new Image();i.onload=()=>res(i);i.onerror=rej;i.src=URL.createObjectURL(file)});const scale=Math.min(1,max/Math.max(img.width,img.height)),w=Math.max(1,Math.round(img.width*scale)),h=Math.max(1,Math.round(img.height*scale)),c=document.createElement('canvas');c.width=w;c.height=h;c.getContext('2d').drawImage(img,0,0,w,h);return c.toDataURL('image/webp',.82)}
async function deleteRecord(kind,id){try{await apiWrite(`/api/patient/record/${kind}/${id}`,'DELETE');state.patient=await api('/api/patient');renderPatient();setPatientTab(state.patientTab);if(['device','mask','accessory','setup'].includes(kind))await loadEquipmentPage()}catch(e){showError(e)}}
function confirmAction(text,fn,yesLabel='Törlés'){state.confirmAction=fn;$('#confirmText').textContent=text;$('#confirmYes').textContent=yesLabel;$('#confirmModal').classList.remove('hidden')}
function closeConfirm(){$('#confirmModal').classList.add('hidden');state.confirmAction=null;$('#confirmYes').textContent='Törlés'}
async function deletePatientOnly(){try{await apiWrite('/api/patient','DELETE');state.patient=await api('/api/patient');renderPatient();setPatientTab('overview');addLog('INFO','Kezelt személy metaadatai törölve; CPAP mérési adatok változatlanok.')}catch(e){showError(e)}}
function bytesToBase64(bytes){let out='';const step=0x8000;for(let i=0;i<bytes.length;i+=step)out+=String.fromCharCode(...bytes.subarray(i,i+step));return btoa(out)}
function base64ToBytes(s){const bin=atob(s),out=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)out[i]=bin.charCodeAt(i);return out}
async function backupKey(password,salt,iterations=250000){if(!globalThis.crypto?.subtle)throw new Error('A böngésző titkosítási API-ja nem érhető el. A mentést a helyi localhost címen készítsd el.');const enc=new TextEncoder(),base=await crypto.subtle.importKey('raw',enc.encode(password),'PBKDF2',false,['deriveKey']);return crypto.subtle.deriveKey({name:'PBKDF2',salt,iterations,hash:'SHA-256'},base,{name:'AES-GCM',length:256},false,['encrypt','decrypt'])}
async function exportPatientBackup(){const pwd=$('#backupPassword').value;if(pwd.length<8){showError(new Error('A mentési jelszó legyen legalább 8 karakter.'));return}try{clearError();$('#backupExportInfo').textContent='Mentés készítése…';const bundle=await api('/api/patient/export'),salt=crypto.getRandomValues(new Uint8Array(16)),iv=crypto.getRandomValues(new Uint8Array(12)),key=await backupKey(pwd,salt),plain=new TextEncoder().encode(JSON.stringify(bundle)),cipher=new Uint8Array(await crypto.subtle.encrypt({name:'AES-GCM',iv},key,plain)),wrapper={format:'cpap-elemzo-encrypted-backup',version:1,kdf:{name:'PBKDF2-SHA256',iterations:250000,salt:bytesToBase64(salt)},cipher:{name:'AES-GCM',iv:bytesToBase64(iv)},data:bytesToBase64(cipher)};const blob=new Blob([JSON.stringify(wrapper)],{type:'application/json'}),a=document.createElement('a'),name=(state.patient?.profile?.name||'kezelt_szemely').replace(/[^a-z0-9áéíóöőúüű_-]+/gi,'_');a.href=URL.createObjectURL(blob);a.download=`SleepMate_${name}_${new Date().toISOString().slice(0,10)}.cpapbackup`;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),1000);const c=bundle.equipment_counts||{};$('#backupExportInfo').textContent=`Titkosított mentés elkészült. Felszerelés: ${c.devices||0} készülék • ${c.masks||0} maszk • ${c.accessories||0} kiegészítő • ${c.setups||0} konfiguráció. Az EDF mérési adatok nincsenek benne.`;addLog('INFO','Kezelt személy titkosított biztonsági mentése elkészült, felszerelési adatokkal.')}catch(e){showError(e);$('#backupExportInfo').textContent='A mentés nem sikerült.'}}
function askEquipmentImport(bundle){return new Promise(resolve=>{const modal=$('#equipmentImportModal'),sum=$('#equipmentImportSummary'),yes=$('#equipmentImportYes'),no=$('#equipmentImportNo'),cancel=$('#equipmentImportCancel');const eq=bundle?.equipment||{},counts=bundle?.equipment_counts||{devices:(eq.devices||bundle?.data?.devices||[]).length,masks:(eq.masks||bundle?.data?.masks||[]).length,accessories:(eq.accessories||bundle?.data?.accessories||[]).length,setups:(eq.setups||bundle?.data?.setups||[]).length};sum.innerHTML=`<span><b>${counts.devices||0}</b> készülék</span><span><b>${counts.masks||0}</b> maszk</span><span><b>${counts.accessories||0}</b> kiegészítő</span><span><b>${counts.setups||0}</b> konfiguráció</span>`;const done=v=>{modal.classList.add('hidden');yes.onclick=no.onclick=cancel.onclick=null;resolve(v)};yes.onclick=()=>done(true);no.onclick=()=>done(false);cancel.onclick=()=>done(null);modal.classList.remove('hidden')})}
async function importPatientBackup(){const file=$('#importBackupFile').files?.[0],pwd=$('#importBackupPassword').value,mode=$('#importBackupMode').value;if(!file){showError(new Error('Válassz ki egy .cpapbackup fájlt.'));return}if(!pwd){showError(new Error('Add meg a mentés jelszavát.'));return}const proceed=async()=>{try{clearError();$('#backupImportInfo').textContent='Visszatöltés…';const wrapper=JSON.parse(await file.text());if(wrapper.format!=='cpap-elemzo-encrypted-backup'||wrapper.version!==1)throw new Error('Nem támogatott mentési fájl.');const salt=base64ToBytes(wrapper.kdf?.salt||''),iv=base64ToBytes(wrapper.cipher?.iv||''),key=await backupKey(pwd,salt,Number(wrapper.kdf?.iterations)||250000),plain=await crypto.subtle.decrypt({name:'AES-GCM',iv},key,base64ToBytes(wrapper.data||'')),bundle=JSON.parse(new TextDecoder().decode(plain));const includeEquipment=await askEquipmentImport(bundle);if(includeEquipment===null){$('#backupImportInfo').textContent='A visszatöltés megszakítva.';return}const res=await apiWrite('/api/patient/import','POST',{bundle,mode,include_equipment:includeEquipment});state.patient=await api('/api/patient');renderPatient();setPatientTab('overview');$('#backupImportInfo').textContent=`Visszatöltve: ${res.records_imported||0} rekord${includeEquipment?` • ebből ${res.equipment_imported||0} felszerelési rekord`: ' • felszerelés nélkül'}.`;addLog('INFO',`Kezelt személy mentése visszatöltve (${mode}, felszerelés: ${includeEquipment?'igen':'nem'}).`)}catch(e){showError(new Error(e.name==='OperationError'?'A jelszó hibás vagy a mentési fájl sérült.':e.message||e));$('#backupImportInfo').textContent='A visszatöltés nem sikerült.'}};if(mode==='replace')confirmAction('A teljes profil-visszaállítás lecseréli a jelenlegi személyes és terápiás metaadatokat. A következő lépésben külön eldöntheted, hogy a felszerelést is visszatöltöd-e. Az EDF/CPAP mérési fájlokat NEM törli. Biztosan folytatod?',proceed,'Visszatöltés');else await proceed()}


function dayAssessmentFromPatient(day){return (state.patient?.daily_assessments||[]).find(x=>x.day===day||x.id===`day-${day}`)||null}
function renderDailyAssessmentDisplay(day){
  const a=dayAssessmentFromPatient(day),box=$('#dailyAssessmentDisplay'),status=$('#dailyAssessmentStatus'),btn=$('#openDailyAssessment'),del=$('#deleteDailyAssessment');if(!box||!status)return;
  if(!a){box.className='assessment-display hidden';box.innerHTML='';status.textContent='Nincs még rögzített értékelés.';if(btn)btn.textContent='Értékelés rögzítése';if(del)del.classList.add('hidden');return}
  if(del)del.classList.remove('hidden');
  const facts=[];
  if(a.headache!==undefined&&a.headache!=='')facts.push(['Reggeli fejfájás',a.headache]);
  if(a.fatigue!==undefined&&a.fatigue!=='')facts.push(['Nappali fáradtság',a.fatigue]);
  if(a.awakenings!==undefined&&a.awakenings!=='')facts.push(['Ébredések',String(a.awakenings)]);
  if(a.sleep_quality!==undefined&&a.sleep_quality!=='')facts.push(['Alvásminőség',`${a.sleep_quality}/10`]);
  if(a.dry_mouth)facts.push(['Tünet','Szájszárazság']);
  if(a.congestion)facts.push(['Tünet','Orrdugulás']);
  box.className='assessment-display has-data';
  box.innerHTML=`<div class="assessment-chips">${facts.map(([k,v])=>`<span><small>${escapeHtml(k)}</small><b>${escapeHtml(v)}</b></span>`).join('')}</div>${a.note?`<div class="assessment-note">${escapeHtml(a.note)}</div>`:''}`;
  status.textContent=a.updated_at?`Mentve: ${new Date(a.updated_at).toLocaleString('hu-HU')}`:'Rögzített értékelés';
  if(btn)btn.textContent='Értékelés szerkesztése'
}
function loadDailyAssessment(day,patient=state.patient){
  state.patient=patient||state.patient;const a=dayAssessmentFromPatient(day)||{};
  $('#dailyHeadache').value=a.headache||'nincs';$('#dailyFatigue').value=a.fatigue||'nincs';$('#dailyAwakenings').value=a.awakenings??'';$('#dailySleepQuality').value=a.sleep_quality??'';$('#dailyDryMouth').checked=!!a.dry_mouth;$('#dailyCongestion').checked=!!a.congestion;$('#dailyAssessmentNote').value=a.note||'';
  renderDailyAssessmentDisplay(day)
}
function openDailyAssessmentModal(){if(!state.currentDay)return;loadDailyAssessment(state.currentDay,state.patient);$('#dailyAssessmentModalTitle').textContent=`Napi értékelés – ${formatDayCode(state.currentDay)}`;$('#dailyAssessmentModal').classList.remove('hidden')}
function closeDailyAssessmentModal(){$('#dailyAssessmentModal').classList.add('hidden')}
function collectDailyAssessment(){const day=state.currentDay;if(!day)return null;return{id:`day-${day}`,day,headache:$('#dailyHeadache').value,fatigue:$('#dailyFatigue').value,awakenings:$('#dailyAwakenings').value===''?'':Number($('#dailyAwakenings').value),sleep_quality:$('#dailySleepQuality').value===''?'':Number($('#dailySleepQuality').value),dry_mouth:$('#dailyDryMouth').checked,congestion:$('#dailyCongestion').checked,note:$('#dailyAssessmentNote').value.trim()}}
async function saveDailyAssessment(e){e?.preventDefault?.();const data=collectDailyAssessment();if(!data)return;try{await apiWrite('/api/patient/record/daily_assessment','POST',data);state.patient=await api('/api/patient');renderDailyAssessmentDisplay(data.day);closeDailyAssessmentModal();addLog('INFO',`Napi saját értékelés mentve: ${formatDayCode(data.day)}.`);if($('#dashboardCalendarMonth'))renderDashboardCalendar(false)}catch(err){showError(err)}}
async function deleteDailyAssessment(){if(!state.currentDay)return;const a=dayAssessmentFromPatient(state.currentDay);if(!a)return;confirmAction('Biztosan törlöd az adott nap saját értékelését?',async()=>{try{await apiWrite(`/api/patient/record/daily_assessment/${encodeURIComponent(a.id)}`,'DELETE');state.patient=await api('/api/patient');renderDailyAssessmentDisplay(state.currentDay);addLog('INFO',`Napi saját értékelés törölve: ${formatDayCode(state.currentDay)}.`)}catch(e){showError(e)}},'Törlés')}
function mainTherapySessions(summary){const ss=(summary?.sessions||[]).filter(x=>Number(x.duration_s||0)>=300);return ss.length?ss:(summary?.sessions||[])}
function therapyInterruptionMinutes(summary){const ss=mainTherapySessions(summary);let total=0;for(let i=1;i<ss.length;i++){const gap=(new Date(ss[i].start)-new Date(ss[i-1].end))/60000;if(gap>1&&gap<180)total+=gap}return Math.round(total)}
function nightEvaluationData(summary,stats,patient){
  const map=Object.fromEntries((stats?.rows||[]).map(r=>[r.key,r])),ahi=Number(summary?.ahi||0),leak=map.leak?.p95,pressure=map.pressure?.p95,rx=currentPrescription(patient?.prescriptions||[]),counts=summary?.counts||{},gap=therapyInterruptionMinutes(summary),usage=summary?.therapy_seconds||0;
  let title='Terápia eredményes',tone='good',lead='A fő terápiás mutatók kedvezőek.';
  if(ahi>=15){title='Magas maradék AHI';tone='bad';lead='Az eseményszám alapján érdemes a terápiát részletesen áttekinteni.'}
  else if(ahi>=5){title='Emelkedett maradék AHI';tone='warn';lead='A terápiás eseményszám magasabb a kívánatosnál.'}
  else if(usage<14400){title='Rövid terápiás használat';tone='warn';lead='Az éjszakai használat nem érte el a 4 órát.'}
  const items=[];
  items.push({icon:'♥',label:'AHI',value:`${num(ahi,2)} /óra`,detail:ahi<1?'Kiváló':ahi<5?'Jó':ahi<15?'Emelkedett':'Magas',tone:ahi<5?'good':ahi<15?'warn':'bad'});
  if(leak!=null)items.push({icon:'≋',label:'Szivárgás P95',value:`${num(leak,1)} L/perc`,detail:leak<24?'Elfogadható':'Magasabb',tone:leak<24?'good':'warn'});
  if(pressure!=null){let detail='Napi 95. percentilis';if(rx?.mode?.includes('APAP')||rx?.pressure_type?.includes('APAP')){const lo=Number(rx.min_pressure),hi=Number(rx.max_pressure);if(Number.isFinite(lo)&&Number.isFinite(hi))detail=pressure>=lo&&pressure<=hi?`Előírt ${num(lo,1)}–${num(hi,1)} tartományban`:`Előírt: ${num(lo,1)}–${num(hi,1)} cmH₂O`}items.push({icon:'↕',label:'Nyomás P95',value:`${num(pressure,2)} cmH₂O`,detail,tone:'info'})}
  const eventText=[counts.OA?`${counts.OA} OA`:null,counts.CA?`${counts.CA} CA`:null,counts.H?`${counts.H} H`:null,counts.RERA?`${counts.RERA} RERA`:null].filter(Boolean).join(' • ')||'Nem volt jelölt esemény';
  items.push({icon:'!',label:'Események',value:eventText,detail:`Összesen ${['OA','CA','H','UA','RERA'].reduce((n,k)=>n+(counts[k]||0),0)} esemény`,tone:'info'});
  items.push({icon:'◷',label:'Megszakítás',value:gap>0?`${gap} perc`:'Nincs jelentős',detail:gap>0?'A fő terápiás szakaszok között':'Folyamatos fő alvási szakasz',tone:gap>0?'warn':'good'});
  return{title,tone,lead,items}
}
function renderNightEvaluation(summary,stats,patient){
  const ev=nightEvaluationData(summary,stats,patient);$('#nightEvalTitle').textContent=ev.title;$('#nightEvalTitle').dataset.tone=ev.tone;$('#nightEvalSubtitle').textContent=ev.lead;
  $('#nightEvalList').innerHTML=ev.items.map(x=>`<li class="night-fact ${x.tone}"><span class="night-fact-icon">${x.icon}</span><div><small>${escapeHtml(x.label)}</small><strong>${escapeHtml(x.value)}</strong><em>${escapeHtml(x.detail)}</em></div></li>`).join('')
}
function renderLatestNightOverview(summary,keyStats={}){
  if(!summary){$('#latestEvalTitle').textContent='Nincs értékelhető éjszaka';$('#latestEvalFacts').innerHTML='';return}
  const fakeStats={rows:[{key:'leak',p95:keyStats.leak_p95},{key:'pressure',p95:keyStats.pressure_p95}]},ev=nightEvaluationData(summary,fakeStats,state.patient||{});
  $('#latestEvalDate').textContent=formatDayCode(summary.day);$('#latestEvalTitle').textContent=ev.title;$('#latestEvalLead').textContent=ev.lead;$('#latestEvalIcon').textContent=ev.tone==='good'?'✓':ev.tone==='warn'?'!':'×';$('#latestEvalIcon').className=`eval-icon ${ev.tone}`;
  $('#latestEvalFacts').innerHTML=ev.items.slice(0,4).map(x=>`<div class="latest-eval-fact"><small>${escapeHtml(x.label)}</small><strong>${escapeHtml(x.value)}</strong><span>${escapeHtml(x.detail)}</span></div>`).join('')
}
function normalizeFaqText(v){return String(v??'').toLocaleLowerCase('hu-HU').normalize('NFD').replace(/[\u0300-\u036f]/g,'').trim()}
async function loadFaqPage(){
  try{
    if(!state.faqLoaded){const r=await fetch(`/glossary.json?_=${Date.now()}`,{cache:'no-store'});if(!r.ok)throw new Error('A fogalomtár nem tölthető be.');const j=await r.json();state.glossary=Array.isArray(j.entries)?j.entries:[];state.faqLoaded=true;const cats=[...new Set(state.glossary.map(x=>x.category).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'hu'));$('#faqCategory').innerHTML='<option value="">Minden kategória</option>'+cats.map(c=>`<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('')}
    renderFaqResults();
  }catch(e){showError(e)}
}
function faqNameHaystack(e){return [e.abbr,e.hungarian,e.english].map(normalizeFaqText)}
function faqFullHaystack(e){return [e.category,e.abbr,e.english,e.hungarian,e.meaning,e.details,e.unit,e.relevance,e.note].map(normalizeFaqText)}
function faqMatches(e,raw,scope){
  let q=String(raw||'').trim();if(!q)return true;const exact=q.length>=2&&q.startsWith('"')&&q.endsWith('"');if(exact)q=q.slice(1,-1);q=normalizeFaqText(q);if(!q)return true;const fields=scope==='full'?faqFullHaystack(e):faqNameHaystack(e);return exact?fields.some(v=>v===q):fields.some(v=>v.includes(q));
}
function renderFaqResults(){
  const box=$('#faqResults');if(!box)return;const q=$('#faqSearch').value,scope=$('input[name="faqScope"]:checked')?.value||'name',cat=$('#faqCategory').value;const rows=state.glossary.filter(e=>(!cat||e.category===cat)&&faqMatches(e,q,scope));$('#faqResultCount').textContent=`${rows.length} / ${state.glossary.length} fogalom`;
  if(!rows.length){box.innerHTML='<div class="panel empty-state">Nincs a keresésnek megfelelő fogalom.</div>';return}
  const grouped=new Map();for(const e of rows){if(!grouped.has(e.category||'Egyéb'))grouped.set(e.category||'Egyéb',[]);grouped.get(e.category||'Egyéb').push(e)}
  box.innerHTML=[...grouped.entries()].map(([category,items])=>`<section class="faq-category"><div class="faq-category-title"><h3>${escapeHtml(category)}</h3><span>${items.length} találat</span></div><div class="faq-entry-grid">${items.map(e=>`<details class="panel faq-entry"><summary><div class="faq-entry-title"><span class="faq-abbr">${escapeHtml(e.abbr||'—')}</span><div><strong>${escapeHtml(e.hungarian||e.english||e.abbr||'Fogalom')}</strong><small>${escapeHtml(e.english||'')}</small></div></div><span class="faq-expand">+</span></summary><div class="faq-entry-body"><div class="faq-meaning"><label>Mit jelent?</label><p>${escapeHtml(e.meaning||'—')}</p></div><div class="faq-details"><label>Részletes magyarázat</label><p>${escapeHtml(e.details||'—')}</p></div><div class="faq-meta"><span><b>Mértékegység</b>${escapeHtml(e.unit||'—')}</span><span><b>AirSense 11 relevancia</b>${escapeHtml(e.relevance||'—')}</span>${e.note?`<span><b>Megjegyzés</b>${escapeHtml(e.note)}</span>`:''}</div></div></details>`).join('')}</div></section>`).join('');
  box.querySelectorAll('.faq-entry').forEach(d=>d.addEventListener('toggle',()=>{if(!d.open)return;box.querySelectorAll('.faq-entry[open]').forEach(other=>{if(other!==d)other.open=false});requestAnimationFrame(()=>d.scrollIntoView({behavior:'smooth',block:'nearest'}))}));
}
function monthKeyFromDay(day){return day?day.slice(0,6):''}
function monthLabel(key){if(!key)return'–';const y=+key.slice(0,4),m=+key.slice(4,6);return new Intl.DateTimeFormat('hu-HU',{year:'numeric',month:'long'}).format(new Date(y,m-1,1))}
async function renderDashboardCalendar(force=false){try{const rows=await loadDayRows(force);if(!state.patient)try{state.patient=await api('/api/patient')}catch{}const months=[...new Set(rows.map(r=>monthKeyFromDay(r.day)))].sort().reverse(),sel=$('#dashboardCalendarMonth');if(!months.length){$('#dashboardCalendar').innerHTML='<div class="empty-state">Nincs naptárban megjeleníthető nap.</div>';return}const wanted=state.dashboardCalendarMonth&&months.includes(state.dashboardCalendarMonth)?state.dashboardCalendarMonth:months[0];state.dashboardCalendarMonth=wanted;sel.innerHTML=months.map(k=>`<option value="${k}" ${k===wanted?'selected':''}>${monthLabel(k)}</option>`).join('');const y=+wanted.slice(0,4),m=+wanted.slice(4,6),first=(new Date(y,m-1,1).getDay()+6)%7,last=new Date(y,m,0).getDate(),byDay=new Map(rows.filter(r=>monthKeyFromDay(r.day)===wanted).map(r=>[+r.day.slice(6,8),r])),ass=state.patient?.daily_assessments||[];let html='<div class="calendar-weekdays">'+['H','K','Sze','Cs','P','Szo','V'].map(x=>`<b>${x}</b>`).join('')+'</div><div class="calendar-grid">';for(let i=0;i<first;i++)html+='<div class="calendar-cell empty"></div>';for(let d=1;d<=last;d++){const r=byDay.get(d),a=ass.find(x=>x.day===`${wanted}${String(d).padStart(2,'0')}`);if(!r){html+=`<div class="calendar-cell"><strong>${d}</strong></div>`;continue}const ahi=Number(r.ahi||0),cls=ahi<1?'excellent':ahi<5?'good':ahi<15?'warn':'bad';html+=`<button class="calendar-cell has-data ${cls}" data-calendar-day="${r.day}" type="button"><strong>${d}</strong><span>AHI <b>${num(r.ahi,2)}</b></span><span>${escapeHtml(formatUsageShort(r.usage))}</span><span>Sziv. ${r.leak_p95==null?'–':num(r.leak_p95,1)}</span>${a?.sleep_quality?`<em>★ ${a.sleep_quality}/10</em>`:''}</button>`}html+='</div>';$('#dashboardCalendar').innerHTML=html;$$('[data-calendar-day]').forEach(b=>b.onclick=()=>navigate('dashboard',b.dataset.calendarDay))}catch(e){showError(e)}}
function diagnosticAdvice(title){
  if(title==='Sérült / csonka EDF')return{target:'damagedFilesPanel',text:'Töltsd le vagy másold le újra az érintett EDF-fájlt az SD-kártyáról. Amíg a fájl csonka, az abból számolt részletes görbe vagy statisztika nem tekinthető teljesnek.'};
  if(title==='Hiányzó BRP / PLD / EVE')return{target:'missingFilesPanel',text:'Ellenőrizd az érintett szakaszt az alábbi táblázatban, majd készíts teljes SD-mentést újra. A BRP a nagyfelbontású légáramlást, a PLD a részletes terápiás csatornákat, az EVE az eseményeket tartalmazza.'};
  if(title==='STR vs DATALOG')return{target:null,text:'A részletes DATALOG-adat ettől még használható. A következő teljes mentésnél az STR.EDF gyökérfájlt töltsd le újra és írd felül, hogy a napi összesítő is friss legyen.'};
  if(title==='Utolsó sikeres frissítés')return{target:null,text:'Ez az időpont jelzi, mikor olvasta újra sikeresen a program az adatforrást. Ha túl régi, használd felül az „Adatok frissítése” gombot.'};
  return{target:null,text:'Ez tájékoztató állapot. Ha figyelmeztetés látható, a részletes sor megmutatja, melyik adatforrást érdemes ellenőrizni.'};
}
function renderDiagnosticSummary(rows){
  const box=$('#diagnosticSummary');if(!box)return;box.innerHTML=(rows||[]).map((r,i)=>{const a=diagnosticAdvice(r.title);return`<article class="diagnostic-row ${r.level==='WARN'?'warn':'ok'}" data-diag="${i}"><div class="diagnostic-main"><b>${escapeHtml(r.title)}</b><span>${escapeHtml(r.message)}</span></div><button class="diagnostic-help" type="button">${r.level==='WARN'?'Mit tegyek?':'Részletek'}</button><div class="diagnostic-advice hidden"><p>${escapeHtml(a.text)}</p>${a.target?`<button type="button" data-scroll-diagnostic="${a.target}">Ugrás a részletekhez</button>`:''}</div></article>`}).join('');
  box.querySelectorAll('.diagnostic-help').forEach(b=>b.onclick=()=>{const row=b.closest('.diagnostic-row'),ad=row.querySelector('.diagnostic-advice'),opening=ad.classList.contains('hidden');box.querySelectorAll('.diagnostic-advice').forEach(x=>x.classList.add('hidden'));box.querySelectorAll('.diagnostic-row').forEach(x=>x.classList.remove('expanded'));if(opening){ad.classList.remove('hidden');row.classList.add('expanded')}});
  box.querySelectorAll('[data-scroll-diagnostic]').forEach(b=>b.onclick=()=>document.getElementById(b.dataset.scrollDiagnostic)?.scrollIntoView({behavior:'smooth',block:'start'}));
}
async function clearAllLogs(){
  try{await apiWrite('/api/logs/clear','POST',{});state.logs=[];renderLogs();await loadAiDiagnosticLog();flashInlineStatus($('#logGeneratedAt'),'Naplók kiürítve.');}
  catch(e){showError(e)}
}
async function loadDiagnostics(){try{await loadAiDiagnosticLog();const [d,h,sys]=await Promise.all([api('/api/logs/diagnostics'),api('/api/logs/history?limit=80'),api('/api/system/status')]);state.diagnostics=d;state.systemStatus=sys;renderSystemStatus(sys);$('#logImportCount').textContent=`${d.days||0} nap`;$('#logGeneratedAt').textContent=`${d.edf_files||0} EDF • utolsó sikeres frissítés: ${new Date(d.last_successful_refresh||d.generated_at).toLocaleString('hu-HU')}`;$('#logErrorCount').textContent=(d.errors||[]).length;$('#logDamagedCount').textContent=(d.damaged_files||[]).length;$('#logMissingCount').textContent=(d.missing_required||[]).length;$('#logStrWarningText').textContent=d.str_warning?'⚠ STR régebbi a DATALOG-nál':'STR/DATALOG ellenőrzés rendben';renderDiagnosticSummary(d.summary||[]);$('#damagedFilesBody').innerHTML=(d.damaged_files||[]).length?(d.damaged_files||[]).map(r=>`<tr><td>${escapeHtml(r.day)}</td><td>${escapeHtml(r.file||'–')}</td><td>${r.header_records??'–'}</td><td>${r.actual_records??'–'}</td><td>${r.trailing_bytes??'–'}</td></tr>`).join(''):'<tr><td colspan="5">Nem találtam sérült vagy csonka EDF fájlt.</td></tr>';$('#missingFilesBody').innerHTML=(d.missing_required||[]).length?(d.missing_required||[]).map(r=>`<tr><td>${escapeHtml(r.day)}</td><td>#${r.session}</td><td>${fmtClock(r.start)}</td><td>${escapeHtml((r.missing||[]).join(', '))}</td><td>${escapeHtml((r.present||[]).join(', '))}</td></tr>`).join(''):'<tr><td colspan="5">Nem találtam hiányzó BRP / PLD / EVE szakaszfájlt.</td></tr>';if(h?.rows?.length){const persistent=h.rows.map(x=>({time:new Date(x.time),type:x.level==='HIBA'?'HIBA':x.level==='WARN'?'WARN':'INFO',msg:(x.kind==='ai'?'[AI] ':'')+x.message+(x.kind==='ai'&&x.details?.model?` • ${x.details.model}`:''),source:'persistent'}));state.logs=[...persistent,...state.logs].slice(0,200);renderLogs()}addLog('INFO','Adatintegritási diagnosztika lefutott.')}catch(e){showError(e)}}
document.addEventListener('click',async e=>{if(e.target?.id==='deletePhotoInline'){e.preventDefault();confirmAction('Biztosan törlöd a profilképet?',async()=>{await apiWrite('/api/patient/photo','DELETE');state.patient=await api('/api/patient');renderPatient();closePatientModal()})}});

// One document load = exactly one animated SleepMate startup splash.
// Service-worker activation never reloads standalone PWA, and this guard also
// prevents an accidental duplicate boot if the bundle is evaluated twice.
if(!window.__sleepmateBootStarted){
  window.__sleepmateBootStarted=true;
  prepareStartupSplash();
  init();
}
