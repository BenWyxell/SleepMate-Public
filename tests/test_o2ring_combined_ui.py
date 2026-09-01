from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_combined_oximetry_timeline_has_shared_time_contract():
    js = (ROOT / "web" / "o2ring-combined.js").read_text(encoding="utf-8")

    for marker in (
        "o2rCombinedTimeline",
        "o2rCombinedCpap",
        "o2rCombinedSpo2",
        "o2rCombinedHr",
        "o2rCombinedCpapOverlay",
        "o2rCombinedSpo2Overlay",
        "o2rCombinedHrOverlay",
    ):
        assert marker in js

    assert "/api/day/${day}/signal/${currentSignal}" in js
    assert "/api/o2ring/day?day=${day}" in js
    assert "const dayStart=new Date(sessions[0].start).getTime()/1000" in js
    assert "const shift=start-dayStart" in js
    assert "t:Number(x.t)" in js
    assert "pointermove" in js
    assert "function nearest(" in js
    assert "summary.events" in js
    assert "currentSignal==='pressure'&&pressureValues.length" in js
    assert "model.unit||SIGNALS[currentSignal].unit" in js


def test_combined_timeline_is_owned_by_v532_dynamic_shell_only():
    shell = (ROOT / "cpap" / "v530_features.py").read_text(encoding="utf-8")
    runtime = (ROOT / "web" / "o2ring-v532.js").read_text(encoding="utf-8")
    base_html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")

    assert '("o2ring-v532.js", "sm-o2-v532-inline")' in shell
    assert "feature_path = app_module.WEB / filename" in shell
    assert "sm-o2-v532-inline" in shell
    assert 'replace("</script", "<\\\\/script")' in shell
    assert "o2ring-combined.js" not in shell
    assert "o2ring-v532.js" not in base_html
    for marker in ("smO2FocusDual", "smStackO2Dual", "smO2LiveCombined"):
        assert marker in runtime


def test_combined_timeline_is_inert_without_dynamic_o2_daily_panel():
    js = (ROOT / "web" / "o2ring-combined.js").read_text(encoding="utf-8")

    assert "const host=document.getElementById('o2rDailyPanel')" in js
    assert "if(!host||document.getElementById('o2rCombinedTimeline'))return" in js
    assert "window.SleepMateO2Combined" in js
