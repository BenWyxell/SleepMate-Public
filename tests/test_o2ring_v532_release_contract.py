from pathlib import Path
from cpap.version import API_VERSION, APP_VERSION, BUILD_CHANNEL
ROOT=Path(__file__).resolve().parents[1]
def read(path:str)->str:return (ROOT/path).read_text(encoding="utf-8")
def test_current_release_identity_supersedes_historical_v532_contract():
    assert APP_VERSION=="5.3.17" and API_VERSION==19 and BUILD_CHANNEL=="stable"
    assert read("RELEASE_NOTES_5_3_4.md").startswith("# SleepMate 5.3.4\n")
def test_current_packaged_pwa_keeps_authoritative_o2_assets_network_first():
    for path in ("web/service-worker.js","web/service-worker-v508-base.js"):
        sw=read(path)
        for asset in ("/sleepmate-aurora.css","/sleepmate-v530.css","/sleepmate-v530.js","/o2ring.css","/o2ring.js","/o2ring-report-ui.js","/o2ring-v534.css","/frontend-v534.js"):
            assert asset in sw
        assert "/o2ring-v532.js" not in sw and "/frontend-v533.js" not in sw
def test_current_shell_activates_only_v534_post_release_owner():
    shell=read("cpap/v530_features.py")
    assert "install_o2ring_runtime_v534" in shell
    assert "o2ring-v534.css" in shell and "frontend-v534.js" in shell
    assert "o2ring-v532.js" not in shell and "frontend-v533.js" not in shell
def test_current_user_requested_surfaces_are_present():
    runtime=read("web/o2ring.js")
    for marker in ("switchMode","O2_FOCUS_DEFS","o2_spo2","o2_hr","card.className='overview-card sm-o2-focus-mini'","function o2CoreSignal(key)","smStackO2Dual","sm-o2-overlay-select","smNightO2Card","smDashboardO2V534","o2rTrendSpo2","smO2QuickBar","SpO₂ + pulzus – élő"):
        assert marker in runtime
    assert "smO2FocusDual" not in runtime and "smO2FocusSpo2" not in runtime and "smO2FocusHr" not in runtime
def test_reports_keep_batched_cpap_overlap_data():
    runtime=read("web/o2ring.js");backend=read("cpap/o2ring_v532.py")
    assert "/api/o2ring/day-batch?days=" in runtime
    assert 'parsed.path == "/api/o2ring/day-batch"' in backend