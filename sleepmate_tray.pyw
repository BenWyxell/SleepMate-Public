from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
import shutil
import socket
import csv
import io
from datetime import datetime
from pathlib import Path

from cpap.runtime import app_root, resource_root, state_root, config_path, ensure_state_layout, migrate_legacy_state, is_frozen

BASE = app_root()
RESOURCE_BASE = resource_root()
STATE_BASE = ensure_state_layout(BASE)
CONFIG = config_path(BASE)
ICON_PATH = BASE / "SleepMate.ico"
if not ICON_PATH.is_file():
    ICON_PATH = RESOURCE_BASE / "SleepMate.ico"
APP_PATH = BASE / "app.py"
APP_NAME = "SleepMate"
MUTEX_NAME = "Global\\SleepMateTraySingleton_v1"
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
ACTIVE_PORT: int | None = None
AUTO_PORT_SPAN = 100
TRAY_PID_FILE = STATE_BASE / "private" / "tray.pid"
TRAY_HEARTBEAT_FILE = STATE_BASE / "private" / "tray_heartbeat.json"
OPEN_REQUEST_FILE = STATE_BASE / "private" / "open_app.request"
QUIT_REQUEST_FILE = STATE_BASE / "private" / "quit_tray.request"
APP_USER_MODEL_ID = "SleepMate.Desktop"




def launcher_log(message: str) -> None:
    try:
        log_dir = STATE_BASE / "private"
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / "launcher.log").open("a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {message}\n")
    except Exception:
        pass


def port_is_open(port: int, host: str = "127.0.0.1", timeout: float = 0.35) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            return sock.connect_ex((host, int(port))) == 0
    except Exception:
        return False


def find_windows_port_owner(port: int) -> dict:
    result = {"port": int(port), "pid": None, "process": None, "line": None}
    if os.name != "nt":
        return result
    try:
        cp = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            creationflags=CREATE_NO_WINDOW, timeout=8, check=False,
        )
        needle = f":{int(port)}"
        for raw in (cp.stdout or "").splitlines():
            line = raw.strip()
            if needle not in line or "LISTENING" not in line.upper():
                continue
            parts = line.split()
            if len(parts) < 5:
                continue
            local = parts[1]
            if not (local.endswith(needle) or local.endswith(f"]{needle}")):
                continue
            try:
                pid = int(parts[-1])
            except Exception:
                pid = None
            result.update({"pid": pid, "line": line})
            break
        pid = result.get("pid")
        if pid:
            cp2 = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                creationflags=CREATE_NO_WINDOW, timeout=8, check=False,
            )
            row = next(csv.reader(io.StringIO(cp2.stdout or "")), None)
            if row and row[0] and not row[0].startswith("INFO:"):
                result["process"] = row[0]
    except Exception as exc:
        result["error"] = str(exc)
    return result


def diagnose_port(port: int) -> dict:
    port = int(port)
    open_now = port_is_open(port)
    diag = {"port": port, "open": open_now, "sleepmate": False, "owner": {}}
    if open_now:
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{port}/api/version", headers={"Accept":"application/json"})
            with urllib.request.urlopen(req, timeout=1.2) as r:
                obj = json.loads(r.read().decode("utf-8"))
                diag["sleepmate"] = obj.get("app") == "SleepMate"
                diag["version"] = obj.get("version")
        except Exception:
            pass
        diag["owner"] = find_windows_port_owner(port)
    return diag


def candidate_ports(cfg: dict | None = None) -> list[int]:
    cfg = cfg or load_config()
    preferred = int(cfg.get("port", 8895) or 8895)
    mode = str(cfg.get("port_mode") or "auto").lower()
    if mode == "fixed":
        return [preferred]
    end = min(65535, preferred + AUTO_PORT_SPAN)
    return list(range(preferred, end + 1))

def find_existing_sleepmate_port(cfg: dict | None = None) -> int | None:
    for port in candidate_ports(cfg):
        if not port_is_open(port):
            continue
        diag = diagnose_port(port)
        if diag.get("sleepmate"):
            return int(port)
    return None

