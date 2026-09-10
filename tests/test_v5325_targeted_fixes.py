from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def compact(path: str) -> str:
    return "".join(read(path).split())


def test_sleepsync_sends_user_push_after_wifi_restore() -> None:
    integration = read("cpap/sleepsync_integration.py")

    assert "send_therapy_refresh_push" in integration
    assert '"SleepSync szinkron kész"' not in integration
    assert "_engine_sync_job(self, jid, trigger)" in integration
    assert "SleepMate-SleepSync-Push" in integration
    assert "time.sleep(2.0)" in integration


def test_diagnostic_push_dedupes_human_visible_warning_not_only_aggregate() -> None:
    push = read("cpap/push_service.py")

    assert "warning_body_history_v5325" in push
    assert 'hashlib.sha256(f"{title}|{body}"' in push
    assert "Upgrade baseline" in push
    assert "if body_signature in history" in push


def test_missing_brp_pld_eve_remains_visible_but_is_not_a_warning() -> None:
    diagnostics = read("cpap/v513_diagnostics.py")
    block = diagnostics.split('"title": "Hiányzó BRP / PLD / EVE"', 1)[0].rsplit("rows.append({", 1)[1]

    assert '"level": "INFO"' in block
    assert "tájékoztató adat-teljességi jelzés" in diagnostics
    assert '"missing_required": missing_required' in diagnostics
    assert '"errors": [r for r in rows if r["level"] == "WARN"]' in diagnostics
    assert '"level": "WARN" if damaged else "INFO"' in diagnostics


def test_oximetry_status_pill_is_an_intelligent_ble_toggle() -> None:
    frontend = read("web/frontend-v534.js")

    for marker in (
        "installO2BleQuickToggle",
        "toggleO2BleQuick",
        "o2rBleToggle",
        "o2ring_ble_enabled:next",
        "Bluetooth kikapcsolása",
        "Bluetooth bekapcsolása",
        "sm-o2-ble-toggle",
    ):
        assert marker in frontend
    assert "await window.SleepMateO2Ring?.refreshStatus?.()" in frontend


def test_mobile_maintenance_buttons_keep_normal_height() -> None:
    frontend = compact("web/frontend-v534.js")

    assert ".system-maintenance-panel.settings-actionsbutton{flex:none!important" in frontend
    assert "min-height:40px!important;height:auto!important" in frontend
    assert "grid-template-columns:repeat(2,minmax(0,1fr))!important" in frontend


def test_old_missing_file_action_copy_is_replaced_with_information() -> None:
    frontend = read("web/frontend-v534.js")

    assert "normalizeDiagnosticCompletenessCopy" in frontend
    assert "önmagában ez nem jelent sérült adatot" in frontend
    assert "sérült / csonka EDF figyelmeztetés" in frontend
