from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_v512_pdf_cover_contract():
    src = (ROOT / "cpap" / "v512_features.py").read_text(encoding="utf-8")
    assert "58 * mm" in src
    assert '"PAP-TERÁPIÁS JELENTÉS"' in src
    assert 'setFont("SleepSansBold", 16)' in src
    assert "page_height - 105 * mm" in src
    assert "page_height - 119 * mm" in src
    assert "float(y) + 10 * mm" in src


def test_v512_is_installed_after_v511():
    src = (ROOT / "sleepmate_main.py").read_text(encoding="utf-8")
    assert "from cpap.v512_features import install_v512_features" in src
    assert src.index("install_v511_features()") < src.index("install_v512_features()")


def test_mobile_settings_no_vertical_flex_button_explosion():
    src = (ROOT / "web" / "mobile-boot-diagnostics.js").read_text(encoding="utf-8")
    assert "sleepmateV512MobileSettingsStyle" in src
    assert ".system-maintenance-panel .settings-actions button{flex:none!important" in src
    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in src
    assert "min-height:40px!important;height:auto!important" in src


def test_mobile_remote_drive_backup_and_system_are_width_safe():
    src = (ROOT / "web" / "mobile-boot-diagnostics.js").read_text(encoding="utf-8")
    assert ".remote-grid{grid-template-columns:minmax(0,1fr)!important" in src
    assert "#googleDriveRemoteCard .drive-form{grid-template-columns:minmax(0,1fr)!important" in src
    assert "#googleDriveBackupCard .drive-backup-row{grid-template-columns:minmax(0,1fr)!important" in src
    assert '[data-settings-panel="backup"].settings-data-grid.active{grid-template-columns:minmax(0,1fr)!important' in src
    assert ".maintenance-grid{grid-template-columns:minmax(0,1fr)!important" in src
    assert ".secret-input-row{display:grid!important;grid-template-columns:minmax(0,1fr) auto" in src


def test_mobile_v512_styles_are_inline_and_offline_safe():
    src = (ROOT / "web" / "mobile-boot-diagnostics.js").read_text(encoding="utf-8")
    # The diagnostics script is already part of the proven service-worker shell.
    # Keeping the v5.1.2 CSS inline means no new stylesheet request can disappear
    # when the backend is offline during a PWA restart.
    assert "function installV512MobileSettingsStyles()" in src
    assert "document.head.appendChild(style)" in src
    assert "installV512MobileSettingsStyles();" in src
