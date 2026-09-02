from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = (ROOT / "build" / "windows" / "SleepMate.spec").read_text(encoding="utf-8")


def test_v534_packaging_requires_current_o2_frontend_assets():
    for asset in (
        "/sleepmate-aurora.css",
        "/sleepmate-v530.css",
        "/sleepmate-v530.js",
        "/o2ring.css",
        "/o2ring.js",
        "/o2ring-report-ui.js",
        "/o2ring-v534.css",
        "/frontend-v534.js",
    ):
        assert repr(asset) in SPEC
    assert "protected_base_assets" in SPEC


def test_v534_packaging_rejects_obsolete_o2_runtime_assets():
    assert "for obsolete in ('/o2ring-v532.css','/o2ring-v532.js','/frontend-v533.js')" in SPEC
    assert "obsolete O2 frontend asset returned to active worker" in SPEC


def test_v534_packaging_replaces_legacy_latest_session_status_flash():
    # The legacy text remains only as the exact replacement needle in the build
    # recipe. The generated packaged app must replace it with session count + label.
    assert "textContent='Befejezve'" in SPEC
    assert "textContent=String(latest.sessions?.length||0)" in SPEC
    assert "textContent='szakasz'" in SPEC
