from pathlib import Path

p = Path('tests/test_o2ring_v534_release_contract.py')
text = p.read_text(encoding='utf-8')
old = '''    assert "function fixLatestLoading()" in bootstrap\n    assert "function syncLatestSessionCard()" in bootstrap\n    assert "latest.sessions" in bootstrap\n    assert "status.textContent='—'" in bootstrap\n    assert "Befejezve" not in bootstrap\n'''
new = '''    assert "function fixLatestLoading()" in bootstrap\n    assert "function syncLatestSessionCard()" in bootstrap\n    assert "latest?.summary||latest" in bootstrap\n    assert "latestDuration(summary)" in bootstrap\n    assert "summary.sessions" in bootstrap\n    assert "status.textContent='—'" in bootstrap\n    assert "Befejezve" not in bootstrap\n'''
if text.count(old) != 1:
    raise SystemExit('legacy latest-session contract marker block not found exactly once')
p.write_text(text.replace(old, new, 1), encoding='utf-8')
print('legacy v5.3.4 marker updated for v5.3.5 duration contract')
