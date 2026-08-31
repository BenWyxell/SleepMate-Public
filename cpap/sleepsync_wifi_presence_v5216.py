from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any

from . import sleepsync_legacy as legacy
from . import sleepsync_wifi_v5215 as wifi_v5215
from .sleepsync_engine_v2 import SleepSyncService


# Field log 2026-08-29 showed a distinct hardware-side failure mode: after a
# successful strong association the ez Share HTTP endpoint can stop answering and
# the SSID can disappear from scans entirely. In that state repeated connect,
# profile re-arm and AutoConfig recovery cannot help because there is no AP to
# associate with. Detect that state before active recovery and keep the normal
# internet WLAN connected while waiting for the card to start broadcasting again.
PRESENCE_CONFIRM_DELAY_SECONDS = 2
MANUAL_PRESENCE_RECHECK_SECONDS = 30
AUTO_PRESENCE_RECHECK_SECONDS = 45
PRESENCE_POLL_SECONDS = 30


class EzShareNotBroadcastingError(RuntimeError):
    """Raised when other WLANs are visible but ez Share itself is not broadcasting."""


def _visible_match(values: list[str], profile: str) -> str | None:
    return next((ssid for ssid in values if ssid.casefold() == profile.casefold()), None)


def _presence_aware_active_connect(
    self: SleepSyncService,
    profile: str,
) -> dict[str, str | None]:
    """Do not hammer Windows recovery when the ez Share radio is absent.

    This wrapper is intentionally installed *under* the v5.2.15 automatic
    association grace layer. Windows still gets its clean 12-second no-scan,
    no-connect window first. Only when that path fails do we take two short scan
    samples before entering the expensive active recovery engine.
    """
    if os.name != "nt":
        return _ACTIVE_RECOVERY_CONNECT(self, profile)

    current = self.get_current_wifi_ssid()
    if current and current.casefold() == profile.casefold():
        return _ACTIVE_RECOVERY_CONNECT(self, profile)

    try:
        first = self.visible_wifi_ssids()
    except Exception as exc:
        self.log(
            f'Az "{profile}" sugárzás-ellenőrzés első scan-je sikertelen: {exc}; '
            "a normál WLAN-helyreállítás folytatódik.",
            "WARN",
        )
        return _ACTIVE_RECOVERY_CONNECT(self, profile)

    first_match = _visible_match(first, profile)
    if first_match:
        self.log(f'Az "{profile}" SSID látható; aktív WLAN-helyreállítás folytatódik.')
        return _ACTIVE_RECOVERY_CONNECT(self, profile)

    self.log(
        f'Az "{profile}" SSID nincs az első scan-listában. '
        f'{PRESENCE_CONFIRM_DELAY_SECONDS} mp múlva megerősítő scan következik; '
        "addig nem küldünk connect/reset/profile-helyreállítást."
    )
    time.sleep(PRESENCE_CONFIRM_DELAY_SECONDS)

    try:
        second = self.visible_wifi_ssids()
    except Exception as exc:
        self.log(
            f'Az "{profile}" sugárzás-ellenőrzés megerősítő scan-je sikertelen: {exc}; '
            "a normál WLAN-helyreállítás folytatódik.",
            "WARN",
        )
        return _ACTIVE_RECOVERY_CONNECT(self, profile)

    second_match = _visible_match(second, profile)
    if second_match:
        self.log(
            f'Az "{profile}" SSID a megerősítő scan-ben visszatért; '
            "aktív WLAN-helyreállítás folytatódik."
        )
        return _ACTIVE_RECOVERY_CONNECT(self, profile)

    # At least one non-empty scan proves Windows WLAN scanning itself works and
    # other radios are visible. That is the signature from the field log where
    # the ez Share AP itself had disappeared.
    if first or second:
        seen = []
        for ssid in [*first, *second]:
            if ssid and ssid not in seen:
                seen.append(ssid)
        visible_text = ", ".join(seen[:12]) or "nincs"
        self._update_status(
            connection="ez Share nem sugároz",
            current_wifi=current,
            sd_visible=False,
        )
        raise EzShareNotBroadcastingError(
            f'Az "{profile}" Wi-Fi két egymást követő scan-ben sem látható, '
            f'miközben más hálózatok elérhetők ({visible_text}). '
            "A SleepSync nem indít felesleges WLAN connect/reset ciklust; "
            "visszaáll az internetre és ott várja meg, amíg az ez Share újra sugároz."
        )

    # An entirely empty scan can also mean a Windows/driver-side scan failure, so
    # do not misclassify it as card hardware absence.
    self.log(
        f'Az "{profile}" nem látható, de a Windows egyik scan-ben sem adott '
        "értékelhető SSID-listát; a normál WLAN-helyreállítás folytatódik.",
        "WARN",
    )
    return _ACTIVE_RECOVERY_CONNECT(self, profile)


