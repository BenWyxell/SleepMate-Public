from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly 1 match, got {count}")
    return text.replace(old, new, 1)


spec_path = Path('build/windows/SleepMate.spec')
spec = spec_path.read_text(encoding='utf-8')

# 1) Never ship the Dashboard PWA stylesheet under the same immutable-looking
# query string after its content changes. Tie it to the exact generated frontend.
spec = replace_once(
    spec,
    "    dashboard_pwa_link = '<link rel=\"stylesheet\" href=\"/dashboard-pwa-v5312.css?v=1\">'",
    "    dashboard_pwa_link = f'<link rel=\"stylesheet\" href=\"/dashboard-pwa-v5312.css?v={FRONTEND_ID}\">'",
    'versioned Dashboard PWA stylesheet link',
)

sw_anchor = "    sw = sw.replace(f\"'/app.js?v={APP_VERSION}'\", f\"'/app.js?v={FRONTEND_ID}'\")\n"
if sw_anchor not in spec:
    raise SystemExit('service-worker app.js versioning anchor missing')
if "dashboard-pwa-v5312.css?v={FRONTEND_ID}" not in spec.split(sw_anchor, 1)[1]:
    spec = spec.replace(
        sw_anchor,
        sw_anchor + "    sw = sw.replace(\"'/dashboard-pwa-v5312.css?v=2'\", f\"'/dashboard-pwa-v5312.css?v={FRONTEND_ID}'\")\n",
        1,
    )

# 2) Daily SpO2 / pulse must not depend on the O2 UI runtime already having
# completed its asynchronous PWA bootstrap. The daily endpoint is the source of
# truth, so use it as a direct fallback with short bounded retries.
o2_anchor = '''replace_literal(
    sidebar_app_js,
    "ind.classList.add('refreshing');ind.querySelector('b').textContent='Adatok ellenőrzése…';refreshData()",
    "ind.classList.add('refreshing');ind.querySelector('b').textContent='Adatok ellenőrzése…';setTimeout(()=>{if(state.pullRefreshing)resetPullRefreshUi()},1100);refreshData()",
)
'''
o2_patch = '''replace_literal(
    sidebar_app_js,
    "const o2Promise=window.SleepMateO2Ring?.getDailySummary?.(day)||null;",
    "const o2Promise=(async()=>{const code=String(day||'').replace(/-/g,'').slice(0,8);for(let attempt=0;attempt<3;attempt++){try{const getter=window.SleepMateO2Ring?.getDailySummary;if(typeof getter==='function'){const x=await getter(day);if(x)return x}const x=await api(`/api/o2ring/day?day=${encodeURIComponent(code)}&max_points=1`);if(x)return x}catch{}if(attempt<2)await sleep(180*(attempt+1))}return null})();",
)
'''
if o2_patch not in spec:
    if o2_anchor not in spec:
        raise SystemExit('core patch insertion anchor missing')
    spec = spec.replace(o2_anchor, o2_anchor + o2_patch, 1)

spec_path.write_text(spec, encoding='utf-8')

# The source worker is also used outside the packaged generation path. Give the
# changed Dashboard stylesheet a fresh request URL there as well.
for rel in ('web/service-worker-v508-base.js', 'web/service-worker.js'):
    path = Path(rel)
    text = path.read_text(encoding='utf-8')
    if '/dashboard-pwa-v5312.css?v=1' in text:
        text = text.replace('/dashboard-pwa-v5312.css?v=1', '/dashboard-pwa-v5312.css?v=2')
    elif '/dashboard-pwa-v5312.css?v=2' not in text:
        raise SystemExit(f'{rel}: Dashboard PWA shell entry not found')
    path.write_text(text, encoding='utf-8')

# Focused regression contract.
test_path = Path('tests/test_v5315_pwa_daily_delivery_and_o2.py')
test_path.write_text('''from pathlib import Path\n\n\ndef text(path):\n    return Path(path).read_text(encoding="utf-8")\n\n\ndef test_packaged_dashboard_pwa_css_is_build_versioned():\n    spec = text("build/windows/SleepMate.spec")\n    assert "dashboard_pwa_link = f'<link rel=\\\"stylesheet\\\" href=\\\"/dashboard-pwa-v5312.css?v={FRONTEND_ID}\\\">'" in spec\n    assert "sw = sw.replace(\\\"'/dashboard-pwa-v5312.css?v=2'\\\", f\\\"'/dashboard-pwa-v5312.css?v={FRONTEND_ID}'\\\")" in spec\n    assert "/dashboard-pwa-v5312.css?v=2" in text("web/service-worker-v508-base.js")\n    assert "/dashboard-pwa-v5312.css?v=2" in text("web/service-worker.js")\n\n\ndef test_daily_o2_has_runtime_independent_api_fallback():\n    spec = text("build/windows/SleepMate.spec")\n    assert "window.SleepMateO2Ring?.getDailySummary" in spec\n    assert "/api/o2ring/day?day=${encodeURIComponent(code)}&max_points=1" in spec\n    assert "for(let attempt=0;attempt<3;attempt++)" in spec\n\n\ndef test_daily_bento_css_is_still_present_and_phone_scoped():\n    css = text("web/dashboard-pwa-v5312.css")\n    assert "/* Phone PWA daily detail bento extension */" in css\n    assert "html.sm-phone-pwa #page-dashboard #dashboardDailyView .daily-core-grid" in css\n    assert "grid-template-columns:repeat(2,minmax(0,1fr))!important" in css\n''', encoding='utf-8')
