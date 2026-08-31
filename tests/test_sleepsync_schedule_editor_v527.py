from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_integrated_schedule_editor_is_present_and_not_forced_hidden():
    engine = (ROOT / "web" / "app-engine119.js").read_text(encoding="utf-8")
    polish = (ROOT / "web" / "sleepsync-polish.js").read_text(encoding="utf-8")

    for needle in (
        'id="ssScheduleMode"',
        'value="card_available"',
        'value="scheduled"',
        'id="ssScheduleDays"',
        'id="ssTimeList"',
        'id="ssAddTime"',
    ):
        assert needle in engine

    assert "forceScheduleEditorVisible" in polish
    assert "modeRow.style.setProperty('display','flex','important')" in polish
    assert "cardSchedule.style.setProperty('display',selectedMode==='card_available'?'block':'none','important')" in polish
    assert "timedSchedule.style.setProperty('display',selectedMode==='scheduled'?'block':'none','important')" in polish


def test_auto_toggle_preserves_selected_schedule_mode():
    polish = (ROOT / "web" / "sleepsync-polish.js").read_text(encoding="utf-8")

    assert "const selectedMode=document.getElementById('ssScheduleMode')?.value||'scheduled';" in polish
    assert "JSON.stringify({auto_sync_enabled:enabled,auto_sync_mode:selectedMode})" in polish
    assert "mode.value='scheduled'" not in polish
    assert "mode.closest('.ss-mode-row')?.classList.add('ss-polish-hidden')" not in polish


def test_schedule_can_be_edited_while_auto_sync_is_off():
    polish = (ROOT / "web" / "sleepsync-polish.js").read_text(encoding="utf-8")

    assert "Az automatikus futás kikapcsolt, de az ütemezés továbbra is szerkeszthető." in polish
    assert "if(!enabled)next.textContent='Következő futás: Kikapcsolva';" in polish
