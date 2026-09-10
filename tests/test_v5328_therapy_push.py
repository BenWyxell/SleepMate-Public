from __future__ import annotations

from pathlib import Path

import cpap.therapy_push_v5328 as therapy_push


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class FakeSleepService:
    def __init__(self, blocks):
        self.blocks = blocks

    def analyze(self, dataset, period="all"):
        return {"rows": [{"date": "2026-09-10", "blocks": self.blocks}]}


def test_changed_nap_selects_that_block_not_whole_therapy_day(monkeypatch) -> None:
    blocks = [
        {
            "id": "night",
            "start": "2026-09-09T22:00:00",
            "end": "2026-09-10T06:00:00",
            "therapy_seconds": 8 * 3600,
            "ahi": 1.2,
            "source_days": ["20260909"],
            "session_starts": ["2026-09-09T22:00:04"],
            "type": "main",
        },
        {
            "id": "nap",
            "start": "2026-09-10T10:44:00",
            "end": "2026-09-10T12:42:00",
            "therapy_seconds": 118 * 60,
            "ahi": 0.0,
            "source_days": ["20260909", "20260910"],
            "session_starts": ["2026-09-10T10:44:03", "2026-09-10T12:00:02"],
            "type": "nap",
        },
    ]
    monkeypatch.setattr(therapy_push, "get_sleep_analysis_service", lambda app: FakeSleepService(blocks))
    result = {"changed_files": ["DATALOG/20260910/20260910_104400_BRP.edf"]}

    chosen = therapy_push.choose_impacted_block(object(), object(), result)

    assert chosen is not None
    assert chosen["id"] == "nap"
    assert chosen["therapy_seconds"] == 118 * 60


def test_notification_is_therapy_centric_and_contains_requested_metrics(monkeypatch) -> None:
    block = {
        "id": "nap",
        "start": "2026-09-10T10:44:00",
        "end": "2026-09-10T12:41:00",
        "therapy_seconds": 117 * 60,
        "ahi": 0.84,
        "source_days": ["20260910"],
        "session_starts": ["2026-09-10T10:44:03"],
        "type": "nap",
    }
    monkeypatch.setattr(therapy_push, "get_sleep_analysis_service", lambda app: FakeSleepService([block]))
    monkeypatch.setattr(therapy_push, "leak_p95_for_block", lambda dataset, selected: 2.44)

    payload = therapy_push.therapy_notification_payload(
        object(), object(), {"changed_files": ["DATALOG/20260910/20260910_104400_PLD.edf"]}
    )

    assert payload is not None
    assert payload["title"] == "CPAP terápia feldolgozva"
    assert payload["body"] == "Használat: 1:57 • AHI: 0.8 • Szivárgás P95: 2.4 L/perc"
    assert "éjszaka" not in payload["title"].lower()
    assert "fájl" not in payload["body"].lower()


def test_root_file_only_refresh_does_not_create_therapy_push(monkeypatch) -> None:
    monkeypatch.setattr(therapy_push, "get_sleep_analysis_service", lambda app: FakeSleepService([]))
    assert therapy_push.therapy_notification_payload(object(), object(), {"changed_files": ["STR.EDF"]}) is None


def test_sleepsync_uses_same_therapy_push_after_internet_restore() -> None:
    source = read("cpap/sleepsync_integration.py")

    assert "send_therapy_refresh_push(self.handler, imported, \"SleepSync szinkron\")" in source
    assert "time.sleep(2.0)" in source
    assert '"SleepSync szinkron kész"' not in source
    assert 'ps.send(\n            "sync_complete"' not in source


def test_all_normal_refresh_paths_are_routed_through_central_handler_hook() -> None:
    source = read("cpap/therapy_push_v5328.py")

    assert "handler_cls._push_after_refresh = _therapy_push_after_refresh" in source
    assert 'startswith("SleepSync")' in source
    assert "send_therapy_refresh_push(cls, result, reason)" in source
    assert "_send_diagnostic_warning(cls, result)" in source
