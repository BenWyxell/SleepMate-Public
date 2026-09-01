from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
JS=(ROOT/'web'/'app-core.js').read_text(encoding='utf-8')
CSS=(ROOT/'web'/'style.css').read_text(encoding='utf-8')
APP=(ROOT/'app.py').read_text(encoding='utf-8')
SW=(ROOT/'web'/'service-worker.js').read_text(encoding='utf-8')


def test_pwa_navigation_does_not_create_history_for_edge_back_gesture():
    assert "if(standalonePwa())" in JS
    assert "history.replaceState({sleepmate:true},'',next)" in JS
    assert 'e.preventDefault()' in JS
    assert "{passive:false}" in JS
    assert 'overscroll-behavior-x:none!important' in CSS


def test_custom_loader_is_enabled_once_in_pwa():
    assert 'window.__sleepmateBootStarted' in JS
    assert 'html.pwa-standalone #startupSplash{display:grid!important}' in CSS
    assert 'sleepmate-shell-v5.2.14-ss131' in SW


def test_diagnostic_push_is_human_readable_and_only_on_changed_data():
    assert 'if new_night or changed_count > 0:' in APP
    assert 'warning_rows = [x for x in (diag.get("errors") or []) if isinstance(x, dict)]' in APP
    assert 'ps.send_warning_once(signature, "Adatfigyelmeztetés", body, "/#logs")' in APP
    assert 'warnings = [str(x)' not in APP
