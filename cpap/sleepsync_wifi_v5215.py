from __future__ import annotations

import os
import re
import subprocess
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from . import sleepsync_legacy as legacy
from .sleepsync_engine_v2 import EZSHARE_ROOT, SleepSyncService


# The old ez Share adapter used by SleepSync normally exposes its HTTP server on
# 192.168.4.1.  Keep the historical hostname as a fallback, but do not make a
# successful Wi-Fi association depend on Windows DNS/captive-portal name lookup.
EZSHARE_DIRECT_BASE = "http://192.168.4.1"
EZSHARE_HOST_BASE = "http://ezshare.card"

# A scheduled sync is valuable only if it keeps trying through transient Windows
# WLAN failures.  These are minimum *outer* recovery cycles; each cycle contains
# several adaptive association strategies and still has a hard time window.
MANUAL_MIN_SYNC_ATTEMPTS = 8
AUTO_MIN_SYNC_ATTEMPTS = 12
MANUAL_RECOVERY_WINDOW_SECONDS = 25 * 60
AUTO_RECOVERY_WINDOW_SECONDS = 45 * 60
MAX_SYNC_ATTEMPTS = 30

# One acquisition cycle escalates instead of repeating an identical command.
ASSOCIATION_WINDOWS = (20, 25, 30, 45)
DIAGNOSTIC_INTERVAL_SECONDS = 5


def _windows_oem_encoding() -> str:
    """Return the code page used by classic Windows console tools.

    netsh redirected through a pipe is not guaranteed to be UTF-8.  Decoding it
    as UTF-8 corrupted Hungarian profile names (for example Kovács -> Kov�cs),
    which meant those competing autoconnect profiles were never really disabled.
    """
    if os.name != "nt":
        return "utf-8"
    try:
        import ctypes

        code_page = int(ctypes.windll.kernel32.GetOEMCP())
        if code_page > 0:
            return f"cp{code_page}"
    except Exception:
        pass
    return "utf-8"


def _decode_console_bytes(raw: bytes | None) -> str:
    if not raw:
        return ""
    encoding = _windows_oem_encoding()
    try:
        return raw.decode(encoding)
    except Exception:
        try:
            return raw.decode("utf-8")
        except Exception:
            return raw.decode(encoding, errors="replace")


def _run_netsh_native(args: list[str]) -> tuple[int, str]:
    """Run netsh without forcing UTF-8 onto its localized console output."""
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run(
        ["netsh"] + list(args),
        capture_output=True,
        text=False,
        creationflags=creationflags,
    )
    return result.returncode, _decode_console_bytes(result.stdout) + _decode_console_bytes(result.stderr)


def _wlan_interface_snapshot(self: SleepSyncService) -> str:
    """Read WLAN state without starting a scan or changing association."""
    if os.name != "nt":
        return "nem Windows"
    try:
        code, output = self._run_netsh(["wlan", "show", "interfaces"])
    except Exception as exc:
        return f"lekérdezési hiba: {exc}"
    if code != 0:
        cleaned = (output or "").strip().replace("\r", " ").replace("\n", " ")
        return f"netsh code={code}" + (f"; {cleaned[:500]}" if cleaned else "")

    values: dict[str, str] = {}
    for raw_line in (output or "").splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            continue
        folded = key.casefold()
        if folded in {"name", "név"}:
            values["interfész"] = value
        elif folded == "state" or "állapot" in folded:
            values["állapot"] = value
        elif folded == "ssid":
            values["SSID"] = value
        elif folded == "bssid":
            values["BSSID"] = value
        elif folded in {"signal", "jel"} or "jelerősség" in folded:
            values["jel"] = value
        elif "channel" in folded or "csatorna" in folded:
            values["csatorna"] = value
        elif "radio type" in folded or "rádió" in folded:
            values["rádió"] = value

    order = ("interfész", "állapot", "SSID", "BSSID", "jel", "csatorna", "rádió")
    parts = [f'{key}="{values[key]}"' for key in order if values.get(key)]
    if parts:
        return "; ".join(parts)
    cleaned_lines = [line.strip() for line in (output or "").splitlines() if line.strip()]
    return " | ".join(cleaned_lines[:8])[:900] or "nincs értelmezhető interfészadat"


