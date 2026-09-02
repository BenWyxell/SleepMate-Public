from pathlib import Path

root=Path(__file__).resolve().parents[1]
path=root/'build/windows/SleepMate.spec'
text=path.read_text(encoding='utf-8')
old="""    protected_base_assets = (\n        '/sleepmate-sleep.js',\n        '/sleepmate-sleep-v523.js',\n        '/sleepmate-chart-v523.js',\n        '/sleepmate-sleep-v524.js',\n        '/sleepmate-sleep-refresh-v5212.js',\n        '/o2ring-v532.css',\n        '/o2ring-v532.js',\n    )\n"""
new="""    protected_base_assets = (\n        '/sleepmate-sleep.js',\n        '/sleepmate-sleep-v523.js',\n        '/sleepmate-chart-v523.js',\n        '/sleepmate-sleep-v524.js',\n        '/sleepmate-sleep-refresh-v5212.js',\n        '/sleepmate-aurora.css',\n        '/sleepmate-v530.css',\n        '/sleepmate-v530.js',\n        '/o2ring.css',\n        '/o2ring.js',\n        '/o2ring-report-ui.js',\n        '/o2ring-v534.css',\n        '/frontend-v534.js',\n    )\n"""
if old not in text:
    raise RuntimeError('old v5.3.2 packaging guard not found')
text=text.replace(old,new,1)
anchor="""    for asset in protected_base_assets:\n        if repr(asset) not in code_items:\n            raise RuntimeError(f'proven service worker lost network-first asset: {asset}')\n"""
replacement=anchor+"""    for obsolete in ('/o2ring-v532.css','/o2ring-v532.js','/frontend-v533.js'):\n        if repr(obsolete) in code_items:\n            raise RuntimeError(f'obsolete O2 frontend asset returned to active worker: {obsolete}')\n"""
if anchor not in text:
    raise RuntimeError('packaging guard loop not found')
text=text.replace(anchor,replacement,1)
path.write_text(text,encoding='utf-8')
print('v5.3.4 packaging guard migrated')
