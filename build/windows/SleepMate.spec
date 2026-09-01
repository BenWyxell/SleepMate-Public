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

# For integration test builds start from the exact PWA worker that shipped with
# the known-good v5.0.8 frontend. Extra SleepSync/v5.3 assets are added below,
# but the navigation/cache algorithm itself stays identical to that release.
proven_sw = WEB_GENERATED / 'service-worker-v508-base.js'
if proven_sw.exists():
    shutil.copy2(proven_sw, WEB_GENERATED / 'service-worker.js')


def replace_exact(relative_path, pattern, replacement, expected=1):
    path = WEB_GENERATED / relative_path
    text = path.read_text(encoding='utf-8')
    updated, count = re.subn(pattern, replacement, text)
    if count != expected:
        raise RuntimeError(
            f'{relative_path}: expected {expected} frontend version replacement(s), got {count} for {pattern!r}'
        )
    path.write_text(updated, encoding='utf-8')


def replace_literal(relative_path, old, new, expected=1):
    path = WEB_GENERATED / relative_path
    text = path.read_text(encoding='utf-8')
    count = text.count(old)
    if count != expected:
        raise RuntimeError(
            f'{relative_path}: expected {expected} literal replacement(s), got {count} for {old!r}'
        )
    path.write_text(text.replace(old, new, expected), encoding='utf-8')


# app-core.js is byte-for-byte the original v5.0.8 monolithic app.js. Patch its
# visible version first; packaged builds restore it as the primary app.js.
sidebar_app_js = 'app-core.js' if (WEB_GENERATED / 'app-core.js').exists() else 'app.js'
replace_exact(
    sidebar_app_js,
    r"if\(\$\('#sidebarVersion'\)\) \$\('#sidebarVersion'\)\.textContent='v\d+\.\d+\.\d+';",
    f"if($('#sidebarVersion')) $('#sidebarVersion').textContent='v{APP_VERSION}';",
)

# Core behaviour fixes are deliberately applied to the packaged copy while the
# frozen v5.0.8 source blob stays available as a known-good reference.
replace_literal(
    sidebar_app_js,
    "$('#openLatestSleep').onclick=()=>{if(state.latestDay)navigate('dashboard',state.latestDay)};",
    "$('#openLatestSleep').onclick=()=>{const day=state.latestDay||state.currentDay||state.days[0];if(!day)return;const next=`#dashboard/${day}`,reroute=()=>{const fn=typeof window.route==='function'?window.route:route;fn()};if(standalonePwa()){history.replaceState({sleepmate:true},'',next);reroute()}else if(location.hash===next)reroute();else location.hash=next};",
)
replace_literal(
    sidebar_app_js,
    "d.average_usage_seconds?d.average_usage_seconds/60:null",
    "d.average_usage_seconds==null?null:d.average_usage_seconds/60",
)
replace_literal(
    sidebar_app_js,
    "ind.classList.add('refreshing');ind.querySelector('b').textContent='Adatok ellenőrzése…';refreshData()",
    "ind.classList.add('refreshing');ind.querySelector('b').textContent='Adatok ellenőrzése…';setTimeout(()=>{if(state.pullRefreshing)resetPullRefreshUi()},1100);refreshData()",
)

replace_exact(
    'index.html',
    r'<strong id="sidebarVersion">v[^<]+</strong>',
    f'<strong id="sidebarVersion">v{APP_VERSION}</strong>',
)
replace_exact(
    'index.html',
    r'href="/style\.css\?v=\d+\.\d+\.\d+"',
    f'href="/style.css?v={APP_VERSION}"',
)
replace_exact(
    'index.html',
    r'src="/app\.js\?v=\d+\.\d+\.\d+"',
    f'src="/app.js?v={APP_VERSION}"',
)
replace_exact(
    'service-worker.js',
    r'sleepmate-shell-v\d+\.\d+\.\d+',
    f'sleepmate-shell-v{APP_VERSION}',
    expected=2,
)
replace_exact(
    'service-worker.js',
    r'sleepmate-api-v\d+\.\d+\.\d+',
    f'sleepmate-api-v{APP_VERSION}',
)
replace_exact(
    'service-worker.js',
    r'/style\.css\?v=\d+\.\d+\.\d+',
    f'/style.css?v={APP_VERSION}',
)
replace_exact(
    'service-worker.js',
    r'/app\.js\?v=\d+\.\d+\.\d+',
    f'/app.js?v={APP_VERSION}',
)

