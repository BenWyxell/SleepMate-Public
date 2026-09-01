from pathlib import Path

root = Path(__file__).resolve().parents[1]
js = (root / 'web' / 'app-core.js').read_text(encoding='utf-8')
css = (root / 'web' / 'style.css').read_text(encoding='utf-8')

assert "document.body.appendChild(ov)" in js
assert "ov.style.left=`${r.left}px`" in js and "ov.style.top=`${r.top}px`" in js
assert "function trendMetaX" in js and "xPositions" in js
assert "trendIndexAtX" in js
assert "findIndex(r=>String(r.day)===String(row.day))" in js
assert "kind:'usage',rows,xPositions" in js
assert "kind:'events',rows,xPositions" in js
assert "position:fixed!important" in css and "z-index:1200!important" in css
print('PASS: v4.0.7 trend cursor geometry/date synchronization')
