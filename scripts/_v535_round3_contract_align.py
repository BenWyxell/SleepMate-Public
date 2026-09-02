from pathlib import Path

p = Path('tests/test_o2ring_v534_release_contract.py')
text = p.read_text(encoding='utf-8')

old_modes = '''def test_v534_dashboard_modes_focus_charts_and_night_card_are_present():
    js = read("web/o2ring.js")
    for marker in (
        "#focusViewBtn,#stackViewBtn,#o2rDailyBtn",
        "if(o)o.textContent='Oximetria'",
        "smO2FocusSpo2",
        "smO2FocusHr",
        "smO2FocusDual",
        "smStackO2Spo2",
        "smStackO2Hr",
        "smStackO2Dual",
        "smNightO2Card",
        "smDashboardO2V534",
    ):
        assert marker in js
    assert "Vissza" not in js
'''
new_modes = '''def test_v534_dashboard_modes_focus_charts_and_night_card_are_present():
    js = read("web/o2ring.js")
    for marker in (
        "#focusViewBtn,#stackViewBtn,#o2rDailyBtn",
        "if(o)o.textContent='Oximetria'",
        "O2_FOCUS_DEFS",
        "o2_spo2",
        "o2_hr",
        "card.className='overview-card sm-o2-focus-mini'",
        "card.onclick=()=>selectSignal(d.key)",
        "function o2CoreSignal(key)",
        "smStackO2Spo2",
        "smStackO2Hr",
        "smStackO2Dual",
        "smNightO2Card",
        "smDashboardO2V534",
    ):
        assert marker in js
    assert "smO2FocusSpo2" not in js
    assert "smO2FocusHr" not in js
    assert "smO2FocusDual" not in js
    assert "Vissza" not in js
'''
if text.count(old_modes) != 1:
    raise SystemExit('legacy Focus dashboard contract block not found exactly once')
text = text.replace(old_modes, new_modes, 1)

old_interaction = '''def test_v534_o2_chart_interaction_has_zoom_exact_crosshair_and_sync_groups():
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
        "syncGroup:'focus-o2'",
        "syncGroup:'recording'",
        "setHover(ctl.syncGroup,t)",
    ):
        assert marker in js
'''
new_interaction = '''def test_v534_o2_chart_interaction_has_zoom_exact_crosshair_and_sync_groups():
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
        "card.onclick=()=>selectSignal(d.key)",
        "state.mainSignal=data",
        "drawHeroBase()",
        "drawHeroOverlay()",
    ):
        assert marker in js
    assert "syncGroup:'focus-o2'" not in js
'''
if text.count(old_interaction) != 1:
    raise SystemExit('legacy Focus interaction contract block not found exactly once')
text = text.replace(old_interaction, new_interaction, 1)

p.write_text(text, encoding='utf-8')
print('legacy v5.3.4 contracts aligned to v5.3.5 Focus behavior')
