from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_windows_release_pipeline_uses_localized_msi_and_verified_publish_contract():
    assert (ROOT / "sleepmate_main.py").is_file()
    assert (ROOT / "build/windows/SleepMate.spec").is_file()
    assert (ROOT / "build/windows/SleepMateUpdater.spec").is_file()
    assert (ROOT / "scripts/generate_msi_wxs.py").is_file()
    assert (ROOT / "build/windows/msi/SleepMate.hu-HU.wxl").is_file()
    assert (ROOT / ".github/workflows/windows-release.yml").is_file()

    workflow = (ROOT / ".github/workflows/windows-release.yml").read_text(encoding="utf-8")
    assert "Windows release + Hungarian MSI + verified publish" in workflow
    assert "Build and fully test SleepMate Windows program tree" in workflow
    assert ".\\build\\windows\\build_release.ps1" in workflow
    assert ".\\build\\windows\\build_release.ps1 -SkipTests" not in workflow
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
    assert "verify-release-set:" in workflow
    assert "needs: smoke-test-msi" in workflow
    assert "SleepMate-Windows-x64-VERIFIED-RELEASE" in workflow
    assert "sha256sum -c SHA256SUMS.txt" in workflow
    assert "publish-github-release:" in workflow
    assert "needs: verify-release-set" in workflow
    assert "gh release create" in workflow
    assert "--draft" in workflow
    assert "gh release upload" in workflow
    assert "gh release edit \"$TAG\" --repo \"$GITHUB_REPOSITORY\" --draft=false" in workflow
    assert "Install Inno Setup" not in workflow
    assert "WINDOWS_CERT_PFX_BASE64" not in workflow
    assert "WINDOWS_CERT_PASSWORD" not in workflow
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
    assert "LICENCFELTÉTELEK" in text
    assert "ADATVÉDELMI TÁJÉKOZTATÓ" in text
    assert "WIXUI_EXITDIALOGOPTIONALCHECKBOXTEXT" in text
    assert "SleepMate indítása" in text
    # Architecture is supplied to candle with -arch x64.
    assert '"Platform": "x64"' not in text
    assert '"CompressionLevel": "high"' not in text
    assert '"Vital": "yes"' not in text

    loc = (ROOT / "build/windows/msi/SleepMate.hu-HU.wxl").read_text(encoding="utf-8")
    assert 'Culture="hu-HU"' in loc
    assert "Licencfeltételek és adatvédelem" in loc
    assert "Adatvédelmi tájékoztatót" in loc
    assert "Elolvastam és" in loc


def test_first_run_onboarding_contract():
    onboarding = ROOT / "cpap/onboarding.py"
    first_run = ROOT / "web/first-run.js"
    first_css = ROOT / "web/first-run.css"
    hydration = ROOT / "web/sleepsync-hydration-v529.js"
    launcher = ROOT / "sleepmate_main.py"
    spec = ROOT / "build/windows/SleepMate.spec"

    for path in (onboarding, first_run, first_css, hydration, launcher, spec):
        assert path.is_file(), path

    backend = onboarding.read_text(encoding="utf-8")
    compile(backend, str(onboarding), "exec")
    assert "/api/onboarding/status" in backend
    assert "/api/onboarding/state" in backend
    assert "private/onboarding.json" in backend
    assert "cloudflare_token" not in backend
    assert "api_key" not in backend

    launcher_text = launcher.read_text(encoding="utf-8")
    assert "from cpap.onboarding import install_onboarding" in launcher_text
    assert "install_onboarding(app)" in launcher_text

    js = first_run.read_text(encoding="utf-8")
    for required in (
        "/api/onboarding/status",
        "/api/onboarding/state",
        "/api/system/pick-folder",
        "/api/sleepsync/settings",
        "/api/remote/install",
        "/api/remote/tailscale",
        "/api/remote/cloudflare",
        "/api/ai/config",
        "Tailscale",
        "Cloudflare Tunnel",
        "Google Gemini",
        "Groq",
        "Backup és",
    ):
        assert required in js

    # The Windows MSI onboarding is desktop-focused: PWA installation and browser
    # notification permission belong to the regular web/PWA settings, not first-run.
    for forbidden in (
        "window.installPwa",
        "window.enablePwaNotifications",
        "frPwaInstall",
        "frNotify",
        "PWA + Web Push",
        "PWA / értesítések",
        "sleepmate-logo.webp",
        "icon-192.png",
    ):
        assert forbidden not in js

    css = first_css.read_text(encoding="utf-8")
    assert "display:flex;flex-direction:column" in css
    assert ".fr-top{position:relative;z-index:2;display:flex;flex:0 0 auto" in css
    assert ".fr-body{position:relative;flex:1 1 0;height:0;max-height:100%;min-width:0;min-height:0" in css
    assert "overflow-y:scroll!important" in css
    assert ".fr-footer{position:relative;z-index:3;display:flex;flex:0 0 auto" in css
    assert "#sleepmateFirstRun *,#sleepmateFirstRun *::before,#sleepmateFirstRun *::after{box-sizing:border-box}" in css
    assert "height:min(820px,calc(100dvh - 52px))" in css
    assert "height:100dvh" in css
    assert "html.fr-open,html.fr-open body{overflow:hidden}" in css
    assert "body.scrollTop=0" in js
    assert "/first-run.css?v=3" in js

    hydration_text = hydration.read_text(encoding="utf-8")
    assert "loadPackagedOnboarding" in hydration_text
    assert "lateBootPackagedOnboarding" in hydration_text
    assert "/first-run.js?v=3" in hydration_text
    assert "PWA, backup és AI" not in hydration_text

    spec_text = spec.read_text(encoding="utf-8")
    assert "shutil.copytree(WEB_SOURCE, WEB_GENERATED)" in spec_text
    # first-run.js/css therefore enter the exact packaged MSI/PWA web tree even
    # though the release builder restores app-core.js as the primary app.js.
    assert "shutil.copy2(core_app, WEB_GENERATED / 'app.js')" in spec_text


def test_first_run_frontend_javascript_syntax():
    node = shutil.which("node")
    if not node:
        return
    for path in (
        ROOT / "web/first-run.js",
        ROOT / "web/app.js",
        ROOT / "web/sleepsync-hydration-v529.js",
    ):
        result = subprocess.run(
            [node, "--check", str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert result.returncode == 0, f"{path.name}: {result.stdout}\n{result.stderr}"


def test_binary_release_builder_contract():
    text = (ROOT / "tools/build_binary_release.py").read_text(encoding="utf-8")
    assert "package_type': 'windows-x64-program-tree'" in text
    assert "--min-version', default='4.2.2'" in text
    maintenance = (ROOT / "cpap/maintenance.py").read_text(encoding="utf-8")
    assert "SleepMateUpdater.exe" in maintenance
    assert "_prepare_binary_state_transition" in maintenance
