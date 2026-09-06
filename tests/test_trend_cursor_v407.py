from pathlib import Path

root = Path(__file__).resolve().parents[1]
js = (root / 'web' / 'app-core.js').read_text(encoding='utf-8')
compact = ''.join(js.split())
css = (root / 'web' / 'style.css').read_text(encoding='utf-8')

assert "document.body.appendChild(ov)" in js
assert "ov.style.left=`${r.left}px`" in compact and "ov.style.top=`${r.top}px`" in compact
assert "function trendMetaX" in js and "xPositions" in js
assert "trendIndexAtX" in js
assert "findIndex(r=>String(r.day)===String(row.day))" in compact
assert "kind:'usage',rows,xPositions" in compact
assert "kind:'events',rows,xPositions" in compact
assert "position:fixed!important" in css and "z-index:1200!important" in css
print('PASS: v4.0.7 trend cursor geometry/date synchronization')