def _is_elevated() -> bool:
    if os.name != "nt":
        return False
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _ensure_autoconfig_enabled(self: SleepSyncService, interface: str | None) -> bool:
    if not interface:
        return False
    code, output = self._run_netsh(
        ["wlan", "set", "autoconfig", "enabled=yes", f"interface={interface}"]
    )
    if code == 0:
        return True
    cleaned = (output or "").strip().replace("\r", " ").replace("\n", " ")
    self.log(
        f'WLAN AutoConfig bekapcsolása nem sikerült [{interface}]: code={code}'
        + (f'; {cleaned}' if cleaned else ""),
        "WARN",
    )
    return False


def _soft_reset_wlan_autoconfig(self: SleepSyncService, interface: str | None) -> bool:
    """Reset WLAN AutoConfig state when Windows is stuck in associating.

    Disabling AutoConfig requires elevation on normal Windows installs.  Never
    attempt the off/on reset without it; non-elevated SleepMate simply uses the
    safe profile re-arm path instead.  If off succeeds, always make several
    attempts to turn AutoConfig back on before returning.
    """
    if not interface:
        return False
    if not _is_elevated():
        self.log(
            "WLAN AutoConfig teljes újraélesztése kihagyva: a SleepMate nem emelt jogosultsággal fut; profil-helyreállítással folytatjuk."
        )
        _ensure_autoconfig_enabled(self, interface)
        return False

    off_code, off_output = self._run_netsh(
        ["wlan", "set", "autoconfig", "enabled=no", f"interface={interface}"]
    )
    if off_code != 0:
        cleaned = (off_output or "").strip().replace("\r", " ").replace("\n", " ")
        self.log(
            f'WLAN AutoConfig reset nem indítható [{interface}]: code={off_code}'
            + (f'; {cleaned}' if cleaned else ""),
            "WARN",
        )
        _ensure_autoconfig_enabled(self, interface)
        return False

    self.log(f'WLAN AutoConfig ideiglenesen leállítva az "{interface}" interfészen a beragadt társítás törléséhez.')
    time.sleep(1.2)
    for enable_attempt in range(1, 4):
        if _ensure_autoconfig_enabled(self, interface):
            self.log(f'WLAN AutoConfig újraindítva [{interface}] ({enable_attempt}/3).')
            time.sleep(1.5)
            return True
        time.sleep(1)
    raise RuntimeError(
        f'A WLAN AutoConfigot a helyreállítás után nem sikerült visszakapcsolni az "{interface}" interfészen.'
    )


def _rearm_target_profile(self: SleepSyncService, profile: str) -> None:
    """Rewrite only the target profile connection mode, then use explicit connect."""
    try:
        self._set_profile_mode(profile, "auto")
        time.sleep(0.5)
        self._set_profile_mode(profile, "manual")
        self.log(f'Az "{profile}" Wi-Fi profil újraélesítve (auto -> manual); explicit kapcsolódással folytatjuk.')
    except Exception as exc:
        self.log(f'Az "{profile}" profil újraélesztése részben sikertelen: {exc}', "WARN")


