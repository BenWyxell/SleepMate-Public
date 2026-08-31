from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from contextlib import contextmanager
from datetime import datetime, timedelta
from html import unescape
from pathlib import Path
from typing import Any


# The integrated engine intentionally follows the proven standalone SleepSync 1.1.5
# Wi-Fi, ez Share scan, stability, retry and incremental-sync behavior. SleepMate
# only supplies persistence, jobs, API/UI and the final CPAP import.
EZSHARE_BASE = "http://ezshare.card"
EZSHARE_WIFI_PROFILE = "ez Share"
TIMEOUT = 25
FILE_RETRY_COUNT = 3
WIFI_SWITCH_WAIT_SECONDS = 3
WIFI_CONNECT_TIMEOUT_SECONDS = 35
DAY_ORDER = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
EXCLUDED_ROOT_FILES = {"ezshare.cfg"}
EXCLUDED_DIR_NAMES = {"System Volume Information"}
ALWAYS_REFRESH_FILES = {
    "STR.EDF",
    "JOURNAL.JNL",
    "IDENTIFICATION.JSON",
    "IDENTIFICATION.CRC",
    "SETTINGS/CURRENTSETTINGS.JSON",
    "SETTINGS/CURRENTSETTINGS.CRC",
}
# STR.EDF is the mandatory ResMed sentinel. A run that cannot see it is not a
# valid SD scan and must never be reported as "Minden naprakész".
MANDATORY_SENTINEL = "STR.EDF"


def _safe_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip()


def _normalize_times(values: Any) -> list[str]:
    if not isinstance(values, list):
        values = ["09:00"]
    result: list[str] = []
    for value in values:
        try:
            result.append(datetime.strptime(str(value).strip(), "%H:%M").strftime("%H:%M"))
        except Exception:
            pass
    return sorted(set(result)) or ["09:00"]


