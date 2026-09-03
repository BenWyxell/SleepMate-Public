from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cpap.version import APP_VERSION, UPDATE_MANIFEST_FORMAT


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
            stderr=subprocess.DEVNULL, timeout=5,
        ).strip() or None
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the canonical MSI update manifest.")
    parser.add_argument("--msi", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--min-version", default="4.2.2")
    args = parser.parse_args()

    msi = Path(args.msi).resolve()
    expected_name = f"SleepMate_Setup_v{APP_VERSION}.msi"
    if not msi.is_file() or msi.name != expected_name:
        raise SystemExit(f"Expected exact MSI release asset: {expected_name}")
    with msi.open("rb") as source:
        if source.read(8) != bytes.fromhex("D0CF11E0A1B11AE1"):
            raise SystemExit("Release asset is not an MSI container")

    manifest = {
        "format": UPDATE_MANIFEST_FORMAT,
        "version": APP_VERSION,
        "min_version": args.min_version,
        "asset": expected_name,
        "sha256": sha256(msi),
        "package_type": "windows-msi-x64",
        "git_commit": git_commit(),
        "requires_installer": True,
    }
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(output), "asset": expected_name, "sha256": manifest["sha256"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
