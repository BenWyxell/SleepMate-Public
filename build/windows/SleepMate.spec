# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import os
import re
import shutil

ROOT = Path(SPECPATH).resolve().parents[1]

version_source = (ROOT / 'cpap' / 'version.py').read_text(encoding='utf-8')
version_match = re.search(r'^APP_VERSION\s*=\s*"(\d+\.\d+\.\d+)"\s*$', version_source, re.MULTILINE)
if not version_match:
    raise RuntimeError('Cannot read semantic APP_VERSION from cpap/version.py')
APP_VERSION = version_match.group(1)
BUILD_ID = re.sub(r'[^0-9A-Za-z._-]+', '-', os.environ.get('GITHUB_RUN_NUMBER', 'local')).strip('-') or 'local'
FRONTEND_ID = f'{APP_VERSION}-b{BUILD_ID}'

WEB_SOURCE = ROOT / 'web'
WEB_GENERATED = ROOT / 'build' / 'windows' / 'web-generated'
if WEB_GENERATED.exists():
    shutil.rmtree(WEB_GENERATED)
shutil.copytree(WEB_SOURCE, WEB_GENERATED)

# Package the exact web tree exercised in source-mode acceptance. The build
# changes identity metadata only; it never generates loaders or rewrites
# application behaviour.
index_path = WEB_GENERATED / 'index.html'
index_text = index_path.read_text(encoding='utf-8')
index_text, count = re.subn(
    r'<meta name="sleepmate-build-id" content="[^"]+">',
    f'<meta name="sleepmate-build-id" content="{FRONTEND_ID}">',
    index_text,
    count=1,
)
if count != 1:
    raise RuntimeError('index.html is missing canonical build identity metadata')
index_path.write_text(index_text, encoding='utf-8')

sw_path = WEB_GENERATED / 'service-worker.js'
sw = sw_path.read_text(encoding='utf-8')
for name, value in (
    ('SHELL_CACHE', f'sleepmate-shell-v{FRONTEND_ID}'),
    ('API_CACHE', f'sleepmate-api-v{FRONTEND_ID}'),
    ('RELEASE_VERSION', APP_VERSION),
    ('BUILD_ID', FRONTEND_ID),
):
    sw, count = re.subn(
        rf"const {name}='[^']+';",
        f"const {name}='{value}';",
        sw,
        count=1,
    )
    if count != 1:
        raise RuntimeError(f'service-worker.js is missing canonical {name}')
sw_path.write_text(sw, encoding='utf-8')

hiddenimports = [
    'pystray._win32',
    'groq',
    'pywebpush',
    'qrcode.image.pil',
]

a = Analysis(
    [str(ROOT / 'sleepmate_main.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(WEB_GENERATED), 'web'),
        (str(ROOT / 'build_info.json'), '.'),
        (str(ROOT / 'SleepMate.ico'), '.'),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SleepMate',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / 'SleepMate.ico'),
    version=str(ROOT / 'build' / 'windows' / 'version_info.generated.txt'),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='SleepMate',
)
