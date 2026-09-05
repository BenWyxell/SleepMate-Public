from datetime import datetime, timedelta
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_pdf_cover_uses_real_sleepmate_logo_without_duplicate_wordmark():
    source = text("cpap/v511_features.py")
    assert "sleepmate-icon-v410.webp" in source
    assert 'str(text).strip() == "SleepMate"' in source
    assert 'getattr(doc, "page", 0)' in source


def test_daily_share_card_adds_sleepmate_logo():
    source = text("web/sleepmate-enhancements.js")
    assert "const LOGO='/assets/sleepmate-icon-v410.webp'" in source
    assert "coreShareCard" in source
    assert "x.drawImage(logo" in source


def test_trend_spline_interpolates_through_measurement_points():
    source = text("web/sleepmate-enhancements.js")
    assert "Catmull-Rom -> Bezier" in source
    assert "ctx.bezierCurveTo" in source
    assert "p2.x,p2.y" in source


def test_offline_mode_is_network_first_and_gateway_specific():
    worker = text("web/service-worker-v508-base.js")
    runtime = text("web/sleepmate-offline-runtime.js")
    assert "[502,503,504]" in worker
    assert "fresh.status>=500" not in worker
    assert "boundedFetch" in worker
    assert "sleepmate-enhancements.js" in worker
    assert "sleepmate-offline-runtime.js" in worker
    assert "X-SleepMate-Offline" in worker
    assert "offline read-only guard" in runtime
    assert "__sleepmateCheckServerRecovery" in runtime


def test_google_drive_is_optional_backup_mirror_with_restore_api():
    source = text("cpap/google_drive_integration.py")
    assert "https://www.googleapis.com/auth/drive.file" in source
    assert '"auto_upload": False' in source
    assert "/api/google-drive/status" in source
    assert "/api/google-drive/upload-latest" in source
    assert "/api/google-drive/restore" in source
    assert "request_handler._restore_backup_job" in source
    assert "SleepMate_auto_backup_*.zip" in source


def test_backend_installs_v511_features_after_sleepsync_core():
    source = text("sleepmate_main.py")
    assert "install_v511_features()" in source
    assert "install_sleepsync_integration(app)" in source
    assert "install_google_drive_integration(app)" in source
    assert source.index("install_sleepsync_integration(app)") < source.index("install_google_drive_integration(app)")


def test_v512_pdf_cover_is_larger_and_tighter():
    source = text("cpap/v512_features.py")
    assert "58 * mm" in source
    assert '"PAP-TERÁPIÁS JELENTÉS"' in source
    assert 'setFont("SleepSansBold", 16)' in source
    assert "page_height - 105 * mm" in source
    assert "page_height - 119 * mm" in source
    main = text("sleepmate_main.py")
    assert "install_v512_features()" in main
    assert main.index("install_v511_features()") < main.index("install_v512_features()")


def test_v512_phone_settings_layout_prevents_overflow_and_huge_buttons():
    source = text("web/mobile-boot-diagnostics.js")
    assert "sleepmateV512MobileSettingsStyle" in source
    assert ".remote-grid{grid-template-columns:minmax(0,1fr)!important" in source
    assert "#googleDriveRemoteCard .drive-form{grid-template-columns:minmax(0,1fr)!important" in source
    assert "#googleDriveBackupCard .drive-backup-row{grid-template-columns:minmax(0,1fr)!important" in source
    assert '[data-settings-panel="backup"].settings-data-grid.active{grid-template-columns:minmax(0,1fr)!important' in source
    assert ".maintenance-grid{grid-template-columns:minmax(0,1fr)!important" in source
    # Critical regression: the old mobile rules combined flex-direction:column
    # with flex-basis:150px, turning updater buttons into ~150px-tall blocks.
    assert ".system-maintenance-panel .settings-actions button{flex:none!important" in source
    assert "min-height:40px!important;height:auto!important" in source