def choose_start_port(cfg: dict | None = None) -> tuple[int | None, dict | None]:
    cfg = cfg or load_config()
    mode = str(cfg.get("port_mode") or "auto").lower()
    preferred = int(cfg.get("port", 8895) or 8895)
    first_conflict = None
    for port in candidate_ports(cfg):
        diag = diagnose_port(port)
        if diag.get("sleepmate"):
            return int(port), {**diag, "existing_sleepmate": True}
        if not diag.get("open"):
            return int(port), {**diag, "existing_sleepmate": False}
        if first_conflict is None:
            first_conflict = diag
        if mode == "fixed":
            break
    return None, first_conflict or {"port": preferred, "open": True}

def message_box(text: str, title: str = APP_NAME, flags: int = 0x40) -> None:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(None, text, title, flags)


def set_windows_app_identity() -> None:
    """Make Windows attribute tray notifications to SleepMate, not Python."""
    if os.name != "nt":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass


def ensure_dependencies() -> bool:
    if is_frozen():
        try:
            import pystray
            from PIL import Image
            return True
        except Exception as exc:
            message_box(f"A telepített SleepMate csomag hiányos: {exc}", flags=0x10)
            return False
    try:
        import pystray  # noqa: F401
        from PIL import Image  # noqa: F401
        return True
    except Exception:
        py = Path(sys.executable)
        python_exe = py.with_name("python.exe") if py.name.lower() == "pythonw.exe" else py
        try:
            subprocess.run(
                [str(python_exe), "-m", "pip", "install", "pystray>=0.19.5", "Pillow>=10.0.0"],
                cwd=str(BASE), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW, timeout=180, check=False,
            )
            import pystray  # noqa: F401
            from PIL import Image  # noqa: F401
            return True
        except Exception:
            message_box("A SleepMate tálcaikonhoz szükséges pystray/Pillow csomag telepítése nem sikerült.\n\nFuttasd egyszer a SleepMate_fuggosegek_telepitese.bat fájlt.", flags=0x10)
            return False


def load_config() -> dict:
    defaults = {
        "host": "127.0.0.1", "port": 8895, "port_mode": "auto",
        "auto_scan_enabled": True,
        "tray_notifications": True,
        "start_with_windows": False,
    }
    try:
        if CONFIG.is_file():
            obj = json.loads(CONFIG.read_text(encoding="utf-8"))
            if isinstance(obj, dict): defaults.update(obj)
    except Exception:
        pass
    return defaults


def configured_port() -> int:
    try:
        return int(load_config().get("port", 8895) or 8895)
    except Exception:
        return 8895

def current_port() -> int:
    return int(ACTIVE_PORT or configured_port())

def internal_url(path: str = "") -> str:
    return f"http://127.0.0.1:{current_port()}{path}"

def browser_url() -> str:
    return f"http://sleepmate.localhost:{current_port()}"


