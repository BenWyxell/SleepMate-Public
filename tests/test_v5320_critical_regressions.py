from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_o2ring_has_one_static_deterministic_boot_chain():
    index = read("web/index.html")
    installer = read("cpap/v530_features.py")
    bootstrap = read("web/sleepmate-v530.js")
    frontend = read("web/frontend-v534.js")

    for asset in ("frontend-v534.js", "sleepmate-v530.js", "o2ring-data-management.js"):
        assert index.count(f'src="/{asset}?v=5.3.21"') == 1
    assert "o2ring-recovery-v5318.js" not in index + frontend
    assert "do_GET" not in installer
    assert "_patch_index" not in installer
    assert "_patch_v530" not in installer
    assert "await ensureO2Modules()" in bootstrap
    assert "await Promise.resolve(window.SleepMateO2Ring.install())" in bootstrap
    assert "sleepmate-o2-config-ready" in bootstrap
    assert "bindO2HydrationRecovery" not in bootstrap


def test_o2_settings_navigation_and_visualizations_share_the_same_ready_event():
    bootstrap = read("web/sleepmate-v530.js")
    frontend = read("web/frontend-v534.js")
    o2ring = read("web/o2ring.js")

    assert "installO2MasterPanel();hydrateO2Master();if(activeO2())await ensureO2Modules()" in bootstrap
    assert "sleepmate-o2-config-ready" in frontend
    assert "#smO2Advanced" not in frontend  # DOM id is created once, not queried as a CSS workaround.
    for canvas in ("o2rLiveDual", "o2rLiveSpo2Chart", "o2rLiveHrChart", "o2rTrendSpo2"):
        assert f'id="{canvas}"' in o2ring
    assert "async function install(){if(R.installed)return refresh()" in o2ring
    assert "await refreshDashboardO2()" in o2ring


def test_pwa_handover_is_atomic_and_has_no_competing_navigation_or_ack_deadlock():
    worker = read("web/service-worker.js")
    base = read("web/service-worker-v508-base.js")
    core = read("web/app-core.js")
    index = read("web/index.html")
    assert worker == base
    assert "precacheShellAtomic" in worker
    assert "await self.skipWaiting()" in worker
    assert "await self.clients.claim()" in worker
    assert "await cleanupStaleSleepMateCaches()" in worker
    assert "client.navigate(client.url)" not in worker
    assert "SLEEPMATE_CLIENT_READY" not in worker
    assert "SHELL_BY_PATH.get(pathname)" in worker
    assert "releaseMatches(fresh)" in worker
    assert "sleepmate-shell-v5.3.21" in worker
    assert "sleepmate-api-v5.3.21" in worker
    assert "navigator.serviceWorker.addEventListener('controllerchange'" not in core
    controller = index.split("navigator.serviceWorker.addEventListener('controllerchange'", 1)[1].split("})})();", 1)[0]
    assert controller.count("location.reload()") == 1
    assert "window.__sleepmatePwaHandover" in index
    assert "window.__sleepmateCoreLoaded = true" in core
    assert "!handover.hadController" in controller
    assert "window.__sleepmateBootComplete=resolvedO2()" in read("web/sleepmate-v530.js")
    assert "reconcilePwaRelease" not in core
    assert "postPwaClientReady" not in core


def test_release_uses_windows_installer_and_supports_explicit_signing_modes():
    maintenance = read("cpap/maintenance.py")
    build = read("build/windows/build_release.ps1")
    generator = read("scripts/generate_msi_wxs.py")
    workflow = read(".github/workflows/windows-release.yml")

    assert not (ROOT / "build/windows/SleepMateUpdater.spec").exists()
    assert "SleepMateUpdater PyInstaller build" not in build
    assert "StableUpdater" not in build
    assert 'system_root / "System32" / "msiexec.exe"' in maintenance
    assert "WinVerifyTrust" in maintenance
    assert '"SLEEPMATE_AUTOLAUNCH=1"' in maintenance
    assert "update_worker.py" not in maintenance
    assert 'update_launch.text = \'SLEEPMATE_AUTOLAUNCH = 1 AND NOT REMOVE~="ALL"\'' in generator
    assert "signpath/github-action-submit-signing-request@v1" in workflow
    assert "SleepMate-Windows-x64-SIGNED-RELEASE" in workflow
    assert "SleepMate-Windows-x64-VERIFIED-RELEASE" in workflow
    assert "Get-AuthenticodeSignature" in workflow
    assert "signing_configured" in workflow
    assert "verified-unsigned" in workflow
    assert "authenticode-required" in maintenance


def test_only_msi_stage_creates_the_update_manifest():
    portable = read("tools/build_binary_release.py")
    msi = read("tools/build_msi_update_manifest.py")
    assert "sleepmate-update.json" not in portable
    assert '"package_type": "windows-msi-x64"' in msi
    assert '"requires_installer": True' in msi
    assert '"signature_mode": args.signature_mode' in msi
