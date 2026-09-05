from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v5310_first_run_offers_external_ai_prompt_without_api_key():
    js = read("web/first-run.js")
    css = read("web/first-run.css")
    assert 'id="frAiPrompt"' in js
    assert "Prompt külső AI-hoz bekapcsolása" in js
    assert "request('/api/ui/preferences',{method:'POST',body:{ai_prompting_enabled:prompting}})" in js
    assert "$('#frAiPrompt').checked=state.ui.ai_prompting_enabled===true" in js
    assert ".fr-btn.primary" in css and "color:#fff" in css


def test_v5310_self_check_uses_current_msi_updater_path():
    maintenance = read("cpap/maintenance.py")
    assert '["SleepMate.exe", "Updater/SleepMateUpdater.exe", "build_info.json", "installed.marker"]' in maintenance
    assert '["SleepMate.exe", "SleepMateUpdater.exe", "build_info.json", "installed.marker"]' not in maintenance
    assert 'legacy_updater_exe = self.base / "SleepMateUpdater.exe"' in maintenance
    assert 'updater_dir = self.base / "Updater"' in maintenance
    assert 'updater_exe = updater_dir / "SleepMateUpdater.exe"' in maintenance


def test_v5310_o2_live_view_is_page_scoped_and_has_fast_windows():
    js = read("web/o2ring.js")
    assert 'value="instant" selected>Azonnali' in js
    assert 'value="1">1 perc' in js
    assert "x.measuring===true&&x.last_sample_ts" in js
    assert "Jelenleg nincs mérés folyamatban." in js
    assert "await refillLive(since)" not in js
    assert "livePageActive:false" in js


def test_v5310_dashboard_o2_trends_use_smoothed_dashboard_style():
    js = read("web/o2ring.js")
    assert "function drawSmoothLine" in js
    assert "smooth:true,points:true,connectGaps:true,lineWidth:2" in js
    assert "syncGroup:'dash-o2'" in js
