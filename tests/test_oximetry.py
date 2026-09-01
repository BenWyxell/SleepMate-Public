from cpap.oximetry import OximetrySample, match_recording_to_cpap, summarize_samples


def test_summary_calculates_core_metrics():
    samples = [
        OximetrySample(0, 97, 60),
        OximetrySample(4, 96, 62),
        OximetrySample(8, 89, 70),
        OximetrySample(12, 88, 75),
        OximetrySample(16, 95, 65),
    ]
    summary = summarize_samples(samples, start_ts=0, end_ts=16)
    assert summary.spo2_minimum == 88
    assert summary.heart_rate_maximum == 75
    assert summary.t90_seconds > 0
    assert summary.coverage_percent == 100.0


def test_session_match_uses_actual_time_overlap():
    recording = {"recording_id": "night", "start_ts": 1000, "end_ts": 5000}
    match = match_recording_to_cpap(recording, 1500, 4500)
    assert match is not None
    assert match.overlap_start == 1500
    assert match.overlap_end == 4500
    assert match.cpap_coverage_percent == 100.0


def test_session_match_rejects_tiny_overlap():
    recording = {"recording_id": "night", "start_ts": 1000, "end_ts": 1200}
    assert match_recording_to_cpap(recording, 1100, 5000) is None
