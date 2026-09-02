from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v534_dynamic_settings_observer_is_idempotent_and_raf_coalesced():
    front = read("web/frontend-v534.js")
    assert "const setText=" in front
    assert "el.textContent!==String(value)" in front
    assert "push&&push.textContent!=='PWA'" in front
    assert "tab&&tab.textContent!=='O2Ring'" in front
    assert "o&&o.textContent!=='O2Ring'" in front
    assert "settingsNormalizeRaf" in front
    assert "new MutationObserver(schedule)" in front
    assert "settingsNormalizeRaf=requestAnimationFrame" in front
    assert "if(done())ob?.disconnect()" in front


def test_v534_latest_session_card_has_idempotent_dom_ownership():
    front = read("web/frontend-v534.js")
    assert "function watchLatestSessionCard()" in front
    assert "new MutationObserver(()=>syncLatestSessionCard())" in front
    assert "status&&status.textContent!=='—'" in front
    assert "latest?.summary||latest" in front
    assert "function latestDuration(summary)" in front
    assert "Array.isArray(summary.sessions)" in front
    assert "setText(status,latestDuration(summary))" in front
    assert "`${count} szakasz`" in front
    assert "Befejezve" not in front