def test_v513_str_freshness_uses_edf_content_not_filesystem_mtime():
    from cpap.v513_diagnostics import _str_latest_summary_day

    # The user's real STR shape: 2026-08-20 start + 9 daily records = 2026-08-28.
    fake = SimpleNamespace(
        start_time=datetime(2026, 8, 20, 12, 0, 0),
        actual_num_records=9,
        record_duration_s=86400.0,
    )
    assert _str_latest_summary_day(fake) == "20260828"
    source = text("cpap/v513_diagnostics.py")
    assert "stat().st_mtime" not in source
    assert "latest_str_day < latest_datalog_day" in source


def test_v513_zero_duration_resmed_start_stub_is_not_missing_file_error():
    from cpap.v513_diagnostics import _cluster_has_therapy_payload

    recording_starts = SimpleNamespace(description="Recording starts")
    stub_edf = SimpleNamespace(duration_s=0.0, read_annotations=lambda: [recording_starts])
    cluster = [
        SimpleNamespace(kind="CSL", edf=stub_edf),
        SimpleNamespace(kind="EVE", edf=stub_edf),
    ]
    assert _cluster_has_therapy_payload(cluster) is False

    # Once there is real therapy data, missing BRP/PLD must remain diagnosable.
    real_edf = SimpleNamespace(duration_s=60.0, read_annotations=lambda: [])
    assert _cluster_has_therapy_payload([SimpleNamespace(kind="SA2", edf=real_edf)]) is True


def test_v513_event_evidence_keeps_missing_file_warning_conservative():
    from cpap.v513_diagnostics import _cluster_has_therapy_payload

    event_edf = SimpleNamespace(
        duration_s=0.0,
        read_annotations=lambda: [SimpleNamespace(description="Obstructive Apnea")],
    )
    assert _cluster_has_therapy_payload([SimpleNamespace(kind="EVE", edf=event_edf)]) is True


def test_backend_installs_v513_diagnostics_before_dataset_startup():
    source = text("sleepmate_main.py")
    assert "install_v513_diagnostics()" in source
    assert source.index("install_v512_features()") < source.index("install_v513_diagnostics()")
    assert source.index("install_v513_diagnostics()") < source.index("app.main()")


def _sleep_block(start: datetime, hours: float, suffix: str = ""):
    from cpap.sleep_analysis import SleepBlock

    return SleepBlock(
        block_id="slp-test-" + start.strftime("%Y%m%d%H%M") + suffix,
        start=start,
        end=start + timedelta(hours=hours),
        therapy_seconds=hours * 3600,
        wall_seconds=hours * 3600,
        session_count=1,
        source_days=[start.strftime("%Y%m%d")],
        session_starts=[start.isoformat()],
        counts={k: 0 for k in ("OA", "CA", "H", "UA", "RERA", "CSR", "OTHER")},
    )


def test_v520_irregular_clock_times_do_not_change_main_sleep_logic():
    from cpap.sleep_analysis import classify_blocks

    blocks = [
        _sleep_block(datetime(2026, 8, 20, 8, 0), 6.0),   # morning-start main sleep
        _sleep_block(datetime(2026, 8, 20, 17, 0), 1.0),  # daytime nap
        _sleep_block(datetime(2026, 8, 21, 2, 0), 7.0),   # 02:00-start main sleep
        _sleep_block(datetime(2026, 8, 22, 20, 0), 6.5),  # 20:00-start main sleep
    ]
    classified, learned = classify_blocks(blocks)
    by_start = {b.start: b.final_type for b in classified}
    assert by_start[datetime(2026, 8, 20, 8, 0)] == "main"
    assert by_start[datetime(2026, 8, 20, 17, 0)] == "nap"
    assert by_start[datetime(2026, 8, 21, 2, 0)] == "main"
    assert by_start[datetime(2026, 8, 22, 20, 0)] == "main"
    assert learned["clock_time_used"] is False


