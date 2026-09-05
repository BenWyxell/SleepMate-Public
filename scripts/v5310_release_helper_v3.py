from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
runpy.run_path(str(here / "v5310_release_helper_v2.py"), run_name="__main__")

test_path = Path("tests/test_v5310_targeted_fixes.py")
text = test_path.read_text(encoding="utf-8")
old = '''    assert 'self.base / "SleepMateUpdater.exe"' in maintenance\n    assert 'self.base / "Updater" / "SleepMateUpdater.exe"' in maintenance\n'''
new = '''    assert 'legacy_updater_exe = self.base / "SleepMateUpdater.exe"' in maintenance\n    assert 'updater_dir = self.base / "Updater"' in maintenance\n    assert 'updater_exe = updater_dir / "SleepMateUpdater.exe"' in maintenance\n'''
if old not in text:
    raise SystemExit("Expected updater-path assertions not found")
test_path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("SleepMate 5.3.10 updater-path regression aligned with actual launch_worker structure.")
