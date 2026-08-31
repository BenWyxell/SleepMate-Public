from pathlib import Path


SLEEP_ASSETS = (
    "/sleepmate-sleep.js?v=5.2.6",
    "/sleepmate-sleep-v523.js?v=5.2.6",
    "/sleepmate-chart-v523.js?v=5.2.6",
    "/sleepmate-sleep-v524.js?v=5.2.6",
)
REFRESH_ASSET = "/sleepmate-sleep-refresh-v5212.js?v=5.2.12"


def test_pwa_precaches_sleep_feature_and_rotates_shell_cache():
    root = Path(__file__).resolve().parents[1]
    sw = (root / "web" / "service-worker.js").read_text(encoding="utf-8")

    assert "sleepmate-shell-v5.2.12-ss129" in sw
    assert "sleepmate-api-v5.2.12-ss129" in sw
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
    assert "sleepmate-shell-v5.2.12" in sw
    assert "sleepmate-api-v5.2.12" in sw
    for asset in SLEEP_ASSETS:
        assert asset in sw
    assert REFRESH_ASSET in sw
    assert "sleep-analysis" in sw
    # The Windows spec intentionally guards this exact proven fetch rule. The
    # sleep feature is versioned in SHELL, so rotating the cache is sufficient.
    assert "const codeAsset=url.pathname==='/style.css'||url.pathname==='/app.js'||url.pathname==='/manifest.webmanifest';" in sw


def test_new_service_worker_reloads_live_pwa_after_stale_cache_cleanup():
    root = Path(__file__).resolve().parents[1]
    for filename in ("service-worker.js", "service-worker-v508-base.js"):
        sw = (root / "web" / filename).read_text(encoding="utf-8")
        assert "const stale=keys.filter" in sw
        assert "self.clients.matchAll({type:'window',includeUncontrolled:true})" in sw
        assert "await client.navigate(client.url)" in sw


def test_server_shell_cache_bust_matches_release():
    root = Path(__file__).resolve().parents[1]
    patch = (root / "cpap" / "sleep_analysis_v522.py").read_text(encoding="utf-8")
    for asset in SLEEP_ASSETS:
        assert asset.lstrip("/") in patch
    assert REFRESH_ASSET.lstrip("/") in patch