def _refresh_saved_profile(self: SleepSyncService, profile: str, interface: str | None) -> bool:
    """Export and re-import the saved profile without deleting it.

    This is deliberately non-destructive: a valid XML backup must exist before
    re-import, and the existing profile is never deleted.  It refreshes Windows'
    cached profile representation while keeping credentials/security metadata.
    """
    try:
        folder = Path(self.private_dir) / "wifi_profile_recovery"
        folder.mkdir(parents=True, exist_ok=True)
        before = {p.resolve() for p in folder.glob("*.xml")}
        args = ["wlan", "export", "profile", f"name={profile}", f"folder={folder}"]
        if interface:
            args.append(f"interface={interface}")
        code, output = self._run_netsh(args)
        if code != 0:
            cleaned = (output or "").strip().replace("\r", " ").replace("\n", " ")
            self.log(
                f'Az "{profile}" profil exportja sikertelen; törlés nem történik: code={code}'
                + (f'; {cleaned}' if cleaned else ""),
                "WARN",
            )
            return False

        candidates = [p for p in folder.glob("*.xml") if p.resolve() not in before]
        if not candidates:
            candidates = list(folder.glob("*.xml"))
        if not candidates:
            self.log(f'Az "{profile}" profil exportja után nem található XML; törlés nem történt.', "WARN")
            return False
        xml_path = max(candidates, key=lambda p: p.stat().st_mtime)
        try:
            add_args = ["wlan", "add", "profile", f"filename={xml_path}"]
            if interface:
                add_args.append(f"interface={interface}")
            add_args.append("user=current")
            add_code, add_output = self._run_netsh(add_args)
            cleaned = (add_output or "").strip().replace("\r", " ").replace("\n", " ")
            if add_code == 0:
                self.log(f'Az "{profile}" mentett profil biztonságosan újraimportálva a Windows WLAN-ba.')
                return True
            self.log(
                f'Az "{profile}" profil újraimportja nem sikerült; az eredeti profil érintetlen maradt: code={add_code}'
                + (f'; {cleaned}' if cleaned else ""),
                "WARN",
            )
            return False
        finally:
            try:
                xml_path.unlink(missing_ok=True)
            except Exception:
                pass
    except Exception as exc:
        self.log(f'Az "{profile}" profil biztonságos újraimportja kihagyva: {exc}', "WARN")
        return False


