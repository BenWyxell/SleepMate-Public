from pathlib import Path
root=Path(__file__).resolve().parents[1]
js=(root/'web'/'app-core.js').read_text(encoding='utf-8')
assert 'drawTherapyChangeMarkers' not in js
assert 'therapyMarkerEvents' not in js
assert 'Terápiaváltozás:' not in js
assert 'function renderTherapyTimeline' in js
assert 'function timelineIcon' in js
print('PASS: v4.2.0 trend therapy markers/tooltips removed; patient timeline preserved')
