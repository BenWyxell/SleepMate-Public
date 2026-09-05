from pathlib import Path

from cpap.version import APP_VERSION

# This matrix is the source-level companion to the exact-SHA packaged Edge acceptance.
ROOT = Path(__file__).resolve().parents[1]

def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')

JS = read('web/o2ring.js')
CSS = read('web/o2ring-v534.css')
FRONT = read('web/frontend-v534.js')
HTML = read('web/index.html')
DOMAIN = read('cpap/oximetry.py')
BROWSER = read('scripts/v534_browser_acceptance.py')
RELEASE_NOTES = read('RELEASE_NOTES.md')
SW = read('web/service-worker.js')
SW_BASE = read('web/service-worker-v508-base.js')

def test_01_daily_spo2_and_pulse_cards_use_matched_medians():
    assert 'function hydrateDailyO2Metrics()' in JS
    assert 's.spo2_median' in JS and 's.heart_rate_median' in JS
    assert 'daily SpO2 card did not hydrate the matched O2 median' in BROWSER

def test_02_focus_contains_only_two_stock_o2_mini_cards():
    focus = JS[JS.index('const O2_FOCUS_DEFS'):JS.index('function ensureStackO2')]
    assert "title:'SpO₂'" in focus and "title:'Pulzus'" in focus
    assert 'smO2FocusDual' not in focus
    assert "card.className='overview-card sm-o2-focus-mini'" in focus

def test_03_o2_drag_selection_is_visibly_painted():
    assert "drag?.mode==='zoom'" in JS and "rgba(85,183,255,.16)" in JS
    assert 'require_drag_selection(page, "o2rDaySpo2Chart")' in BROWSER
    assert 'require_drag_selection(page, "o2rDayHrChart")' in BROWSER

def test_04_focus_o2_uses_the_normal_core_hero_chart():
    assert 'card.onclick=()=>selectSignal(d.key)' in JS
    assert 'loadMainSignal.__smO2' in JS and 'o2CoreSignal(state.selectedSignal)' in JS
    assert 'SpO2 Focus mini did not open the normal hero chart' in BROWSER

def test_05_o2_line_weight_matches_normal_charts():
    assert 'opts.lineWidth??1.15' in JS
    assert 'COLORS.spo2,1.05' in JS and 'COLORS.hr,1.05' in JS
    assert 'O2 chart line weight is thicker than normal charts' in BROWSER

def test_06_all_charts_overlay_has_right_scales_and_hover_values():
    assert 'function drawOverlayScaleLabels' in JS
    assert 'O₂ 100%' in JS and 'O₂ 75%' in JS and 'HR ${hrHi}' in JS and 'HR ${hrLo}' in JS
    assert "parts.push(`SpO₂ ${fmt(r.spo2,0)}%`)" in JS
    assert "parts.push(`Pulzus ${fmt(r.heart_rate,0)} bpm`)" in JS
    assert 'All Charts overlay lacks SpO2 right-axis labels' in BROWSER
    assert "'SpO₂' in x and 'Pulzus' in x" in BROWSER

def test_07_overlay_off_option_is_alapnezet():
    assert '<option value="off">Alapnézet</option>' in JS
    assert '+ O₂</option>' not in JS

def test_08_latest_sleep_card_shows_total_duration():
    assert '<label>Alvásidő</label>' in HTML
    assert 'latestDuration(summary)' in FRONT
    assert 'latest?.summary||latest' in FRONT
    assert 'latest sleep card does not show total therapy duration' in BROWSER

def test_09_dashboard_oximetry_summary_is_stably_owned_and_draws_data():
    assert 'function ensureDashboardO2Section()' in JS
    assert 'const sec=ensureDashboardO2Section();if(!sec)return' in JS
    assert 'seg.length===1' in JS
    assert 'Dashboard O2 summary disappeared with one matched night' in BROWSER

def test_10_report_selected_days_table_is_compact():
    assert "classList.add('sm-report-days-compact')" in JS
    assert '.sm-report-days-compact .report-days-table th' in CSS
    assert 'Reports selected-days table remains oversized' in BROWSER

def test_11_daily_statistics_contains_spo2_and_pulse_min_median_max():
    assert 'spo2_maximum: int | None' in DOMAIN
    assert "row('spo2','SpO₂ (O2Ring)'" in JS
    assert "row('hr','Pulzus (O2Ring)'" in JS
    assert 'Daily Statistics missing pulse min/median/max' in BROWSER
    assert 'Daily Statistics did not use refreshed minimum SpO2' in BROWSER

def test_12_oximetry_top_navigation_is_one_row_after_sync():
    install = JS[JS.index('function installPage()'):JS.index('function closeMobileO2Drawer()')]
    actions = install[install.index('<div class="o2r-hero-actions">'):install.index('</div><div id="o2rSearchState"')]
    assert actions.index('o2rSyncNowTop') < actions.index('data-o2r-tab="live"') < actions.index('data-o2r-tab="recordings"') < actions.index('data-o2r-tab="trends"')
    assert '<div class="o2r-tabs">' not in install

def test_13_large_state_card_is_moved_under_connection_search_area():
    install = JS[JS.index('function installPage()'):JS.index('function closeMobileO2Drawer()')]
    assert 'id="o2rSearchState" class="o2r-search-state"' in install
    assert 'o2r-live-card state' not in install
    assert '.o2r-search-state{' in CSS

