from pathlib import Path

path = Path('scripts/v534_browser_acceptance.py')
text = path.read_text(encoding='utf-8')


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected one target, found {count}')
    text = text.replace(old, new, 1)


main_anchor = '\n\ndef main() -> int:\n'
pinch_helper = r'''

def pinch_canvas(page: Page, canvas_id: str) -> tuple[list[float], list[float]]:
    canvas = page.locator(f"#{canvas_id}")
    canvas.scroll_into_view_if_needed()
    page.wait_for_timeout(60)
    before = page.evaluate(
        "id => {const m=document.getElementById(id)?._smO2Meta;return m?[m.a,m.b]:null}",
        canvas_id,
    )
    require(before is not None and before[1] > before[0], f"{canvas_id}: missing pre-pinch range")
    page.evaluate(
        """id => {
          const c=document.getElementById(id),r=c.getBoundingClientRect(),y=r.top+r.height*.5,cx=r.left+r.width*.55;
          const fire=(type,pointerId,x)=>c.dispatchEvent(new PointerEvent(type,{
            bubbles:true,cancelable:true,pointerId,pointerType:'touch',button:0,buttons:type==='pointerup'?0:1,
            clientX:x,clientY:y,width:12,height:12,pressure:type==='pointerup'?0:.5,isPrimary:pointerId===701
          }));
          fire('pointerdown',701,cx-45);
          fire('pointerdown',702,cx+45);
          fire('pointermove',701,cx-90);
          fire('pointermove',702,cx+90);
          fire('pointerup',701,cx-90);
          fire('pointerup',702,cx+90);
        }""",
        canvas_id,
    )
    page.wait_for_timeout(240)
    after = page.evaluate(
        "id => {const m=document.getElementById(id)?._smO2Meta;return m?[m.a,m.b]:null}",
        canvas_id,
    )
    require(after is not None and after[1]-after[0] < before[1]-before[0], f"{canvas_id}: two-finger pinch did not zoom: {before} -> {after}")
    return before, after
'''
replace_once(main_anchor, pinch_helper + main_anchor, 'pinch helper')

old_daily_reset = '''        page.locator("#o2rDayDual").dblclick()
        page.wait_for_timeout(120)

        page.wait_for_function("() => window.__smAcceptanceO2.invalidationHandlers.length > 0")
'''
new_daily_reset = '''        page.locator("#o2rDayDual").dblclick()
        page.wait_for_timeout(120)
        _, daily_pinch = pinch_canvas(page, "o2rDayDual")
        pinch_ranges = page.evaluate(
            """() => ['o2rDayDual','o2rDaySpo2Chart','o2rDayHrChart'].map(id=>{const m=document.getElementById(id)?._smO2Meta;return m?[m.a,m.b]:null})"""
        )
        require(all(r is not None for r in pinch_ranges), f"daily pinch synchronized ranges missing: {pinch_ranges}")
        require(max(abs(r[0]-daily_pinch[0])+abs(r[1]-daily_pinch[1]) for r in pinch_ranges) < .05, f"daily two-finger pinch is not synchronized: {pinch_ranges}")
        page.locator("#o2rDayDual").dblclick()
        page.wait_for_timeout(120)

        page.wait_for_function("() => window.__smAcceptanceO2.invalidationHandlers.length > 0")
'''
replace_once(old_daily_reset, new_daily_reset, 'daily pinch acceptance')

old_overlay_prepare = '''        page.evaluate(
            """() => {
              const f=window.__smAcceptanceO2;f.canvasText=[];
              state.hoverTime=f.daily.samples[1].timestamp*1000;
              window.dispatchEvent(new Event('resize'));
            }"""
        )
'''
new_overlay_prepare = '''        page.evaluate(
            """() => {
              const f=window.__smAcceptanceO2;f.canvasText=[];f.pathRecords=[];
              state.hoverTime=f.daily.samples[1].timestamp*1000;
              window.dispatchEvent(new Event('resize'));
            }"""
        )
'''
replace_once(old_overlay_prepare, new_overlay_prepare, 'overlay path reset')

old_overlay_persist = '''        require(page.evaluate("() => localStorage.getItem('sm-o2-overlay:flow')") == "both", "per-chart O2 overlay selection was not persisted")

        _, focus_zoom = zoom_canvas(page, "smO2FocusDual")
'''
new_overlay_persist = '''        require(page.evaluate("() => localStorage.getItem('sm-o2-overlay:flow')") == "both", "per-chart O2 overlay selection was not persisted")
        overlay_paths = page.evaluate(
            """() => window.__smAcceptanceO2.pathRecords.filter(x => x.id==='smO2HeroCanvas' && x.lines>0)"""
        )
        overlay_spo2 = [x for x in overlay_paths if str(x.get("style", "")).lower() in ("#55d8ff", "rgb(85, 216, 255)")]
        overlay_hr = [x for x in overlay_paths if str(x.get("style", "")).lower() in ("#a98bff", "rgb(169, 139, 255)")]
        require(len(overlay_spo2) >= 2 and len(overlay_hr) >= 2, f"CPAP O2 overlay bridged a long no-data gap: {overlay_paths}")

        _, focus_zoom = zoom_canvas(page, "smO2FocusDual")
'''
replace_once(old_overlay_persist, new_overlay_persist, 'overlay gap acceptance')

old_trend_start = '''        progress("O2 trend crosshair tooltips")
        page.locator('[data-o2r-tab="trends"]').click()
        page.wait_for_function("() => document.getElementById('o2rTrendSpo2')?._smO2Meta?.rows?.length >= 5")
        hover_canvas(page, "o2rTrendSpo2", ("SpO₂",))
'''
new_trend_start = '''        progress("O2 trend crosshair tooltips")
        page.evaluate("() => { window.__smAcceptanceO2.pathRecords=[]; }")
        page.locator('[data-o2r-tab="trends"]').click()
        page.wait_for_function("() => document.getElementById('o2rTrendSpo2')?._smO2Meta?.rows?.length >= 5")
        trend_paths = page.evaluate(
            """() => window.__smAcceptanceO2.pathRecords.filter(x =>
              x.id==='o2rTrendSpo2' && x.lines>0 &&
              ['#55d8ff','rgb(85, 216, 255)'].includes(String(x.style).toLowerCase())
            )"""
        )
        require(any(x.get("moves") == 1 and x.get("lines", 0) >= 4 for x in trend_paths), f"nightly SpO2 trend was incorrectly split between consecutive days: {trend_paths}")
        hover_canvas(page, "o2rTrendSpo2", ("SpO₂",))
'''
replace_once(old_trend_start, new_trend_start, 'trend continuity acceptance')

path.write_text(text, encoding='utf-8')
