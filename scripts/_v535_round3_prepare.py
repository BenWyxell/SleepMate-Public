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
text = text[:i] + replacement + text[j:]

# The Focus replacement is embedded in a triple-single-quoted Python string.
# Use a triple-double-quoted Playwright expression so data-key quotes survive
# generation into scripts/v534_browser_acceptance.py.
old = '        page.wait_for_function("() => document.querySelector(\'.overview-card[data-key=\\"o2_spo2\\"]\') && document.querySelector(\'.overview-card[data-key=\\"o2_hr\\"]\')")'
new = '        page.wait_for_function("""() => document.querySelector(\'.overview-card[data-key="o2_spo2"]\') && document.querySelector(\'.overview-card[data-key="o2_hr"]\')""")'
if text.count(old) != 1:
    raise SystemExit(f'Focus browser quoting marker count={text.count(old)}')
text = text.replace(old, new, 1)

# Keep the original end marker as the single stack-mode click; do not emit a
# second identical click from the replacement body.
duplicate = '        page.locator("#stackViewBtn").click()\n\'\'\',\n)\n\n# All Charts:'
if text.count(duplicate) != 1:
    raise SystemExit(f'Focus duplicate stack-click marker count={text.count(duplicate)}')
text = text.replace(duplicate, "'''\n)\n\n# All Charts:", 1)

p.write_text(text, encoding='utf-8')
print('round3 patch aligned with existing ca93f233 layout and valid browser quoting')
