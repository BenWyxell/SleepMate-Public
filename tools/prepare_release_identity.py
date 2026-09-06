from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".py", ".js", ".css", ".html"}
SYNC_ROOTS = (ROOT / "web", ROOT / "scripts", ROOT / "tests")
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def current_app_version() -> str:
    version_file = read(ROOT / "cpap" / "version.py")
    match = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', version_file, flags=re.MULTILINE)
    if not match:
        raise SystemExit("APP_VERSION not found in cpap/version.py")
    return match.group(1)


def sync_release_literals(previous: str, current: str) -> list[str]:
    changed: list[str] = []
    for root in SYNC_ROOTS:
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            text = read(path)
            if previous not in text:
                continue
            updated = text.replace(previous, current)
            if updated != text:
                write(path, updated)
                changed.append(path.relative_to(ROOT).as_posix())
    return changed


def sync_release_notes(current: str) -> bool:
    notes_file = ROOT / "release-notes" / f"v{current}.md"
    if not notes_file.is_file():
        raise SystemExit(f"Missing release note file: {notes_file.relative_to(ROOT)}")

    source = read(notes_file).strip()
    expected_header = f"# SleepMate {current}"
    if not source.startswith(expected_header):
        raise SystemExit(f"{notes_file.relative_to(ROOT)} must start with {expected_header}")

    canonical = ROOT / "RELEASE_NOTES.md"
    existing = read(canonical)
    if expected_header in existing:
        return False
    write(canonical, source + "\n\n---\n\n" + existing)
    return True


def verify(previous: str, current: str) -> None:
    if current_app_version() != current:
        raise SystemExit("APP_VERSION changed unexpectedly while preparing the release")

    stale: list[str] = []
    for root in SYNC_ROOTS:
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if previous in read(path):
                stale.append(path.relative_to(ROOT).as_posix())
    if stale:
        raise SystemExit("Previous release identity remains in runtime/test sources: " + ", ".join(stale))

    worker = (ROOT / "web" / "service-worker.js").read_bytes()
    base = (ROOT / "web" / "service-worker-v508-base.js").read_bytes()
    if worker != base:
        raise SystemExit("service-worker.js and service-worker-v508-base.js diverged during release sync")

    for marker in (
        f"sleepmate-shell-v{current}",
        f"sleepmate-api-v{current}",
        f"RELEASE_VERSION='{current}'",
    ):
        if marker not in read(ROOT / "web" / "service-worker.js"):
            raise SystemExit(f"Missing current release marker in service worker: {marker}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize SleepMate current-release identity before an automated release.")
    parser.add_argument("--previous", required=True)
    parser.add_argument("--current", required=True)
    args = parser.parse_args()

    previous = args.previous.strip().removeprefix("v")
    current = args.current.strip().removeprefix("v")
    if not SEMVER.fullmatch(previous) or not SEMVER.fullmatch(current):
        raise SystemExit("--previous and --current must be canonical X.Y.Z versions")
    if previous == current:
        raise SystemExit("Previous and current versions must differ")
    if current_app_version() != current:
        raise SystemExit(f"cpap/version.py APP_VERSION is {current_app_version()}, expected {current}")

    changed = sync_release_literals(previous, current)
    notes_changed = sync_release_notes(current)
    verify(previous, current)

    print(f"Release identity synchronized: {previous} -> {current}")
    for path in changed:
        print(f"  updated: {path}")
    if notes_changed:
        print("  updated: RELEASE_NOTES.md")
    print(f"Changed runtime/test files: {len(changed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
