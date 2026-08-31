from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_windows_release_pipeline_uses_localized_msi_and_no_active_inno_builder():
    assert (ROOT / "sleepmate_main.py").is_file()
    assert (ROOT / "build/windows/SleepMate.spec").is_file()
    assert (ROOT / "build/windows/SleepMateUpdater.spec").is_file()
    assert (ROOT / "scripts/generate_msi_wxs.py").is_file()
    assert (ROOT / "build/windows/msi/SleepMate.hu-HU.wxl").is_file()
    assert (ROOT / ".github/workflows/windows-release.yml").is_file()

    workflow = (ROOT / ".github/workflows/windows-release.yml").read_text(encoding="utf-8")
    assert "Windows build + Hungarian MSI - unsigned CI only" in workflow
    assert "choco install wixtoolset --version 3.14.1.20250415" in workflow
    assert "WIX_CANDLE" in workflow
    assert "WIX_LIGHT" in workflow
    assert "-ext WixUIExtension" in workflow
    assert "-cultures:hu-HU" in workflow
    assert "SleepMate.hu-HU.wxl" in workflow
    assert "SleepMate-Legal.rtf" in workflow
    assert "SleepMate_Setup_v${version}.msi" in workflow
    assert "msiexec.exe" in workflow
    assert "'/i'" in workflow
    assert "'/x'" in workflow
    assert "Install Inno Setup" not in workflow
    assert "WINDOWS_CERT_PFX_BASE64" not in workflow
    assert "WINDOWS_CERT_PASSWORD" not in workflow
    assert "gh release create" not in workflow
    assert "publish-unsigned" not in workflow

    build = (ROOT / "build/windows/build_release.ps1").read_text(encoding="utf-8")
    assert "SLEEPMATE_SIGN_PFX" not in build
    assert "ISCC.exe" not in build
    assert "windows-onedir-msi-ready" in build
    assert "MSI packaging is performed" in build


def test_windows_release_uses_locked_dependencies_and_packages_notices():
    runtime_lock = ROOT / "build/windows/requirements-runtime.lock"
    build_lock = ROOT / "build/windows/requirements-build.lock"
    notices = ROOT / "THIRD_PARTY_NOTICES.md"
    assert runtime_lock.is_file()
    assert build_lock.is_file()
    assert notices.is_file()

    runtime = runtime_lock.read_text(encoding="utf-8")
    build_deps = build_lock.read_text(encoding="utf-8")
    assert "groq==1.7.0" in runtime
    assert "Pillow==12.3.0" in runtime
    assert "pystray==0.19.5" in runtime
    assert "cryptography==50.0.1" in runtime
    assert "pyinstaller==6.22.2" in build_deps
    assert "pytest==9.1.1" in build_deps

    build = (ROOT / "build/windows/build_release.ps1").read_text(encoding="utf-8")
    assert "pip==26.2.1" in build
    assert "requirements-runtime.lock" in build
    assert "requirements-build.lock" in build
    assert "pip freeze --all" in build
    assert "THIRD_PARTY_NOTICES.md" in build
    assert "PRIVACY.md" in build
    assert "LICENSE" in build

    notice_text = notices.read_text(encoding="utf-8")
    assert "Reference release: `v5.2.16`" in notice_text
    assert "LGPL-3.0-or-later" in notice_text
    assert "MIT-CMU" in notice_text
    assert "BSD-3-Clause" in notice_text
    assert "No proprietary Python runtime dependency" in notice_text


def test_msi_generator_contract():
    text = (ROOT / "scripts/generate_msi_wxs.py").read_text(encoding="utf-8")
    assert 'InstallScope": "perUser"' in text
    assert '"Language": "1038"' in text
    assert '"SummaryCodepage": "1250"' in text
    assert "MajorUpgrade" in text
    assert "LocalAppDataFolder" in text
    assert "INSTALLFOLDER" in text
    assert "SleepMateStartMenuShortcut" in text
    assert "SleepMateUninstallShortcut" in text
    assert "SleepMateDesktopShortcut" in text
    assert "SleepMateStartup" in text
    assert "LEGACY_INNO_UNINSTALL" in text
    assert "SleepMateUpdater.exe" in text
    assert "SleepMate.ico" in text
    assert "WixUI_FeatureTree" in text
    assert "WixUI_ErrorProgressText" in text
    assert "write_legal_rtf" in text
    assert 'repo_root / "LICENSE"' in text
    assert 'repo_root / "PRIVACY.md"' in text
    assert "SleepMate-Legal.rtf" in text
    assert "Licencfeltételek" in text
    assert "ADATVÉDELMI TÁJÉKOZTATÓ" in text
    # Architecture is supplied to candle with -arch x64.
    assert '"Platform": "x64"' not in text
    assert '"CompressionLevel": "high"' not in text
    assert '"Vital": "yes"' not in text

    loc = (ROOT / "build/windows/msi/SleepMate.hu-HU.wxl").read_text(encoding="utf-8")
    assert 'Culture="hu-HU"' in loc
    assert "Licencfeltételek és adatvédelem" in loc
    assert "Adatvédelmi tájékoztatót" in loc


def test_binary_release_builder_contract():
    text = (ROOT / "tools/build_binary_release.py").read_text(encoding="utf-8")
    assert "package_type': 'windows-x64-program-tree'" in text
    assert "--min-version', default='4.2.2'" in text
    maintenance = (ROOT / "cpap/maintenance.py").read_text(encoding="utf-8")
    assert "SleepMateUpdater.exe" in maintenance
    assert "_prepare_binary_state_transition" in maintenance