def test_14_night_evaluation_o2_card_only_contains_spo2_and_pulse_medians():
    block = JS[JS.index('function renderNightCard()'):JS.index('function drawDashboardO2Mini()')]
    assert "list=id('nightEvalList')" in block
    assert 's.spo2_median' in block and 's.heart_rate_median' in block
    for forbidden in ('Minimum <b>', 'T90 <b>', 'ODI3 / ODI4 <b>'):
        assert forbidden not in block

def test_15_night_o2_card_is_a_normal_grid_card_not_full_width():
    assert '#nightEvalList .sm-night-o2-card' in CSS
    assert 'width:auto!important' in CSS and 'max-width:none!important' in CSS
    assert 'night O2 card still spans the full PC width' in BROWSER


def test_browser_acceptance_fixture_has_single_live_rows_declaration():
    assert BROWSER.count('const liveRows = [') == 1


def test_release_tree_has_no_v535_one_shot_patch_helpers():
    forbidden_names = {
        '_v535_round3_patch.py',
        '_v535_round3_prepare.py',
        '_v535_round3_contract_align.py',
        '_v535_fix_browser_fixture.py',
        'v535_stability_followup_patch.py',
        '_v535_round3_patch.yml',
        '_v535_fix_browser_fixture.yml',
        'v535-stability-followup-patch.yml',
    }
    leftovers = [
        p.relative_to(ROOT).as_posix()
        for p in ROOT.rglob('*')
        if p.is_file() and (p.name.startswith('_v535_') or p.name in forbidden_names)
    ]
    assert leftovers == []


def test_stability_status_timer_cannot_rearm_after_uninstall():
    assert "async function refreshStatus(){if(!R.installed)return" in JS
    assert "if(!R.installed)return;R.status=x" in JS
    assert "finally{if(R.installed)" in JS
    assert "clearO2Interactions();if(R.eventSource)" in JS

def test_stability_peer_mode_switch_reuses_loaded_daily_o2():
    assert "ox?.classList.remove('hidden');loadDaily(false).then(drawDaily)" in JS
    assert "peer-mode switching force-refetched daily O2 data" in BROWSER

def test_stability_trends_use_date_axis_and_dashboard_o2_matches_smooth_core_style():
    assert JS.count("gapSeconds:36*3600") >= 1
    assert JS.count("xLabel:date") >= 2
    assert "tooltipLabel:ts=>`${date(ts)} ${clock(ts)}`" in JS
    assert "smooth:true,points:true,connectGaps:true,lineWidth:2" in JS
    assert "Dashboard O2 trend is not smoothed like the core Dashboard trends" in BROWSER
    assert "O2 trend X-axis did not render dates" in BROWSER


def test_stability_live_view_starts_fresh_and_never_refills_historical_buffer():
    resume = JS[JS.index('async function resumeLive()'):JS.index('function updateLiveLifecycle()')]
    assert 'openLiveStream()' in resume
    assert 'await refillLive(' not in resume
    assert 'if(R.liveResumePromise)return R.liveResumePromise' in resume
    assert 'R.livePageActive=true;R.live=[];R.liveZoom=null;drawLive()' in JS
    assert 'if(!measuring&&R.live.length){R.live=[];R.liveZoom=null;drawLive()}' in JS
    assert 'Live O2 uses only the current visible measurement session' in BROWSER


def test_request_05_edge_compares_o2_hero_to_real_core_hero_width():
    assert "normal_hero_widths" in BROWSER
    assert "spo2_hero_width" in BROWSER
    assert "Focus SpO2 hero line does not match normal hero line width" in BROWSER
    assert "Focus SpO2 hero line is thicker than normal" not in BROWSER


def test_request_01_restores_core_oximetry_when_ring_match_disappears():
    assert "applyOximetryVisibility(state.summary)" in JS
    assert "daily SpO2 card stayed stale after matched O2 data disappeared" in BROWSER
    assert "daily pulse card stayed stale after matched O2 data disappeared" in BROWSER
    assert "daily SpO2 median did not return when matched O2 data returned" in BROWSER


def test_request_05_edge_fixture_loads_real_core_flow_signal_path():
    assert "flowSignal" in BROWSER
    assert "/signal/flow" in BROWSER
    assert "state.selectedSignal==='flow' && state.mainSignal?.series?.length" in BROWSER


def test_mobile_oximetry_landscape_is_behaviorally_covered():
    assert "iPhone landscape Oximetria geometry" in BROWSER
    assert "Oximetria iPhone landscape" in BROWSER
    assert "landscape O2 X origins differ" in BROWSER
    assert "landscape O2 plot widths differ" in BROWSER


def test_release_identity_is_v535():
    assert APP_VERSION == '5.3.19'
    assert RELEASE_NOTES.startswith('# SleepMate 5.3.19\n')
    section = RELEASE_NOTES.split('\n---\n', 1)[0]
    assert 'Release build: **5.3.19**.' in section
    assert 'Kiadási csatorna: **stable**.' in section


def test_release_cache_generation_is_v535_while_frontend_generation_remains_v534():
    for worker in (SW, SW_BASE):
        assert "const CACHE='sleepmate-shell-v5.3.19-o2-updater-recovery-1';" in worker
        assert "const API_CACHE='sleepmate-api-v5.3.9-refactor';" in worker
        assert "const UI_VERSION='5.3.4';" in worker
        assert '/frontend-v534.js?v=5.3.4' in worker
