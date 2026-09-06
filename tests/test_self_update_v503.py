from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_startup_uses_only_web_loader_and_keeps_stuck_tray_recovery():
    main = (ROOT / "sleepmate_main.py").read_text(encoding="utf-8")
    spec = (ROOT / "build/windows/SleepMate.spec").read_text(encoding="utf-8")
    index = (ROOT / "web/index.html").read_text(encoding="utf-8")
    assert "--startup-splash" not in main
    assert "_launch_startup_splash" not in main
    assert "_run_startup_splash" not in main
    assert "_recover_stuck_tray()" in main
    assert "tray_heartbeat.json" in main
    assert "'PIL.ImageTk'" not in spec
    assert "'tkinter'" not in spec
    assert 'id="startupSplash"' in index
    assert "sleepmate-splash-v410.webp" in index


def test_installed_update_uses_no_custom_process_or_program_replacement():
    maintenance = (ROOT / "cpap/maintenance.py").read_text(encoding="utf-8")
    build = (ROOT / "build/windows/build_release.ps1").read_text(encoding="utf-8")
    assert "update_worker.py" not in maintenance
    assert "replace_program(" not in maintenance
    assert "taskkill" not in maintenance
    assert 'system_root / "System32" / "msiexec.exe"' in maintenance
    assert 'quit_request = self.private / "quit_tray.request"' in maintenance
    assert "SleepMateUpdater" not in build


def test_portable_zip_is_not_an_in_app_update_package():
    portable = (ROOT / "tools/build_binary_release.py").read_text(encoding="utf-8")
    manifest = (ROOT / "tools/build_msi_update_manifest.py").read_text(encoding="utf-8")
    assert "sleepmate-update.json" not in portable
    assert '"package_type": "windows-msi-x64"' in manifest
    assert '"requires_installer": True' in manifest
