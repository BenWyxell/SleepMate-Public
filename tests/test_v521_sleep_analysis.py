from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from cpap.sleep_analysis import SleepBlock
from cpap.sleep_analysis_v521 import _block_json, _build_blocks, aggregate_rows, analyze
from cpap.version import API_VERSION, APP_VERSION


ROOT = Path(__file__).resolve().parents[1]
ZERO_COUNTS = {k: 0 for k in ("OA", "CA", "H", "UA", "RERA", "CSR", "OTHER")}


def make_block(start: str, end: str, seconds: float, kind: str = "main") -> SleepBlock:
    block = SleepBlock(
        block_id="slp-test-" + start.replace(":", "").replace("-", ""),
        start=datetime.fromisoformat(start),
        end=datetime.fromisoformat(end),
        therapy_seconds=seconds,
        wall_seconds=(datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds(),
        session_count=1,
        source_days=[start[:10].replace("-", "")],
        session_starts=[start],
        counts=dict(ZERO_COUNTS),
        ahi=0.0,
    )
    block.final_type = kind
    block.automatic_type = kind
    return block


def test_overnight_sleep_is_grouped_by_wakeup_day_not_start_day():
    main = make_block("2026-08-23T23:15:00", "2026-08-24T06:15:00", 7 * 3600, "main")
    minute = make_block("2026-08-24T21:00:00", "2026-08-24T21:01:00", 60, "short")
    rows = aggregate_rows([main, minute])
    assert len(rows) == 1
    assert rows[0]["date"] == "2026-08-24"
    assert rows[0]["main_seconds"] == 7 * 3600
    assert rows[0]["short_seconds"] == 60
    assert rows[0]["total_seconds"] == 7 * 3600 + 60


def test_merged_sleep_keeps_exact_constituent_session_intervals():
    class Dataset:
        def days(self): return ["20260824"]
        def sessions(self, day):
            return [
                SimpleNamespace(start=datetime.fromisoformat("2026-08-23T23:00:00"), end=datetime.fromisoformat("2026-08-24T01:00:00"), duration_s=7200),
                SimpleNamespace(start=datetime.fromisoformat("2026-08-24T01:20:00"), end=datetime.fromisoformat("2026-08-24T05:20:00"), duration_s=14400),
            ]
        def events(self, day): return []
    blocks = _build_blocks(None, Dataset())
    assert len(blocks) == 1
    assert blocks[0].session_count == 2
    payload = _block_json(blocks[0])
    assert payload["sleep_date"] == "2026-08-24"
    assert [x["start"] for x in payload["session_details"]] == ["2026-08-23T23:00:00", "2026-08-24T01:20:00"]
    assert [x["end"] for x in payload["session_details"]] == ["2026-08-24T01:00:00", "2026-08-24T05:20:00"]


def test_custom_sleep_date_range_is_inclusive():
    rows = []
    for day, seconds in [("2026-08-23", 3600), ("2026-08-24", 7200), ("2026-08-25", 10800), ("2026-08-26", 14400)]:
        rows.append({"date": day, "main_seconds": seconds, "nap_seconds": 0, "short_seconds": 0, "total_seconds": seconds, "main_ahi": 0.0, "total_ahi": 0.0, "main_parts": 1, "nap_count": 0, "short_count": 0, "counts": dict(ZERO_COUNTS), "blocks": []})
    class Service:
        def _full_payload(self, dataset):
            return {"generated_at": "2026-08-28T23:00:00", "settings": {}, "learned": {}, "overrides": 0, "rows": rows}
    result = analyze(Service(), None, "range:2026-08-24:2026-08-25")
    assert [r["date"] for r in result["rows"]] == ["2026-08-24", "2026-08-25"]
    assert result["summary"]["total_seconds"] == 18000
    assert result["filter"]["start"] == "2026-08-24"
    assert result["filter"]["end"] == "2026-08-25"


def test_frontend_backend_api_contract_matches_again():
    core = (ROOT / "web" / "app-core.js").read_text(encoding="utf-8")
    assert API_VERSION == 19
    assert "ver.api!==19" in core
    assert APP_VERSION == "5.2.20"


def test_v521_sleep_ui_has_required_filters_order_and_editing():
    ui = (ROOT / "web" / "sleepmate-sleep-v521.js").read_text(encoding="utf-8")
    assert "7 nap" in ui
    assert "30 nap" in ui
    assert "Előző hét" in ui
    assert "Előző hónap" in ui
    assert "Teljes" in ui
    assert "Egyedi" in ui
    assert "Idővonal" in ui
    assert "CPAP-szakasz" in ui
    assert "Szerkesztés" in ui
    assert "kézzel módosítva" in ui
    header = "<th>Nap</th><th>Összes alvás</th><th>Fő alvás</th><th>Szundi</th><th>Rövid használat</th>"
    assert header in ui


def test_shell_loader_serves_original_sleep_ui_then_v521_patch():
    patch = (ROOT / "cpap" / "sleep_analysis_v521.py").read_text(encoding="utf-8")
    assert 'sleepmate-sleep.js?v=5.2.1' in patch
    assert 'sleepmate-sleep-v521.js?v=5.2.1' in patch
    assert 'parsed.path in {"/", "/index.html"}' in patch
