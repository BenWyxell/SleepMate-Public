from pathlib import Path
import json
import os
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def test_windows_release_pipeline_files_present():
    assert (ROOT/'sleepmate_main.py').is_file()
    assert (ROOT/'build/windows/SleepMate.spec').is_file()
    assert (ROOT/'build/windows/SleepMateUpdater.spec').is_file()
    assert (ROOT/'build/windows/installer/SleepMate.iss').is_file()
    assert (ROOT/'build/windows/installer/install-winget-package.ps1').is_file()
    assert (ROOT/'.github/workflows/windows-release.yml').is_file()
    iss=(ROOT/'build/windows/installer/SleepMate.iss').read_text(encoding='utf-8')
    assert r'DefaultDirName={localappdata}\Programs\SleepMate' in iss
    assert 'PrivilegesRequired=lowest' in iss
    assert 'Tailscale.Tailscale' in iss and 'Cloudflare.cloudflared' in iss
    assert 'Git.Git' in iss and 'GitHub.cli' in iss and 'githubtools' in iss
    assert "WizardIsTaskSelected('tailscale')" in iss
    assert "WizardIsTaskSelected('cloudflared')" in iss
    assert "WizardIsTaskSelected('githubtools')" in iss
    assert "InstallWingetPackage('Tailscale.Tailscale'" in iss
    assert 'where winget' not in iss.lower()
    helper=(ROOT/'build/windows/installer/install-winget-package.ps1').read_text(encoding='utf-8')
    assert 'Get-Command winget.exe' in helper
    assert 'Microsoft.DesktopAppInstaller' in helper
    assert "'--source', 'winget'" in helper
    assert 'winget.exe nem található' in helper
    workflow=(ROOT/'.github/workflows/windows-release.yml').read_text(encoding='utf-8')
    assert 'WINDOWS_CERT_PFX_BASE64' in workflow
    assert 'SleepMate_Setup_v*.exe' in workflow


def test_explicit_legacy_state_migration_is_copy_only():
    from cpap.runtime import migrate_from_path
    with tempfile.TemporaryDirectory() as td:
        td=Path(td); source=td/'legacy'; target=td/'state'; app=td/'app'
        (source/'private'/'push').mkdir(parents=True)
        (source/'config.json').write_text(json.dumps({'port':8895}),encoding='utf-8')
        (source/'private'/'note.txt').write_text('keep',encoding='utf-8')
        app.mkdir()
        old=os.environ.get('SLEEPMATE_STATE_DIR')
        os.environ['SLEEPMATE_STATE_DIR']=str(target)
        try:
            r=migrate_from_path(source, app)
        finally:
            if old is None: os.environ.pop('SLEEPMATE_STATE_DIR',None)
            else: os.environ['SLEEPMATE_STATE_DIR']=old
        assert r['migrated'] and not r['errors']
        assert (target/'config.json').is_file()
        assert (target/'private'/'note.txt').read_text(encoding='utf-8')=='keep'
        # Source is never deleted/moved.
        assert (source/'private'/'note.txt').is_file()


def test_binary_release_builder_contract():
    text=(ROOT/'tools/build_binary_release.py').read_text(encoding='utf-8')
    assert "package_type': 'windows-x64-program-tree'" in text
    assert "--min-version', default='4.2.2'" in text
    maintenance=(ROOT/'cpap/maintenance.py').read_text(encoding='utf-8')
    assert 'SleepMateUpdater.exe' in maintenance
    assert '_prepare_binary_state_transition' in maintenance
