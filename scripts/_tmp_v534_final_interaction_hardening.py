from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one target, found {count}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


p = Path("scripts/v534_browser_acceptance.py")
text = p.read_text(encoding="utf-8")

listener_anchor = "          window.__smLatestStatusHistory=[];\n"
listener_block = """          window.__smO2ListenerCounts={};
          const __smTrackedCanvasEvents=new Set(['pointerdown','pointermove','pointerup','pointercancel','pointerleave','dblclick','wheel']);
          const __smNativeTargetAdd=EventTarget.prototype.addEventListener;
          EventTarget.prototype.addEventListener=function(type,listener,options){
            if(this instanceof HTMLCanvasElement && this.id && __smTrackedCanvasEvents.has(type)){
              window.__smO2ListenerCounts[this.id]=(window.__smO2ListenerCounts[this.id]||0)+1;
            }
            return __smNativeTargetAdd.call(this,type,listener,options);
          };
"""
if "__smO2ListenerCounts" not in text:
    if listener_anchor not in text:
        raise SystemExit("listener instrumentation anchor missing")
    text = text.replace(listener_anchor, listener_anchor + listener_block, 1)

main_anchor = "\n\ndef main() -> int:\n"
pan_helper = r'''

def pan_canvas(page: Page, canvas_id: str) -> tuple[list[float], list[float]]:
    canvas = page.locator(f"#{canvas_id}")
    canvas.scroll_into_view_if_needed()
    page.wait_for_timeout(60)
    before = page.evaluate(
        "id => {const m=document.getElementById(id)?._smO2Meta;return m?[m.a,m.b]:null}",
        canvas_id,
    )
    require(before is not None and before[1] > before[0], f"{canvas_id}: missing pre-pan range")
    touch_action = page.evaluate("id => getComputedStyle(document.getElementById(id)).touchAction", canvas_id)
    require("pan-y" in str(touch_action), f"{canvas_id}: vertical page-scroll touch contract was lost: {touch_action}")
    page.evaluate(
        """id => {
          const c=document.getElementById(id),r=c.getBoundingClientRect(),y=r.top+r.height*.5,cx=r.left+r.width*.52;
          const fire=(type,x)=>c.dispatchEvent(new PointerEvent(type,{
            bubbles:true,cancelable:true,pointerId:703,pointerType:'touch',button:0,buttons:type==='pointerup'?0:1,
            clientX:x,clientY:y,width:12,height:12,pressure:type==='pointerup'?0:.5,isPrimary:true
          }));
          fire('pointerdown',cx);
          fire('pointermove',cx+70);
          fire('pointerup',cx+70);
        }""",
        canvas_id,
    )
    page.wait_for_timeout(260)
    after = page.evaluate(
        "id => {const m=document.getElementById(id)?._smO2Meta;return m?[m.a,m.b]:null}",
        canvas_id,
    )
    require(after is not None, f"{canvas_id}: missing post-pan range")
    before_span, after_span = before[1]-before[0], after[1]-after[0]
    before_mid, after_mid = (before[0]+before[1])/2, (after[0]+after[1])/2
    require(abs(after_span-before_span) < .05, f"{canvas_id}: one-finger touch pan changed zoom span: {before} -> {after}")
    require(abs(after_mid-before_mid) > .5, f"{canvas_id}: one-finger touch pan did not move the time window: {before} -> {after}")
    return before, after
'''
if "def pan_canvas(" not in text:
    if main_anchor not in text:
        raise SystemExit("main anchor missing")
    text = text.replace(main_anchor, pan_helper + main_anchor, 1)

pinch_anchor = '''        require(max(abs(r[0]-daily_pinch[0])+abs(r[1]-daily_pinch[1]) for r in pinch_ranges) < .05, f"daily two-finger pinch is not synchronized: {pinch_ranges}")
        page.locator("#o2rDayDual").dblclick()
'''
pan_block = '''        require(max(abs(r[0]-daily_pinch[0])+abs(r[1]-daily_pinch[1]) for r in pinch_ranges) < .05, f"daily two-finger pinch is not synchronized: {pinch_ranges}")
        _, daily_pan = pan_canvas(page, "o2rDayDual")
        pan_ranges = page.evaluate(
            """() => ['o2rDayDual','o2rDaySpo2Chart','o2rDayHrChart'].map(id=>{const m=document.getElementById(id)?._smO2Meta;return m?[m.a,m.b]:null})"""
        )
        require(all(r is not None for r in pan_ranges), f"daily touch-pan synchronized ranges missing: {pan_ranges}")
        require(max(abs(r[0]-daily_pan[0])+abs(r[1]-daily_pan[1]) for r in pan_ranges) < .05, f"daily one-finger touch pan is not synchronized: {pan_ranges}")
        page.locator("#o2rDayDual").dblclick()
'''
if "daily one-finger touch pan is not synchronized" not in text:
    if pinch_anchor not in text:
        raise SystemExit("pinch insertion anchor missing")
    text = text.replace(pinch_anchor, pan_block, 1)

