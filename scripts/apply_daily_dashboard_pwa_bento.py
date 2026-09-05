from pathlib import Path

CSS_PATH = Path('web/dashboard-pwa-v5312.css')
MARKER = '/* Phone PWA daily detail bento extension */'
css = CSS_PATH.read_text(encoding='utf-8')
if MARKER in css:
    raise SystemExit('Daily Dashboard bento extension already present.')

BLOCK = r'''

/* Phone PWA daily detail bento extension */
html.sm-phone-pwa #page-dashboard #dashboardDailyView{min-width:0;padding-bottom:8px}

html.sm-phone-pwa #page-dashboard #dashboardDailyView .daily-backbar{display:grid!important;grid-template-columns:minmax(0,1fr) auto!important;gap:8px!important;margin:0 0 8px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .daily-backbar button{min-height:38px!important;padding:8px 10px!important;border-radius:13px!important;font-size:10px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .day-toolbar{display:grid!important;grid-template-columns:1fr!important;gap:9px!important;margin:0 0 10px!important;padding:12px 13px!important;border:1px solid var(--dash-edge-soft)!important;border-radius:18px!important;background:radial-gradient(ellipse at 100% 0,rgba(169,140,255,.08),transparent 48%),linear-gradient(145deg,rgba(13,28,43,.94),rgba(8,18,30,.97))!important;box-shadow:0 12px 30px rgba(0,5,14,.16),inset 0 1px 0 rgba(255,255,255,.03)!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .day-toolbar h2{font-size:16px!important;line-height:1.1!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .day-toolbar #integrity{display:block;margin-top:4px;font-size:9px!important;line-height:1.25}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .date-nav{display:grid!important;grid-template-columns:40px minmax(0,1fr) 40px!important;gap:6px!important;width:100%!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .date-nav select{min-width:0!important;width:100%!important;min-height:38px!important;font-size:10px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .date-nav button{min-width:0!important;min-height:38px!important;padding:5px!important;border-radius:12px!important}

html.sm-phone-pwa #page-dashboard #dashboardDailyView .daily-overview-panel{margin:0 0 10px!important;padding:12px!important;border-radius:20px!important;border-color:rgba(85,220,255,.26)!important;background:radial-gradient(ellipse at 0 0,rgba(85,220,255,.085),transparent 44%),radial-gradient(ellipse at 100% 100%,rgba(169,140,255,.07),transparent 44%),linear-gradient(145deg,rgba(14,29,43,.96),rgba(8,18,30,.98))!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .daily-overview-head{display:grid!important;grid-template-columns:1fr!important;gap:8px!important;margin-bottom:9px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .daily-overview-head h3{font-size:14px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .daily-overview-head span{font-size:9px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .day-session-strip{max-width:none!important;display:flex!important;justify-content:flex-start!important;align-items:center!important;gap:6px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .day-session-strip>span{font-size:9px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .day-session-strip .sessions{gap:5px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .day-session-strip .session{padding:5px 7px!important;border-radius:10px!important;font-size:8.5px!important}

html.sm-phone-pwa #page-dashboard #dashboardDailyView .daily-core-grid{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:8px!important;border:0!important;background:transparent!important;overflow:visible!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .daily-primary-stat{--daily-accent:var(--dash-cyan);min-width:0!important;min-height:88px!important;padding:11px 11px 10px 13px!important;border:1px solid color-mix(in srgb,var(--daily-accent) 26%,rgba(91,157,199,.18))!important;border-radius:16px!important;overflow:hidden;background:radial-gradient(circle at 105% -10%,color-mix(in srgb,var(--daily-accent) 12%,transparent),transparent 50%),linear-gradient(145deg,rgba(22,38,54,.95),rgba(10,21,34,.98))!important;box-shadow:0 9px 23px rgba(0,5,14,.15),inset 0 1px 0 rgba(255,255,255,.028)!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .daily-primary-stat::before{left:0!important;top:12px!important;bottom:12px!important;width:3px!important;height:auto!important;border-radius:0 99px 99px 0!important;background:var(--daily-accent)!important;box-shadow:0 0 14px color-mix(in srgb,var(--daily-accent) 36%,transparent)}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .daily-primary-stat.ahi{--daily-accent:var(--dash-teal)}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .daily-primary-stat.usage{--daily-accent:#61b8ff}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .daily-primary-stat.events{--daily-accent:var(--dash-amber)}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .daily-primary-stat.spo2{--daily-accent:var(--dash-cyan)}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .daily-primary-stat.hr{--daily-accent:#f08da0}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .daily-primary-stat label{margin:0 0 6px!important;font-size:9px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .daily-primary-stat strong{display:block!important;margin:0!important;font-size:23px!important;line-height:1.02!important;letter-spacing:-.03em}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .daily-primary-stat small{display:block!important;margin:6px 0 0!important;font-size:8.5px!important;line-height:1.15}

html.sm-phone-pwa #page-dashboard #dashboardDailyView .daily-event-badges{display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:5px!important;margin:8px 0!important;padding:0!important;border:0!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .daily-event-badges span{min-width:0!important;padding:6px 3px!important;border-radius:11px!important;text-align:center!important;font-size:8.5px!important;white-space:nowrap}

html.sm-phone-pwa #page-dashboard #dashboardDailyView .therapy-vitals{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:7px!important;border:0!important;border-radius:0!important;overflow:visible!important;background:transparent!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .therapy-vital{min-width:0!important;min-height:72px!important;gap:8px!important;padding:9px 10px!important;border:1px solid rgba(90,162,204,.23)!important;border-radius:14px!important;background:linear-gradient(145deg,rgba(17,32,47,.92),rgba(8,19,31,.96))!important;box-shadow:inset 0 1px 0 rgba(255,255,255,.022),0 7px 18px rgba(0,5,14,.11)!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .therapy-vital-icon{width:27px!important;height:27px!important;border-radius:9px!important;font-size:9px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .therapy-vital label{font-size:8.5px!important;line-height:1.1}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .therapy-vital strong{font-size:16px!important;line-height:1.05}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .therapy-vital small{font-size:8px!important}

html.sm-phone-pwa #page-dashboard #dashboardDailyView .night-evaluation-full,html.sm-phone-pwa #page-dashboard #dashboardDailyView .compact-assessment,html.sm-phone-pwa #page-dashboard #dashboardDailyView .full-width-therapy{margin:0 0 10px!important;padding:12px!important;border-radius:18px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .night-evaluation-full .night-evaluation-grid{display:grid!important;grid-template-columns:1fr!important;gap:8px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .night-evaluation-full .night-score{min-height:auto!important;padding:10px 11px!important;border-radius:14px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .night-evaluation-full .night-score strong{font-size:17px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .night-evaluation-full .night-eval-list{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:7px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .night-evaluation-full .night-eval-list li{min-width:0!important;min-height:56px!important;padding:9px 10px!important;border-radius:13px!important;font-size:9px!important;line-height:1.3}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .compact-assessment .assessment-head{display:grid!important;grid-template-columns:minmax(0,1fr) auto!important;gap:8px!important;align-items:center!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .compact-assessment .assessment-head>div:first-child{display:block!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .compact-assessment .assessment-actions{display:flex!important;gap:5px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .compact-assessment .assessment-actions button{min-height:36px!important;padding:7px 9px!important;font-size:9px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .full-width-therapy .daily-therapy-grid{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:7px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .full-width-therapy .daily-therapy-grid>div{min-width:0!important;min-height:70px!important;padding:9px 10px!important;border-radius:13px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .full-width-therapy .daily-therapy-grid>div:first-child{grid-column:1/-1!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .full-width-therapy .daily-therapy-grid label{font-size:8.5px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .full-width-therapy .daily-therapy-grid strong{font-size:16px!important;overflow-wrap:anywhere}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .full-width-therapy .daily-therapy-grid small{font-size:8px!important}

html.sm-phone-pwa #page-dashboard #dashboardDailyView .hero-panel{margin:0 0 10px!important;padding:11px!important;border-radius:18px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .hero-head{display:grid!important;grid-template-columns:1fr!important;gap:8px!important;margin-bottom:7px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .hero-head .toolbar{display:grid!important;grid-template-columns:1fr auto!important;gap:6px!important;width:100%!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .hero-head .view-switch{display:grid!important;grid-template-columns:1fr 1fr!important;width:100%!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .hero-head .view-switch button,html.sm-phone-pwa #page-dashboard #dashboardDailyView #resetZoom{min-height:36px!important;padding:6px 8px!important;font-size:9px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .hero-stack{height:210px!important;border-radius:12px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .navigator{height:54px!important;border-radius:10px!important}

html.sm-phone-pwa #page-dashboard #dashboardDailyView .overview-block{margin:0 0 10px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .section-title{display:block!important;margin:0 1px 7px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .section-title h3{font-size:13px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .section-title span{display:block;margin-top:3px;font-size:8.5px!important;line-height:1.3}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .overview-grid{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:7px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .overview-card{min-width:0!important;padding:7px!important;border-radius:13px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .overview-card canvas{height:78px!important;border-radius:8px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .mini-head{font-size:8.5px!important;gap:4px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .mini-head small{font-size:7.5px!important}

html.sm-phone-pwa #page-dashboard #dashboardDailyView>.panel:not(.daily-overview-panel):not(.night-evaluation-full):not(.daily-note-panel):not(.daily-therapy-compare):not(.hero-panel){margin-bottom:10px!important;padding:11px!important;border-radius:18px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .panel-head{gap:8px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .panel-head h3{font-size:12.5px!important}
html.sm-phone-pwa #page-dashboard #dashboardDailyView .panel-head span{font-size:8.5px!important}

@media(max-width:370px){
  html.sm-phone-pwa #page-dashboard #dashboardDailyView .daily-core-grid,html.sm-phone-pwa #page-dashboard #dashboardDailyView .therapy-vitals,html.sm-phone-pwa #page-dashboard #dashboardDailyView .night-evaluation-full .night-eval-list,html.sm-phone-pwa #page-dashboard #dashboardDailyView .full-width-therapy .daily-therapy-grid,html.sm-phone-pwa #page-dashboard #dashboardDailyView .overview-grid{gap:6px!important}
  html.sm-phone-pwa #page-dashboard #dashboardDailyView .daily-primary-stat{min-height:84px!important;padding:10px 9px 9px 11px!important}
  html.sm-phone-pwa #page-dashboard #dashboardDailyView .daily-primary-stat strong{font-size:21px!important}
  html.sm-phone-pwa #page-dashboard #dashboardDailyView .therapy-vital{padding:8px!important;gap:6px!important}
  html.sm-phone-pwa #page-dashboard #dashboardDailyView .therapy-vital-icon{width:24px!important;height:24px!important}
}
'''
CSS_PATH.write_text(css.rstrip() + BLOCK + '\n', encoding='utf-8')

