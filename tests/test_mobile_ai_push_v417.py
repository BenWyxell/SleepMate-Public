from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUSH = (ROOT / "cpap" / "push_service.py").read_text(encoding="utf-8")
HTML = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "web" / "style.css").read_text(encoding="utf-8")
APP = (ROOT / "web" / "app-core.js").read_text(encoding="utf-8")
SW = (ROOT / "web" / "service-worker.js").read_text(encoding="utf-8")
RECOVERY = (ROOT / "cpap" / "v530_features.py").read_text(encoding="utf-8")


def test_vapid_subject_is_strict_py_vapid_compatible():
    assert 'def _vapid_subject(origin: str | None)' in PUSH
    assert 'vapid_claims={"sub": self._vapid_subject(row["vapid_subject"])}' in PUSH
    assert 'mailto:sleepmate@localhost' not in PUSH
    assert 'vapid_claims={"sub": "https://sleepmate.local/"}' not in PUSH


def test_mobile_ai_intro_is_compact():
    assert "Streamelt válasz" not in HTML
    assert "PDF / nyomtatás" not in HTML
    assert "Kontextusos chat" not in HTML
    assert '.ai-page .ai-credit-summary{justify-self:center' in CSS
    assert '.ai-page .ai-provider-grid{grid-template-columns:repeat(2' in CSS


def test_ai_chat_does_not_ios_zoom_and_autogrows():
    assert 'id="aiChatInput" rows="1"' in HTML
    assert ".ai-page .ai-chat-compose textarea{box-sizing:border-box!important;font-size:16px!important" in CSS
    assert "function resizeAIChatInput()" in APP
    assert "addEventListener('input',resizeAIChatInput)" in APP
    assert "resizeAIChatInput();state.ai.chatBusy=true" in APP


def test_mobile5_cache_bust():
    assert 'sleepmate-shell-v5.2.14-ss131' in SW
    assert "const UI_VERSION='5.3.4'" in SW
    assert 'sleepmate-shell-v5.3.19-o2-updater-recovery-1' in SW
    assert 'sleepmate-api-v5.3.9-refactor' in SW
    assert '/style.css?v=5.3.4' in SW
    assert '/app.js?v=5.3.4' in SW
    assert '/style.css?v=5.0.0' in HTML
    assert '/app.js?v=5.0.0' in HTML
    assert 'UI_VERSION = "5.3.4"' in RECOVERY
    assert "text.replace('/style.css?v=5.0.0', f'/style.css?v={UI_VERSION}')" in RECOVERY
    assert "text.replace('/app.js?v=5.0.0', f'/app.js?v={UI_VERSION}')" in RECOVERY
    assert 'X-SleepMate-UI-Version' in RECOVERY
