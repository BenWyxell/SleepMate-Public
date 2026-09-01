from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/'web/index.html').read_text(encoding='utf-8')
css=(ROOT/'web/style.css').read_text(encoding='utf-8')
js=(ROOT/'web/app-core.js').read_text(encoding='utf-8')
sw=(ROOT/'web/service-worker.js').read_text(encoding='utf-8')
app=(ROOT/'app.py').read_text(encoding='utf-8')
assert '/style.css?v=5.0.0' in html and '/app.js?v=5.0.0' in html
assert 'width:288px!important' in css and 'pointer-events:none!important' in css
assert '#sidebar.mobile-open,body.mobile-nav-open #sidebar' in css
assert '#sidebarScrim.active,body.mobile-nav-open #sidebarScrim' in css
assert 'bindMobileDrawerGestures' in js and ("t.clientX>28" in js or "t.clientX>42" in js or "t.clientX>48" in js)
assert "window.addEventListener('pageshow',()=>closeMobileSidebar())" in js
assert "const CACHE='sleepmate-shell-v5.2.14-ss131'" in sw
assert "CODE_ASSETS.has(url.pathname)" in sw and "'/app.js'" in sw and "'/app-core.js'" in sw
assert 'APP_VERSION' in app and 'from cpap.version import APP_NAME, APP_VERSION' in app
print('PASS: current stable PWA drawer + versioned shell/network-first code assets')