def test_v520_lone_short_night_is_main_not_automatic_nap():
    from cpap.sleep_analysis import classify_blocks

    lone = _sleep_block(datetime(2026, 8, 24, 9, 30), 2.5)
    classified, _ = classify_blocks([lone])
    assert classified[0].final_type == "main"


def test_v520_short_usage_and_historical_fragment_learning():
    from cpap.sleep_analysis import classify_blocks

    blocks = [
        _sleep_block(datetime(2026, 8, 18, 0, 0), 7.0, "a"),
        _sleep_block(datetime(2026, 8, 19, 2, 0), 7.0, "b"),
        _sleep_block(datetime(2026, 8, 20, 3, 0), 3.5, "c"),
        _sleep_block(datetime(2026, 8, 20, 8, 30), 3.0, "d"),  # 2h gap after first part
        _sleep_block(datetime(2026, 8, 20, 15, 0), 10 / 60, "e"),
    ]
    classified, learned = classify_blocks(blocks)
    by_id = {b.block_id: b for b in classified}
    assert by_id[blocks[2].block_id].final_type == "main"
    assert by_id[blocks[3].block_id].final_type == "main"
    assert by_id[blocks[3].block_id].anchor_id == blocks[2].block_id
    assert by_id[blocks[4].block_id].final_type == "short"
    assert learned["typical_main_seconds"] >= 6 * 3600


def test_v520_manual_override_is_persistent_authority_over_auto_classification():
    from cpap.sleep_analysis import classify_blocks

    main = _sleep_block(datetime(2026, 8, 25, 1, 0), 7.0, "m")
    nap = _sleep_block(datetime(2026, 8, 25, 14, 0), 1.0, "n")
    classified, _ = classify_blocks([main, nap], {main.block_id: "nap", nap.block_id: "main"})
    by_id = {b.block_id: b for b in classified}
    assert by_id[main.block_id].final_type == "nap"
    assert by_id[main.block_id].manual is True
    assert by_id[nap.block_id].final_type == "main"
    assert by_id[nap.block_id].manual is True


def test_v520_stacked_daily_totals_are_exact_category_sum():
    from cpap.sleep_analysis import aggregate_rows, classify_blocks

    blocks = [
        _sleep_block(datetime(2026, 8, 26, 2, 0), 6.0, "m"),
        _sleep_block(datetime(2026, 8, 26, 14, 0), 1.0, "n"),
        _sleep_block(datetime(2026, 8, 26, 18, 0), 10 / 60, "s"),
    ]
    classified, _ = classify_blocks(blocks)
    rows = aggregate_rows(classified)
    assert len(rows) == 1
    row = rows[0]
    assert row["total_seconds"] == pytest.approx(row["main_seconds"] + row["nap_seconds"] + row["short_seconds"])
    assert row["nap_count"] == 1
    assert row["short_count"] == 1


def test_v520_sleep_ui_and_offline_contract():
    source = text("web/sleepmate-sleep.js")
    runtime = text("web/sleepmate-offline-runtime.js")
    worker = text("web/service-worker-v508-base.js")
    main = text("sleepmate_main.py")
    backend = text("cpap/sleep_analysis.py")
    assert "Szekciók" in source and "Alvások" in source
    assert "sleepStackedChart" in source
    assert "Fő alvás" in source and "Szundi" in source and "Rövid használat" in source
    assert "latestStatus" in source and "latestSessions" in source
    assert "sleepmate-sleep.js" in runtime
    assert "sleepmate-sleep.js" in worker
    assert "sleep-analysis" in worker
    assert "/api/sleep-analysis" in backend
    assert "/api/sleep-analysis/override" in backend
    assert "install_sleep_analysis(app)" in main
    assert main.index("install_v513_diagnostics()") < main.index("install_sleep_analysis(app)") < main.index("install_sleepsync_integration(app)")


def test_v520_sleep_ui_javascript_is_syntax_valid():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this local test environment")
    result = subprocess.run(
        [node, "--check", str(ROOT / "web" / "sleepmate-sleep.js")],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr or result.stdout
