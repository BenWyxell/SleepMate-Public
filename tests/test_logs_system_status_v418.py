from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def test_system_status_card_is_on_logs_not_dashboard():
    dashboard = HTML.split('id="page-dashboard"', 1)[1].split('id="page-patient"', 1)[0]
    logs = HTML.split('id="page-logs"', 1)[1].split('id="page-settings"', 1)[0]
    assert 'id="systemStatusCenter"' not in dashboard
    assert 'id="systemStatusCenter"' in logs
    assert logs.index('id="systemStatusCenter"') < logs.index('id="diagnosticSummary"')


def test_logs_reload_system_status_with_diagnostics():
    dashboard_loader = JS.split('async function loadDashboardOverview', 1)[1].split('function renderSystemStatus', 1)[0]
    diagnostics_loader = JS.split('async function loadDiagnostics()', 1)[1].split('document.addEventListener', 1)[0]
    assert "api('/api/system/status')" not in dashboard_loader
    assert "api('/api/system/status')" in diagnostics_loader
    assert 'renderSystemStatus(sys)' in diagnostics_loader


def test_warning_visual_precedence_and_complete_diagnostics():
    render = JS.split('function renderSystemStatus', 1)[1].split('function isoFromCode', 1)[0]
    assert "x.warning?'warn':x.ok?'ok'" in render
    assert "x.warning?'!'" in render
    assert 'filter(x=>x.warning||(!x.ok&&!x.optional))' in render
    assert 'diagnostic_warnings = list(diag.get("errors") or [])' in APP
    assert '"diagnostics": {' in APP
    assert '"ok": damaged == 0 and missing == 0' in APP
    assert 'warning = (days == 0) or bool(diagnostic_warnings) or not last_backup' in APP
