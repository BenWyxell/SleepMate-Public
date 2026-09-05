from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_installer_bootstraps_winget_before_optional_packages():
    iss = (ROOT / "build/windows/installer/SleepMate.iss").read_text(encoding="utf-8")
    helper = (ROOT / "build/windows/installer/install-winget-package.ps1").read_text(encoding="utf-8")

    assert 'Name: "winget"' in iss
    assert 'Windows Package Manager (winget) ellenőrzése / telepítése' in iss
    assert 'EnsureWingetAvailable' in iss
    assert '-EnsureOnly' in iss
    assert "WingetReady := EnsureWingetAvailable(Failures);" in iss

    assert 'function Ensure-WinGet' in helper
    assert 'Add-AppxPackage -RegisterByFamilyName -MainPackage Microsoft.DesktopAppInstaller_8wekyb3d8bbwe' in helper
    assert 'Install-Module -Name Microsoft.WinGet.Client' in helper
    assert 'Repair-WinGetPackageManager -Force -Latest' in helper
    assert "'--disable-interactivity'" in helper
    assert "'--source', 'winget'" in helper

    # Optional tools still use exact package IDs after WinGet is available.
    for package_id in ('Tailscale.Tailscale', 'Cloudflare.cloudflared', 'Git.Git', 'GitHub.cli'):
        assert package_id in iss