mode_anchor = '''        progress("Focus/All charts/Oximetria repeated mode switching")
        for _ in range(6):
            for control in ("focusViewBtn", "stackViewBtn", "o2rDailyBtn"):
                page.evaluate("id => document.getElementById(id)?.click()", control)
        require(page.locator("#focusViewBtn").inner_text().strip() == "Fókusz nézet", "Focus button text mutated")
'''
mode_block = '''        progress("Focus/All charts/Oximetria repeated mode switching")
        persistent_daily_ids = [
            "o2rDayDual","o2rDaySpo2Chart","o2rDayHrChart",
            "smO2FocusSpo2","smO2FocusHr","smO2FocusDual",
            "smStackO2Spo2Canvas","smStackO2HrCanvas","smStackO2DualCanvas",
        ]
        daily_listener_before = page.evaluate(
            "ids => Object.fromEntries(ids.map(id => [id, window.__smO2ListenerCounts[id] || 0]))",
            persistent_daily_ids,
        )
        for _ in range(6):
            for control in ("focusViewBtn", "stackViewBtn", "o2rDailyBtn"):
                page.evaluate("id => document.getElementById(id)?.click()", control)
        daily_listener_after = page.evaluate(
            "ids => Object.fromEntries(ids.map(id => [id, window.__smO2ListenerCounts[id] || 0]))",
            persistent_daily_ids,
        )
        require(daily_listener_after == daily_listener_before, f"daily O2 chart listeners leaked across peer-mode switching: {daily_listener_before} -> {daily_listener_after}")
        require(page.locator("#smDailyModeSwitchHost").count() == 1, "daily peer-mode host duplicated during repeated switching")
        require(page.locator("#focusViewBtn").inner_text().strip() == "Fókusz nézet", "Focus button text mutated")
'''
if "daily O2 chart listeners leaked across peer-mode switching" not in text:
    if mode_anchor not in text:
        raise SystemExit("mode listener anchor missing")
    text = text.replace(mode_anchor, mode_block, 1)

page_tabs_anchor = '''        progress("Oximetria Live/Recordings/Trends repeated switching")
        page.locator('#sidebar [data-page="oximetry"]').click()
        page.wait_for_function("() => document.querySelector('#page-oximetry')?.classList.contains('active')")
        for _ in range(5):
            for tab in ("recordings", "trends", "live"):
                page.locator(f'[data-o2r-tab="{tab}"]').click()
                page.wait_for_timeout(60)
        require(page.locator("#page-oximetry").count() == 1, "Oximetria tab switching duplicated page")
'''
page_tabs_block = '''        progress("Oximetria Live/Recordings/Trends repeated switching")
        page.locator('#sidebar [data-page="oximetry"]').click()
        page.wait_for_function("() => document.querySelector('#page-oximetry')?.classList.contains('active')")
        for tab in ("recordings", "trends", "live"):
            page.locator(f'[data-o2r-tab="{tab}"]').click()
            page.wait_for_timeout(90)
        persistent_page_ids = [
            "o2rLiveDual","o2rLiveSpo2Chart","o2rLiveHrChart",
            "o2rTrendSpo2","o2rTrendHr","o2rTrendT90","o2rTrendOdi",
        ]
        page_listener_before = page.evaluate(
            "ids => Object.fromEntries(ids.map(id => [id, window.__smO2ListenerCounts[id] || 0]))",
            persistent_page_ids,
        )
        for _ in range(5):
            for tab in ("recordings", "trends", "live"):
                page.locator(f'[data-o2r-tab="{tab}"]').click()
                page.wait_for_timeout(60)
        page_listener_after = page.evaluate(
            "ids => Object.fromEntries(ids.map(id => [id, window.__smO2ListenerCounts[id] || 0]))",
            persistent_page_ids,
        )
        require(page_listener_after == page_listener_before, f"Oximetria page chart listeners leaked across tab switching: {page_listener_before} -> {page_listener_after}")
        require(page.locator("#page-oximetry").count() == 1, "Oximetria tab switching duplicated page")
'''
if "Oximetria page chart listeners leaked across tab switching" not in text:
    if page_tabs_anchor not in text:
        raise SystemExit("page tab listener anchor missing")
    text = text.replace(page_tabs_anchor, page_tabs_block, 1)

trend_wait_anchor = '''        page.locator('[data-o2r-tab="trends"]').click()
        page.wait_for_function("() => document.getElementById('o2rTrendSpo2')?._smO2Meta?.rows?.length >= 5")
        trend_paths = page.evaluate(
'''
trend_wait_block = '''        page.locator('[data-o2r-tab="trends"]').click()
        page.wait_for_function("() => document.getElementById('o2rTrendSpo2')?._smO2Meta?.rows?.length >= 5")
        page.wait_for_function("() => window.__smAcceptanceO2.pathRecords.some(x => x.id==='o2rTrendSpo2' && x.lines>0)")
        trend_paths = page.evaluate(
'''
if "pathRecords.some(x => x.id==='o2rTrendSpo2'" not in text:
    if trend_wait_anchor not in text:
        raise SystemExit("trend fresh-render anchor missing")
    text = text.replace(trend_wait_anchor, trend_wait_block, 1)

p.write_text(text, encoding="utf-8")
