from cpap.oximetry import OximetrySample, match_recording_to_cpap, summarize_samples


def test_summary_uses_sample_interval_for_t90_and_invalid_coverage():
    samples = [
        OximetrySample(0, 96, 60, valid=True),
        OximetrySample(4, 89, 62, valid=True),
        OximetrySample(8, None, None, valid=False),
        OximetrySample(12, 88, 64, valid=True),
    ]
    summary = summarize_samples(samples, start_ts=0, end_ts=16)
    assert summary.sample_count == 4
    assert summary.valid_sample_count == 3
    assert summary.t90_seconds == 8.0
    assert summary.coverage_percent == 75.0
    assert summary.spo2_minimum == 88
    assert summary.heart_rate_average == 62.0


def test_session_matching_uses_real_overlap_not_calendar_day():
    recording = {"recording_id": "r1", "start_ts": 1000.0, "end_ts": 5000.0}
    match = match_recording_to_cpap(recording, 1600.0, 4600.0)
    assert match is not None
    assert match.overlap_start == 1600.0
    assert match.overlap_end == 4600.0
    assert match.overlap_seconds == 3000.0
    assert match.cpap_coverage_percent == 100.0


def test_short_overlap_is_not_attached():
    recording = {"recording_id": "r1", "start_ts": 1000.0, "end_ts": 1200.0}
    assert match_recording_to_cpap(recording, 1100.0, 5000.0) is None
