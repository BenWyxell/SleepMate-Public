from pathlib import Path

root = Path('.')

path = root / 'tests/test_pwa_sleep_shell_v526.py'
text = path.read_text(encoding='utf-8')
text = text.replace(
    'def test_new_service_worker_claims_live_pwa_without_mid_boot_navigation():',
    'def test_new_service_worker_performs_safe_generation_handover():',
)
text = text.replace('assert "const stale=keys.filter" in sw', 'assert "cleanupStaleSleepMateCaches" in sw')
text = text.replace('assert "await client.navigate(client.url)" not in sw', 'assert "await client.navigate(client.url)" in sw')
path.write_text(text, encoding='utf-8')

path = root / 'tests/test_v5315_pwa_daily_delivery_and_o2.py'
text = path.read_text(encoding='utf-8')
old = '''    assert "sw = sw.replace(\"'/dashboard-pwa-v5312.css?v=2'\", f\"'/dashboard-pwa-v5312.css?v={FRONTEND_ID}'\")" in spec\n'''
new = '''    assert "'/dashboard-pwa-v5312.css'" in spec\n    assert "asset + f'?v={FRONTEND_ID}'" in spec\n'''
if old not in text:
    raise SystemExit('old dashboard SW versioning assertion not found')
text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')

print('Legacy PWA regression expectations updated.')
