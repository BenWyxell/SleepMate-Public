from __future__ import annotations

import os
import time

from .sleepsync_engine_v2 import SleepSyncService
from . import sleepsync_wifi_v5215 as wifi_v5215


# The 2026-08-29 field log captured an important success pattern: after SleepSync
# made every competing saved network manual and disconnected the current internet
# WLAN, Windows associated with the already-auto ez Share profile by itself before
# SleepSync issued a single explicit `netsh wlan connect`.  Earlier failures often
# started an explicit connect ~1 second after disconnect and then remained in
# `associating` for every forced retry.  Give Windows a clean autonomous window
# first, then fall back to the v5.2.15 escalating recovery engine only if needed.
AUTO_ASSOCIATION_GRACE_SECONDS = 12
AUTO_ASSOCIATION_DIAGNOSTIC_SECONDS = 4


def _auto_association_first_connect(
    self: SleepSyncService,
    profile: str,
) -> dict[str, str | None]:
    if os.name != "nt":
        return _ACTIVE_RECOVERY_CONNECT(self, profile)

    current = self.get_current_wifi_ssid()
    if current and current.casefold() == profile.casefold():
        self.log(f'Az "{profile}" Wi-Fi már aktív; nincs szükség hálózatváltásra.')
        return {}

    # Save the *real* original modes before changing anything.  If the passive
    # Windows auto-association succeeds, this exact map is returned to
    # _run_with_wifi(), which restores every mode after the sync.  If it fails,
    # the same map is also used after the active recovery path, so the nested
    # recovery layer cannot accidentally leave originally-auto internet profiles
    # in manual mode.
    target_mode = self._profile_mode(profile)
    original_states = self._suspend_other_autoconnect(profile)
    if target_mode in {"auto", "manual"}:
        original_states[profile] = target_mode

    interface = self._wifi_interface_name()
    try:
        try:
            self._set_profile_mode(profile, "auto")
        except Exception as exc:
            self.log(
                f'Az "{profile}" profil automatikus társításra állítása nem sikerült: {exc}; '
                "az aktív helyreállítási motor fogja átvenni a próbát.",
                "WARN",
            )

        try:
            wifi_v5215._ensure_autoconfig_enabled(self, interface)
        except Exception as exc:
            self.log(f"WLAN AutoConfig ellenőrzés kihagyva: {exc}", "WARN")

        try:
            self._disconnect_wifi()
        except Exception as exc:
            self.log(f"Kezdeti Wi-Fi bontás kihagyva: {exc}", "WARN")

        self._update_status(
            connection="ez Share automatikus társítás",
            current_wifi=None,
            sd_visible=True,
        )
        self.log(
            f'ez Share elsődleges csatlakozási mód: Windows automatikus társítás; '
            f'{AUTO_ASSOCIATION_GRACE_SECONDS} mp-ig nem küldünk connect/scant/resetet.'
        )

        deadline = time.monotonic() + AUTO_ASSOCIATION_GRACE_SECONDS
        next_diag = 0.0
        while time.monotonic() < deadline:
            current = self.get_current_wifi_ssid()
            if current and current.casefold() == profile.casefold():
                self._update_status(
                    current_wifi=current,
                    sd_visible=True,
                    connection="ez Share",
                )
                self.log(
                    f'Wi-Fi csatlakozás sikeres Windows automatikus társítással: '
                    f'"{current}"; explicit netsh connect nem kellett.'
                )
                return original_states

            now = time.monotonic()
            if now >= next_diag:
                snapshot = wifi_v5215._wlan_interface_snapshot(self)
                elapsed = max(
                    0,
                    AUTO_ASSOCIATION_GRACE_SECONDS - int(deadline - now),
                )
                self.log(
                    f'WLAN automatikus társítás (+{elapsed} mp): {snapshot}'
                )
                next_diag = now + AUTO_ASSOCIATION_DIAGNOSTIC_SECONDS
            time.sleep(1)

        self.log(
            "A Windows automatikus ez Share társítása nem fejeződött be az elsődleges ablakban; "
            "átváltunk az aktív, több lépcsős WLAN helyreállításra.",
            "WARN",
        )

        # Keep competing profiles suspended while the active engine takes over.
        # It will record their currently-manual state internally, but on success
        # we deliberately return original_states so _run_with_wifi restores the
        # actual pre-sync configuration rather than the nested snapshot.
        _ACTIVE_RECOVERY_CONNECT(self, profile)
        return original_states
    except Exception:
        self._restore_wifi_modes(original_states)
        raise


def _gateway_first_candidates() -> list[str]:
    """Prefer the currently installed route before DNS or a historical fixed IP."""
    candidates: list[str] = []
    for base in (
        *wifi_v5215._route_gateway_bases(),
        wifi_v5215.EZSHARE_DIRECT_BASE,
        str(getattr(wifi_v5215.legacy, "EZSHARE_BASE", "") or ""),
        wifi_v5215.EZSHARE_HOST_BASE,
    ):
        clean = str(base or "").rstrip("/")
        if clean and clean not in candidates:
            candidates.append(clean)
    return candidates


def install_sleepsync_wifi_autograce_v5215() -> None:
    """Layer field-proven auto-association first over the v5.2.15 recovery engine."""
    if getattr(SleepSyncService, "_wifi_autograce_v5215_installed", False):
        return

    global _ACTIVE_RECOVERY_CONNECT
    _ACTIVE_RECOVERY_CONNECT = SleepSyncService._connect_wifi
    wifi_v5215._ezshare_base_candidates = _gateway_first_candidates
    SleepSyncService._connect_wifi = _auto_association_first_connect
    SleepSyncService._wifi_autograce_v5215_installed = True


_ACTIVE_RECOVERY_CONNECT = SleepSyncService._connect_wifi


__all__ = [
    "AUTO_ASSOCIATION_GRACE_SECONDS",
    "install_sleepsync_wifi_autograce_v5215",
]
