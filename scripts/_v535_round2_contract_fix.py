from pathlib import Path
p=Path('tests/test_v534_acceptance_matrix.py')
text=p.read_text(encoding='utf-8')
old='''    assert "function fixLatestLoading()" in front\n    assert "function syncLatestSessionCard()" in front\n    assert "latest.sessions" in front\n    assert "status.textContent='—'" in front\n'''
new='''    assert "function fixLatestLoading()" in front\n    assert "function syncLatestSessionCard()" in front\n    assert "latest?.summary||latest" in front\n    assert "latestDuration(summary)" in front\n    assert "summary.sessions" in front\n    assert "status.textContent='—'" in front\n'''
if text.count(old)!=1: raise SystemExit('remaining latest-session acceptance block not found exactly once')
p.write_text(text.replace(old,new,1),encoding='utf-8')
