from pathlib import Path

p = Path('scripts/_v535_round3_patch.py')
text = p.read_text(encoding='utf-8')
start = '# ---------------------------------------------------------------------------\n# Requirements 12-13:'
end = '# ---------------------------------------------------------------------------\n# Browser fixture:'
i = text.find(start)
j = text.find(end, i + 1) if i >= 0 else -1
if i < 0 or j < 0:
    raise SystemExit('round3 requirements block markers not found')
replacement = '''# ---------------------------------------------------------------------------
# Requirements 12-13 are already product code from ca93f233. Preserve that
# implementation; add a stable acceptance id and normalize the remaining v534
# desktop grid override from four columns to the three actual measurement cards.
# ---------------------------------------------------------------------------
replace_once(
    'web/o2ring.js',
    '<div class="o2r-search-state"><span>Keresés állapota</span>',
    '<div id="o2rSearchState" class="o2r-search-state"><span>Keresés állapota</span>',
)
replace_once(
    'web/o2ring-v534.css',
    '.o2r-live-cards{grid-template-columns:repeat(4,minmax(0,1fr))!important;',
    '.o2r-live-cards{grid-template-columns:repeat(3,minmax(0,1fr))!important;',
)

'''
p.write_text(text[:i] + replacement + text[j:], encoding='utf-8')
print('round3 patch aligned with existing ca93f233 layout')
