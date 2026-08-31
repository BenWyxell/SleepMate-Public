from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_windows_release_pipeline_uses_msi_and_no_active_inno_builder():
    assert (ROOT / "sleepmate_main.py").is_file()
    assert (ROOT / "build/windows/SleepMate.spec").is_file()
    assert (ROOT / "build/windows/SleepMateUpdater.spec").is_file()
    assert (ROOT / "scripts/generate_msi_wxs.py").is_file()
    assert (ROOT / ".github/workflows/windows-release.yml").is_file()

    workflow = (ROOT / ".github/workflows/windows-release.yml").read_text(encoding="utf-8")
    assert "Windows build + MSI - unsigned CI only" in workflow
    assert "sudo apt-get install -y msitools" in workflow
    assert "wixl -v -a x64" in workflow
    assert "SleepMate_Setup_v${VERSION}.msi" in workflow
    assert "msiexec.exe" in workflow
    assert "'/i'" in workflow
    assert "'/x'" in workflow
    assert "Install Inno Setup" not in workflow
    assert "WINDOWS_CERT_PFX_BASE64" not in workflow
    assert "WINDOWS_CERT_PASSWORD" not in workflow

    build = (ROOT / "build/windows/build_release.ps1").read_text(encoding="utf-8")
    assert "SLEEPMATE_SIGN_PFX" not in build
    assert "ISCC.exe" not in build
    assert "windows-onedir-msi-ready" in build
    assert "MSI packaging is performed" in build


def test_msi_generator_contract():
    text = (ROOT / "scripts/generate_msi_wxs.py").read_text(encoding="utf-8")
    assert 'InstallScope": "perUser"' in text
    assert "MajorUpgrade" in text
    assert "LocalAppDataFolder" in text
    assert "INSTALLFOLDER" in text
    assert "SleepMateStartMenuShortcut" in text
    assert "SleepMateUninstallShortcut" in text
    assert "LEGACY_INNO_UNINSTALL" in text
    assert "SleepMateUpdater.exe" in text
    assert "SleepMate.ico" in text
    # Architecture is supplied to wixl with `-a x64`; wixl 0.103 rejects
    # newer WiX attributes such as Package/@Platform and File/@Vital.
    assert '"Platform": "x64"' not in text
    assert '"CompressionLevel": "high"' not in text
    assert '"Vital": "yes"' not in text
    assert "q(\"Condition\")" not in text[text.find("component_ids: list[str]"):]


def test_binary_release_builder_contract():
    text = (ROOT / "tools/build_binary_release.py").read_text(encoding="utf-8")
    assert "package_type': 'windows-x64-program-tree'" in text
    assert "--min-version', default='4.2.2'" in text
    maintenance = (ROOT / "cpap/maintenance.py").read_text(encoding="utf-8")
    assert "SleepMateUpdater.exe" in maintenance
    assert "_prepare_binary_state_transition" in maintenance