def http_json(path: str, method: str = "GET", data: dict | None = None, timeout: float = 5.0) -> dict:
    payload = None
    headers = {"Accept": "application/json"}
    if data is not None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(internal_url(path), data=payload, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def wait_server(timeout: float = 20.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            r = http_json("/api/version", timeout=1.2)
            if r.get("app") == "SleepMate": return True
        except Exception:
            time.sleep(.25)
    return False


def set_windows_startup(enabled: bool) -> None:
    if os.name != "nt": return
    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    command = f'"{sys.executable}"' if is_frozen() else f'wscript.exe "{BASE / "SleepMate.vbs"}"'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
        else:
            try: winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError: pass


class SleepMateTray:
    def __init__(self):
        import pystray
        from PIL import Image
        self.pystray = pystray
        self.Image = Image
        self.icon = None
        self.server_process: subprocess.Popen | None = None
        self.owns_server = False
        self.stopping = False
        self.last_scan = None
        self.cached_cfg = load_config()
        self.active_port = int(self.cached_cfg.get("port", 8895) or 8895)
        self._startup_applied = None
        self.app_window_process: subprocess.Popen | None = None
        self._opening_app = False
        self._last_open_app_at = 0.0

    def notify(self, message: str, title: str = APP_NAME) -> None:
        if not self.cached_cfg.get("tray_notifications", True) or not self.icon:
            return
        try: self.icon.notify(message, title)
        except Exception: pass

    def spawn_server(self) -> bool:
        global ACTIVE_PORT
        cfg = load_config()
        preferred = int(cfg.get("port", 8895) or 8895)
        mode = str(cfg.get("port_mode") or "auto").lower()
        selected, diag = choose_start_port(cfg)
        if selected is None:
            owner = (diag or {}).get("owner") or {}
            pid = owner.get("pid"); proc = owner.get("process")
            detail = []
            if proc: detail.append(f"Folyamat: {proc}")
            if pid: detail.append(f"PID: {pid}")
            detail_text = "\n".join(detail) if detail else "A foglaló folyamat neve nem volt megállapítható."
            if mode == "fixed":
                text = (f"A SleepMate fix portja ({preferred}) foglalt.\n\n{detail_text}\n\n"
                        "A SleepMate nem állít le más programot automatikusan. Válassz másik fix portot, vagy kapcsold be az automatikus portválasztást.")
            else:
                text = (f"A SleepMate nem talált szabad portot a {preferred}–{min(65535, preferred+AUTO_PORT_SPAN)} tartományban.\n\n"
                        f"Az első ütközés: {detail_text}")
            launcher_log(f"Portválasztás sikertelen. mode={mode}, preferred={preferred}, diag={diag}")
            message_box(text, "SleepMate – nincs szabad port", 0x30)
            return False

        self.active_port = int(selected); ACTIVE_PORT = int(selected)
        if (diag or {}).get("existing_sleepmate"):
            self.owns_server = False
            launcher_log(f"Port {selected}: már fut SleepMate v{(diag or {}).get('version') or '?'}, a meglévő szolgáltatást használom.")
            return True

        if selected != preferred:
            launcher_log(f"A {preferred}-ös port foglalt; automatikus mód szabad portot választott: {selected}.")
        else:
            launcher_log(f"Port {selected}: szabad. SleepMate háttérszolgáltatás indítása.")

        py = Path(sys.executable)
        pythonw = py.with_name("pythonw.exe") if os.name == "nt" else py
        if not pythonw.exists(): pythonw = py
        log_dir = STATE_BASE / "private"
        log_dir.mkdir(parents=True, exist_ok=True)
        service_log = log_dir / "service_startup.log"
        try:
            log_handle = service_log.open("ab")
        except Exception:
            log_handle = subprocess.DEVNULL
        try:
            child_env = os.environ.copy()
            child_env["PYTHONUTF8"] = "1"
            child_env["PYTHONIOENCODING"] = "utf-8"
            if is_frozen():
                child_env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
                cmd = [str(sys.executable), "--backend", "--no-browser", "--port", str(selected)]
            else:
                cmd = [str(pythonw), str(APP_PATH), "--no-browser", "--port", str(selected)]
            self.server_process = subprocess.Popen(
                cmd, cwd=str(BASE), stdout=log_handle, stderr=log_handle,
                creationflags=CREATE_NO_WINDOW, env=child_env,
            )
        finally:
            if hasattr(log_handle, "close"):
                try: log_handle.close()
                except Exception: pass
        self.owns_server = True
        if wait_server(25.0):
            launcher_log(f"Port {selected}: SleepMate szolgáltatás sikeresen elindult. mode={mode}, preferred={preferred}.")
            if selected != preferred:
                self.notify(f"A {preferred}-ös port foglalt volt. A SleepMate a {selected}-es porton indult el.")
            return True
        rc = self.server_process.poll() if self.server_process else None
        diag_after = diagnose_port(selected)
        owner = diag_after.get("owner") or {}
        launcher_log(f"Szolgáltatás nem indult. returncode={rc}, selected_port={selected}, port_diag={diag_after}")
        tail = ""
        try:
            if service_log.is_file():
                lines = service_log.read_text(encoding="utf-8", errors="replace").splitlines()
                tail = "\n".join(lines[-8:])
        except Exception:
            pass
        extra = f"\n\nUtolsó háttérüzenetek:\n{tail}" if tail else ""
        if diag_after.get("open") and not diag_after.get("sleepmate"):
            proc = owner.get("process") or "ismeretlen folyamat"; pid = owner.get("pid")
            extra += f"\n\nA {selected}-es portot jelenleg ez használja: {proc}" + (f" (PID {pid})" if pid else "")
        message_box(
            "A SleepMate Python háttérszolgáltatása nem indult el.\n\n"
            f"A kiválasztott helyi port: {selected}." + extra +
            "\n\nRészletes napló: private\\service_startup.log",
            "SleepMate – indítási hiba", 0x10,
        )
        return False

    def _find_edge(self) -> str | None:
        candidates = [
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
            Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/Application/msedge.exe",
        ]
        for p in candidates:
            if str(p) and p.is_file(): return str(p)
        return shutil.which("msedge")

    def open_app(self, *_):
        now = time.monotonic()
        if self._opening_app or now - self._last_open_app_at < 1.5:
            return
        if self.app_window_process and self.app_window_process.poll() is None:
            return
        self._opening_app = True
        try:
            edge = self._find_edge()
            if edge:
                profile = STATE_BASE / "private" / "browser_profile"
                profile.mkdir(parents=True, exist_ok=True)
                try:
                    self.app_window_process = subprocess.Popen([edge, f"--app={browser_url()}", f"--user-data-dir={profile}", "--no-first-run", "--start-maximized"], cwd=str(BASE), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
                    self._last_open_app_at = time.monotonic()
                    return
                except Exception:
                    self.app_window_process = None
            webbrowser.open(browser_url())
            self._last_open_app_at = time.monotonic()
        finally:
            self._opening_app = False

    def monitor_open_requests(self):
        while not self.stopping:
            try:
                if QUIT_REQUEST_FILE.is_file():
                    QUIT_REQUEST_FILE.unlink(missing_ok=True)
                    launcher_log("Szabályos tálcaleállítási kérés érkezett.")
                    self.quit()
                    return
                if OPEN_REQUEST_FILE.is_file():
                    OPEN_REQUEST_FILE.unlink(missing_ok=True)
                    self.open_app()
            except Exception:
                pass
            time.sleep(.25)

    def poll_job(self, job_id: str, label: str):
        try:
            while True:
                j = http_json(f"/api/job/{job_id}", timeout=4)
                if j.get("status") == "done":
                    result = j.get("result") or {}
                    days = result.get("days")
                    self.notify(f"{label} elkészült." + (f" Terápiás napok: {days}." if days is not None else ""))
                    self.refresh_menu()
                    return
                if j.get("status") == "error":
                    self.notify(j.get("message") or f"{label} nem sikerült.", "SleepMate – hiba")
                    return
                time.sleep(.5)
        except Exception as exc:
            self.notify(str(exc), "SleepMate – hiba")

    def start_job(self, endpoint: str, label: str):
        def worker():
            try:
                r = http_json(endpoint, "POST", {}, timeout=8)
                jid = r.get("job")
                if not jid: raise RuntimeError("A háttérművelet nem indult el.")
                self.notify(f"{label} elindult.")
                self.poll_job(jid, label)
            except urllib.error.HTTPError as exc:
                try: msg = json.loads(exc.read().decode("utf-8")).get("error")
                except Exception: msg = str(exc)
                self.notify(msg or str(exc), "SleepMate – hiba")
            except Exception as exc:
                self.notify(str(exc), "SleepMate – hiba")
        threading.Thread(target=worker, daemon=True).start()

    def refresh_now(self, *_): self.start_job("/api/import/refresh", "Adatfrissítés")
    def scan_sd(self, *_): self.start_job("/api/import/sd-search", "SD-kártya beolvasás")

    def toggle_auto(self, *_):
        def worker():
            try:
                current = bool(self.cached_cfg.get("auto_scan_enabled", True))
                r = http_json("/api/settings", "POST", {"auto_scan_enabled": not current})
                self.cached_cfg.update(r)
                self.notify("Automatikus frissítés bekapcsolva." if not current else "Automatikus frissítés kikapcsolva.")
                self.refresh_menu()
            except Exception as exc: self.notify(str(exc), "SleepMate – hiba")
        threading.Thread(target=worker, daemon=True).start()

    def toggle_notifications(self, *_):
        def worker():
            try:
                new = not bool(self.cached_cfg.get("tray_notifications", True))
                r = http_json("/api/settings", "POST", {"tray_notifications": new})
                self.cached_cfg.update(r); self.refresh_menu()
                if new: self.notify("Tálcaértesítések bekapcsolva.")
            except Exception as exc: message_box(str(exc), "SleepMate – hiba", 0x10)
        threading.Thread(target=worker, daemon=True).start()

    def toggle_startup(self, *_):
        def worker():
            try:
                new = not bool(self.cached_cfg.get("start_with_windows", False))
                r = http_json("/api/settings", "POST", {"start_with_windows": new})
                self.cached_cfg.update(r); set_windows_startup(new); self._startup_applied = new; self.refresh_menu()
                self.notify("A SleepMate mostantól a Windows indításakor automatikusan elindul." if new else "A Windowszal együtt történő automatikus indítás kikapcsolva.")
            except Exception as exc: message_box(str(exc), "SleepMate – hiba", 0x10)
        threading.Thread(target=worker, daemon=True).start()

    def port_text(self, _item=None):
        cfg = self.cached_cfg
        preferred = int(cfg.get("port_preferred", cfg.get("port", 8895)) or 8895)
        mode = str(cfg.get("port_mode") or "auto")
        if mode == "auto" and self.active_port != preferred:
            return f"Helyi port: {self.active_port} (automatikusan választva)"
        return f"Helyi port: {self.active_port}"

    def status_text(self, _item=None):
        cfg = self.cached_cfg
        last = cfg.get("auto_scan_last_run")
        nxt = cfg.get("auto_scan_next_run")
        if last:
            try:
                dt = last.replace("T", " ")[:16]
                return f"Utolsó frissítés: {dt}"
            except Exception: pass
        return "Utolsó frissítés: még nem futott"

    def next_text(self, _item=None):
        nxt = self.cached_cfg.get("auto_scan_next_run")
        return f"Következő: {str(nxt).replace('T',' ')[:16]}" if nxt else "Következő: nincs ütemezve"

    def health_text(self, _item=None):
        try:
            s = http_json("/api/system/status", timeout=3)
            overall = s.get("overall")
            if overall == "ok": return "Rendszerállapot: rendben ✓"
            if overall == "error": return "Rendszerállapot: beavatkozás szükséges"
            return "Rendszerállapot: van mire figyelni"
        except Exception:
            return "Rendszerállapot: nem elérhető"

    def refresh_menu(self):
        try:
            if self.icon: self.icon.update_menu()
        except Exception: pass

    def close_app_window(self):
        p = self.app_window_process
        self.app_window_process = None
        if p and p.poll() is None:
            try: p.terminate(); p.wait(timeout=4)
            except Exception:
                try: p.kill()
                except Exception: pass

    def request_shutdown(self):
        self.close_app_window()
        try: http_json("/api/system/shutdown", "POST", {}, timeout=2)
        except Exception: pass
        if self.server_process:
            try: self.server_process.wait(timeout=5)
            except Exception:
                try: self.server_process.terminate()
                except Exception: pass
        self.server_process = None

    def restart(self, *_):
        def worker():
            self.notify("SleepMate újraindítása…")
            self.request_shutdown()
            time.sleep(.6)
            if self.spawn_server():
                self.notify("SleepMate újraindult.")
                self.refresh_menu()
            else:
                self.notify("Az újraindítás nem sikerült.", "SleepMate – hiba")
        threading.Thread(target=worker, daemon=True).start()

    def quit(self, *_):
        if self.stopping: return
        self.stopping = True
        def worker():
            self.request_shutdown()
            try: self.icon.stop()
            except Exception: pass
        threading.Thread(target=worker, daemon=True).start()

    def monitor(self):
        global ACTIVE_PORT
        while not self.stopping:
            try:
                TRAY_HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
                TRAY_HEARTBEAT_FILE.write_text(json.dumps({"pid": os.getpid(), "time": datetime.now().isoformat(timespec="seconds")}), encoding="utf-8")
            except Exception:
                pass
            try:
                cfg = http_json("/api/config", timeout=3)
                previous = self.last_scan
                self.cached_cfg.update(cfg)
                try:
                    self.active_port = int(cfg.get("port") or self.active_port)
                    ACTIVE_PORT = self.active_port
                except Exception:
                    pass
                self.last_scan = cfg.get("auto_scan_last_run")
                desired = bool(cfg.get("start_with_windows", False))
                if desired != self._startup_applied:
                    try: set_windows_startup(desired); self._startup_applied = desired
                    except Exception: pass
                if previous is not None and self.last_scan and previous != self.last_scan:
                    try:
                        rows = http_json("/api/day-table", timeout=4).get("rows") or []
                        if rows:
                            row = sorted(rows, key=lambda r: str(r.get("date") or r.get("day") or ""))[-1]
                            ahi = row.get("ahi")
                            usage = row.get("usage") or row.get("usage_hms") or ""
                            self.notify(f"Új adatállapot beolvasva. AHI: {ahi if ahi is not None else '–'}" + (f" • Használat: {usage}" if usage else ""))
                        else: self.notify("Az automatikus adatfrissítés elkészült.")
                    except Exception: self.notify("Az automatikus adatfrissítés elkészült.")
                self.refresh_menu()
            except Exception:
                pass
            time.sleep(10)

    def run(self):
        image = self.Image.open(ICON_PATH).convert("RGBA")
        Menu = self.pystray.Menu; Item = self.pystray.MenuItem
        menu = Menu(
            Item("SleepMate megnyitása", self.open_app, default=True),
            Menu.SEPARATOR,
            Item("Adatok frissítése most", self.refresh_now),
            Item("SD-kártya keresése és beolvasása", self.scan_sd),
            Item("Automatikus frissítés", self.toggle_auto, checked=lambda item: bool(self.cached_cfg.get("auto_scan_enabled", True))),
            Menu.SEPARATOR,
            Item(self.health_text, lambda icon, item: None, enabled=False),
            Item(self.port_text, lambda icon, item: None, enabled=False),
            Item(self.status_text, lambda icon, item: None, enabled=False),
            Item(self.next_text, lambda icon, item: None, enabled=False),
            Menu.SEPARATOR,
            Item("Értesítések", self.toggle_notifications, checked=lambda item: bool(self.cached_cfg.get("tray_notifications", True))),
            Item("Induljon el a Windows indításakor", self.toggle_startup, checked=lambda item: bool(self.cached_cfg.get("start_with_windows", False))),
            Menu.SEPARATOR,
            Item("Újraindítás", self.restart),
            Item("SleepMate bezárása", self.quit),
        )
        self.icon = self.pystray.Icon("SleepMate", image, "SleepMate", menu)
        if not self.spawn_server():
            return
        try:
            cfg = http_json("/api/config", timeout=3); self.cached_cfg.update(cfg); self.last_scan = cfg.get("auto_scan_last_run")
        except Exception: pass
        threading.Thread(target=self.monitor, daemon=True, name="SleepMateTrayMonitor").start()
        threading.Thread(target=self.monitor_open_requests, daemon=True, name="SleepMateOpenRequestMonitor").start()
        threading.Timer(1.1, self.open_app).start()
        self.icon.run()


def acquire_mutex() -> bool:
    if os.name != "nt": return True
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not handle: return True
    if kernel32.GetLastError() == 183:
        global ACTIVE_PORT
        try:
            existing = find_existing_sleepmate_port(load_config())
            if existing: ACTIVE_PORT = int(existing)
            OPEN_REQUEST_FILE.parent.mkdir(parents=True, exist_ok=True)
            OPEN_REQUEST_FILE.write_text(str(time.time()), encoding="ascii")
        except Exception:
            pass
        return False
    return True


def main():
    set_windows_app_identity()
    if not acquire_mutex(): return
    try:
        QUIT_REQUEST_FILE.unlink(missing_ok=True)
        TRAY_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        TRAY_PID_FILE.write_text(str(os.getpid()), encoding="ascii")
        TRAY_HEARTBEAT_FILE.write_text(json.dumps({"pid": os.getpid(), "time": datetime.now().isoformat(timespec="seconds")}), encoding="utf-8")
        if not ensure_dependencies(): return
        SleepMateTray().run()
    finally:
        for fp in (TRAY_PID_FILE, TRAY_HEARTBEAT_FILE, QUIT_REQUEST_FILE):
            try:
                if fp == TRAY_PID_FILE and fp.exists() and fp.read_text(encoding="ascii").strip() != str(os.getpid()):
                    continue
                if fp == TRAY_HEARTBEAT_FILE and fp.exists():
                    try:
                        if int(json.loads(fp.read_text(encoding="utf-8")).get("pid") or 0) != os.getpid():
                            continue
                    except Exception:
                        pass
                fp.unlink(missing_ok=True)
            except Exception:
                pass


if __name__ == "__main__":
    main()