TEST = r'''from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def daily_css() -> str:
    css = read("web/dashboard-pwa-v5312.css")
    assert "/* Phone PWA daily detail bento extension */" in css
    return css.split("/* Phone PWA daily detail bento extension */", 1)[1]


def test_phone_pwa_daily_dashboard_is_compact_two_column_bento():
    css = daily_css()
    for selector in ("#dashboardDailyView .daily-core-grid", "#dashboardDailyView .therapy-vitals", "#dashboardDailyView .night-evaluation-full .night-eval-list", "#dashboardDailyView .full-width-therapy .daily-therapy-grid", "#dashboardDailyView .overview-grid"):
        assert selector in css
    assert css.count("grid-template-columns:repeat(2,minmax(0,1fr))!important") >= 5


def test_daily_bento_preserves_all_existing_data_surfaces():
    css = daily_css()
    assert "display:none" not in css
    assert "visibility:hidden" not in css
    assert "content-visibility:hidden" not in css
    for surface in ("daily-overview-panel", "night-evaluation-full", "compact-assessment", "full-width-therapy", "hero-panel", "overview-grid"):
        assert surface in css


def test_daily_bento_is_phone_pwa_scoped():
    css = daily_css()
    selectors = [line.strip() for line in css.splitlines() if line.strip().endswith('{') and not line.strip().startswith('@')]
    assert selectors
    assert all(line.startswith("html.sm-phone-pwa #page-dashboard #dashboardDailyView") for line in selectors)
'''
Path('tests/test_pwa_dashboard_daily_bento.py').write_text(TEST, encoding='utf-8')
