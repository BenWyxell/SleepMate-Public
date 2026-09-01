from pathlib import Path

from cpap.maintenance import OFFICIAL_GITHUB_REPO
from cpap.version import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]


def _version_tuple(value: str) -> tuple[int, int, int]:
    parts = str(value).split(".")
    return tuple(int(x) for x in parts[:3])


def test_official_public_updater_has_no_user_credentials():
    maintenance = (ROOT / "cpap" / "maintenance.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "web" / "app-core.js").read_text(encoding="utf-8")

    # This contract originated in the public v5.2.20 release and must remain
    # true for later descendants; do not pin future feature releases back to
    # the old product version just to satisfy the updater-security test.
    assert _version_tuple(APP_VERSION) >= (5, 2, 20)
    assert OFFICIAL_GITHUB_REPO == "BenWyxell/SleepMate-Public"
    assert 'OFFICIAL_GITHUB_REPO = "BenWyxell/SleepMate-Public"' in maintenance
    assert 'headers["Authorization"]' not in maintenance
    assert 'Ellenőrizd a privát repo nevét és a GitHub tokent' not in maintenance
    assert '"authentication": "public-anonymous"' in maintenance
    assert 'repo = OFFICIAL_GITHUB_REPO' in maintenance

    assert '"update_github_repo": "BenWyxell/SleepMate-Public"' in app
    assert 'defaults["update_github_repo"] = "BenWyxell/SleepMate-Public"' in app
    assert 'time.sleep(12 * 60 * 60)' in app
    assert 'update_github_repo") or ""' not in app.split('def _background_update_check',1)[1].split('try:',1)[0]

    for removed in ('updateGithubRepo','updateGithubToken','updateGithubClearToken','updateGithubTokenHint'):
        assert removed not in html
        assert removed not in js
    assert 'Hivatalos SleepMate kiadások' in html
    assert 'GitHub token nem szükséges' in html
    assert 'Frissítés keresése' in html
    assert 'Frissítés telepítése' in html


def test_cloudflare_saved_hostname_provenance_and_cache_bust():
    first = (ROOT / "web" / "first-run.js").read_text(encoding="utf-8")
    hydration = (ROOT / "web" / "sleepsync-hydration-v529.js").read_text(encoding="utf-8")
    source_loader = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    assert 'id="frCfHostOrigin"' in first
    assert 'Korábban mentett SleepMate-beállítás.' in first
    assert "savedCfHost" in first and "origin.hidden=true" in first
    assert '/first-run.css?v=4' in first
    assert '/first-run.js?v=4' in hydration
    assert "const FIRST_RUN='/first-run.js?v=4'" in source_loader
    assert "/sleepsync-hydration-v529.js?v=131" in source_loader
