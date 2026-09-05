from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "5.3.13"
PREVIOUS = "5.3.12"


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Hiányzó marker: {path}: {old}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once("cpap/version.py", 'APP_VERSION = "5.3.12"', 'APP_VERSION = "5.3.13"')

for path in ("web/service-worker.js", "web/service-worker-v508-base.js"):
    replace_once(path, "sleepmate-shell-v5.3.12-o2-hydration-1", "sleepmate-shell-v5.3.13-o2-hydration-1")

sw = ROOT / "web/service-worker.js"
text = sw.read_text(encoding="utf-8")
text = text.replace("active shell cache is v5.3.12", "active shell cache is v5.3.13", 1)
sw.write_text(text, encoding="utf-8")

release_test_files = [
    "tests/test_mobile_ai_push_v417.py",
    "tests/test_o2ring_v532_release_contract.py",
    "tests/test_o2ring_v534_release_contract.py",
    "tests/test_pwa_sleep_shell_v526.py",
    "tests/test_v534_acceptance_matrix.py",
    "tests/test_v535_user_acceptance_matrix.py",
    "tests/test_v537_targeted_fixes.py",
]
for relative in release_test_files:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    if PREVIOUS not in text:
        raise RuntimeError(f"Nincs {PREVIOUS} release marker ebben a tesztben: {relative}")
    path.write_text(text.replace(PREVIOUS, VERSION), encoding="utf-8")

notes = (ROOT / "release-notes" / "v5.3.13.md").read_text(encoding="utf-8").rstrip() + "\n\n---\n"
release_notes = ROOT / "RELEASE_NOTES.md"
current = release_notes.read_text(encoding="utf-8")
if not current.startswith("# SleepMate 5.3.13\n"):
    release_notes.write_text(notes + current, encoding="utf-8")

Path(__file__).unlink()
