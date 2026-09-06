from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_packager_ships_canonical_worker_and_one_build_identity():
    spec = read("build/windows/SleepMate.spec")
    assert "shutil.copy2(proven_sw, WEB_GENERATED / 'service-worker.js')" not in spec
    assert "shutil.copytree(WEB_SOURCE, WEB_GENERATED)" in spec
    assert "sleepmate-build-id" in spec
    assert "('SHELL_CACHE', f'sleepmate-shell-v{FRONTEND_ID}')" in spec
    assert "('BUILD_ID', FRONTEND_ID)" in spec
    assert "replace_literal" not in spec


def test_worker_handover_is_atomic_and_has_no_stale_client_ack_deadlock():
    for path in ("web/service-worker.js", "web/service-worker-v508-base.js"):
        sw = read(path)
        assert "precacheShellAtomic" in sw
        assert "await caches.delete(SHELL_CACHE);throw error" in sw
        assert "for(const url of SHELL){const response=await fetchShellAsset(url);await cache.put(url,response)}" in sw
        assert "await self.skipWaiting()" in sw
        assert "await self.clients.claim()" in sw
        assert "await client.navigate(client.url)" not in sw
        assert "SLEEPMATE_CLIENT_READY" not in sw
        assert "cleanupStaleSleepMateCaches" in sw
        activate = sw.split("self.addEventListener('activate'",1)[1].split("function backendUnavailable",1)[0]
        assert "await cleanupStaleSleepMateCaches()" in activate
        assert "key.startsWith('sleepmate-shell-')||key.startsWith('sleepmate-api-')" in sw


def test_page_checks_for_updates_on_wake_and_reloads_once_on_controller_change():
    app = read("web/app-core.js")
    index = read("web/index.html")
    assert "sleepmate-release-version" in app
    assert "sleepmate-build-id" in app
    assert "SLEEPMATE_CLIENT_READY" not in app
    assert "reconcilePwaRelease" not in app
    assert "navigator.serviceWorker.addEventListener('controllerchange'" not in app
    assert "window.addEventListener('pageshow'" in index
    assert "document.visibilityState==='visible'" in index
    assert "reg?.update()" in index
    controller = index.split("navigator.serviceWorker.addEventListener('controllerchange'",1)[1].split("})})();",1)[0]
    assert "standalonePwa()" not in controller
    assert controller.count("location.reload()") == 1
    assert "window.__sleepmatePwaHandover" in index
    assert "window.__sleepmateCoreLoaded = true" in app
    assert "!handover.hadController" in controller


def test_o2_dynamic_modules_use_same_build_id_without_recovery_loop():
    shell = read("web/sleepmate-v530.js")
    assert "const ASSET_VERSION=" in shell
    assert "/o2ring.js?v=${ASSET_VERSION}" in shell
    assert "/o2ring-report-ui.js?v=${ASSET_VERSION}" in shell
    assert "scheduleO2Recovery" not in shell
    assert "bindO2HydrationRecovery" not in shell
    assert "sleepmate-build-id" in shell
    assert "ASSET_VERSION" in shell


def test_frozen_frontend_never_deletes_release_caches():
    frontend = read("web/frontend-v534.js")
    patcher = read("cpap/v530_features.py")
    assert "caches.delete" not in frontend
    assert "stale=keys.filter" not in frontend
    assert "do_GET" not in patcher


def test_packager_does_not_generate_retrying_sleepsync_bootstraps():
    spec = read("build/windows/SleepMate.spec")
    assert "sleepsync-bootstrap.js" not in spec
    assert "setTimeout(run" not in spec
    assert "shutil.copytree(WEB_SOURCE, WEB_GENERATED)" in spec
