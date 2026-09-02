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


def test_combined_timeline_is_owned_by_v534_authoritative_runtime():
    shell = (ROOT / "cpap" / "v530_features.py").read_text(encoding="utf-8")
    runtime = (ROOT / "web" / "o2ring.js").read_text(encoding="utf-8")
    assert 'UI_VERSION = "5.3.4"' in shell
    assert "o2ring-v532.js" not in shell
    assert "frontend-v533.js" not in shell
    for marker in ("O2_FOCUS_DEFS", "o2_spo2", "o2_hr", "smStackO2Dual", "o2rLiveDual", "daily-o2"):
        assert marker in runtime
    assert "smO2FocusDual" not in runtime
    assert "smO2FocusSpo2" not in runtime
    assert "smO2FocusHr" not in runtime


def test_combined_timeline_is_inert_without_dynamic_o2_daily_panel():
    js = (ROOT / "web" / "o2ring-combined.js").read_text(encoding="utf-8")

    assert "const host=document.getElementById('o2rDailyPanel')" in js
    assert "if(!host||document.getElementById('o2rCombinedTimeline'))return" in js
    assert "window.SleepMateO2Combined" in js