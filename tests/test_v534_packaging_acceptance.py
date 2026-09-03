from pathlib import Path

import cpap.o2ring_runtime_v534 as o2_runtime

ROOT = Path(__file__).resolve().parents[1]
SPEC = (ROOT / "build" / "windows" / "SleepMate.spec").read_text(encoding="utf-8")
RUNTIME = (ROOT / "cpap" / "o2ring_runtime_v534.py").read_text(encoding="utf-8")
APP_CORE = (ROOT / "web" / "app-core.js").read_text(encoding="utf-8")


def test_v534_packaging_requires_current_o2_frontend_assets():
    for asset in (
        "/sleepmate-aurora.css",
        "/sleepmate-v530.css",
        "/sleepmate-v530.js",
        "/o2ring.css",
        "/o2ring.js",
        "/o2ring-report-ui.js",
        "/o2ring-v534.css",
        "/frontend-v534.js",
    ):
        assert repr(asset) in SPEC
    assert "protected_base_assets" in SPEC


def test_v534_packaging_rejects_obsolete_o2_runtime_assets():
    assert "for obsolete in ('/o2ring-v532.css','/o2ring-v532.js','/frontend-v533.js')" in SPEC
    assert "obsolete O2 frontend asset returned to active worker" in SPEC


def test_v534_packaging_uses_direct_latest_session_duration_fix():
    # The current app-core already renders total therapy duration, so the
    # packager must not depend on a brittle legacy "Befejezve" rewrite.
    assert "$('#latestStatus').textContent=secondsToHM(latest.therapy_seconds||0)" in APP_CORE
    assert "$('#latestSessions').textContent=`${latest.sessions?.length||0} szakasz`" in APP_CORE
    assert "$('#latestStatus').textContent='Befejezve'" not in APP_CORE
    assert "$('#latestStatus').textContent='Befejezve'" not in SPEC


def test_v534_invalidation_sse_resumes_with_standard_event_ids():
    # A PWA reconnect must be able to resume from either our explicit cursor or
    # the browser-standard Last-Event-ID header, and every invalidation frame must
    # carry its own SSE id so EventSource can reconnect without polling/rescans.
    assert 'self.headers.get("Last-Event-ID")' in RUNTIME
    assert "after = max(query_after, last_event_id)" in RUNTIME
    assert 'frame = f"id: {current}\\nevent: invalidation\\ndata: {payload}\\n\\n"' in RUNTIME
    assert "deque(maxlen=max(16, int(max_events)))" in RUNTIME


def test_v534_invalidation_sequence_moves_forward_across_normal_backend_restart(monkeypatch):
    # Make the restart scenario deterministic rather than relying on CI clock
    # resolution. The wall-clock-seeded sequence must move forward after restart,
    # even after several invalidations were emitted by the previous runtime.
    base = 1_800_000_000.000
    monkeypatch.setattr(o2_runtime.time, "time", lambda: base)
    previous = o2_runtime._EventHub(max_events=16)
    for index in range(5):
        previous.publish("therapy-invalidated", days=[f"2026090{index + 1}"])
    previous_seq = previous.snapshot()["seq"]

    monkeypatch.setattr(o2_runtime.time, "time", lambda: base + 0.010)
    restarted = o2_runtime._EventHub(max_events=16)
    assert restarted.snapshot()["seq"] > previous_seq
