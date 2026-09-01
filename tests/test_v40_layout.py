from pathlib import Path
root=Path(__file__).resolve().parents[1]
css=(root/'web'/'style.css').read_text(encoding='utf-8')
js=(root/'web'/'app-core.js').read_text(encoding='utf-8')
assert 'height:100vh;min-height:0;overflow:hidden' in css
assert '.content-shell{min-width:0;height:100vh;min-height:0;overflow-y:auto' in css
assert 'maskSizeOptions' in js and "normalizeFaqText('ResMed')" in js and "return uniqueSorted(['SW',...exact])" in js
print('PASS: v4.0 fixed sidebar + content-only scrolling + persistent ResMed SW size')
