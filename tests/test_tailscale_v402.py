from pathlib import Path

root = Path(__file__).resolve().parents[1]
app = (root / 'app.py').read_text(encoding='utf-8')
html = (root / 'web' / 'index.html').read_text(encoding='utf-8')
# Integrated release builds package app-core.js as the primary app.js. Keep the
# regression test aligned with the code users actually receive while retaining
# compatibility with branches that still use a monolithic source app.js.
core_js = root / 'web' / 'app-core.js'
js = (core_js if core_js.exists() else root / 'web' / 'app.js').read_text(encoding='utf-8')
req = (root / 'requirements.txt').read_text(encoding='utf-8').lower()

assert '"tailscale_auto_serve": False' in app
assert 'save_config({"tailscale_auto_serve": True})' in app
assert 'save_config({"tailscale_auto_serve": False})' in app
assert '_restore_tailscale_serve' in app
assert '/api/remote/tailscale/qr' in app
assert 'import qrcode' in app
assert 'id="tailscaleQr"' in html
assert 'id="tailscaleQrModal"' in html
assert 'openTailscaleQr' in js
assert "$('#tailscaleQr').disabled=!(t.serve_active&&t.url)" in js
assert 'qrcode>=' in req
print('PASS: v4.0.2 Tailscale auto-restore + local QR')
