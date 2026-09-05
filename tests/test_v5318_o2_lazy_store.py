from cpap.oximetry import OximetrySample, OximetryStore


def test_recording_list_does_not_load_sample_array(tmp_path):
    store = OximetryStore(tmp_path)
    samples = [
        OximetrySample(timestamp=1_700_000_000 + i, spo2=96, heart_rate=62, motion=0)
        for i in range(20_000)
    ]
    saved = store.save_recording(
        device_id="ring-1",
        start_ts=samples[0].timestamp,
        end_ts=samples[-1].timestamp,
        samples=samples,
        source_name="night.vld",
    )

    rows = store.list_recordings()
    assert len(rows) == 1
    row = rows[0]
    assert row["recording_id"] == saved["recording_id"]
    assert row["summary"]["sample_count"] == 20_000
    assert row._samples_loaded is False

    # Startup/status/recording-list callers only touch metadata and must not
    # deserialize the 20k-point array.
    assert row.get("source_name") == "night.vld"
    assert row._samples_loaded is False

    # Detailed/daily/export paths still receive the exact samples on demand.
    loaded = row.get("samples")
    assert row._samples_loaded is True
    assert len(loaded) == 20_000
    assert loaded[0]["spo2"] == 96


def test_recording_metadata_parser_keeps_summary_without_samples(tmp_path):
    store = OximetryStore(tmp_path)
    samples = [
        OximetrySample(timestamp=1_700_100_000 + i * 4, spo2=95, heart_rate=65)
        for i in range(100)
    ]
    store.save_recording(
        device_id="ring-2",
        start_ts=samples[0].timestamp,
        end_ts=samples[-1].timestamp,
        samples=samples,
        source_name="summary.vld",
    )

    row = store.list_recordings()[0]
    assert row["start_ts"] == samples[0].timestamp
    assert row["end_ts"] == samples[-1].timestamp
    assert row["summary"]["spo2_average"] == 95.0
    assert row._samples_loaded is False
