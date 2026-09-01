from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "web" / "first-run.js").read_text(encoding="utf-8")
CSS = (ROOT / "web" / "first-run.css").read_text(encoding="utf-8")
HYDRATION = (ROOT / "web" / "sleepsync-hydration-v529.js").read_text(encoding="utf-8")


def test_desktop_first_run_has_no_pwa_or_broken_brand_image():
    assert "sleepmate-logo.webp" not in JS
    assert "icon-192.png" not in JS
    assert "frPwaInstall" not in JS
    assert "frNotify" not in JS
    assert "PWA + Web Push" not in JS
    assert "PWA / értesítések" not in JS


def test_every_wizard_step_uses_global_scrollable_body():
    assert "grid-template-rows:auto minmax(0,1fr) auto" in CSS
    assert ".fr-body{min-width:0;min-height:0;overflow-x:hidden;overflow-y:auto" in CSS
    assert "height:min(820px,calc(100dvh - 52px))" in CSS
    assert "height:100dvh" in CSS
    assert "html.fr-open,html.fr-open body{overflow:hidden}" in CSS
    assert "body.scrollTop=0" in JS


def test_first_run_cache_busters_follow_hotfix():
    assert "/first-run.css?v=2" in JS
    assert "/first-run.js?v=2" in HYDRATION
