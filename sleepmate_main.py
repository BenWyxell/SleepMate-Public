from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from cpap.runtime import app_root, config_path, migrate_from_path, state_root
from cpap.version import APP_VERSION


MUTEX_NAME = "Global\\SleepMateTraySingleton_v1"
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
TRAY_HEARTBEAT_FRESH_SECONDS = 45


def _value_after(flag: str) -> str | None:
    try:
        i = sys.argv.index(flag)
        return sys.argv[i + 1]
    except Exception:
        return None


def _load_startup_config() -> dict:
    defaults = {"port": 8895, "port_mode": "auto"}
    try:
        p = config_path(app_root())
        if p.is_file():
            obj = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(obj, dict):
                defaults.update(obj)
    except Exception:
        pass
    return defaults


def _candidate_ports() -> list[int]:
    cfg = _load_startup_config()
    try:
        preferred = int(cfg.get("port", 8895) or 8895)
    except Exception:
        preferred = 8895
    if str(cfg.get("port_mode") or "auto").lower() == "fixed":
        return [preferred]
    return list(range(preferred, min(65535, preferred + 100) + 1))


def _sleepmate_port() -> int | None:
    for port in _candidate_ports():
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/version",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=0.22) as r:
                obj = json.loads(r.read().decode("utf-8"))
            if obj.get("app") == "SleepMate":
                return int(port)
        except Exception:
            continue
    return None


def _tray_mutex_exists() -> bool:
    if os.name != "nt":
        return False
    try:
        import ctypes
        SYNCHRONIZE = 0x00100000
        handle = ctypes.windll.kernel32.OpenMutexW(SYNCHRONIZE, False, MUTEX_NAME)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    except Exception:
        return False


def _recover_stuck_tray() -> bool:
    """Recover only a genuinely stale tray, never a healthy tray still starting."""
    if os.name != "nt" or not _tray_mutex_exists():
        return False
    if _sleepmate_port() is not None:
        return False

    try:
        private = state_root(app_root()) / "private"
        pid_file = private / "tray.pid"
        heartbeat = private / "tray_heartbeat.json"
        pid = int(pid_file.read_text(encoding="ascii").strip())
        hb = json.loads(heartbeat.read_text(encoding="utf-8"))
        if int(hb.get("pid") or 0) != pid or pid <= 0:
            return False

        heartbeat_age = time.time() - heartbeat.stat().st_mtime
        if heartbeat_age <= TRAY_HEARTBEAT_FRESH_SECONDS:
            return False
    except Exception:
        return False

    end = time.time() + 3.5
    while time.time() < end:
        if _sleepmate_port() is not None:
            return False
        try:
            heartbeat_age = time.time() - heartbeat.stat().st_mtime
            if heartbeat_age <= TRAY_HEARTBEAT_FRESH_SECONDS:
                return False
        except Exception:
            return False
        time.sleep(0.35)

    try:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
            timeout=10,
            check=False,
        )
        for _ in range(30):
            if not _tray_mutex_exists():
                return True
            time.sleep(0.1)
        return not _tray_mutex_exists()
    except Exception:
        return False


def main() -> int:
    if "--version" in sys.argv:
        print(APP_VERSION)
        return 0

    if "--migrate-from" in sys.argv:
        source = _value_after("--migrate-from")
        if not source:
            print("Missing path after --migrate-from", file=sys.stderr)
            return 2
        result = migrate_from_path(Path(source), app_root())
        print(json.dumps(result, ensure_ascii=False))
        if "--migrate-only" in sys.argv:
            return 0 if not result.get("errors") else 3
        i = sys.argv.index("--migrate-from")
        del sys.argv[i:i + 2]

    if "--backend" in sys.argv:
        sys.argv = [arg for arg in sys.argv if arg != "--backend"]
        import app
        from cpap.v511_features import install_v511_features
        from cpap.v512_features import install_v512_features
        from cpap.v513_diagnostics import install_v513_diagnostics
        from cpap.sleep_analysis import install_sleep_analysis
        from cpap.sleep_analysis_v521 import install_sleep_analysis_v521
        from cpap.sleep_analysis_v522 import install_sleep_analysis_v522
        from cpap.sleepsync_integration import install_sleepsync_integration
        from cpap.google_drive_integration import install_google_drive_integration
        from cpap.o2ring_integration import install_o2ring_integration
        install_v511_features()
        install_v512_features()
        install_v513_diagnostics()
        install_sleep_analysis(app)
        install_sleep_analysis_v521(app)
        install_sleep_analysis_v522(app)
        install_sleepsync_integration(app)
        install_google_drive_integration(app)
        install_o2ring_integration(app)
        app.main()
        return 0

    if _tray_mutex_exists():
        _recover_stuck_tray()

    from sleepmate_tray import main as tray_main
    tray_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
