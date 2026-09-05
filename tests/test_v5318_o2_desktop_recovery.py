from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_app_boots_o2_recovery_independently():
    app = (WEB / "app.js").read_text(encoding="utf-8")
    assert "/o2ring-recovery-v5318.js?v=1" in app
    assert "data-sleepmate-o2-recovery" in app


def test_packaged_frontend_also_boots_o2_recovery_after_app_core_replacement():
    frontend = (WEB / "frontend-v534.js").read_text(encoding="utf-8")
    spec = (ROOT / "build" / "windows" / "SleepMate.spec").read_text(encoding="utf-8")
    assert "shutil.copy2(core_app, WEB_GENERATED / 'app.js')" in spec
    assert "function ensureO2Recovery()" in frontend
    assert "/o2ring-recovery-v5318.js?v=" in frontend
    assert "ensureO2Recovery();bind();" in frontend


def test_recovery_detects_missing_desktop_oximetry_ui():
    js = (WEB / "o2ring-recovery-v5318.js").read_text(encoding="utf-8")
    assert "/api/o2ring/status" in js
    assert '#sidebar [data-page="oximetry"]' in js
    assert "page-oximetry" in js
    assert "/o2ring.js?v=" in js
    assert "SleepMateO2Ring.uninstall" in js
    assert "SleepMateO2Ring.install" in js


def test_recovery_can_restore_sidebar_even_without_reports_anchor():
    js = (WEB / "o2ring-recovery-v5318.js").read_text(encoding="utf-8")
    assert "if(reports)nav.insertBefore(button,reports);else nav.appendChild(button);" in js
    assert "window.SleepMateO2Ring?.open?.('live')" in js


def test_recovery_is_not_pwa_or_mobile_gated():
    js = (WEB / "o2ring-recovery-v5318.js").read_text(encoding="utf-8")
    assert "display-mode: standalone" not in js
    assert "sm-phone-pwa" not in js
    assert "matchMedia" not in js