def _wait_for_ezshare_broadcast(
    self: SleepSyncService,
    profile: str,
    *,
    recovery_deadline: float,
    trigger: str,
) -> bool:
    """Keep internet online and poll gently until ez Share reappears."""
    first_wait = (
        MANUAL_PRESENCE_RECHECK_SECONDS
        if trigger == "manual"
        else AUTO_PRESENCE_RECHECK_SECONDS
    )
    wait_seconds = first_wait
    check = 0

    while True:
        remaining = max(0, int(recovery_deadline - time.monotonic()))
        if remaining <= 0:
            self.log(
                f'Az "{profile}" SSID a teljes helyreállítási ablak alatt nem tért vissza.',
                "WARN",
            )
            return False

        wait_seconds = max(1, min(wait_seconds, remaining))
        current = self.get_current_wifi_ssid()
        self._update_status(
            connection="interneten várakozik az ez Share-re",
            current_wifi=current,
            sd_visible=False,
            phase=(
                f'Az ez Share Wi-Fi jelenleg nem elérhető. '
                f'Internetkapcsolat megtartva; újraellenőrzés {wait_seconds} mp múlva…'
            ),
        )
        self.log(
            f'Az "{profile}" jelenleg nem sugároz. '
            f'Az internetkapcsolatot nem bontjuk; újraellenőrzés {wait_seconds} mp múlva.'
        )
        time.sleep(wait_seconds)

        check += 1
        try:
            visible = self.visible_wifi_ssids()
        except Exception as exc:
            self.log(f'ez Share passzív jelenlét-ellenőrzés {check}: scan hiba: {exc}', "WARN")
            visible = []

        exact = _visible_match(visible, profile)
        if exact:
            current = self.get_current_wifi_ssid()
            self._update_status(
                connection="ez Share újra elérhető",
                current_wifi=current,
                sd_visible=True,
                phase="Az ez Share Wi-Fi visszatért. Kapcsolódás indul…",
                last_error=None,
            )
            self.log(
                f'Az "{exact}" SSID újra megjelent a levegőben '
                f'({check}. passzív ellenőrzés). A SleepSync most újra megpróbál kapcsolódni.'
            )
            return True

        wait_seconds = PRESENCE_POLL_SECONDS


