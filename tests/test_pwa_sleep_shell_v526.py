from pathlib import Path


SLEEP_ASSETS = (
    "/sleepmate-sleep.js?v=5.2.6",
    "/sleepmate-sleep-v523.js?v=5.2.6",
    "/sleepmate-chart-v523.js?v=5.2.14",
    "/sleepmate-sleep-v524.js?v=5.2.6",
)
REFRESH_ASSET = "/sleepmate-sleep-refresh-v5212.js?v=5.2.12"


def test_pwa_precaches_sleep_feature_and_rotates_shell_cache():
    root = Path(__file__).resolve().parents[1]
    sw = (root / "web" / "service-worker.js").read_text(encoding="utf-8")

    assert "sleepmate-shell-v5.2.14-ss131" in sw
    assert "sleepmate-api-v5.2.14-ss131" in sw
    for asset in SLEEP_ASSETS:
        assert asset in sw
    assert REFRESH_ASSET in sw
    assert "'/sleepmate-sleep.js'" in sw
    assert "'/sleepmate-sleep-v523.js'" in sw
    assert "'/sleepmate-chart-v523.js'" in sw
    assert "'/sleepmate-sleep-v524.js'" in sw
    assert "'/sleepmate-sleep-refresh-v5212.js'" in sw
    assert "|sleep-analysis|" in sw


def test_packaged_service_worker_base_precaches_same_sleep_feature():
    root = Path(__file__).resolve().parents[1]
    sw = (root / "web" / "service-worker-v508-base.js").read_text(encoding="utf-8")
    assert "sleepmate-shell-v5.2.14" in sw
    assert "sleepmate-api-v5.2.14" in sw
    for asset in SLEEP_ASSETS:
        assert asset in sw
    assert REFRESH_ASSET in sw
    assert "sleep-analysis" in sw
    assert "const codeAsset=['/style.css','/app.js','/sleepmate-sleep.js','/sleepmate-sleep-v523.js','/sleepmate-chart-v523.js','/sleepmate-sleep-v524.js','/sleepmate-sleep-refresh-v5212.js','/manifest.webmanifest'].includes(url.pathname);" in sw


def test_new_service_worker_reloads_live_pwa_after_stale_cache_cleanup():
    root = Path(__file__).resolve().parents[1]
    for filename in ("service-worker.js", "service-worker-v508-base.js"):
        sw = (root / "web" / filename).read_text(encoding="utf-8")
        assert "const stale=keys.filter" in sw
        assert "self.clients.matchAll({type:'window',includeUncontrolled:true})" in sw
        assert "await client.navigate(client.url)" in sw


def test_server_and_packager_shell_contract_matches_current_sleep_release():
    root = Path(__file__).resolve().parents[1]
    live = (root / "web" / "service-worker.js").read_text(encoding="utf-8")
    base = (root / "web" / "service-worker-v508-base.js").read_text(encoding="utf-8")
    spec = (root / "build" / "windows" / "SleepMate.spec").read_text(encoding="utf-8")
    for asset in SLEEP_ASSETS + (REFRESH_ASSET,):
        assert asset in live
        assert asset in base
        assert (root / "web" / asset.split('?', 1)[0].lstrip('/')).is_file()
    for name in (
        "'/sleepmate-sleep.js'",
        "'/sleepmate-sleep-v523.js'",
        "'/sleepmate-chart-v523.js'",
        "'/sleepmate-sleep-v524.js'",
        "'/sleepmate-sleep-refresh-v5212.js'",
    ):
        assert name in spec
