from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BROWSER = ROOT / 'scripts' / 'v534_browser_acceptance.py'
MATRIX = ROOT / 'tests' / 'test_v535_user_acceptance_matrix.py'

text = BROWSER.read_text(encoding='utf-8')
old = '''        page.locator('.overview-card[data-key="o2_spo2"]').click()\n        page.wait_for_function("() => state.selectedSignal==='o2_spo2' && state.mainSignal?.series?.length")\n        require(page.locator("#heroTitle").inner_text().strip() == "SpO₂", "SpO2 Focus mini did not open the normal hero chart")\n        page.evaluate("() => { window.__smAcceptanceO2.pathRecords=[]; drawHeroBase(); }")\n        hero_spo2_widths = page.evaluate("""() => window.__smAcceptanceO2.pathRecords.filter(x=>x.id==='heroBase' && ['#55d8ff','rgb(85, 216, 255)'].includes(String(x.style).toLowerCase()) && x.lines>0).map(x=>x.width)""")\n        require(bool(hero_spo2_widths) and max(hero_spo2_widths) <= 1.2, f"Focus SpO2 hero line is thicker than normal: {hero_spo2_widths}")\n'''
new = '''        page.locator('.overview-card[data-key="flow"]').click()\n        page.wait_for_function("() => state.selectedSignal==='flow' && state.mainSignal?.series?.length")\n        page.evaluate("() => { window.__smAcceptanceO2.pathRecords=[]; drawHeroBase(); }")\n        normal_hero_widths = page.evaluate("""() => window.__smAcceptanceO2.pathRecords.filter(x=>x.id==='heroBase' && ['#57c7ff','rgb(87, 199, 255)'].includes(String(x.style).toLowerCase()) && x.lines>0).map(x=>x.width)""")\n        require(bool(normal_hero_widths), f"normal CPAP hero line was not measurable: {normal_hero_widths}")\n\n        page.locator('.overview-card[data-key="o2_spo2"]').click()\n        page.wait_for_function("() => state.selectedSignal==='o2_spo2' && state.mainSignal?.series?.length")\n        require(page.locator("#heroTitle").inner_text().strip() == "SpO₂", "SpO2 Focus mini did not open the normal hero chart")\n        page.evaluate("() => { window.__smAcceptanceO2.pathRecords=[]; drawHeroBase(); }")\n        hero_spo2_widths = page.evaluate("""() => window.__smAcceptanceO2.pathRecords.filter(x=>x.id==='heroBase' && ['#55d8ff','rgb(85, 216, 255)'].includes(String(x.style).toLowerCase()) && x.lines>0).map(x=>x.width)""")\n        require(bool(hero_spo2_widths), f"Focus SpO2 hero line was not measurable: {hero_spo2_widths}")\n        normal_hero_width=max(normal_hero_widths)\n        spo2_hero_width=max(hero_spo2_widths)\n        require(abs(spo2_hero_width-normal_hero_width) <= 0.0001, f"Focus SpO2 hero line does not match normal hero line width: normal={normal_hero_widths}, SpO2={hero_spo2_widths}")\n'''
if text.count(old) != 1:
    raise SystemExit(f'expected exactly one request-5 Edge block, found {text.count(old)}')
BROWSER.write_text(text.replace(old, new, 1), encoding='utf-8')

matrix = MATRIX.read_text(encoding='utf-8')
addition = '''\n\ndef test_request_05_edge_compares_o2_hero_to_real_core_hero_width():\n    assert "normal_hero_widths" in BROWSER\n    assert "spo2_hero_width" in BROWSER\n    assert "Focus SpO2 hero line does not match normal hero line width" in BROWSER\n    assert "Focus SpO2 hero line is thicker than normal" not in BROWSER\n'''
if 'test_request_05_edge_compares_o2_hero_to_real_core_hero_width' not in matrix:
    MATRIX.write_text(matrix.rstrip() + addition, encoding='utf-8')
