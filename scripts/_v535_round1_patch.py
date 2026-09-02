from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


def write(path, text):
    (ROOT / path).write_text(text, encoding='utf-8')


def replace_once(path, old, new):
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{path}: expected 1 occurrence, found {count}: {old[:100]!r}')
    write(path, text.replace(old, new, 1))


def replace_between(path, start, end, new_block):
    text = read(path)
    i = text.find(start)
    if i < 0:
        raise SystemExit(f'{path}: start marker not found: {start}')
    j = text.find(end, i + len(start))
    if j < 0:
        raise SystemExit(f'{path}: end marker not found: {end}')
    write(path, text[:i] + new_block.rstrip() + '\n' + text[j:])


# 1 + 11: summary model has medians/min/max, including missing SpO2 maximum.
replace_once(
    'cpap/oximetry.py',
    '    spo2_minimum: int | None\n    heart_rate_average: float | None\n',
    '    spo2_minimum: int | None\n    spo2_maximum: int | None\n    heart_rate_average: float | None\n',
)
replace_once(
    'cpap/oximetry.py',
    '        spo2_minimum=min(spo2) if spo2 else None,\n        heart_rate_average=round(sum(heart_rate) / len(heart_rate), 2) if heart_rate else None,\n',
    '        spo2_minimum=min(spo2) if spo2 else None,\n        spo2_maximum=max(spo2) if spo2 else None,\n        heart_rate_average=round(sum(heart_rate) / len(heart_rate), 2) if heart_rate else None,\n',
)

# 1: hydrate the existing daily cards from the matched O2Ring summary, not legacy summary.oximetry.
replace_once(
    'web/o2ring.js',
    "async function loadDaily(force=false){const code=dayCode();if(!/^\\d{8}$/.test(code))return null;if(!force&&R.day&&R.dayCode===code)return R.day;const x=await getDay(code,true,force);R.day=x;R.dayCode=code;renderNightCard();renderFocus();ensureStackO2();ensureOverlayControls();return x}\n",
    "function hydrateDailyO2Metrics(){const s=R.day?.summary;if(!R.day?.available||!s)return;const spo2=num(s.spo2_median),hr=num(s.heart_rate_median);if(id('spo2')&&spo2!=null){id('spo2').textContent=`${fmt(spo2,1)}%`;id('spo2').classList.remove('no-data')}if(id('hr')&&hr!=null){id('hr').textContent=`${fmt(hr,1)}`;id('hr').classList.remove('no-data')}}\nasync function loadDaily(force=false){const code=dayCode();if(!/^\\d{8}$/.test(code))return null;if(!force&&R.day&&R.dayCode===code){hydrateDailyO2Metrics();return R.day}const x=await getDay(code,true,force);R.day=x;R.dayCode=code;hydrateDailyO2Metrics();renderNightCard();renderFocus();ensureStackO2();ensureOverlayControls();return x}\n",
)

# 14-15: make the O2 card a normal Night Evaluation grid item and keep only median SpO2 + pulse.
replace_between(
    'web/o2ring.js',
    'function renderNightCard(){',
    'function drawDashboardO2Mini(){',
    """function renderNightCard(){const list=id('nightEvalList');if(!list)return;let c=id('smNightO2Card');if(c&&c.parentElement!==list){c.remove();c=null}if(!c){c=document.createElement('li');c.id='smNightO2Card';c.className='night-fact info sm-night-o2-card';c.dataset.o2ringFeature='1';list.appendChild(c)}const x=R.day;if(!x?.available||!x.summary){c.innerHTML='<span class=\"night-fact-icon\">O₂</span><div><small>Oximetria</small><strong>Nincs illesztett O2Ring adat</strong><em>CPAP-idővel átfedő mérés nem található.</em></div>';return}const s=x.summary||{},spo2=num(s.spo2_median)??num(s.spo2_average),hr=num(s.heart_rate_median)??num(s.heart_rate_average),parts=[];if(spo2!=null)parts.push(`SpO₂ ${fmt(spo2,1)}%`);if(hr!=null)parts.push(`Pulzus ${fmt(hr,1)} bpm`);c.innerHTML=`<span class=\"night-fact-icon\">O₂</span><div><small>Oximetria</small><strong>${parts.length?parts.join(' • '):'Nincs értékelhető adat'}</strong><em>Medián • CPAP-idővel átfedő O2Ring adat</em></div>`}
""",
)

