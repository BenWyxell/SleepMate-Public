from pathlib import Path

browser = Path('scripts/v534_browser_acceptance.py')
text = browser.read_text(encoding='utf-8')
bad = '          const liveRows = [\n          const liveRows = [\n'
good = '          const liveRows = [\n'
if text.count(bad) != 1:
    raise SystemExit(f'expected exactly one duplicated liveRows declaration, found {text.count(bad)}')
text = text.replace(bad, good, 1)
browser.write_text(text, encoding='utf-8')

matrix = Path('tests/test_v535_user_acceptance_matrix.py')
t = matrix.read_text(encoding='utf-8')
addition = '''\n\ndef test_browser_acceptance_fixture_has_single_live_rows_declaration():\n    assert BROWSER.count('const liveRows = [') == 1\n'''
if 'test_browser_acceptance_fixture_has_single_live_rows_declaration' not in t:
    t += addition
matrix.write_text(t, encoding='utf-8')
print('browser fixture declaration fixed and guarded')