def _resilient_connect_wifi(self: SleepSyncService, profile: str) -> dict[str, str | None]:
    """Acquire ez Share with escalating, self-healing Windows WLAN strategies."""
    if os.name != "nt":
        raise RuntimeError("A SleepSync Wi-Fi váltás Windows alatt támogatott.")

    saved = self.saved_wifi_profiles()
    if saved and not any(p.casefold() == profile.casefold() for p in saved):
        raise RuntimeError(f'A Windowsban nincs elmentve "{profile}" nevű Wi-Fi profil.')

    current = self.get_current_wifi_ssid()
    if current and current.casefold() == profile.casefold():
        self.log(f'Az "{profile}" Wi-Fi már aktív; nincs szükség hálózatváltásra.')
        return {}

    target_mode = self._profile_mode(profile)
    states = self._suspend_other_autoconnect(profile)
    if target_mode in {"auto", "manual"}:
        states[profile] = target_mode

    interface = self._wifi_interface_name()
    try:
        # The target is connected explicitly by SleepSync, therefore temporary
        # manual mode is deterministic and prevents Windows from autonomously
        # roaming while the no-internet ez Share network is being acquired.
        try:
            self._set_profile_mode(profile, "manual")
        except Exception as exc:
            self.log(f'Az "{profile}" ideiglenes kézi módja nem állítható: {exc}', "WARN")
        _ensure_autoconfig_enabled(self, interface)

        try:
            self._disconnect_wifi()
        except Exception as exc:
            self.log(f"Kezdeti Wi-Fi bontás kihagyva: {exc}", "WARN")
        time.sleep(1.2)

        last_output = ""
        last_visible: list[str] = []
        last_snapshot = "nincs"

        for attempt, association_wait in enumerate(ASSOCIATION_WINDOWS, start=1):
            current = self.get_current_wifi_ssid()
            if current and current.casefold() == profile.casefold():
                self.log(f'Wi-Fi csatlakozás sikeres: "{current}" ({attempt}. helyreállítási kör előtt).')
                return states

            # Escalate only BETWEEN association windows.  Never rescan, reconnect
            # or reset AutoConfig while Windows is inside a passive wait window.
            if attempt == 2:
                _rearm_target_profile(self, profile)
            elif attempt == 3:
                _soft_reset_wlan_autoconfig(self, interface)
                _rearm_target_profile(self, profile)
            elif attempt == 4:
                _refresh_saved_profile(self, profile, interface)
                _rearm_target_profile(self, profile)
                _ensure_autoconfig_enabled(self, interface)

            if attempt > 1:
                try:
                    self._disconnect_wifi()
                except Exception:
                    pass
                time.sleep(1.2)

            try:
                visible = self.visible_wifi_ssids()
                last_visible = visible
            except Exception as exc:
                visible = []
                self.log(f"Wi-Fi scan hiba a {attempt}. helyreállítási kör előtt: {exc}", "WARN")
            exact_visible = next((ssid for ssid in visible if ssid.casefold() == profile.casefold()), None)

            self._update_status(
                connection=f"ez Share helyreállítás ({attempt}/{len(ASSOCIATION_WINDOWS)})",
                current_wifi=current,
                sd_visible=bool(exact_visible),
            )
            self.log(
                f'ez Share helyreállítási kör {attempt}/{len(ASSOCIATION_WINDOWS)}: '
                + (f'SSID látható mint "{exact_visible}".' if exact_visible else 'SSID nincs az aktuális scan-listában; a mentett profilt közvetlenül kérjük.')
            )

            interface = self._wifi_interface_name() or interface
            args = ["wlan", "connect", f"name={profile}"]
            if exact_visible:
                args.append(f"ssid={exact_visible}")
            if interface:
                args.append(f"interface={interface}")
            code, output = self._run_netsh(args)
            last_output = output or last_output
            cleaned = (output or "").strip().replace("\r", " ").replace("\n", " ")
            self.log(
                f'netsh connect {attempt}/{len(ASSOCIATION_WINDOWS)}: code={code}'
                + (f', interface="{interface}"' if interface else "")
                + (f', üzenet="{cleaned}"' if cleaned else "")
                + f'; {association_wait} mp passzív társítási ablak következik.'
            )

            deadline = time.monotonic() + association_wait
            next_diagnostic = 0.0
            while time.monotonic() < deadline:
                current = self.get_current_wifi_ssid()
                if current and current.casefold() == profile.casefold():
                    self._update_status(current_wifi=current, sd_visible=True, connection="ez Share")
                    self.log(f'Wi-Fi csatlakozás sikeres: "{current}" ({attempt}/{len(ASSOCIATION_WINDOWS)}).')
                    return states

                now = time.monotonic()
                if now >= next_diagnostic:
                    last_snapshot = _wlan_interface_snapshot(self)
                    elapsed = max(0, association_wait - int(deadline - now))
                    self.log(
                        f'WLAN passzív állapot {attempt}/{len(ASSOCIATION_WINDOWS)} '
                        f'(+{elapsed} mp): {last_snapshot}'
                    )
                    next_diagnostic = now + DIAGNOSTIC_INTERVAL_SECONDS
                time.sleep(1)

            active = self.get_current_wifi_ssid()
            last_snapshot = _wlan_interface_snapshot(self)
            self.log(
                f'Az {attempt}/{len(ASSOCIATION_WINDOWS)}. ez Share helyreállítási kör lejárt. '
                f'Aktív SSID: "{active or "nincs kapcsolat"}". '
                f'Windows WLAN állapot: {last_snapshot}',
                "WARN",
            )

        visible_text = ", ".join(last_visible[:12]) if last_visible else "nincs / nem frissült"
        raise RuntimeError(
            f'Az "{profile}" Wi-Fihez egy teljes, {len(ASSOCIATION_WINDOWS)} lépcsős Windows WLAN helyreállítási ciklus után sem sikerült kapcsolódni. '
            f'Utolsó Windows WLAN állapot: {last_snapshot}. '
            f'Utolsó látható SSID-k: {visible_text}. '
            f'Utolsó netsh válasz: {last_output.strip() or "nincs"}'
        )
    except Exception:
        self._restore_wifi_modes(states)
        raise


def _route_gateway_bases() -> list[str]:
    """Return private IPv4 default gateways as HTTP base candidates."""
    if os.name != "nt":
        return []
    try:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run(
            ["route", "print", "-4"],
            capture_output=True,
            text=False,
            creationflags=creationflags,
        )
        text = _decode_console_bytes(result.stdout) + _decode_console_bytes(result.stderr)
    except Exception:
        return []

    bases: list[str] = []
    for match in re.finditer(
        r"(?m)^\s*0\.0\.0\.0\s+0\.0\.0\.0\s+(\d{1,3}(?:\.\d{1,3}){3})\s+",
        text,
    ):
        ip = match.group(1)
        parts = [int(x) for x in ip.split(".")]
        private = (
            parts[0] == 10
            or (parts[0] == 172 and 16 <= parts[1] <= 31)
            or (parts[0] == 192 and parts[1] == 168)
        )
        if private:
            base = f"http://{ip}"
            if base not in bases:
                bases.append(base)
    return bases[:4]


