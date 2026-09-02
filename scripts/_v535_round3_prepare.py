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

# The old release contract still required the three custom Focus O2 canvases.
# That contract now contradicts the requested architecture: two ordinary mini
# cards selecting the ordinary core hero chart. Update only those two stale
# tests; keep every other v5.3.4 regression guard intact.
tp = Path('tests/test_o2ring_v534_release_contract.py')
t = tp.read_text(encoding='utf-8')
start1 = 'def test_v534_dashboard_modes_focus_charts_and_night_card_are_present():'
start2 = 'def test_v534_o2_chart_interaction_has_zoom_exact_crosshair_and_sync_groups():'
start3 = 'def test_v534_overlay_is_per_signal_timestamp_aligned_and_gap_aware():'
i1, i2, i3 = t.find(start1), t.find(start2), t.find(start3)
if min(i1, i2, i3) < 0 or not (i1 < i2 < i3):
    raise SystemExit('legacy Focus contract function markers not found')
block1 = '''def test_v534_dashboard_modes_focus_charts_and_night_card_are_present():
    js = read("web/o2ring.js")
    for marker in (
        "#focusViewBtn,#stackViewBtn,#o2rDailyBtn",
        "if(o)o.textContent='Oximetria'",
        "O2_FOCUS_DEFS",
        "o2_spo2",
        "o2_hr",
        "card.className='overview-card sm-o2-focus-mini'",
        "card.onclick=()=>selectSignal(d.key)",
        "smStackO2Spo2",
        "smStackO2Hr",
        "smStackO2Dual",
        "smNightO2Card",
        "smDashboardO2V534",
    ):
        assert marker in js
    focus = js[js.index("const O2_FOCUS_DEFS"):js.index("function ensureStackO2")]
    assert "smO2FocusSpo2" not in focus
    assert "smO2FocusHr" not in focus
    assert "smO2FocusDual" not in focus
    assert "Vissza" not in js


'''
block2 = '''def test_v534_o2_chart_interaction_has_zoom_exact_crosshair_and_sync_groups():
    js = read("web/o2ring.js")
    for marker in (
        "hour:'2-digit',minute:'2-digit',second:'2-digit'",
        "function nearest(rows,t)",
        "function bindChart(c,",
        "pointerdown",
        "pointermove",
        "dblclick",
        "syncGroup:'live'",
        "syncGroup:'daily-o2'",
        "syncGroup:'recording'",
        "setHover(ctl.syncGroup,t)",
        "function o2CoreSignal(key)",
        "loadMainSignal.__smO2",
        "o2CoreSignal(state.selectedSignal)",
        "card.onclick=()=>selectSignal(d.key)",
    ):
        assert marker in js


'''
t = t[:i1] + block1 + block2 + t[i3:]
tp.write_text(t, encoding='utf-8')
print('round3 patch aligned with applied layout, valid browser quoting, and current Focus architecture')
