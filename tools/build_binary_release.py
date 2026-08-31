from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def version() -> str:
    ns: dict[str, object] = {}
    exec((ROOT / 'cpap' / 'version.py').read_text(encoding='utf-8'), ns)
    return str(ns['APP_VERSION'])


def git_commit() -> str | None:
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--program-dir', default=str(ROOT / 'dist' / 'SleepMate'))
    ap.add_argument('--out-dir', default=str(ROOT / 'release'))
    ap.add_argument('--min-version', default='4.2.2')
    args = ap.parse_args()

    program = Path(args.program_dir).resolve()
    out = Path(args.out_dir).resolve(); out.mkdir(parents=True, exist_ok=True)
    if not (program / 'SleepMate.exe').is_file():
        raise SystemExit('SleepMate.exe missing from program directory')
    if not (program / 'SleepMateUpdater.exe').is_file():
        raise SystemExit('SleepMateUpdater.exe missing from program directory')

    ver = version()
    commit = git_commit()
    build_id = f'sleepmate-{ver}-{(commit or "local")[:12]}'
    build = {
        'version': ver,
        'build_id': build_id,
        'git_commit': commit,
        'channel': 'stable',
        'packaging': 'windows-onedir-x64',
        'built_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    }
    (program / 'build_info.json').write_text(json.dumps(build, ensure_ascii=False, indent=2), encoding='utf-8')
    shutil.copy2(program / 'build_info.json', ROOT / 'build_info.json')

    asset_name = f'SleepMate_v{ver}_windows_x64.zip'
    asset = out / asset_name
    top = f'SleepMate_v{ver}'
    with zipfile.ZipFile(asset, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for p in sorted(program.rglob('*')):
            if p.is_file():
                zf.write(p, (Path(top) / p.relative_to(program)).as_posix())
    digest = sha256(asset)
    manifest = {
        'format': 'sleepmate-update',
        'version': ver,
        'min_version': args.min_version,
        'asset': asset_name,
        'sha256': digest,
        'package_type': 'windows-x64-program-tree',
        'build_id': build_id,
        'git_commit': commit,
        'requires_installer': False,
    }
    manifest_path = out / 'sleepmate-update.json'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'asset': str(asset), 'manifest': str(manifest_path), 'sha256': digest, 'build_id': build_id}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
