import re
from pathlib import Path

from cpap.version import APP_VERSION

ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/'web/index.html').read_text(encoding='utf-8')
css=(ROOT/'web/style.css').read_text(encoding='utf-8')
js=(ROOT/'web/app-core.js').read_text(encoding='utf-8')
js_compact=''.join(js.split())
sw=(ROOT/'web/service-worker.js').read_text(encoding='utf-8')
app=(ROOT/'app.py').read_text(encoding='utf-8')
assert f'/style.css?v={APP_VERSION}' in html and f'/app-core.js?v={APP_VERSION}' in html
assert f'/app.js?v={APP_VERSION}' not in html
assert 'width:288px!important' in css and 'pointer-events:none!important' in css
assert '#sidebar.mobile-open,body.mobile-nav-open #sidebar' in css
assert '#sidebarScrim.active,body.mobile-nav-open #sidebarScrim' in css
assert 'bindMobileDrawerGestures' in js and ("t.clientX>28" in js_compact or "t.clientX>42" in js_compact or "t.clientX>48" in js_compact)
assert "window.addEventListener('pageshow',()=>closeMobileSidebar())" in js_compact
cache=re.search(r"const SHELL_CACHE='([^']+)'",sw)
assert cache and cache.group(1).startswith(f'sleepmate-shell-v{APP_VERSION}')
assert "precacheShellAtomic" in sw and "SLEEPMATE_SHELL_READY" in sw
assert "await self.clients.claim()" in sw and "client.navigate(client.url)" not in sw
assert "SLEEPMATE_CLIENT_READY" not in sw and "cleanupStaleSleepMateCaches" in sw
activate=sw.split("self.addEventListener('activate'",1)[1].split("function backendUnavailable",1)[0]
assert "await cleanupStaleSleepMateCaches()" in activate
assert "event.respondWith(navigationFallback(request))" in sw and "event.respondWith(currentCodeAsset(url.pathname))" in sw
assert "CODE_ASSETS.has(url.pathname)" in sw and "'/app.js'" not in sw and "'/app-core.js'" in sw
assert 'APP_VERSION' in app and 'from cpap.version import APP_NAME, APP_VERSION' in app
print('PASS: current stable PWA drawer + atomic generation handover/current-generation code assets')
