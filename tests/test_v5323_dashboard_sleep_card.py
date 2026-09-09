from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_dashboard_sleep_card_uses_latest_sleep_block_not_raw_therapy_day() -> None:
    frontend = read("web/frontend-v534.js")
    start = frontend.index("let latestSleepCardBlock")
    end = frontend.index("function waitForDynamicSettings")
    card_logic = frontend[start:end]

    assert "/api/sleep-analysis?period=day" in card_logic
    assert "payload?.latest?.blocks" in card_logic
    assert "Date.parse(block?.end||block?.start||'')" in card_logic
    assert "latestDuration(block)" in card_logic
    assert "block.session_count" in card_logic

    # The sleep card must not fall back to the raw ResMed therapy-day summary,
    # because a sleep that crosses the device's noon boundary would be truncated.
    assert "state?.dashboardOverview" not in card_logic
    assert "latestSummary" not in card_logic


def test_dashboard_usage_card_keeps_existing_therapy_day_logic() -> None:
    core = read("web/app-core.js")
    frontend = read("web/frontend-v534.js")
    start = frontend.index("let latestSleepCardBlock")
    end = frontend.index("function waitForDynamicSettings")
    card_logic = frontend[start:end]

    assert "$('#latestUsage').textContent = formatUsageShort(latest.usage);" in core
    assert "latestUsage" not in card_logic
