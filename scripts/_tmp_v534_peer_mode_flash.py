from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one replacement target, found {count}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


o2 = Path("web/o2ring.js")
replace_once(
    o2,
    "function installDaily(){const sw=q('#dashboardDailyView .view-switch,.view-switch');",
    "function installDaily(){const daily=id('dashboardDailyView'),hero=q('#dashboardDailyView .hero-panel'),sw=q('#dashboardDailyView .view-switch,.view-switch');if(daily&&sw&&!id('smDailyModeSwitchHost')){const host=document.createElement('div');host.id='smDailyModeSwitchHost';host.className='sm-daily-mode-switch-row';host.dataset.o2ringFeature='1';if(hero)hero.insertAdjacentElement('beforebegin',host);else daily.prepend(host);host.appendChild(sw)}",
)
replace_once(
    o2,
    "}const hero=q('#dashboardDailyView .hero-panel');if(hero&&!id('o2rDailyPanel')){",
    "}if(hero&&!id('o2rDailyPanel')){",
)

css = Path("web/o2ring-v534.css")
css_text = css.read_text(encoding="utf-8")
css_marker = ".sm-daily-mode-switch-row{"
if css_marker not in css_text:
    css_text += "\n/* v5.3.4 persistent peer-mode switch */\n.sm-daily-mode-switch-row{display:flex;justify-content:flex-end;align-items:center;min-width:0;margin:0 0 10px;overflow-x:auto;padding-bottom:2px}.sm-daily-mode-switch-row .view-switch{flex:0 0 auto;margin:0}@media(max-width:600px){.sm-daily-mode-switch-row{justify-content:flex-start}}\n"
    css.write_text(css_text, encoding="utf-8")

acceptance = Path("scripts/v534_browser_acceptance.py")
observer_anchor = "          const now = Math.floor(Date.now()/1000);\n"
observer_block = """          window.__smLatestStatusHistory=[];
          const attachLatestStatusWatch=()=>{
            const el=document.getElementById('latestStatus');
            if(!el||el.__smAcceptanceWatched)return !!el;
            el.__smAcceptanceWatched=true;
            const record=()=>window.__smLatestStatusHistory.push(String(el.textContent||'').trim());
            record();
            new MutationObserver(record).observe(el,{childList:true,subtree:true,characterData:true});
            return true;
          };
          if(!attachLatestStatusWatch()){
            const rootObserver=new MutationObserver(()=>{if(attachLatestStatusWatch())rootObserver.disconnect()});
            rootObserver.observe(document,{childList:true,subtree:true});
          }
"""
text = acceptance.read_text(encoding="utf-8")
if "__smLatestStatusHistory" not in text:
    if observer_anchor not in text:
        raise SystemExit("acceptance observer anchor missing")
    text = text.replace(observer_anchor, observer_anchor + observer_block, 1)

first_anchor = '        progress("runtime ready on first load")\n'
first_block = """        first_status_history = page.evaluate("() => window.__smLatestStatusHistory || []")
        require(
            not any("Befejezve" in value for value in first_status_history),
            f"latest-session card flashed legacy Befejezve during first boot: {first_status_history}",
        )
"""
if "latest-session card flashed legacy Befejezve during first boot" not in text:
    if first_anchor not in text:
        raise SystemExit("first boot flash anchor missing")
    text = text.replace(first_anchor, first_anchor + first_block, 1)

reload_anchor = '        require(page.locator("#sidebarVersion").inner_text().strip() == f"v{VERSION}", "reload restored stale UI version")\n'
reload_block = """        reload_status_history = page.evaluate("() => window.__smLatestStatusHistory || []")
        require(
            not any("Befejezve" in value for value in reload_status_history),
            f"latest-session card flashed legacy Befejezve during stale-cache recovery: {reload_status_history}",
        )
"""
if "latest-session card flashed legacy Befejezve during stale-cache recovery" not in text:
    if reload_anchor not in text:
        raise SystemExit("stale reload flash anchor missing")
    text = text.replace(reload_anchor, reload_anchor + reload_block, 1)

mode_anchor = '        page.locator("#o2rDailyBtn").click()\n'
mode_block = """        require(
            page.locator("#focusViewBtn").is_visible()
            and page.locator("#stackViewBtn").is_visible()
            and page.locator("#o2rDailyBtn").is_visible(),
            "daily peer-mode controls disappeared after entering Oximetria",
        )
        require(page.locator("#smDailyModeSwitchHost").count() == 1, "daily peer-mode switch host missing/duplicated")
"""
if "daily peer-mode controls disappeared after entering Oximetria" not in text:
    if mode_anchor not in text:
        raise SystemExit("daily mode visibility anchor missing")
    text = text.replace(mode_anchor, mode_anchor + mode_block, 1)

nav_anchor = '            navigate(page, "dashboard")\n\n        progress("data-backed Dashboard Oximetria/Focus/All charts and SleepSync invalidation")\n'
nav_block = """            navigate(page, "dashboard")

        navigation_status_history = page.evaluate("() => window.__smLatestStatusHistory || []")
        require(
            not any("Befejezve" in value for value in navigation_status_history),
            f"latest-session card flashed legacy Befejezve during repeated navigation: {navigation_status_history}",
        )

        progress("data-backed Dashboard Oximetria/Focus/All charts and SleepSync invalidation")
"""
if "latest-session card flashed legacy Befejezve during repeated navigation" not in text:
    if nav_anchor not in text:
        raise SystemExit("navigation flash anchor missing")
    text = text.replace(nav_anchor, nav_block, 1)

acceptance.write_text(text, encoding="utf-8")