def _json_read(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _json_write_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


class SleepSyncService:
    def __init__(self, app_module):
        self.app = app_module
        self.handler = app_module.Handler
        self.state_base = Path(app_module.STATE_BASE)
        self.private_dir = self.state_base / "private" / "sleepsync"
        self.settings_file = self.private_dir / "settings.json"
        self.sync_state_file = self.private_dir / "sync_state.json"
        self.history_file = self.private_dir / "history.json"
        self.log_file = self.private_dir / "technical.log"
        self.private_dir.mkdir(parents=True, exist_ok=True)

        self._settings_lock = threading.RLock()
        self._status_lock = threading.RLock()
        self._operation_lock = threading.Lock()
        self._scheduler_stop = threading.Event()
        self._scheduler_wakeup = threading.Event()
        self._card_visible_latched = False
        self._settings = self._load_settings()
        self._sync_state = self._load_sync_state()
        self._status: dict[str, Any] = {
            "running": False,
            "operation": None,
            "phase": "Készen áll.",
            "progress": 0,
            "total_files": 0,
            "work_files": 0,
            "processed_files": 0,
            "downloaded": 0,
            "unchanged": 0,
            "errors": 0,
            "current_file": "—",
            "last_error": None,
            "last_run": None,
            "next_run": None,
            "connection": "készenlét",
            "current_wifi": None,
            "sd_visible": False,
        }
        self.log("SleepSync integrált motor inicializálva – standalone 1.1.5 működésre építve.")
        threading.Thread(target=self._network_monitor_loop, daemon=True, name="SleepMate-SleepSync-NetworkMonitor").start()
        threading.Thread(target=self._scheduler_loop, daemon=True, name="SleepMate-SleepSync-Scheduler").start()

    # ------------------------------------------------------------------
    # Persistence / status
    # ------------------------------------------------------------------
    def _default_settings(self) -> dict[str, Any]:
        return {
            "backup_root": str(Path.home() / "Documents" / "SleepSync_Backups"),
            "auto_sync_enabled": False,
            "auto_sync_mode": "card_available",
            "schedule_days": list(DAY_ORDER),
            "schedule_times": ["09:00"],
            "card_scan_interval_seconds": 30,
            "auto_retry_count": 5,
            "auto_retry_wait_minutes": 5,
            "ezshare_ready_timeout_seconds": 25,
            "stability_wait_seconds": 4,
            "buffer_days": 2,
            "internet_wifi_fallbacks": [],
        }

    def _load_settings(self) -> dict[str, Any]:
        data = self._default_settings()
        loaded = _json_read(self.settings_file, {})
        if isinstance(loaded, dict):
            data.update(loaded)
        if data.get("auto_sync_mode") not in {"card_available", "scheduled"}:
            data["auto_sync_mode"] = "card_available"
        days = data.get("schedule_days") if isinstance(data.get("schedule_days"), list) else list(DAY_ORDER)
        data["schedule_days"] = [d for d in DAY_ORDER if d in days] or list(DAY_ORDER)
        data["schedule_times"] = _normalize_times(data.get("schedule_times"))
        for key, lo, hi, default in (
            ("card_scan_interval_seconds", 10, 300, 30),
            ("auto_retry_count", 1, 10, 5),
            ("auto_retry_wait_minutes", 1, 60, 5),
            ("ezshare_ready_timeout_seconds", 5, 120, 25),
            ("stability_wait_seconds", 2, 30, 4),
            ("buffer_days", 0, 30, 2),
        ):
            try:
                data[key] = max(lo, min(hi, int(data.get(key, default))))
            except Exception:
                data[key] = default
        fallbacks = data.get("internet_wifi_fallbacks") if isinstance(data.get("internet_wifi_fallbacks"), list) else []
        data["internet_wifi_fallbacks"] = [
            str(x).strip() for x in fallbacks
            if str(x).strip() and str(x).strip().lower() != EZSHARE_WIFI_PROFILE.lower()
        ]
        _json_write_atomic(self.settings_file, data)
        return data

    def _load_sync_state(self) -> dict[str, Any]:
        data = _json_read(self.sync_state_file, {"files": {}})
        if not isinstance(data, dict):
            data = {"files": {}}
        if not isinstance(data.get("files"), dict):
            data["files"] = {}
        return data

    def reload_from_disk(self) -> None:
        with self._settings_lock:
            self._settings = self._load_settings()
            self._sync_state = self._load_sync_state()
        self._scheduler_wakeup.set()
        self.log("SleepSync állapot újratöltve a teljes rendszer-visszaállítás után.")

    @contextmanager
    def exclusive(self):
        with self._operation_lock:
            yield

    def log(self, message: str, level: str = "INFO") -> None:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            self.private_dir.mkdir(parents=True, exist_ok=True)
            with self.log_file.open("a", encoding="utf-8") as fh:
                fh.write(f"[{stamp}] [{level}] {message}\n")
        except Exception:
            pass
        try:
            self.handler.persistent_log.append("HIBA" if level == "ERROR" else level, "sleepsync", message)
        except Exception:
            pass

    def _add_history(self, kind: str, success: bool, result: dict | None = None, error: Exception | str | None = None, trigger: str = "manual") -> None:
        result = result or {}
        row = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "kind": kind,
            "success": bool(success),
            "trigger": trigger,
            "checked": int(result.get("checked_files", result.get("total_files", 0)) or 0),
            "downloaded": int(result.get("downloaded", result.get("successful", 0)) or 0),
            "unchanged": int(result.get("unchanged", result.get("skipped", 0)) or 0),
            "errors": int(result.get("errors", result.get("failed", 0)) or 0),
            "error": str(error) if error else None,
            "zip_path": str(result.get("zip_path") or ""),
        }
        rows = _json_read(self.history_file, [])
        if not isinstance(rows, list):
            rows = []
        rows.insert(0, row)
        _json_write_atomic(self.history_file, rows[:250])

    def history(self) -> list[dict[str, Any]]:
        rows = _json_read(self.history_file, [])
        return rows if isinstance(rows, list) else []

    def clear_history(self) -> None:
        _json_write_atomic(self.history_file, [])

    def technical_log_tail(self, max_chars: int = 120000) -> str:
        try:
            return self.log_file.read_text(encoding="utf-8", errors="replace")[-max(2000, int(max_chars)):]
        except Exception:
            return ""

    def settings(self) -> dict[str, Any]:
        with self._settings_lock:
            cfg = dict(self._settings)
        app_cfg = self.app.load_config()
        cfg["therapy_data_dir"] = str(app_cfg.get("data_dir") or "")
        cfg["managed_data_dir"] = str(self.handler.dataset.root)
        return cfg

    def save_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValueError("Érvénytelen SleepSync beállításcsomag.")
        with self._settings_lock:
            cfg = dict(self._settings)
            if "auto_sync_enabled" in data:
                cfg["auto_sync_enabled"] = bool(data.get("auto_sync_enabled"))
            if "auto_sync_mode" in data:
                mode = str(data.get("auto_sync_mode") or "card_available")
                if mode not in {"card_available", "scheduled"}:
                    raise ValueError("Ismeretlen SleepSync automatikus mód.")
                cfg["auto_sync_mode"] = mode
            if "schedule_days" in data:
                raw = data.get("schedule_days")
                if not isinstance(raw, list):
                    raise ValueError("A napok listája érvénytelen.")
                cfg["schedule_days"] = [d for d in DAY_ORDER if d in raw] or list(DAY_ORDER)
            if "schedule_times" in data:
                cfg["schedule_times"] = _normalize_times(data.get("schedule_times"))
            for key, lo, hi in (
                ("card_scan_interval_seconds", 10, 300),
                ("auto_retry_count", 1, 10),
                ("auto_retry_wait_minutes", 1, 60),
                ("ezshare_ready_timeout_seconds", 5, 120),
                ("stability_wait_seconds", 2, 30),
                ("buffer_days", 0, 30),
            ):
                if key in data:
                    cfg[key] = max(lo, min(hi, int(data.get(key))))
            if "backup_root" in data:
                raw = str(data.get("backup_root") or "").strip()
                if not raw:
                    raise ValueError("Az SD backup mappa nem lehet üres.")
                path = Path(raw).expanduser().resolve()
                path.mkdir(parents=True, exist_ok=True)
                cfg["backup_root"] = str(path)
            if "internet_wifi_fallbacks" in data:
                raw = data.get("internet_wifi_fallbacks")
                if not isinstance(raw, list):
                    raise ValueError("A Wi-Fi visszaállítási lista érvénytelen.")
                cfg["internet_wifi_fallbacks"] = [
                    str(x).strip() for x in raw
                    if str(x).strip() and str(x).strip().lower() != EZSHARE_WIFI_PROFILE.lower()
                ]
            self._settings = cfg
            _json_write_atomic(self.settings_file, cfg)

        if "therapy_data_dir" in data:
            raw = str(data.get("therapy_data_dir") or "").strip()
            if not raw:
                raise ValueError("A terápiás adatmappa nem lehet üres.")
            root = Path(raw).expanduser().resolve()
            root.mkdir(parents=True, exist_ok=True)
            (root / "DATALOG").mkdir(parents=True, exist_ok=True)
            self.app.save_config({"data_dir": str(root)})

        self._scheduler_wakeup.set()
        self.log("SleepSync beállítások mentve.")
        return self.settings()

    def _update_status(self, **values: Any) -> None:
        with self._status_lock:
            self._status.update(values)

    def status(self) -> dict[str, Any]:
        # Deliberately NO netsh / network scan here. The browser polls this endpoint;
        # blocking network work in status caused the old UI to buffer and spawn calls.
        with self._status_lock:
            out = dict(self._status)
        out["settings"] = self.settings()
        out["history"] = self.history()[:5]
        next_run = self._next_scheduled_time()
        out["next_run"] = next_run.isoformat(timespec="seconds") if next_run else None
        return out

    # ------------------------------------------------------------------
    # Proven standalone Wi-Fi behavior
    # ------------------------------------------------------------------
    @staticmethod
    def _run_netsh(args: list[str]) -> tuple[int, str]:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run(
            ["netsh"] + args, capture_output=True, text=True,
            encoding="utf-8", errors="replace", creationflags=creationflags,
        )
        return result.returncode, result.stdout + result.stderr

    def get_current_wifi_ssid(self) -> str | None:
        if os.name != "nt":
            return None
        code, output = self._run_netsh(["wlan", "show", "interfaces"])
        if code != 0:
            return None
        for line in output.splitlines():
            stripped = line.strip()
            if stripped.upper().startswith("BSSID"):
                continue
            match = re.match(r"^SSID\s*:\s*(.+)$", stripped, re.IGNORECASE)
            if match and match.group(1).strip():
                return match.group(1).strip()
        return None

    def saved_wifi_profiles(self) -> list[str]:
        if os.name != "nt":
            return []
        code, output = self._run_netsh(["wlan", "show", "profiles"])
        if code != 0:
            return []
        profiles: list[str] = []
        for line in output.splitlines():
            if ":" not in line:
                continue
            value = line.split(":", 1)[1].strip()
            if value and not any(x in value.lower() for x in ["group policy", "felhasználói profil", "user profiles"]):
                if value not in profiles:
                    profiles.append(value)
        return profiles

    def visible_wifi_ssids(self) -> list[str]:
        if os.name != "nt":
            return []
        code, output = self._run_netsh(["wlan", "show", "networks", "mode=bssid"])
        if code != 0:
            return []
        result: list[str] = []
        for line in output.splitlines():
            match = re.match(r"^SSID\s+\d+\s*:\s*(.*)$", line.strip(), re.IGNORECASE)
            if match:
                ssid = match.group(1).strip()
                if ssid and ssid not in result:
                    result.append(ssid)
        return result

    def wifi_network_visible(self, ssid: str) -> bool:
        return any(x.lower() == ssid.lower() for x in self.visible_wifi_ssids())

    def _wait_network_visible(self, ssid: str, timeout_seconds: int = 45) -> bool:
        deadline = time.time() + timeout_seconds
        self.log(f'Keresés a Wi-Fi hálózatok között: "{ssid}"')
        while time.time() < deadline:
            if self.wifi_network_visible(ssid):
                self.log(f'Az "{ssid}" Wi-Fi elérhető.')
                return True
            time.sleep(1)
        return False

    def _wifi_interface_name(self) -> str | None:
        code, output = self._run_netsh(["wlan", "show", "interfaces"])
        if code != 0:
            return None
        for line in output.splitlines():
            match = re.match(r"^(?:Name|Név)\s*:\s*(.+)$", line.strip(), re.IGNORECASE)
            if match and match.group(1).strip():
                return match.group(1).strip()
        return None

    def _disconnect_wifi(self) -> None:
        args = ["wlan", "disconnect"]
        interface = self._wifi_interface_name()
        if interface:
            args.append(f"interface={interface}")
        code, output = self._run_netsh(args)
        if code == 0:
            self.log("Jelenlegi Wi-Fi kapcsolat bontása: OK" + (f" [{interface}]" if interface else ""))
        else:
            self.log(f"FIGYELEM: Wi-Fi bontási hiba: {output.strip()}", "WARN")

    def _wait_for_wifi(self, target_ssid: str, timeout_seconds: int) -> bool:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            current = self.get_current_wifi_ssid()
            if current and current.lower() == target_ssid.lower():
                return True
            time.sleep(1)
        return False

    def _profile_mode(self, profile: str) -> str | None:
        code, output = self._run_netsh(["wlan", "show", "profile", f"name={profile}"])
        if code != 0:
            return None
        text = output.lower()
        if "connect manually" in text or "manuálisan" in text:
            return "manual"
        if "connect automatically" in text or "automatikusan" in text or "kapcsolódási mód" in text:
            return "auto"
        return None

    def _set_profile_mode(self, profile: str, mode: str) -> None:
        code, output = self._run_netsh(["wlan", "set", "profileparameter", f"name={profile}", f"connectionmode={mode}"])
        cleaned = output.strip().replace("\r", " ").replace("\n", " ")
        self.log(f'Wi-Fi profil mód: "{profile}" -> {mode}; code={code}' + (f'; üzenet="{cleaned}"' if cleaned else ""))

    def _suspend_other_autoconnect(self, target: str) -> dict[str, str | None]:
        states: dict[str, str | None] = {}
        for profile in self.saved_wifi_profiles():
            if profile.lower() == target.lower():
                continue
            states[profile] = self._profile_mode(profile)
            try:
                self._set_profile_mode(profile, "manual")
            except Exception as exc:
                self.log(f'FIGYELEM: "{profile}" automatikus újracsatlakozása nem tiltható: {exc}', "WARN")
        self.log("Wi-Fi őrzött mód aktív: más mentett hálózatok automatikus visszacsatlakozása ideiglenesen tiltva.")
        return states

    def _restore_wifi_modes(self, states: dict[str, str | None] | None) -> None:
        for profile, mode in (states or {}).items():
            if mode in {"auto", "manual"}:
                try:
                    self._set_profile_mode(profile, mode)
                except Exception as exc:
                    self.log(f'FIGYELEM: "{profile}" Wi-Fi profil eredeti módja nem állítható vissza: {exc}', "WARN")
        if states:
            self.log("Wi-Fi profilok automatikus csatlakozási módjai visszaállítva.")

    def _connect_wifi(self, profile: str) -> dict[str, str | None]:
        if os.name != "nt":
            raise RuntimeError("A SleepSync Wi-Fi váltás Windows alatt támogatott.")
        saved = self.saved_wifi_profiles()
        if saved and not any(p.lower() == profile.lower() for p in saved):
            raise RuntimeError(f'A Windowsban nincs elmentve "{profile}" nevű Wi-Fi profil.')
        if not self._wait_network_visible(profile, 45):
            raise RuntimeError(f'Az "{profile}" Wi-Fi profil el van mentve, de a hálózat 45 másodpercig nem jelent meg.')

        states = self._suspend_other_autoconnect(profile)
        try:
            self._disconnect_wifi()
            time.sleep(1.2)
            last_output = ""
            for attempt in range(1, 4):
                self.log(f'Csatlakozási kísérlet {attempt}/3: "{profile}"')
                interface = self._wifi_interface_name()
                args = ["wlan", "connect", f"name={profile}", f"ssid={profile}"]
                if interface:
                    args.append(f"interface={interface}")
                code, output = self._run_netsh(args)
                last_output = output
                cleaned = output.strip().replace("\r", " ").replace("\n", " ")
                self.log(f'netsh connect eredmény: code={code}' + (f', interface="{interface}"' if interface else "") + (f', üzenet="{cleaned}"' if cleaned else ""))
                if self._wait_for_wifi(profile, 12):
                    self.log(f'Wi-Fi csatlakozás sikeres: "{self.get_current_wifi_ssid()}"')
                    return states
                if attempt < 3:
                    self.log(f'Nem váltott át. Jelenlegi SSID: "{self.get_current_wifi_ssid() or "nincs kapcsolat"}". Újrapróbálkozás...')
                    self._disconnect_wifi()
                    time.sleep(1.5)
            raise RuntimeError(f'Az "{profile}" hálózat látható, de 3 csatlakozási kísérlet után sem lett aktív. Utolsó netsh válasz: {last_output.strip()}')
        except Exception:
            self._restore_wifi_modes(states)
            raise

    def _connect_wifi_fast(self, profile: str, attempts: int = 2) -> bool:
        saved = self.saved_wifi_profiles()
        if not any(p.lower() == profile.lower() for p in saved):
            return False
        current = self.get_current_wifi_ssid()
        if current and current.lower() == profile.lower():
            return True
        visible = {x.lower() for x in self.visible_wifi_ssids()}
        if profile.lower() not in visible:
            self.log(f'Internet Wi-Fi kihagyva, jelenleg nem látható: "{profile}"', "WARN")
            return False
        for attempt in range(1, attempts + 1):
            try:
                self._disconnect_wifi()
            except Exception:
                pass
            time.sleep(0.5)
            code, output = self._run_netsh(["wlan", "connect", f"name={profile}"])
            cleaned = output.strip().replace("\r", " ").replace("\n", " ")
            self.log(f'Internet Wi-Fi csatlakozás {attempt}/{attempts}: "{profile}"; code={code}' + (f'; üzenet="{cleaned}"' if cleaned else ""))
            if self._wait_for_wifi(profile, 8):
                return True
        return False

    def _restore_previous_wifi(self, previous_ssid: str | None) -> str | None:
        configured: list[str] = []
        for value in [previous_ssid, *self._settings.get("internet_wifi_fallbacks", [])]:
            name = str(value or "").strip()
            if not name or name.lower() == EZSHARE_WIFI_PROFILE.lower():
                continue
            if name.lower() not in {x.lower() for x in configured}:
                configured.append(name)
        visible = {x.lower() for x in self.visible_wifi_ssids()}
        candidates = [x for x in configured if x.lower() in visible]
        if not candidates:
            self.log("Nincs jelenleg látható beállított internetes Wi-Fi, amire vissza lehetne kapcsolni.", "WARN")
            return None
        self.log("Internet Wi-Fi visszaállítási sorrend: " + " -> ".join(f'"{x}"' for x in candidates))
        for name in candidates:
            try:
                if self._connect_wifi_fast(name):
                    self.log(f'Wi-Fi/internet kapcsolat visszaállítva: "{name}"')
                    return name
            except Exception as exc:
                self.log(f'Internet Wi-Fi sikertelen: "{name}": {exc}', "WARN")
        self.log("FIGYELEM: egyik kiválasztott internetes Wi-Fihez sem sikerült csatlakozni.", "ERROR")
        return None

    def _browser_pids(self) -> set[int]:
        if os.name != "nt":
            return set()
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        ps = "$names=@('msedge','chrome','iexplore'); Get-Process -ErrorAction SilentlyContinue | Where-Object { $names -contains $_.ProcessName.ToLower() } | ForEach-Object { $_.Id }"
        result = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=creationflags)
        out: set[int] = set()
        for line in result.stdout.splitlines():
            try:
                out.add(int(line.strip()))
            except ValueError:
                pass
        return out

    def _close_new_captive_windows(self, before: set[int]) -> None:
        if os.name != "nt":
            return
        after = self._browser_pids()
        for pid in after - before:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def wifi_options(self) -> dict[str, Any]:
        saved = self.saved_wifi_profiles()
        visible = self.visible_wifi_ssids()
        visible_map = {x.lower(): x for x in visible}
        choices = [visible_map[x.lower()] for x in saved if x.lower() in visible_map and x.lower() != EZSHARE_WIFI_PROFILE.lower()]
        current = self.get_current_wifi_ssid()
        ez_visible = EZSHARE_WIFI_PROFILE.lower() in visible_map
        self._update_status(current_wifi=current, sd_visible=ez_visible)
        return {"current": current, "ezshare_visible": ez_visible, "saved": saved, "visible": visible, "choices": choices, "selected": list(self._settings.get("internet_wifi_fallbacks", []))}

    def _network_monitor_loop(self) -> None:
        while not self._scheduler_stop.is_set():
            try:
                if not self._status.get("running"):
                    visible = self.visible_wifi_ssids()
                    self._update_status(
                        current_wifi=self.get_current_wifi_ssid(),
                        sd_visible=any(x.lower() == EZSHARE_WIFI_PROFILE.lower() for x in visible),
                    )
            except Exception:
                pass
            self._scheduler_stop.wait(5)

    # ------------------------------------------------------------------
    # Proven ez Share directory scan / incremental download behavior
    # ------------------------------------------------------------------
    def _get_url(self, url: str) -> str:
        request = urllib.request.Request(url, headers={"User-Agent": "SleepSync/1.1.5"})
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            raw = response.read()
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin-1", errors="replace")

    @staticmethod
    def _parse_possible_datetime(text: str) -> datetime | None:
        text = re.sub(r"\s+", " ", text)
        for pattern in (
            r"(\d{4})-\s*(\d{1,2})-\s*(\d{1,2})\s+(\d{1,2}):\s*(\d{1,2}):\s*(\d{1,2})",
            r"(\d{4})-\s*(\d{1,2})-\s*(\d{1,2})\s+(\d{1,2}):\s*(\d{1,2})",
        ):
            match = re.search(pattern, text)
            if not match:
                continue
            values = [int(x) for x in match.groups()]
            if len(values) == 5:
                values.append(0)
            try:
                return datetime(*values)
            except ValueError:
                return None
        return None

    @staticmethod
    def _parse_size_token(text: str) -> tuple[str | None, int | None]:
        cleaned = re.sub(r"\s+", " ", text.upper())
        match = re.search(r"(?<!\d)(\d+(?:\.\d+)?)\s*(B|KB|MB|GB)(?![A-Z])", cleaned)
        if not match:
            return None, None
        value = float(match.group(1))
        unit = match.group(2)
        mult = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}[unit]
        return f"{match.group(1)}{unit}", int(value * mult)

    def _parse_directory(self, sd_directory: str) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode({"dir": sd_directory})
        html = self._get_url(f"{EZSHARE_BASE}/dir?{query}")
        entries: list[dict[str, Any]] = []
        pattern = re.compile(r'(?P<prefix>.{0,240}?)<a\s+href=["\'](?P<href>[^"\']+)["\'][^>]*>(?P<name>.*?)</a>', re.IGNORECASE | re.DOTALL)
        for match in pattern.finditer(html):
            prefix = unescape(re.sub(r"<[^>]+>", " ", match.group("prefix")))
            href = unescape(match.group("href")).strip()
            name = unescape(re.sub(r"<[^>]+>", "", match.group("name"))).strip()
            if not name or name in {".", ".."}:
                continue
            if name.lower() in {"back to photo", "photo gallery", "video gallery", "change configuration", "disk_list", "cloud lab", "mobile", "classic"}:
                continue
            is_dir = "<DIR>" in prefix.upper() or "/dir?" in href.lower() or href.lower().startswith("dir?")
            size_token, size_bytes = self._parse_size_token(prefix)
            entries.append({"name": name, "is_dir": is_dir, "url": urllib.parse.urljoin(EZSHARE_BASE + "/", href), "modified": self._parse_possible_datetime(prefix), "size_token": size_token, "size_bytes": size_bytes})
        unique: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for entry in entries:
            key = (entry["name"], entry["url"])
            if key not in seen:
                seen.add(key)
                unique.append(entry)
        return unique

    def _parse_directory_with_retries(self, sd_directory: str, attempts: int = 3) -> list[dict[str, Any]]:
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                entries = self._parse_directory(sd_directory)
                if attempt > 1:
                    self.log(f"Könyvtár olvasása sikerült újrapróbálással ({attempt}/{attempts}): {sd_directory}")
                return entries
            except Exception as exc:
                last_error = exc
                self.log(f"Könyvtár-olvasási hiba {attempt}/{attempts}: {sd_directory}: {exc}", "WARN")
        raise RuntimeError(f"Az SD-könyvtár {attempts} próbálkozás után sem olvasható: {sd_directory}. Utolsó hiba: {last_error}")

    @staticmethod
    def _child_sd_directory(entry: dict[str, Any], fallback: str) -> str:
        try:
            parsed = urllib.parse.urlparse(str(entry.get("url") or ""))
            query = urllib.parse.parse_qs(parsed.query)
            values = query.get("dir") or query.get("DIR")
            if values and values[0]:
                return urllib.parse.unquote(values[0])
        except Exception:
            pass
        return fallback

    def _scan_sd(self, sd_directory: str = "A:\\", relative_path: Path = Path()) -> tuple[list[dict[str, Any]], list[Path]]:
        self.log(f"Könyvtár olvasása: {sd_directory}")
        entries = self._parse_directory_with_retries(sd_directory)
        files: list[dict[str, Any]] = []
        directories: list[Path] = []
        for entry in entries:
            name = entry["name"].strip()
            rel = relative_path / _safe_filename(name)
            if entry["is_dir"] and name in EXCLUDED_DIR_NAMES:
                self.log(f"Kihagyva: {rel}")
                continue
            if not entry["is_dir"] and rel.parent == Path(".") and name.lower() in {x.lower() for x in EXCLUDED_ROOT_FILES}:
                self.log(f"Kihagyva: {rel}")
                continue
            if entry["is_dir"]:
                directories.append(rel)
                child = self._child_sd_directory(entry, sd_directory + "\\" + name)
                self.log(f"SD mappa felismerve: {rel} -> {child}")
                child_files, child_dirs = self._scan_sd(child, rel)
                files.extend(child_files)
                directories.extend(child_dirs)
            else:
                files.append({**entry, "relative_path": rel, "sd_directory": sd_directory})
        return files, directories

    def _validate_scan(self, files: list[dict[str, Any]], directories: list[Path]) -> list[str]:
        # This is a hard safety boundary. A network/HTML/parser failure that yields
        # zero files is an ERROR, never a successful 0/0/0 sync.
        if not files:
            raise RuntimeError("Az ez Share válaszolt, de 0 fájlt sikerült felismerni. A szinkron érvénytelen; sem import, sem 'minden naprakész' állapot nem engedélyezett.")
        paths = {Path(info["relative_path"]).as_posix().upper() for info in files}
        if MANDATORY_SENTINEL not in paths:
            raise RuntimeError(f"A kötelező ResMed fájl ({MANDATORY_SENTINEL}) nem található a feltérképezett SD-n. A scan nem tekinthető teljesnek.")
        mandatory_seen = sorted(paths & ALWAYS_REFRESH_FILES)
        if not mandatory_seen:
            raise RuntimeError("Egyetlen kötelezően frissítendő ResMed fájlt sem sikerült felismerni.")
        self.log(f"SD scan érvényes: {len(files)} fájl, {len(directories)} mappa; kötelező frissítések: {', '.join(mandatory_seen)}")
        return mandatory_seen

    @staticmethod
    def _metadata_signature(info: dict[str, Any]) -> dict[str, Any]:
        modified = info.get("modified")
        return {"modified": modified.isoformat() if isinstance(modified, datetime) else None, "size_token": info.get("size_token")}

    @staticmethod
    def _state_key(rel: Path) -> str:
        return rel.as_posix()

    @staticmethod
    def _is_always_refresh(rel: Path) -> bool:
        return rel.as_posix().lstrip("./").upper() in ALWAYS_REFRESH_FILES

    def _is_recent(self, modified: datetime | None) -> bool:
        if modified is None:
            return True
        return modified >= datetime.now() - timedelta(days=int(self._settings.get("buffer_days", 2)))

    def _should_download(self, info: dict[str, Any], local_root: Path) -> tuple[bool, str]:
        rel = info["relative_path"]
        if self._is_always_refresh(rel):
            return True, f"{rel} – kötelező frissítés minden szinkronnál"
        local = local_root / rel
        previous = self._sync_state.get("files", {}).get(self._state_key(rel))
        remote = self._metadata_signature(info)
        if not local.exists():
            return True, "új / hiányzó"
        if previous is None:
            if int(self._settings.get("buffer_days", 2)) > 0 and self._is_recent(info.get("modified")):
                return True, "állapot nélküli friss fájl"
            return False, "meglévő fájl – állapot inicializálás"
        if previous.get("modified") != remote.get("modified"):
            return True, "módosítási idő változott"
        if previous.get("size_token") != remote.get("size_token"):
            return True, "méret változott"
        if int(self._settings.get("buffer_days", 2)) == 0:
            return False, "változatlan – 0 napos buffer"
        if self._is_recent(info.get("modified")):
            return True, "friss fájl – biztonsági buffer"
        return False, "régi és változatlan"

    def _record_state(self, info: dict[str, Any]) -> None:
        self._sync_state.setdefault("files", {})[self._state_key(info["relative_path"])] = {**self._metadata_signature(info), "synced_at": datetime.now().isoformat(timespec="seconds")}

    def _remote_entry(self, info: dict[str, Any]) -> dict[str, Any] | None:
        for entry in self._parse_directory_with_retries(info["sd_directory"]):
            if entry["name"] == info["name"] and not entry["is_dir"]:
                return {**entry, "relative_path": info["relative_path"], "sd_directory": info["sd_directory"]}
        return None

    def _download_stable(self, info: dict[str, Any], destination: Path) -> dict[str, Any]:
        first = self._remote_entry(info)
        if first is None:
            raise RuntimeError("A fájl eltűnt az első ellenőrzéskor.")
        sig1 = self._metadata_signature(first)
        time.sleep(int(self._settings.get("stability_wait_seconds", 4)))
        second = self._remote_entry(info)
        if second is None:
            raise RuntimeError("A fájl eltűnt stabilitás-ellenőrzéskor.")
        if sig1 != self._metadata_signature(second):
            raise RuntimeError("A fájl még változik – későbbi próbában újraellenőrizzük.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        tmp = destination.with_suffix(destination.suffix + ".sleepsync.part")
        try:
            request = urllib.request.Request(second["url"], headers={"User-Agent": "SleepSync/1.1.5"})
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response, tmp.open("wb") as out:
                length = response.headers.get("Content-Length")
                shutil.copyfileobj(response, out)
            if length and length.isdigit() and tmp.stat().st_size != int(length):
                raise IOError(f"Félkész letöltés: {tmp.stat().st_size}/{length} byte")
            third = self._remote_entry(info)
            if third is None or self._metadata_signature(second) != self._metadata_signature(third):
                raise RuntimeError("A fájl letöltés közben megváltozott – eldobva.")
            os.replace(tmp, destination)
            return third
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass

    def _download_with_retries(self, info: dict[str, Any], destination: Path) -> dict[str, Any]:
        last: Exception | None = None
        for attempt in range(1, FILE_RETRY_COUNT + 1):
            try:
                if attempt > 1:
                    self.log(f"AUTO SYNC azonnali újrapróbálás {attempt}/{FILE_RETRY_COUNT}: {info['relative_path']}")
                return self._download_stable(info, destination)
            except Exception as exc:
                last = exc
                self.log(f"{info['relative_path']}: letöltési hiba {attempt}/{FILE_RETRY_COUNT}: {exc}", "WARN")
        raise RuntimeError(str(last or "Ismeretlen letöltési hiba."))

    def _wait_http_ready(self) -> None:
        timeout = int(self._settings.get("ezshare_ready_timeout_seconds", 25))
        deadline = time.time() + timeout
        attempt = 0
        last: Exception | None = None
        root = "A:\\"
        while time.time() < deadline:
            attempt += 1
            current = self.get_current_wifi_ssid()
            if not current or current.lower() != EZSHARE_WIFI_PROFILE.lower():
                last = RuntimeError(f'Az aktív Wi-Fi nem "{EZSHARE_WIFI_PROFILE}", hanem "{current or "nincs kapcsolat"}".')
            else:
                try:
                    self._get_url(f"{EZSHARE_BASE}/dir?" + urllib.parse.urlencode({"dir": root}))
                    self.log(f"ezShare HTTP/DNS ellenőrzés sikeres ({attempt}. próbálkozás).")
                    return
                except Exception as exc:
                    last = exc
                    self.log(f"ezShare még nem kész ({attempt}. próba): {exc}", "WARN")
            time.sleep(2)
        raise RuntimeError(f"Az ez Share Wi-Fihez kapcsolódtunk, de a kártya webfelülete {timeout} másodpercen belül nem lett elérhető. Utolsó hiba: {last}")

    # ------------------------------------------------------------------
    # Jobs
    # ------------------------------------------------------------------
    def _jobs(self):
        jobs = getattr(self.handler, "jobs", None)
        if jobs is None:
            raise RuntimeError("A SleepMate feladatkezelő még nem indult el.")
        return jobs

    def start_sync(self, trigger: str = "manual") -> str:
        if self._status.get("running") or self._operation_lock.locked():
            raise RuntimeError("Már fut SleepSync művelet.")
        jid = self._jobs().create("sleepsync_sync", "SleepSync szinkronizálás")
        self._jobs().start(jid, self._sync_job, trigger)
        if self._settings.get("auto_sync_enabled") and self._settings.get("auto_sync_mode") == "card_available" and self._status.get("sd_visible"):
            self._card_visible_latched = True
        return jid

    def start_sd_backup(self) -> str:
        if self._status.get("running") or self._operation_lock.locked():
            raise RuntimeError("Már fut SleepSync művelet.")
        jid = self._jobs().create("sleepsync_backup", "SleepSync teljes SD mentés")
        self._jobs().start(jid, self._backup_job)
        return jid

    def _progress(self, jid: str, progress: int, phase: str, message: str, **stats: Any) -> None:
        value = max(0, min(100, int(progress)))
        self._jobs().update(jid, progress=value, phase=phase, message=message)
        self._update_status(progress=value, phase=message, **stats)

    def _run_with_wifi(self, jid: str, body):
        previous = self.get_current_wifi_ssid()
        guard_states: dict[str, str | None] | None = None
        browser_pids = self._browser_pids()
        try:
            self._progress(jid, 3, "Kapcsolódás", "Kapcsolódás az ez Share Wi-Fihez…", connection="kapcsolódás", current_wifi=previous)
            if not previous or previous.lower() != EZSHARE_WIFI_PROFILE.lower():
                guard_states = self._connect_wifi(EZSHARE_WIFI_PROFILE)
            if not self._wait_for_wifi(EZSHARE_WIFI_PROFILE, WIFI_CONNECT_TIMEOUT_SECONDS):
                raise RuntimeError(f'Nem sikerült {WIFI_CONNECT_TIMEOUT_SECONDS} másodpercen belül csatlakozni az "{EZSHARE_WIFI_PROFILE}" hálózathoz.')
            self._update_status(current_wifi=EZSHARE_WIFI_PROFILE, sd_visible=True)
            self._progress(jid, 9, "SD ellenőrzése", "A kártya válaszára vár…", connection="ez Share")
            time.sleep(WIFI_SWITCH_WAIT_SECONDS)
            self._close_new_captive_windows(browser_pids)
            self._wait_http_ready()
            return body()
        finally:
            self._progress(jid, 96, "Kapcsolat visszaállítása", "Internetkapcsolat visszaállítása…")
            try:
                self._restore_wifi_modes(guard_states)
            finally:
                restored = self._restore_previous_wifi(previous)
                self._update_status(connection="készenlét", current_wifi=restored or self.get_current_wifi_ssid())

    def _sync_job(self, jid: str, trigger: str = "manual") -> dict[str, Any]:
        if not self._operation_lock.acquire(blocking=False):
            raise RuntimeError("Már fut SleepSync művelet.")
        self._update_status(running=True, operation="sync", progress=0, phase="Szinkronizálás előkészítése…", total_files=0, work_files=0, processed_files=0, downloaded=0, unchanged=0, errors=0, current_file="—", last_error=None)
        self.log(f"SleepSync szinkron indul – trigger={trigger}")
        result: dict[str, Any] | None = None
        try:
            max_attempts = min(3, int(self._settings.get("auto_retry_count", 5))) if trigger == "manual" else int(self._settings.get("auto_retry_count", 5))
            wait_seconds = 8 if trigger == "manual" else int(self._settings.get("auto_retry_wait_minutes", 5)) * 60
            last_error: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    result = self._run_with_wifi(jid, lambda: self._sync_connected(jid))
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc
                    self.log(f"SleepSync szinkron {attempt}/{max_attempts} sikertelen: {exc}", "ERROR")
                    if attempt < max_attempts:
                        self._update_status(phase=f"Újrapróbálás {attempt + 1}/{max_attempts}…", last_error=str(exc))
                        time.sleep(wait_seconds)
            if last_error is not None:
                raise last_error
            if not result or int(result.get("checked_files", 0)) <= 0:
                raise RuntimeError("Érvénytelen SleepSync eredmény: 0 ellenőrzött fájl. Sikeres állapot tiltva.")
            if int(result.get("errors", 0)) > 0:
                raise RuntimeError(f"A szinkron {result['errors']} végleges fájlhibával zárult. Sikeres állapot tiltva.")
            self._add_history("sync", True, result, trigger=trigger)
            self._update_status(running=False, operation=None, progress=100, phase="Szinkronizálás kész. Minden naprakész.", last_run=datetime.now().isoformat(timespec="seconds"), last_error=None, current_file="—")
            self.log(f"SleepSync kész: {result}")
            return result
        except Exception as exc:
            self._add_history("sync", False, result, error=exc, trigger=trigger)
            self._update_status(running=False, operation=None, phase="A szinkronizálás nem sikerült.", last_error=str(exc))
            raise
        finally:
            self._operation_lock.release()
            self._scheduler_wakeup.set()

    def _sync_connected(self, jid: str) -> dict[str, Any]:
        raw_root = str(self.app.load_config().get("data_dir") or "").strip()
        if not raw_root:
            raise RuntimeError("Nincs beállítva SleepMate terápiás adatmappa.")
        data_root = Path(raw_root).expanduser().resolve()
        data_root.mkdir(parents=True, exist_ok=True)
        (data_root / "DATALOG").mkdir(parents=True, exist_ok=True)

        self._progress(jid, 15, "Feltérképezés", "SD-kártya feltérképezése…")
        files, directories = self._scan_sd()
        mandatory_seen = set(self._validate_scan(files, directories))
        for rel_dir in directories:
            (data_root / rel_dir).mkdir(parents=True, exist_ok=True)

        selected: list[tuple[dict[str, Any], str]] = []
        unchanged = 0
        for info in files:
            need, reason = self._should_download(info, data_root)
            if need:
                selected.append((info, reason))
            else:
                self._record_state(info)
                unchanged += 1

        self._progress(jid, 28, "Változások keresése", "Feldolgozási lista kész.", total_files=len(files), work_files=len(selected), unchanged=unchanged)
        self.log(f"AUTO SYNC index: {len(files)} fájl; letöltendő/módosult: {len(selected)}; változatlan: {unchanged}")

        downloaded = 0
        mandatory_refreshed: set[str] = set()
        retry_queue: list[tuple[dict[str, Any], str, Exception]] = []
        total = max(1, len(selected))
        for index, (info, reason) in enumerate(selected, start=1):
            rel = info["relative_path"]
            self._progress(jid, 30 + int(index / total * 52), "Szinkronizálás", f"Szinkronizálás: {rel}", processed_files=index - 1, current_file=str(rel), downloaded=downloaded)
            try:
                final = self._download_with_retries(info, data_root / rel)
                self._record_state({**info, **final, "relative_path": rel, "sd_directory": info["sd_directory"]})
                downloaded += 1
                normalized = rel.as_posix().upper()
                if normalized in mandatory_seen:
                    mandatory_refreshed.add(normalized)
                self.log(f"AUTO SYNC [{index}/{len(selected)}] {rel}: stabil fájl mentve ({reason})")
            except Exception as exc:
                retry_queue.append((info, reason, exc))
                self.log(f"AUTO SYNC: {rel} {FILE_RETRY_COUNT} próbálkozás után sem sikerült; végső körben újrapróbáljuk.", "WARN")
            self._progress(jid, 30 + int(index / total * 52), "Szinkronizálás", f"Szinkronizálás: {rel}", processed_files=index, current_file=str(rel), downloaded=downloaded, errors=len(retry_queue))

        final_failed: list[dict[str, str]] = []
        if retry_queue:
            self.log(f"AUTO SYNC VÉGSŐ ÚJRAPRÓBÁLÁSI KÖR: {len(retry_queue)} fájl")
            for idx, (info, reason, previous_error) in enumerate(retry_queue, start=1):
                rel = info["relative_path"]
                self._progress(jid, 83 + int(idx / max(1, len(retry_queue)) * 4), "Végső újrapróbálás", f"Végső újrapróbálás: {rel}", current_file=str(rel), downloaded=downloaded)
                try:
                    final = self._download_with_retries(info, data_root / rel)
                    self._record_state({**info, **final, "relative_path": rel, "sd_directory": info["sd_directory"]})
                    downloaded += 1
                    normalized = rel.as_posix().upper()
                    if normalized in mandatory_seen:
                        mandatory_refreshed.add(normalized)
                    self.log(f"AUTO SYNC VÉGSŐ ÚJRAPRÓBÁLÁS SIKERES: {rel}")
                except Exception as exc:
                    final_failed.append({"file": str(rel), "error": str(exc), "reason": reason})
                    self.log(f"AUTO SYNC VÉGLEGES FÁJLHIBA: {rel}: {exc}", "ERROR")

        _json_write_atomic(self.sync_state_file, self._sync_state)
        if final_failed:
            self._update_status(errors=len(final_failed), current_file="—")
            raise RuntimeError(f"A SleepSync {len(final_failed)} fájlt a végső újrapróbálás után sem tudott biztonságosan frissíteni.")
        missing_mandatory = sorted(mandatory_seen - mandatory_refreshed)
        if missing_mandatory:
            raise RuntimeError("A kötelezően frissítendő ResMed fájlok közül nem mindegyik frissült: " + ", ".join(missing_mandatory))

        self._progress(jid, 89, "SleepMate import", "A SleepMate mérési adattár frissítése…", current_file="—", errors=0)
        before_days = self.handler.dataset.days()
        before_latest = before_days[-1] if before_days else None
        with self.handler._dataset_lock:
            # Never mirror-delete SleepMate data from a Wi-Fi acquisition folder.
            # A transient/incomplete remote scan must be incapable of deleting good EDFs.
            imported = self.app.import_resmed_tree(data_root, self.handler.dataset.root, authoritative=False)
            self.handler.dataset.refresh()
        self.handler._push_after_refresh(before_latest, imported, "SleepSync szinkron")
        self._progress(jid, 95, "Integritásellenőrzés", "SleepMate adatfrissítés kész.", total_files=len(files), work_files=len(selected), processed_files=len(selected), downloaded=downloaded, unchanged=unchanged, errors=0, current_file="—")
        return {"checked_files": len(files), "downloaded": downloaded, "unchanged": unchanged, "errors": 0, "failed_files": [], "mandatory_seen": sorted(mandatory_seen), "mandatory_refreshed": sorted(mandatory_refreshed), "import": imported, "days": len(self.handler.dataset.days()), "source": str(data_root)}

    def _backup_job(self, jid: str) -> dict[str, Any]:
        if not self._operation_lock.acquire(blocking=False):
            raise RuntimeError("Már fut SleepSync művelet.")
        self._update_status(running=True, operation="backup", progress=0, phase="Teljes SD mentés előkészítése…", total_files=0, work_files=0, processed_files=0, downloaded=0, unchanged=0, errors=0, current_file="—", last_error=None)
        result: dict[str, Any] | None = None
        try:
            result = self._run_with_wifi(jid, lambda: self._backup_connected(jid))
            self._add_history("backup", True, result, trigger="manual")
            self._update_status(running=False, operation=None, progress=100, phase="Teljes SD biztonsági mentés kész.", last_run=datetime.now().isoformat(timespec="seconds"), last_error=None, current_file="—")
            return result
        except Exception as exc:
            self._add_history("backup", False, result, error=exc, trigger="manual")
            self._update_status(running=False, operation=None, phase="A teljes SD mentés nem sikerült.", last_error=str(exc))
            raise
        finally:
            self._operation_lock.release()
            self._scheduler_wakeup.set()

    def _backup_connected(self, jid: str) -> dict[str, Any]:
        raw_root = str(self.app.load_config().get("data_dir") or "").strip()
        if not raw_root:
            raise RuntimeError("Nincs beállítva SleepMate terápiás adatmappa.")
        data_root = Path(raw_root).expanduser().resolve()
        backup_root = Path(str(self._settings.get("backup_root") or (Path.home() / "Documents" / "SleepSync_Backups"))).expanduser().resolve()
        data_root.mkdir(parents=True, exist_ok=True)
        backup_root.mkdir(parents=True, exist_ok=True)
        run_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        run_root = backup_root / run_name
        suffix = 2
        while run_root.exists():
            run_root = backup_root / f"{run_name}_{suffix}"
            suffix += 1
        snapshot = run_root / "SD tartalma"
        zip_dir = run_root / "ZIP"
        snapshot.mkdir(parents=True, exist_ok=True)
        zip_dir.mkdir(parents=True, exist_ok=True)

        self._progress(jid, 15, "Feltérképezés", "SD-kártya feltérképezése…")
        files, directories = self._scan_sd()
        mandatory_seen = set(self._validate_scan(files, directories))
        for rel_dir in directories:
            (snapshot / rel_dir).mkdir(parents=True, exist_ok=True)

        selected: list[tuple[dict[str, Any], str]] = []
        skipped: list[dict[str, Any]] = []
        for info in files:
            need, reason = self._should_download(info, data_root)
            local = data_root / info["relative_path"]
            if need or not local.is_file():
                selected.append((info, reason))
            else:
                skipped.append(info)
                dst = snapshot / info["relative_path"]
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(local, dst)
                self._record_state(info)

        self._progress(jid, 28, "Mentési lista", "Teljes SD-pillanatkép összeállítása…", total_files=len(files), work_files=len(selected), unchanged=len(skipped))
        successful = 0
        mandatory_refreshed: set[str] = set()
        failed: list[tuple[dict[str, Any], str, Exception]] = []
        for index, (info, reason) in enumerate(selected, start=1):
            rel = info["relative_path"]
            self._progress(jid, 30 + int(index / max(1, len(selected)) * 55), "Teljes mentés", f"Letöltés: {rel}", processed_files=index - 1, current_file=str(rel), downloaded=successful)
            try:
                final = self._download_with_retries(info, snapshot / rel)
                live = data_root / rel
                live.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(snapshot / rel, live)
                self._record_state({**info, **final, "relative_path": rel, "sd_directory": info["sd_directory"]})
                successful += 1
                normalized = rel.as_posix().upper()
                if normalized in mandatory_seen:
                    mandatory_refreshed.add(normalized)
            except Exception as exc:
                failed.append((info, reason, exc))
            self._progress(jid, 30 + int(index / max(1, len(selected)) * 55), "Teljes mentés", f"Letöltés: {rel}", processed_files=index, current_file=str(rel), downloaded=successful, errors=len(failed))

        if failed:
            retry_failed: list[tuple[dict[str, Any], str, Exception]] = []
            for info, reason, previous in failed:
                rel = info["relative_path"]
                try:
                    final = self._download_with_retries(info, snapshot / rel)
                    live = data_root / rel
                    live.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(snapshot / rel, live)
                    self._record_state({**info, **final, "relative_path": rel, "sd_directory": info["sd_directory"]})
                    successful += 1
                    normalized = rel.as_posix().upper()
                    if normalized in mandatory_seen:
                        mandatory_refreshed.add(normalized)
                except Exception as exc:
                    retry_failed.append((info, reason, exc))
            failed = retry_failed

        _json_write_atomic(self.sync_state_file, self._sync_state)
        if failed:
            raise RuntimeError(f"A teljes SD mentés {len(failed)} fájlnál végleges hibát jelzett; félkész ZIP nem készül.")
        missing_mandatory = sorted(mandatory_seen - mandatory_refreshed)
        if missing_mandatory:
            raise RuntimeError("A teljes SD mentés kötelező fájljai közül nem mindegyik frissült: " + ", ".join(missing_mandatory))

        self._progress(jid, 89, "ZIP készítése", "A teljes SD-pillanatkép tömörítése…", current_file="—")
        zip_path = zip_dir / f"{run_root.name}_CPAP_SD.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for path in snapshot.rglob("*"):
                if path.is_file():
                    zf.write(path, path.relative_to(snapshot))

        before_days = self.handler.dataset.days()
        before_latest = before_days[-1] if before_days else None
        with self.handler._dataset_lock:
            imported = self.app.import_resmed_tree(data_root, self.handler.dataset.root, authoritative=False)
            self.handler.dataset.refresh()
        self.handler._push_after_refresh(before_latest, imported, "SleepSync teljes SD mentés")
        self._progress(jid, 95, "SleepMate import", "A SleepMate mérési adattár frissítve.", errors=0)
        return {"total_files": len(files), "successful": successful, "skipped": len(skipped), "failed": 0, "mandatory_seen": sorted(mandatory_seen), "mandatory_refreshed": sorted(mandatory_refreshed), "zip_path": str(zip_path), "run_root": str(run_root), "import": imported}

    # ------------------------------------------------------------------
    # Scheduler
    # ------------------------------------------------------------------
    def _next_scheduled_time(self) -> datetime | None:
        if not self._settings.get("auto_sync_enabled") or self._settings.get("auto_sync_mode") != "scheduled":
            return None
        days = set(self._settings.get("schedule_days") or DAY_ORDER)
        times = _normalize_times(self._settings.get("schedule_times"))
        now = datetime.now()
        candidates: list[datetime] = []
        for offset in range(0, 8):
            day = now + timedelta(days=offset)
            if DAY_ORDER[day.weekday()] not in days:
                continue
            for token in times:
                hh, mm = map(int, token.split(":"))
                candidate = day.replace(hour=hh, minute=mm, second=0, microsecond=0)
                if candidate > now:
                    candidates.append(candidate)
        return min(candidates) if candidates else None

    def _scheduler_loop(self) -> None:
        last_scheduled_token: str | None = None
        while not self._scheduler_stop.is_set():
            try:
                if not self._settings.get("auto_sync_enabled"):
                    self._card_visible_latched = False
                    self._update_status(connection="készenlét", next_run=None)
                    self._scheduler_wakeup.wait(10)
                    self._scheduler_wakeup.clear()
                    continue

                mode = self._settings.get("auto_sync_mode", "card_available")
                if mode == "card_available":
                    visible = self.wifi_network_visible(EZSHARE_WIFI_PROFILE)
                    self._update_status(sd_visible=visible, connection="kártya elérhető" if visible else "kártyát figyel", next_run=None)
                    if not visible:
                        self._card_visible_latched = False
                    elif not self._card_visible_latched and not self._status.get("running") and not self._operation_lock.locked():
                        try:
                            self.start_sync("auto")
                            # Latch only after a job was really created. A failed start must
                            # be retried while the card is still present.
                            self._card_visible_latched = True
                        except Exception as exc:
                            self.log(f"Automatikus SleepSync indítási hiba: {exc}", "ERROR")
                            self._card_visible_latched = False
                    self._scheduler_wakeup.wait(max(10, int(self._settings.get("card_scan_interval_seconds", 30))))
                    self._scheduler_wakeup.clear()
                    continue

                now = datetime.now()
                days = set(self._settings.get("schedule_days") or DAY_ORDER)
                times = set(_normalize_times(self._settings.get("schedule_times")))
                current_token = f"{now.date().isoformat()} {now.strftime('%H:%M')}"
                due_now = DAY_ORDER[now.weekday()] in days and now.strftime("%H:%M") in times
                next_run = self._next_scheduled_time()
                self._update_status(connection="időzítés aktív", next_run=next_run.isoformat(timespec="seconds") if next_run else None)
                if due_now and current_token != last_scheduled_token and not self._status.get("running") and not self._operation_lock.locked():
                    try:
                        self.start_sync("auto")
                        last_scheduled_token = current_token
                    except Exception as exc:
                        self.log(f"Időzített SleepSync indítási hiba: {exc}", "ERROR")
                self._scheduler_wakeup.wait(10)
                self._scheduler_wakeup.clear()
            except Exception as exc:
                self.log(f"SleepSync scheduler hiba: {exc}", "ERROR")
                self._scheduler_wakeup.wait(10)
                self._scheduler_wakeup.clear()

    def open_folder(self, kind: str) -> str:
        if kind == "data":
            target = Path(str(self.app.load_config().get("data_dir") or "")).expanduser()
        elif kind == "backup":
            target = Path(str(self._settings.get("backup_root") or "")).expanduser()
        elif kind == "log":
            target = self.private_dir
        else:
            raise ValueError("Ismeretlen megnyitandó mappa.")
        target.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            raise RuntimeError("A mappamegnyitás csak a Windows gazdagépen érhető el.")
        os.startfile(str(target))  # type: ignore[attr-defined]
        return str(target)


_service: SleepSyncService | None = None
_service_lock = threading.RLock()


def get_service(app_module) -> SleepSyncService:
    global _service
    with _service_lock:
        if _service is None:
            _service = SleepSyncService(app_module)
        return _service


def install_sleepsync_integration(app_module) -> None:
    handler_cls = app_module.Handler
    original_get = handler_cls.do_GET
    original_post = handler_cls.do_POST
    original_backup = handler_cls._backup_job
    original_restore = handler_cls._restore_backup_job

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/api/sleepsync/"):
            try:
                service = get_service(app_module)
                if path == "/api/sleepsync/status":
                    return self._json(service.status())
                if path == "/api/sleepsync/settings":
                    return self._json(service.settings())
                if path == "/api/sleepsync/history":
                    return self._json({"rows": service.history()})
                if path == "/api/sleepsync/log":
                    return self._json({"text": service.technical_log_tail()})
                if path == "/api/sleepsync/wifi":
                    return self._json(service.wifi_options())
                return self._json({"error": f"Ismeretlen SleepSync API végpont: {path}"}, 404)
            except Exception as exc:
                return self._json({"error": str(exc)}, 500)
        return original_get(self)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/api/sleepsync/"):
            try:
                service = get_service(app_module)
                if path == "/api/sleepsync/start":
                    return self._json({"ok": True, "job": service.start_sync("manual")})
                if path == "/api/sleepsync/backup":
                    return self._json({"ok": True, "job": service.start_sd_backup()})
                if path == "/api/sleepsync/settings":
                    data = self._read_json_body(max_bytes=200_000)
                    return self._json({"ok": True, "settings": service.save_settings(data)})
                if path == "/api/sleepsync/history/clear":
                    service.clear_history()
                    return self._json({"ok": True})
                if path == "/api/sleepsync/open-folder":
                    data = self._read_json_body(max_bytes=20_000)
                    return self._json({"ok": True, "path": service.open_folder(str(data.get("kind") or ""))})
                return self._json({"error": f"Ismeretlen SleepSync API végpont: {path}"}, 404)
            except Exception as exc:
                return self._json({"error": str(exc)}, 400)
        return original_post(self)

    # SleepSync lives under STATE_BASE/private/sleepsync. SleepMate's full backup
    # already archives the private state tree, therefore this is one shared backup
    # and one shared restore – no second system-backup implementation is needed.
    def backup_job(self, jid: str):
        service = get_service(app_module)
        with service.exclusive():
            service.log("SleepMate és SleepSync teljes rendszermentés indul.")
            result = original_backup(self, jid)
            service.log("SleepMate és SleepSync teljes rendszermentés elkészült.")
            return result

    def restore_job(self, jid: str, uploaded: str):
        service = get_service(app_module)
        with service.exclusive():
            service.log("SleepMate és SleepSync teljes rendszer-visszaállítás indul.")
            result = original_restore(self, jid, uploaded)
            service.reload_from_disk()
            service.log("SleepMate és SleepSync teljes rendszer-visszaállítás elkészült.")
            return result

    handler_cls.do_GET = do_GET
    handler_cls.do_POST = do_POST
    handler_cls._backup_job = backup_job
    handler_cls._restore_backup_job = restore_job

    def bootstrap():
        for _ in range(120):
            if getattr(handler_cls, "jobs", None) is not None and getattr(handler_cls, "dataset", None) is not None:
                get_service(app_module)
                return
            time.sleep(0.25)

    threading.Thread(target=bootstrap, daemon=True, name="SleepMate-SleepSync-Bootstrap").start()
