from pathlib import Path

root = Path(__file__).resolve().parents[1]
browser = root / 'scripts/v534_browser_acceptance.py'
text = browser.read_text(encoding='utf-8')
old = "require('93,0%' in o2_stats['spo2'][1] or '93.0%' in o2_stats['spo2'][1], f\"Daily Statistics missing minimum SpO2: {o2_stats}\")"
new = "require('90,0%' in o2_stats['spo2'][1] or '90.0%' in o2_stats['spo2'][1], f\"Daily Statistics did not use refreshed minimum SpO2: {o2_stats}\")"
if text.count(old) != 1:
    raise SystemExit(f'expected one stale Daily Statistics minimum assertion, got {text.count(old)}')
browser.write_text(text.replace(old, new, 1), encoding='utf-8')

matrix = root / 'tests/test_v535_user_acceptance_matrix.py'
m = matrix.read_text(encoding='utf-8')
needle = "    assert 'Daily Statistics missing pulse min/median/max' in BROWSER\n"
addition = needle + "    assert 'Daily Statistics did not use refreshed minimum SpO2' in BROWSER\n"
if m.count(needle) != 1:
    raise SystemExit(f'expected one point-11 matrix insertion marker, got {m.count(needle)}')
matrix.write_text(m.replace(needle, addition, 1), encoding='utf-8')
print('refreshed Daily Statistics acceptance patched')
