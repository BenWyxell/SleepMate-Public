import time

import pytest

from cpap import sleepsync_wifi_presence_v5216 as presence


class _FakeService:
    def __init__(self, scans):
        self._scans = list(scans)
        self.logs = []
        self.status = {}
        self.active_calls = 0

    def get_current_wifi_ssid(self):
        return "Knorrig"

    def visible_wifi_ssids(self):
        if not self._scans:
            return ["Knorrig"]
        return self._scans.pop(0)

    def log(self, message, level="INFO"):
        self.logs.append((level, message))

    def _update_status(self, **values):
        self.status.update(values)


def test_absent_ezshare_never_enters_active_recovery(monkeypatch):
    fake = _FakeService([["Knorrig", "Snuttig"], ["Knorrig", "Snuttig"]])

    monkeypatch.setattr(presence.os, "name", "nt", raising=False)
    monkeypatch.setattr(presence.time, "sleep", lambda _seconds: None)

    def active(_self, _profile):
        fake.active_calls += 1
        raise AssertionError("active recovery must not run while AP is absent")

    monkeypatch.setattr(presence, "_ACTIVE_RECOVERY_CONNECT", active)

    with pytest.raises(presence.EzShareNotBroadcastingError):
        presence._presence_aware_active_connect(fake, "ez Share")

    assert fake.active_calls == 0
    assert fake.status["connection"] == "ez Share nem sugároz"
    assert fake.status["sd_visible"] is False


def test_visible_ezshare_is_allowed_into_active_recovery(monkeypatch):
    fake = _FakeService([["Knorrig", "ez Share"]])

    monkeypatch.setattr(presence.os, "name", "nt", raising=False)

    def active(_self, _profile):
        fake.active_calls += 1
        return {"Knorrig": "auto"}

    monkeypatch.setattr(presence, "_ACTIVE_RECOVERY_CONNECT", active)

    result = presence._presence_aware_active_connect(fake, "ez Share")

    assert result == {"Knorrig": "auto"}
    assert fake.active_calls == 1


def test_passive_wait_keeps_internet_until_card_reappears(monkeypatch):
    fake = _FakeService(
        [
            ["Knorrig", "Snuttig"],
            ["Knorrig", "Snuttig", "ez Share"],
        ]
    )
    sleeps = []
    monkeypatch.setattr(
        presence.time,
        "sleep",
        lambda seconds: sleeps.append(seconds),
    )

    ok = presence._wait_for_ezshare_broadcast(
        fake,
        "ez Share",
        recovery_deadline=time.monotonic() + 120,
        trigger="manual",
    )

    assert ok is True
    assert sleeps == [
        presence.MANUAL_PRESENCE_RECHECK_SECONDS,
        presence.PRESENCE_POLL_SECONDS,
    ]
    assert fake.status["sd_visible"] is True
    assert "visszatért" in fake.status["phase"]
    assert not hasattr(fake, "_disconnect_wifi")
