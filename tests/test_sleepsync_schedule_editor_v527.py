from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_integrated_schedule_editor_is_present_and_forced_to_scheduled_only():
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

    assert "function enforceScheduledOnlyUi()" in polish
    assert "mode.value='scheduled'" in polish
    assert "modeRow.style.setProperty('display','none','important')" in polish
    assert "cardSchedule.style.setProperty('display','none','important')" in polish
    assert "timedSchedule.style.setProperty('display','block','important')" in polish


def test_auto_toggle_always_persists_scheduled_mode():
    polish = (ROOT / "web" / "sleepsync-polish.js").read_text(encoding="utf-8")

    assert "JSON.stringify({auto_sync_enabled:enabled,auto_sync_mode:'scheduled'})" in polish
    assert "mode.value='scheduled'" in polish
    assert "selectedMode=document.getElementById('ssScheduleMode')" not in polish


def test_schedule_can_be_edited_while_auto_sync_is_off():
    polish = (ROOT / "web" / "sleepsync-polish.js").read_text(encoding="utf-8")

    assert "Az automatikus futás kikapcsolt, de az ütemezés továbbra is szerkeszthető." in polish
    assert "if(!enabled)next.textContent='Következő futás: Kikapcsolva';" in polish
