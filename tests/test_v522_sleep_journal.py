from __future__ import annotations

import shutil
import subprocess
from datetime import date, timedelta
from pathlib import Path

from cpap.sleep_analysis_v522 import _range_from_period


ROOT = Path(__file__).resolve().parents[1]


def _rows(last: str = "2026-08-30", count: int = 90):
    end = date.fromisoformat(last)
    start = end - timedelta(days=count - 1)
    return [{"date": (start + timedelta(days=i)).isoformat()} for i in range(count)]


def test_rolling_periods_are_relative_to_latest_sleep_day():
    rows = _rows()
    start, end, label = _range_from_period(rows, "7")
    assert (start.isoformat(), end.isoformat(), label) == ("2026-08-24", "2026-08-30", "Utolsó 7 nap")
    start, end, label = _range_from_period(rows, "30")
    assert (start.isoformat(), end.isoformat(), label) == ("2026-08-01", "2026-08-30", "Utolsó 30 nap")
    start, end, label = _range_from_period(rows, "prev7")
    assert (start.isoformat(), end.isoformat(), label) == ("2026-08-17", "2026-08-23", "Előző 7 nap")
    start, end, label = _range_from_period(rows, "prev30")
    assert (start.isoformat(), end.isoformat(), label) == ("2026-07-02", "2026-07-31", "Előző 30 nap")


def test_custom_range_is_order_independent():
    rows = _rows()
    start, end, label = _range_from_period(rows, "range:2026-08-20:2026-08-10")
    assert start.isoformat() == "2026-08-10"
    assert end.isoformat() == "2026-08-20"
    assert label == "Egyedi időszak"


def test_sleep_journal_ui_contract_and_filter_order():
    text = (ROOT / "web" / "sleepmate-sleep-v522.js").read_text(encoding="utf-8")
    order = ['option value="7"', 'option value="30"', 'option value="all"', 'option value="range"', 'option value="prev7"', 'option value="prev30"']
    positions = [text.index(token) for token in order]
    assert positions == sorted(positions)
    assert "Ébredés napja" in text
    assert "Alvásnapló" in text
    assert "CPAP-val töltött idő" in text
    assert "data-toggle" in text
    assert "Idővonal" not in text
    assert "v522-duration" in text
    assert "Szerkesztés" in text


def test_v522_backend_stays_installed_while_current_ui_patch_chain_is_served():
    backend = (ROOT / "cpap" / "sleep_analysis_v522.py").read_text(encoding="utf-8")
    main = (ROOT / "sleepmate_main.py").read_text(encoding="utf-8")
    worker = (ROOT / "web" / "service-worker.js").read_text(encoding="utf-8")
    assert "def install_sleep_analysis_v522" in backend
    assert "install_sleep_analysis_v522(app)" in main
    assert 'sleepmate-sleep-v523.js?v=5.2.6' in worker
    assert 'sleepmate-sleep-v524.js?v=5.2.6' in worker
    assert 'sleepmate-sleep-v522.js' not in worker


def test_v522_javascript_syntax_when_node_available():
    node = shutil.which("node")
    if not node:
        return
    result = subprocess.run([node, "--check", str(ROOT / "web" / "sleepmate-sleep-v522.js")], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