# 10-11: mark period table compact, and populate Daily Statistics with O2 min/median/max rows.
replace_once(
    'web/o2ring.js',
    "function ensureReportColumns(){const table=q('.report-days-table'),head=table?.querySelector('thead tr'),body=id('reportDaysBody');if(!table||!head||!body)return false;",
    "function ensureReportColumns(){const table=q('.report-days-table'),head=table?.querySelector('thead tr'),body=id('reportDaysBody');if(!table||!head||!body)return false;table.closest('.table-panel')?.classList.add('sm-report-days-compact');",
)
insert_marker = 'function installSettingsConnection(){'
text = read('web/o2ring.js')
if insert_marker not in text:
    raise SystemExit('web/o2ring.js: report stats insertion marker missing')
report_stats = """async function hydrateReportDailyStats(day){const body=id('statsBody');if(!body||!day)return;qa('tr[data-sm-o2-stat]',body).forEach(x=>x.remove());const x=await getDay(day,false);if(!x?.available||!x.summary)return;const s=x.summary,row=(key,title,minv,med,maxv,unit)=>{const tr=document.createElement('tr');tr.dataset.smO2Stat=key;const show=v=>num(v)==null?'–':`${fmt(v,1)}${unit}`;tr.innerHTML=`<td>${title}</td><td>${show(minv)}</td><td>${show(med)}</td><td>–</td><td>–</td><td>${show(maxv)}</td>`;body.appendChild(tr)};row('spo2','SpO₂ (O2Ring)',s.spo2_minimum,s.spo2_median,s.spo2_maximum,'%');row('hr','Pulzus (O2Ring)',s.heart_rate_minimum,s.heart_rate_median,s.heart_rate_maximum,' bpm')}
"""
text = text.replace(insert_marker, report_stats + insert_marker, 1)
write('web/o2ring.js', text)

# Hook core Night Evaluation and Daily Statistics so later core renders cannot erase O2 additions.
old_hook = "function hookCore(){if(window.__smO2CoreV534)return;window.__smO2CoreV534=true;try{if(typeof setView==='function'){"
new_hook = "function hookCore(){if(window.__smO2CoreV534)return;window.__smO2CoreV534=true;try{if(typeof renderNightEvaluation==='function'&&!renderNightEvaluation.__smO2){const origNight=renderNightEvaluation;renderNightEvaluation=function(...a){const r=origNight(...a);requestAnimationFrame(renderNightCard);return r};renderNightEvaluation.__smO2=true}if(typeof loadReportStats==='function'&&!loadReportStats.__smO2){const origReportStats=loadReportStats;loadReportStats=async function(day){const r=await origReportStats(day);await hydrateReportDailyStats(day);return r};loadReportStats.__smO2=true}if(typeof setView==='function'){"
replace_once('web/o2ring.js', old_hook, new_hook)

# 8: the latest card shows total therapy duration, with session count as secondary text.
replace_between(
    'web/frontend-v534.js',
    'function fixLatestLoading(){',
    'function hookOverviewLoading(){',
    """function latestSummary(){let latest=null;try{latest=state?.dashboardOverview?.latest||null}catch{}return latest?.summary||latest||null}
function latestDuration(summary){const seconds=Number(summary?.therapy_seconds);if(Number.isFinite(seconds)&&seconds>=0){const mins=Math.round(seconds/60);return `${Math.floor(mins/60)}:${String(mins%60).padStart(2,'0')}`}const usage=String(summary?.usage||'');return /^\\d+:\\d{2}/.test(usage)?usage.slice(0,5):'—'}
function fixLatestLoading(){const status=id('latestStatus');if(status&&status.textContent!=='—')status.textContent='—';setText(id('latestSessions'),'—')}
function syncLatestSessionCard(){const status=id('latestStatus'),sessions=id('latestSessions');if(!status||!sessions)return;const summary=latestSummary();if(!summary){setText(status,'—');setText(sessions,'—');return}const count=Array.isArray(summary.sessions)?summary.sessions.length:null;setText(status,latestDuration(summary));setText(sessions,count==null?'teljes terápiás idő':`${count} szakasz`)}
""",
)
replace_once(
    'web/index.html',
    '<article class="metric session-status"><label>Szekció</label><strong id="latestStatus">–</strong><small id="latestSessions">–</small></article>',
    '<article class="metric session-status"><label>Alvásidő</label><strong id="latestStatus">–</strong><small id="latestSessions">–</small></article>',
)

# Packaged core must never paint the old status before the v5.3.5 wrapper runs.
replace_once(
    'build/windows/SleepMate.spec',
    '    "$(\'#latestStatus\').textContent=String(latest.sessions?.length||0);$(\'#latestSessions\').textContent=\'szakasz\';",\n',
    '    "$(\'#latestStatus\').textContent=secondsToHM(latest.therapy_seconds||0);$(\'#latestSessions\').textContent=`${latest.sessions?.length||0} szakasz`;",\n',
)

