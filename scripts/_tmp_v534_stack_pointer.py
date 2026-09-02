from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one target, found {count}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


o2 = Path("web/o2ring.js")
replace_once(
    o2,
    "function bindChart(c,{setRange,resetRange,redraw,syncGroup}){if(!c)return;const existing=R.chartControllers.get(c);",
    "function bindChart(c,{setRange,resetRange,redraw,syncGroup}){if(!c)return;c.style.pointerEvents='auto';const existing=R.chartControllers.get(c);",
)

acceptance = Path("scripts/v534_browser_acceptance.py")
text = acceptance.read_text(encoding="utf-8")
anchor = '        page.wait_for_function("() => document.getElementById(\'smStackO2DualCanvas\')?._smO2Meta?.rows?.length >= 5")\n'
block = """        stack_pointer_events = page.evaluate(
            \"\"\"() => ['smStackO2Spo2Canvas','smStackO2HrCanvas','smStackO2DualCanvas'].map(id => ({
              id, pointerEvents:getComputedStyle(document.getElementById(id)).pointerEvents
            }))\"\"\"
        )
        require(
            all(x[\"pointerEvents\"] != \"none\" for x in stack_pointer_events),
            f\"Stack O2 chart input was disabled by the CPAP base-canvas CSS: {stack_pointer_events}\",
        )
"""
if "Stack O2 chart input was disabled by the CPAP base-canvas CSS" not in text:
    if anchor not in text:
        raise SystemExit("Stack O2 acceptance anchor missing")
    text = text.replace(anchor, anchor + block, 1)
acceptance.write_text(text, encoding="utf-8")
