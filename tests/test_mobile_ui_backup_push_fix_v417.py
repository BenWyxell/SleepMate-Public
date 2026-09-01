from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'web/app-core.js').read_text(encoding='utf-8')
HTML=(ROOT/'web/index.html').read_text(encoding='utf-8')
CSS=(ROOT/'web/style.css').read_text(encoding='utf-8')
SW=(ROOT/'web/service-worker.js').read_text(encoding='utf-8')
BACKEND=(ROOT/'app.py').read_text(encoding='utf-8')
PUSH=(ROOT/'cpap/push_service.py').read_text(encoding='utf-8')
SERVICES=(ROOT/'cpap/services.py').read_text(encoding='utf-8')

assert 'id="settingsCategorySelect"' in HTML
assert '.settings-category-picker' in CSS and '.settings-inner-tabs{display:none!important}' in CSS
assert 'id="aiAnalysisPickerButton"' in HTML and 'id="aiAnalysisSheet"' in HTML
assert 'data-ai-mobile-choice="comparison"' in HTML
assert '.ai-analysis-actions{display:none!important}' in CSS
assert 'font-size:7px!important' in CSS
assert 't.clientX<=48' in APP
assert "isDailyRoute()" in APP
assert "if(!isOpen&&t.clientX>48)return" in APP
assert "{endpoint:sub.endpoint}" in APP
assert 'endpoint=endpoint' in BACKEND
assert 'con.close()' in PUSH
assert 'def maintenance(self)' in PUSH
assert "_looks_like_sqlite" in SERVICES and "push.sqlite3" in SERVICES
assert 'sleepmate-shell-v5.2.14-ss131' in SW
print('PASS: compact settings/AI UI, gesture arbitration, targeted push test and push backup fix present')
