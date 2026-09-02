from pathlib import Path

root = Path(__file__).resolve().parents[1]
browser = root / 'scripts/v534_browser_acceptance.py'
text = browser.read_text(encoding='utf-8')
old = "require(any(x.count(':') >= 2 and 'O₂' in x and 'HR' in x for x in overlay_text), f\"focus CPAP overlay lost hover values: {overlay_text}\")"
new = "require(any(x.count(':') >= 2 and 'SpO₂' in x and 'Pulzus' in x for x in overlay_text), f\"focus CPAP overlay lost localized SpO2/Pulse hover values: {overlay_text}\")"
if text.count(old) != 1:
    raise SystemExit(f'expected exactly one stale Focus hover assertion, got {text.count(old)}')
browser.write_text(text.replace(old, new, 1), encoding='utf-8')

matrix = root / 'tests/test_v535_user_acceptance_matrix.py'
m = matrix.read_text(encoding='utf-8')
needle = "    assert 'All Charts overlay lacks SpO2 right-axis labels' in BROWSER\n"
addition = needle + "    assert \"'SpO₂' in x and 'Pulzus' in x\" in BROWSER\n"
if m.count(needle) != 1:
    raise SystemExit(f'expected one point-6 matrix insertion marker, got {m.count(needle)}')
matrix.write_text(m.replace(needle, addition, 1), encoding='utf-8')
print('localized overlay hover acceptance patched')