def _ezshare_base_candidates() -> list[str]:
    candidates: list[str] = []
    for base in (
        EZSHARE_DIRECT_BASE,
        str(getattr(legacy, "EZSHARE_BASE", "") or ""),
        *_route_gateway_bases(),
        EZSHARE_HOST_BASE,
    ):
        clean = str(base or "").rstrip("/")
        if clean and clean not in candidates:
            candidates.append(clean)
    return candidates


def _probe_ezshare_root(base: str, timeout: float = 6.0) -> str:
    query = urllib.parse.urlencode({"dir": EZSHARE_ROOT})
    request = urllib.request.Request(
        f"{base}/dir?{query}",
        headers={"User-Agent": "SleepSync/1.1.5"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="replace")
    upper = text.upper()
    marker_count = sum(token in upper for token in ("DATALOG", "STR.EDF", "SETTINGS"))
    if marker_count < 2:
        raise RuntimeError("a válasz nem az ez Share ResMed gyökérkönyvtára")
    return text


def _wait_http_ready_resilient(self: SleepSyncService) -> None:
    """Resolve the card by direct IP/gateway before relying on ezshare.card DNS."""
    configured = int(self._settings.get("ezshare_ready_timeout_seconds", 25) or 25)
    timeout = max(60, configured)
    deadline = time.monotonic() + timeout
    attempt = 0
    last: Exception | None = None
    lost_wifi_checks = 0

    while time.monotonic() < deadline:
        attempt += 1
        current = self.get_current_wifi_ssid()
        if not current or current.casefold() != legacy.EZSHARE_WIFI_PROFILE.casefold():
            lost_wifi_checks += 1
            last = RuntimeError(
                f'Az aktív Wi-Fi nem "{legacy.EZSHARE_WIFI_PROFILE}", hanem "{current or "nincs kapcsolat"}".'
            )
            # Do not waste a full HTTP timeout after association has already
            # disappeared.  Return control to the outer recovery loop quickly.
            if lost_wifi_checks >= 3:
                raise RuntimeError(
                    "Az ez Share Wi-Fi kapcsolat megszakadt a kártya webfelületének ébresztése közben; azonnali WLAN újracsatlakozás szükséges."
                )
            time.sleep(2)
            continue
        lost_wifi_checks = 0

        for base in _ezshare_base_candidates():
            if time.monotonic() >= deadline:
                break
            try:
                _probe_ezshare_root(base, timeout=6.0)
                old_base = legacy.EZSHARE_BASE
                legacy.EZSHARE_BASE = base
                try:
                    entries = self._parse_directory(EZSHARE_ROOT)
                    if not entries:
                        raise RuntimeError("0 értelmezhető gyökérelem")
                except Exception:
                    legacy.EZSHARE_BASE = old_base
                    raise
                self._active_ezshare_base = base
                mode = "közvetlen IP/gateway" if base != EZSHARE_HOST_BASE else "ezshare.card"
                self.log(
                    f'ezShare A: könyvtár elérhető ({attempt}. próbálkozás, {len(entries)} gyökérelem, {mode}: {base}).'
                )
                return
            except Exception as exc:
                last = exc
                self.log(f'ezShare végpont még nem kész: {base} – {exc}', "WARN")

        time.sleep(2)

    raise RuntimeError(
        'Az ez Share Wi-Fihez kapcsolódtunk, de az A: könyvtár '
        f'{timeout} másodpercen belül egyik közvetlen vagy név szerinti végponton sem lett olvasható. '
        f'Utolsó hiba: {last}'
    )


def _connection_failure(error: Exception | str) -> bool:
    text = str(error).casefold()
    return any(
        token in text
        for token in (
            "wi-fi",
            "wifi",
            "ez share",
            "associat",
            "társítás",
            "getaddrinfo",
            "a: könyvtár",
            "webfelület",
        )
    )


def _persistent_sync_job(self: SleepSyncService, jid: str, trigger: str = "manual") -> dict[str, Any]:
    """Retry connection failures for a useful recovery window, not only 3/5 times."""
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
        configured = max(1, int(self._settings.get("auto_retry_count", AUTO_MIN_SYNC_ATTEMPTS) or AUTO_MIN_SYNC_ATTEMPTS))
        minimum = MANUAL_MIN_SYNC_ATTEMPTS if trigger == "manual" else AUTO_MIN_SYNC_ATTEMPTS
        max_attempts = min(MAX_SYNC_ATTEMPTS, max(configured, minimum))
        recovery_window = MANUAL_RECOVERY_WINDOW_SECONDS if trigger == "manual" else AUTO_RECOVERY_WINDOW_SECONDS
        recovery_deadline = time.monotonic() + recovery_window
        normal_auto_wait = int(self._settings.get("auto_retry_wait_minutes", 5) or 5) * 60
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                result = self._run_with_wifi(jid, lambda: self._sync_connected(jid))
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                self.log(f"SleepSync helyreállítási ciklus {attempt}/{max_attempts} sikertelen: {exc}", "ERROR")
                if attempt >= max_attempts or time.monotonic() >= recovery_deadline:
                    break

                connection_problem = _connection_failure(exc)
                if connection_problem:
                    # Association failures benefit from another WLAN recovery far
                    # sooner than the old fixed five-minute wait.  Internet has
                    # already been restored by _run_with_wifi before this pause.
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
                    f"SleepSync újrapróbálás {attempt + 1}/{max_attempts} {wait_seconds} mp múlva; "
                    f"helyreállítási ablakból még ~{remaining // 60} perc maradt."
                )
                time.sleep(wait_seconds)

        if last_error is not None:
            raise last_error
        if not result or int(result.get("checked_files", 0)) <= 0:
            raise RuntimeError("Érvénytelen SleepSync eredmény: 0 ellenőrzött fájl. Sikeres állapot tiltva.")
        if int(result.get("errors", 0)) > 0:
            raise RuntimeError(f"A szinkron {result['errors']} végleges fájlhibával zárult. Sikeres állapot tiltva.")

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