# ---------------------------------------------------------------------------
# Mobile/PWA stability contract for SleepSync integration builds
# ---------------------------------------------------------------------------
core_app = WEB_GENERATED / 'app-core.js'
engine_app = WEB_GENERATED / 'app-engine119.js'
if core_app.exists() and engine_app.exists():
    shutil.copy2(core_app, WEB_GENERATED / 'app.js')

    engine_text = engine_app.read_text(encoding='utf-8')
    start_marker = "  core.onload=()=>{\n"
    end_marker = "\n  };\n  document.head.appendChild(core);\n})();"
    if start_marker not in engine_text or end_marker not in engine_text:
        raise RuntimeError('Cannot extract SleepSync integration body from frozen #119 engine')
    integration_body = engine_text.split(start_marker, 1)[1].rsplit(end_marker, 1)[0]
    bridge_text = (
        "(function(){\n"
        "  const style=document.createElement('link');\n"
        "  style.rel='stylesheet';\n"
        f"  style.href='/sleepsync.css?v={FRONTEND_ID}';\n"
        "  document.head.appendChild(style);\n\n"
        + integration_body
        + "\n})();\n"
    )
    (WEB_GENERATED / 'sleepsync-integration.js').write_text(bridge_text, encoding='utf-8')

    bootstrap_text = f"""(function(){{
  'use strict';
  const ID='{FRONTEND_ID}';
  let started=false;
  let attempts=0;
  function loadScript(src,onload){{
    const s=document.createElement('script');
    s.src=src;s.async=false;
    if(onload)s.onload=onload;
    s.onerror=()=>{{try{{fetch('/api/mobile-boot',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{stage:'script-error',build:ID,details:{{src}}}}),keepalive:true,cache:'no-store'}})}}catch{{}}}};
    document.head.appendChild(s);
  }}
  function start(){{
    if(started)return;
    attempts++;
    const shell=document.querySelector('.hidden-until-ready');
    const coreReady=!!shell&&shell.classList.contains('ready')&&typeof window.route==='function'&&typeof window.navigate==='function';
    if(!coreReady){{
      if(attempts<600){{setTimeout(start,50);return;}}
      try{{fetch('/api/mobile-boot',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{stage:'sleepsync-deferred-timeout',build:ID,details:{{shell_class:shell?.className||'',route:typeof window.route,navigate:typeof window.navigate}}}}),keepalive:true,cache:'no-store'}})}}catch{{}}
      return;
    }}
    started=true;
    try{{fetch('/api/mobile-boot',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{stage:'core-ready-before-sleepsync',build:ID,details:{{shell_class:shell.className,hash:location.hash}}}}),keepalive:true,cache:'no-store'}})}}catch{{}}
    loadScript('/sleepsync-integration.js?v='+ID,()=>loadScript('/sleepsync-polish.js?v='+ID));
  }}
  setTimeout(start,0);
}})();
"""
    (WEB_GENERATED / 'sleepsync-bootstrap.js').write_text(bootstrap_text, encoding='utf-8')

    diag_path = WEB_GENERATED / 'mobile-boot-diagnostics.js'
    if not diag_path.exists():
        raise RuntimeError('mobile-boot-diagnostics.js is missing')
    diag_text = diag_path.read_text(encoding='utf-8').replace('__SLEEPMATE_FRONTEND_ID__', FRONTEND_ID)
    diag_path.write_text(diag_text, encoding='utf-8')

    index_path = WEB_GENERATED / 'index.html'
    index_text = index_path.read_text(encoding='utf-8')
    old_script = f'<script src="/app.js?v={APP_VERSION}"></script>'
    new_scripts = (
        f'<script src="/mobile-boot-diagnostics.js?v={FRONTEND_ID}"></script>\n'
        f'<script src="/app.js?v={FRONTEND_ID}"></script>\n'
        f'<script src="/sleepsync-bootstrap.js?v={FRONTEND_ID}"></script>'
    )
    if index_text.count(old_script) != 1:
        raise RuntimeError('index.html does not contain exactly one primary app.js script')
    index_text = index_text.replace(old_script, new_scripts, 1)
    index_text = index_text.replace(f'/style.css?v={APP_VERSION}', f'/style.css?v={FRONTEND_ID}', 1)

    style_link = f'<link rel="stylesheet" href="/style.css?v={FRONTEND_ID}">'
    aurora_link = f'<link rel="stylesheet" href="/sleepmate-aurora.css?v={FRONTEND_ID}">'
    if index_text.count(style_link) != 1:
        raise RuntimeError('generated index does not contain exactly one versioned style.css link')
    index_text = index_text.replace(style_link, style_link + '\n  ' + aurora_link, 1)
    index_path.write_text(index_text, encoding='utf-8')

    # Give every portable workflow run its own PWA generation while preserving
    # the exact proven worker algorithm. v5.3 UI/O2 assets are always cached, but
    # the O2Ring controller only activates them when the user enables the feature.
    sw_path = WEB_GENERATED / 'service-worker.js'
    sw = sw_path.read_text(encoding='utf-8')
    sw = sw.replace(f'sleepmate-shell-v{APP_VERSION}', f'sleepmate-shell-v{APP_VERSION}-b{BUILD_ID}')
    sw = sw.replace(f'sleepmate-api-v{APP_VERSION}', f'sleepmate-api-v{APP_VERSION}-b{BUILD_ID}')
    sw = sw.replace(f"'/style.css?v={APP_VERSION}'", f"'/style.css?v={FRONTEND_ID}'")
    sw = sw.replace(f"'/app.js?v={APP_VERSION}'", f"'/app.js?v={FRONTEND_ID}'")
    app_entry = f"'/app.js?v={FRONTEND_ID}'"
    extra_shell = (
        app_entry
        + f",'/sleepmate-aurora.css?v={FRONTEND_ID}'"
        + f",'/sleepmate-v530.css?v={FRONTEND_ID}'"
        + f",'/sleepmate-v530.js?v={FRONTEND_ID}'"
        + f",'/o2ring.css?v={FRONTEND_ID}'"
        + f",'/o2ring.js?v={FRONTEND_ID}'"
        + f",'/o2ring-report-ui.js?v={FRONTEND_ID}'"
        + f",'/mobile-boot-diagnostics.js?v={FRONTEND_ID}'"
        + f",'/sleepsync-bootstrap.js?v={FRONTEND_ID}'"
        + f",'/sleepsync-integration.js?v={FRONTEND_ID}'"
        + f",'/sleepsync-polish.js?v={FRONTEND_ID}'"
        + f",'/sleepsync.css?v={FRONTEND_ID}'"
        + f",'/sleepsync-polish.css?v={FRONTEND_ID}'"
        + f",'/sleepsync-notice.css?v={FRONTEND_ID}'"
    )
    if app_entry not in sw:
        raise RuntimeError('proven service worker shell does not contain packaged app.js')
    sw = sw.replace(app_entry, extra_shell, 1)
    old_code = "const codeAsset=['/style.css','/app.js','/sleepmate-sleep.js','/sleepmate-sleep-v523.js','/sleepmate-chart-v523.js','/sleepmate-sleep-v524.js','/sleepmate-sleep-refresh-v5212.js','/manifest.webmanifest'].includes(url.pathname);"
    new_code = "const codeAsset=['/style.css','/sleepmate-aurora.css','/sleepmate-v530.css','/sleepmate-v530.js','/o2ring.css','/o2ring.js','/o2ring-report-ui.js','/app.js','/mobile-boot-diagnostics.js','/sleepsync-bootstrap.js','/sleepsync-integration.js','/sleepsync-polish.js','/sleepsync.css','/sleepsync-polish.css','/sleepsync-notice.css','/sleepmate-sleep.js','/sleepmate-sleep-v523.js','/sleepmate-chart-v523.js','/sleepmate-sleep-v524.js','/sleepmate-sleep-refresh-v5212.js','/manifest.webmanifest'].includes(url.pathname);"
    if old_code not in sw:
        raise RuntimeError('proven service worker code-asset rule changed unexpectedly')
    sw = sw.replace(old_code, new_code, 1)
    sw_path.write_text(sw, encoding='utf-8')

    sleepsync_css = WEB_GENERATED / 'sleepsync.css'
    css_text = sleepsync_css.read_text(encoding='utf-8').replace('v=127', f'v={FRONTEND_ID}')
    sleepsync_css.write_text(css_text, encoding='utf-8')

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
