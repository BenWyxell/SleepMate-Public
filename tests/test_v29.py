from pathlib import Path
import json
root = Path(__file__).resolve().parents[1]
html = (root/'web'/'index.html').read_text(encoding='utf-8')
js = (root/'web'/'app.js').read_text(encoding='utf-8')
app = (root/'app.py').read_text(encoding='utf-8')
prompt = (root/'cpap'/'ai_payload.py').read_text(encoding='utf-8')
tray = (root/'sleepmate_tray.pyw').read_text(encoding='utf-8')
req = (root/'requirements.txt').read_text(encoding='utf-8')
cfg = json.loads((root/'config.json').read_text(encoding='utf-8'))
assert 'Naplók ürítése' in html
assert '/api/logs/clear' in app and 'persistent_log.clear()' in app
assert 'start_with_windows' in app and 'tray_notifications' in app
assert 'SleepMate.vbs' in tray and 'SD-kártya keresése és beolvasása' in tray
assert 'pystray' in req.lower() and 'Pillow' in req
assert 'ÉÉÉÉ.HH.NN.' in prompt
assert 'formatAiDate' in js and 'friendlyAiTitle' in js
assert cfg['tray_notifications'] is True and cfg['start_with_windows'] is False
print('PASS: v2.9 tray app + no-console launch + Hungarian AI title/date + unified log clear')