def install_sleepsync_wifi_v5215() -> None:
    """Install the v5.2.15 Windows/ez Share resilience layer exactly once."""
    if getattr(SleepSyncService, "_wifi_v5215_installed", False):
        return

    original_load_settings = SleepSyncService._load_settings
    original_save_settings = SleepSyncService.save_settings

    def load_settings(self: SleepSyncService) -> dict[str, Any]:
        cfg = original_load_settings(self)
        try:
            current = int(cfg.get("auto_retry_count", 5) or 5)
        except Exception:
            current = 5
        # Migrate the historical default 5 to the new useful floor.  A later UI
        # can still expose a larger value; the runtime also enforces its minimum.
        if current < AUTO_MIN_SYNC_ATTEMPTS:
            cfg["auto_retry_count"] = AUTO_MIN_SYNC_ATTEMPTS
            legacy._json_write_atomic(self.settings_file, cfg)
        return cfg

    def save_settings(self: SleepSyncService, data: dict[str, Any]) -> dict[str, Any]:
        result = original_save_settings(self, data)
        try:
            current = int(self._settings.get("auto_retry_count", 5) or 5)
        except Exception:
            current = 5
        if current < AUTO_MIN_SYNC_ATTEMPTS:
            with self._settings_lock:
                self._settings["auto_retry_count"] = AUTO_MIN_SYNC_ATTEMPTS
                legacy._json_write_atomic(self.settings_file, self._settings)
            result = self.settings()
        return result

    SleepSyncService._run_netsh = staticmethod(_run_netsh_native)
    SleepSyncService._wlan_interface_snapshot = _wlan_interface_snapshot
    SleepSyncService._connect_wifi = _resilient_connect_wifi
    SleepSyncService._wait_http_ready = _wait_http_ready_resilient
    SleepSyncService._sync_job = _persistent_sync_job
    SleepSyncService._load_settings = load_settings
    SleepSyncService.save_settings = save_settings
    SleepSyncService._wifi_v5215_installed = True


__all__ = [
    "AUTO_MIN_SYNC_ATTEMPTS",
    "EZSHARE_DIRECT_BASE",
    "MANUAL_MIN_SYNC_ATTEMPTS",
    "install_sleepsync_wifi_v5215",
]