def _presence_aware_sync_job(
    self: SleepSyncService,
    jid: str,
    trigger: str = "manual",
) -> dict[str, Any]:
    """Persistent sync that waits on internet when the card radio disappears."""
    if not self._operation_lock.acquire(blocking=False):
        raise RuntimeError("Már fut SleepSync művelet.")

    self._update_status(
        running=True,
        operation="sync",
        progress=0,
        phase="Szinkronizálás előkészítése…",
        total_files=0,
        work_files=0,
        processed_files=0,
        downloaded=0,
        unchanged=0,
        errors=0,
        current_file="—",
        last_error=None,
    )
    self.log(f"SleepSync szinkron indul – trigger={trigger}")
    result: dict[str, Any] | None = None

    try:
        configured = max(
            1,
            int(
                self._settings.get(
                    "auto_retry_count",
                    wifi_v5215.AUTO_MIN_SYNC_ATTEMPTS,
                )
                or wifi_v5215.AUTO_MIN_SYNC_ATTEMPTS
            ),
        )
        minimum = (
            wifi_v5215.MANUAL_MIN_SYNC_ATTEMPTS
            if trigger == "manual"
            else wifi_v5215.AUTO_MIN_SYNC_ATTEMPTS
        )
        max_attempts = min(
            wifi_v5215.MAX_SYNC_ATTEMPTS,
            max(configured, minimum),
        )
        recovery_window = (
            wifi_v5215.MANUAL_RECOVERY_WINDOW_SECONDS
            if trigger == "manual"
            else wifi_v5215.AUTO_RECOVERY_WINDOW_SECONDS
        )
        recovery_deadline = time.monotonic() + recovery_window
        normal_auto_wait = int(
            self._settings.get("auto_retry_wait_minutes", 5) or 5
        ) * 60
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                result = self._run_with_wifi(
                    jid,
                    lambda: self._sync_connected(jid),
                )
                last_error = None
                break
            except EzShareNotBroadcastingError as exc:
                last_error = exc
                self.log(
                    f"SleepSync: az ez Share rádió jelenleg nem elérhető "
                    f"({attempt}/{max_attempts}): {exc}",
                    "WARN",
                )
                if attempt >= max_attempts or time.monotonic() >= recovery_deadline:
                    break

                if not _wait_for_ezshare_broadcast(
                    self,
                    legacy.EZSHARE_WIFI_PROFILE,
                    recovery_deadline=recovery_deadline,
                    trigger=trigger,
                ):
                    break
                # The passive watcher returns only after the SSID is visible
                # again. Do not add another fixed retry delay.
                continue
            except Exception as exc:
                last_error = exc
                self.log(
                    f"SleepSync helyreállítási ciklus {attempt}/{max_attempts} "
                    f"sikertelen: {exc}",
                    "ERROR",
                )
                if attempt >= max_attempts or time.monotonic() >= recovery_deadline:
                    break

                connection_problem = wifi_v5215._connection_failure(exc)
                if connection_problem:
                    wait_seconds = 12 if trigger == "manual" else 45
                else:
                    wait_seconds = 8 if trigger == "manual" else normal_auto_wait

                remaining = max(0, int(recovery_deadline - time.monotonic()))
                if remaining <= 0:
                    break
                wait_seconds = min(wait_seconds, remaining)
                self._update_status(
                    phase=(
                        f"Kapcsolat helyreállítása: újabb próba {wait_seconds} mp múlva "
                        f"({attempt + 1}/{max_attempts})…"
                    ),
                    last_error=str(exc),
                )
                self.log(
                    f"SleepSync újrapróbálás {attempt + 1}/{max_attempts} "
                    f"{wait_seconds} mp múlva; helyreállítási ablakból még "
                    f"~{remaining // 60} perc maradt."
                )
                time.sleep(wait_seconds)

        if last_error is not None:
            raise last_error
        if not result or int(result.get("checked_files", 0)) <= 0:
            raise RuntimeError(
                "Érvénytelen SleepSync eredmény: 0 ellenőrzött fájl. "
                "Sikeres állapot tiltva."
            )
        if int(result.get("errors", 0)) > 0:
            raise RuntimeError(
                f"A szinkron {result['errors']} végleges fájlhibával zárult. "
                "Sikeres állapot tiltva."
            )

        self._add_history("sync", True, result, trigger=trigger)
        self._update_status(
            running=False,
            operation=None,
            progress=100,
            phase="Szinkronizálás kész. Minden naprakész.",
            last_run=datetime.now().isoformat(timespec="seconds"),
            last_error=None,
            current_file="—",
        )
        self.log(f"SleepSync kész: {result}")
        return result
    except Exception as exc:
        self._add_history("sync", False, result, error=exc, trigger=trigger)
        self._update_status(
            running=False,
            operation=None,
            phase="A szinkronizálás nem sikerült.",
            last_error=str(exc),
        )
        raise
    finally:
        self._operation_lock.release()
        self._scheduler_wakeup.set()


def install_sleepsync_wifi_presence_v5216() -> None:
    """Install AP-presence gating under auto-grace and over active recovery."""
    if getattr(SleepSyncService, "_wifi_presence_v5216_installed", False):
        return

    global _ACTIVE_RECOVERY_CONNECT
    _ACTIVE_RECOVERY_CONNECT = SleepSyncService._connect_wifi
    SleepSyncService._connect_wifi = _presence_aware_active_connect
    SleepSyncService._sync_job = _presence_aware_sync_job
    SleepSyncService._wifi_presence_v5216_installed = True


_ACTIVE_RECOVERY_CONNECT = SleepSyncService._connect_wifi


__all__ = [
    "AUTO_PRESENCE_RECHECK_SECONDS",
    "EzShareNotBroadcastingError",
    "MANUAL_PRESENCE_RECHECK_SECONDS",
    "PRESENCE_POLL_SECONDS",
    "install_sleepsync_wifi_presence_v5216",
]
