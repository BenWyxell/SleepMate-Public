from pathlib import Path
root=Path(__file__).resolve().parents[1]
js=(root/'web/app-core.js').read_text(encoding='utf-8')
compact=''.join(js.split())
html=(root/'web/index.html').read_text(encoding='utf-8')
sw=(root/'web/service-worker.js').read_text(encoding='utf-8')
assert 'id="reportPdfSave"' in html and 'Mentés a Fájlokba' in html
assert 'pendingReportPdf' in js
assert 'navigator.share' in js and 'navigator.canShare' in js
assert 'newFile([blob],name' in compact
assert 'isApplePwa()' in js
assert 'PDF elkészült. Koppints a „Mentés a Fájlokba” gombra.' in js
assert '/style.css?v=5.3.27' in html and '/app-core.js?v=5.3.27' in html
assert "sleepmate-shell-v5.3.27" in sw
print('PASS: current iOS/PWA PDF save-to-Files flow')
