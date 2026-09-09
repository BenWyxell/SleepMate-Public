from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_retired_recovery_layer_is_not_shipped_or_loaded():
    assert not (WEB / "o2ring-recovery-v5318.js").exists()
    combined = "\n".join(
        (WEB / name).read_text(encoding="utf-8")
        for name in ("index.html", "frontend-v534.js", "sleepmate-v530.js", "service-worker.js")
    )
    assert "o2ring-recovery-v5318" not in combined


def test_desktop_oximetry_ui_is_installed_by_the_canonical_runtime():
    bootstrap = (WEB / "sleepmate-v530.js").read_text(encoding="utf-8")
    o2ring = (WEB / "o2ring.js").read_text(encoding="utf-8")
    assert "await ensureO2Modules()" in bootstrap
    assert "await Promise.resolve(window.SleepMateO2Ring.install())" in bootstrap
    assert '#sidebar [data-page="oximetry"]' in o2ring
    assert "page-oximetry" in o2ring
    assert "installNav();installPage();installDaily();installSettingsConnection()" in o2ring


def test_source_and_packaged_entrypoints_load_the_same_static_o2_assets():
    index = (WEB / "index.html").read_text(encoding="utf-8")
    spec = (ROOT / "build/windows/SleepMate.spec").read_text(encoding="utf-8")
    for asset in ("frontend-v534.js", "sleepmate-v530.js", "o2ring-data-management.js"):
        assert index.count(f'src="/{asset}?v=5.3.23"') == 1
        assert "shutil.copytree(WEB_SOURCE, WEB_GENERATED)" in spec
    assert "sm-frontend-v534-inline" not in index
    assert "_patch_index" not in (ROOT / "cpap/v530_features.py").read_text(encoding="utf-8")
