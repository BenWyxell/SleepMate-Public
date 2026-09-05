from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_packager_ships_canonical_worker_and_one_build_identity():
    spec = read("build/windows/SleepMate.spec")
    assert "shutil.copy2(proven_sw, WEB_GENERATED / 'service-worker.js')" not in spec
    assert "sleepmate-release-version" in spec
    assert "sleepmate-build-id" in spec
    assert "const CACHE='sleepmate-shell-v{FRONTEND_ID}'" in spec
    assert "const BUILD_ID='{FRONTEND_ID}'" in spec
    assert "const CODE_ASSETS=new Set" in spec


def test_worker_handover_is_atomic_and_keeps_old_cache_until_new_client_ready():
    for path in ("web/service-worker.js", "web/service-worker-v508-base.js"):
        sw = read(path)
        assert "precacheShellAtomic" in sw
        assert "if(!OPTIONAL_SHELL_ASSETS.has(pathname))throw error" in sw
        assert "await self.skipWaiting()" in sw
        assert "await self.clients.claim()" in sw
        assert "hadPreviousShell" in sw
        assert "await client.navigate(client.url)" in sw
        assert "SLEEPMATE_CLIENT_READY" in sw
        assert "data.buildId!==BUILD_ID" in sw
        assert "cleanupStaleSleepMateCaches" in sw
        activate = sw.split("self.addEventListener('activate'",1)[1].split("function backendUnavailable",1)[0]
        assert "caches.delete" not in activate
        assert "key.startsWith('sleepmate-shell-')||key.startsWith('sleepmate-api-')" in sw


def test_page_reconciles_release_on_wake_including_installed_ios_pwa():
    app = read("web/app-core.js")
    assert "sleepmate-release-version" in app
    assert "sleepmate-build-id" in app
    assert "SLEEPMATE_CLIENT_READY" in app
    assert "reconcilePwaRelease" in app
    assert "window.addEventListener('pageshow',reconcile)" in app
    assert "window.addEventListener('focus',reconcile)" in app
    assert "document.visibilityState==='visible'" in app
    controller = app.split("navigator.serviceWorker.addEventListener('controllerchange'",1)[1].split("});",1)[0]
    assert "standalonePwa()" not in controller
    assert "location.reload()" in controller


def test_o2_dynamic_modules_use_same_build_id_and_self_heal():
    shell = read("cpap/v530_features.py")
    assert "const ASSET_VERSION=" in shell
    assert "/o2ring.js?v=${ASSET_VERSION}" in shell
    assert "/o2ring-report-ui.js?v=${ASSET_VERSION}" in shell
    assert "existing.src===wanted" in shell
    assert "existing?.href===wanted" in shell
    assert "o2RuntimeMissing" in shell
    assert "scheduleO2Recovery" in shell
    assert "Math.min(Number(scheduleO2Recovery.attempt)" in shell
    assert "sleepmate-build-id" in shell
    assert "asset_version" in shell


def test_frozen_frontend_never_deletes_release_caches():
    frontend = read("web/frontend-v534.js")
    patcher = read("cpap/v530_features.py")
    assert "caches.delete" not in frontend
    assert "stale=keys.filter" not in frontend
    assert "Cache ownership and stale-generation cleanup belong exclusively" in frontend
    assert "if safe in text" in patcher


def test_generated_sleepsync_bootstrap_retries_transient_script_failures():
    spec = read("build/windows/SleepMate.spec")
    assert "if(attempt<retries)setTimeout(run,180*attempt)" in spec
    assert "started=false;setTimeout(start,900)" in spec
    assert "window.addEventListener('pageshow'" in spec
    assert "document.visibilityState==='visible'&&!started" in spec
