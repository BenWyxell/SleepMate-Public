from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cpap.version import APP_VERSION, BUILD_CHANNEL, UPDATE_MANIFEST_FORMAT


def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def git_commit() -> str | None:
    try:
        return subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL,timeout=5).strip() or None
    except Exception:
        return None


def main():
    ap=argparse.ArgumentParser(description='SleepMate GitHub Release csomag + manifest')
    ap.add_argument('--out',default=str(ROOT.parent/'release'))
    ap.add_argument('--min-version',default=APP_VERSION)
    args=ap.parse_args()
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    commit=git_commit()
    build_info={
        'version':APP_VERSION,
        'build_id':f"{APP_VERSION}+{commit[:8] if commit else 'local'}",
        'git_commit':commit,
        'channel':BUILD_CHANNEL,
        'built_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'source':'full-source-build',
    }
    asset=out/f'SleepMate_v{APP_VERSION}.zip'
    excluded={'private','.git','__pycache__','.pytest_cache'}
    with zipfile.ZipFile(asset,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        prefix=Path(f'SleepMate_v{APP_VERSION}')
        for p in ROOT.rglob('*'):
            rel=p.relative_to(ROOT)
            if any(part in excluded for part in rel.parts):continue
            if rel.as_posix()=='build_info.json':continue
            if p.is_file():z.write(p,(prefix/rel).as_posix())
        z.writestr((prefix/'build_info.json').as_posix(),json.dumps(build_info,ensure_ascii=False,indent=2))
    manifest={
        'format':UPDATE_MANIFEST_FORMAT,
        'version':APP_VERSION,
        'min_version':args.min_version,
        'asset':asset.name,
        'sha256':sha256(asset),
        'build_id':build_info['build_id'],
        'git_commit':commit,
        'release_contract':1,
    }
    mp=out/'sleepmate-update.json';mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(asset);print(mp);print(manifest['sha256'])

if __name__=='__main__':main()
