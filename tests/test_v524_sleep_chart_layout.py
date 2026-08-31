from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v524_sleep_chart_observes_real_container_width():
    js = (ROOT / "web" / "sleepmate-sleep-v524.js").read_text(encoding="utf-8")
    assert "ResizeObserver" in js
    assert "getBoundingClientRect().width" in js
    assert "width<120" in js
    assert "window.dispatchEvent(new Event('resize'))" in js


def test_v524_marks_dashboard_usage_as_resmed_therapy_day():
    js = (ROOT / "web" / "sleepmate-sleep-v524.js").read_text(encoding="utf-8")
    assert "ResMed terápiás nap szerint" in js
    assert "DATALOG terápiás napjához" in js
    assert "Az Alvások nézet az ébredés napjához" in js


def test_v524_shell_loads_cache_busted_fix():
    py = (ROOT / "cpap" / "sleep_analysis_v522.py").read_text(encoding="utf-8")
    assert 'sleepmate-sleep-v524.js?v=5.2.4' in py
    assert 'sleepmate-sleep-v523.js?v=5.2.4' in py
    assert 'sleepmate-chart-v523.js?v=5.2.4' in py