# Compact reports table and normalize the Night Evaluation O2 grid card.
css = read('web/o2ring-v534.css')
css += """

/* v5.3.5 report + night-card polish */
.sm-report-days-compact>.panel-head{padding:8px 10px 3px!important;margin:0 0 5px!important}.sm-report-days-compact>.panel-head h3{font-size:12px!important}.sm-report-days-compact>.panel-head span{font-size:9px!important}.sm-report-days-compact .report-days-table.clean-fixed-table{table-layout:auto!important;min-width:1080px!important}.sm-report-days-compact .report-days-table th,.sm-report-days-compact .report-days-table td{padding:6px 8px!important;line-height:1.15!important;white-space:nowrap!important;font-size:10px!important}.sm-report-days-compact .report-days-table th{font-size:9px!important}
#nightEvalList .sm-night-o2-card{margin:0!important;width:auto!important;max-width:none!important;min-height:82px!important;background:#101923!important;border:0!important;border-radius:10px!important;box-shadow:none!important}#nightEvalList .sm-night-o2-card .night-fact-icon{background:rgba(85,216,255,.13);color:#55d8ff}
"""
write('web/o2ring-v534.css', css)

# Update the old packaging assertion to the new duration contract.
replace_once(
    'tests/test_v534_packaging_acceptance.py',
    '    # recipe. The generated packaged app must replace it with session count + label.\n    assert "textContent=\'Befejezve\'" in SPEC\n    assert "textContent=String(latest.sessions?.length||0)" in SPEC\n    assert "textContent=\'szakasz\'" in SPEC\n',
    '    # recipe. The generated packaged app must replace it with total therapy duration.\n    assert "textContent=\'Befejezve\'" in SPEC\n    assert "secondsToHM(latest.therapy_seconds||0)" in SPEC\n    assert "${latest.sessions?.length||0} szakasz" in SPEC\n',
)

# New requirements-specific contract.
write('tests/test_v535_polish_contract.py', '''from pathlib import Path\n\nfrom cpap.oximetry import OximetrySample, summarize_samples\n\nROOT = Path(__file__).resolve().parents[1]\n\ndef read(path):\n    return (ROOT / path).read_text(encoding="utf-8")\n\ndef test_v535_o2_summary_exposes_requested_median_min_max():\n    rows = [\n        OximetrySample(timestamp=0, spo2=95, heart_rate=55),\n        OximetrySample(timestamp=1, spo2=97, heart_rate=65),\n        OximetrySample(timestamp=2, spo2=99, heart_rate=75),\n    ]\n    s = summarize_samples(rows, start_ts=0, end_ts=3)\n    assert s.spo2_median == 97\n    assert s.spo2_minimum == 95\n    assert s.spo2_maximum == 99\n    assert s.heart_rate_median == 65\n    assert s.heart_rate_minimum == 55\n    assert s.heart_rate_maximum == 75\n\ndef test_v535_daily_cards_use_matched_o2ring_medians():\n    js = read("web/o2ring.js")\n    assert "function hydrateDailyO2Metrics()" in js\n    assert "s.spo2_median" in js\n    assert "s.heart_rate_median" in js\n\ndef test_v535_latest_sleep_card_is_duration_not_session_status():\n    front = read("web/frontend-v534.js")\n    html = read("web/index.html")\n    spec = read("build/windows/SleepMate.spec")\n    assert "latest?.summary||latest" in front\n    assert "latestDuration(summary)" in front\n    assert "<label>Alvásidő</label>" in html\n    assert "secondsToHM(latest.therapy_seconds||0)" in spec\n\ndef test_v535_reports_and_night_card_contract():\n    js = read("web/o2ring.js")\n    css = read("web/o2ring-v534.css")\n    assert "function hydrateReportDailyStats(day)" in js\n    assert "s.spo2_maximum" in js\n    assert "s.heart_rate_maximum" in js\n    assert "list=id('nightEvalList')" in js\n    assert "Medián • CPAP-idővel átfedő O2Ring adat" in js\n    for forbidden in ("Minimum <b>", "T90 <b>", "ODI3 / ODI4 <b>"):\n        assert forbidden not in js[js.index("function renderNightCard"):js.index("function drawDashboardO2Mini")]\n    assert ".sm-report-days-compact" in css\n''')

print('v5.3.5 round 1 patch applied')
