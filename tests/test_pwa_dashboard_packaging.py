from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_packaged_index_injects_dashboard_pwa_stylesheet():
    spec = read("build/windows/SleepMate.spec")
    assert "dashboard_pwa_link = '<link rel=\"stylesheet\" href=\"/dashboard-pwa-v5312.css?v=1\">'" in spec
    assert "generated index does not contain exactly one PWA Dashboard stylesheet link" in spec


def test_packaged_worker_keeps_dashboard_pwa_stylesheet_network_first():
    base = read("web/service-worker-v508-base.js")
    spec = read("build/windows/SleepMate.spec")
    assert "'/dashboard-pwa-v5312.css?v=1'" in base
    assert "'/dashboard-pwa-v5312.css'" in base
    assert "'/dashboard-pwa-v5312.css'," in spec


def test_dashboard_stylesheet_is_scoped_to_installed_phone_pwa():
    css = read("web/dashboard-pwa-v5312.css")
    assert "html.sm-phone-pwa #page-dashboard" in css
    assert "grid-template-columns:repeat(2,minmax(0,1fr))!important" in css
