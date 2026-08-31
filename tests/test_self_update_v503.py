from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "update_worker.py"
sys.path.insert(0, str(ROOT))
from update_worker import wait_for_exit


def test_worker_stops_all_sleepmate_images_before_program_replacement():
    text = WORKER.read_text(encoding="utf-8")
    stop = text.index('if tray_pid > 0 and not stop_process_tree(tray_pid')
    sweep = text.index('stop_sleepmate_image_processes(launcher_exe', stop)
    replace = text.index('replace_program(package_dir, app_dir, launcher_exe', sweep)
    assert stop < sweep < replace
    assert '["taskkill", "/IM", image_name, "/T", "/F"]' in text
    assert 'SleepMateUpdater.exe' in text
    assert 'terminate_spawned(new_backend' in text
    assert 'restart_tray(0, vbs, app_dir, log_path, launcher_exe)' in text
    assert 'GetExitCodeProcess' in text and 'STILL_ACTIVE = 259' in text


def test_zip_self_update_preserves_inno_uninstaller_files():
    text = WORKER.read_text(encoding="utf-8")
    assert '_installer_owned_file' in text
    assert 'name.startswith("unins")' in text
    assert '{".exe", ".dat", ".msg"}' in text


def test_startup_uses_only_web_loader_and_keeps_stuck_tray_recovery():
    main = (ROOT / "sleepmate_main.py").read_text(encoding="utf-8")
    spec = (ROOT / "build" / "windows" / "SleepMate.spec").read_text(encoding="utf-8")
    index = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert '--startup-splash' not in main
    assert '_launch_startup_splash' not in main
    assert '_run_startup_splash' not in main
    assert 'sleepmate-splash-v410.webp' not in main
    assert '_recover_stuck_tray()' in main
    assert 'tray_heartbeat.json' in main
    assert "'PIL.ImageTk'" not in spec
    assert "'tkinter'" not in spec
    assert 'id="startupSplash"' in index
    assert 'sleepmate-splash-v410.webp' in index


def test_windows_orphan_companion_sleepmate_exe_is_stopped_before_replace():
    if os.name != "nt":
        return

    with tempfile.TemporaryDirectory() as raw:
        td = Path(raw)
        app = td / "app"
        pkg = td / "pkg"
        rollback = td / "rollback"
        state = td / "state"
        for d in (app, pkg, rollback, state / "private" / "update_runtime"):
            d.mkdir(parents=True, exist_ok=True)

        locked_exe = app / "SleepMate.exe"
        # A copied native cmd.exe renamed to SleepMate.exe behaves like a normal
        # Windows executable image and keeps SleepMate.exe locked while running.
        cmd_source = Path(os.environ.get("COMSPEC") or r"C:\Windows\System32\cmd.exe")
        shutil.copy2(cmd_source, locked_exe)
        hold_command = "ping -n 60 127.0.0.1 >nul"
        flags = 0x08000000

        # tray_pid represents the known tray. companion is deliberately not
        # present in the update plan, reproducing the stale/native companion that
        # caused the real 5.0.4 -> 5.0.5 WinError 5 on SleepMate.exe.
        tray = subprocess.Popen([str(locked_exe), "/d", "/c", hold_command], creationflags=flags)
        companion = subprocess.Popen([str(locked_exe), "/d", "/c", hold_command], creationflags=flags)
        try:
            time.sleep(0.8)
            assert tray.poll() is None, "simulated SleepMate.exe tray did not stay alive"
            assert companion.poll() is None, "simulated orphan SleepMate.exe companion did not stay alive"

            (app / "app.py").write_text("# old\n", encoding="utf-8")
            (app / "SleepMate.vbs").write_text("Option Explicit\n", encoding="utf-8")
            (app / "unins000.exe").write_bytes(b"installer-owned-exe")
            (app / "unins000.dat").write_bytes(b"installer-owned-dat")
            (rollback / "app.py").write_text("# rollback\n", encoding="utf-8")
            (rollback / "SleepMate.vbs").write_text("Option Explicit\n", encoding="utf-8")

            marker = state / "private" / "update_runtime" / "update_boot_ok.json"
            new_code = (
                "import json,os,time\n"
                "from pathlib import Path\n"
                f"p=Path({str(marker)!r})\n"
                "p.parent.mkdir(parents=True,exist_ok=True)\n"
                "p.write_text(json.dumps({'version':'5.0.6','pid':os.getpid()}),encoding='utf-8')\n"
                "time.sleep(1.2)\n"
            )
            (pkg / "app.py").write_text(new_code, encoding="utf-8")
            (pkg / "SleepMate.vbs").write_text("Option Explicit\n", encoding="utf-8")

            log = state / "private" / "update_runtime" / "worker.log"
            plan = {
                "format": "sleepmate-update-plan",
                "from_version": "5.0.5",
                "to_version": "5.0.6",
                "app_dir": str(app),
                "package_dir": str(pkg),
                "rollback_dir": str(rollback),
                "health_marker": str(marker),
                "old_pid": 0,
                "port": 19993,
                "tray_pid": tray.pid,
                "restart_tray": False,
                "launch_vbs": str(app / "SleepMate.vbs"),
                "launcher_exe": str(app / "SleepMate.exe"),
                "state_dir": str(state),
                "worker_log": str(log),
                "timeout_seconds": 8,
            }
            pp = td / "plan.json"
            pp.write_text(json.dumps(plan), encoding="utf-8")
            rc = subprocess.run([sys.executable, str(WORKER), str(pp)], timeout=30).returncode
            details = log.read_text(encoding="utf-8", errors="replace") if log.exists() else str(rc)
            assert rc == 0, details
            assert tray.poll() is not None, "known locked SleepMate.exe tray was not stopped"
            assert companion.poll() is not None, "orphan locked SleepMate.exe companion was not stopped"
            assert not locked_exe.exists(), "old locked executable survived program replacement"
            assert (app / "unins000.exe").read_bytes() == b"installer-owned-exe"
            assert (app / "unins000.dat").read_bytes() == b"installer-owned-dat"
            assert "update_boot_ok" in (pkg / "app.py").read_text(encoding="utf-8")
            assert "update_boot_ok" in (app / "app.py").read_text(encoding="utf-8")
            assert "minden SleepMate.exe folyamat leállítási kérése elküldve" in details

            health = json.loads(marker.read_text(encoding="utf-8"))
            assert wait_for_exit(int(health.get("pid") or 0), 5), "simulated updated backend did not exit"
        finally:
            for proc in (tray, companion):
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=5)
