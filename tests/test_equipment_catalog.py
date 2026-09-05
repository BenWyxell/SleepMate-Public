from pathlib import Path
import json
root = Path(__file__).resolve().parents[1]
p = root / 'web' / 'equipment_catalog.json'
data = json.loads(p.read_text(encoding='utf-8'))
assert data.get('format') == 'PAP_COMPATIBILITY_DATABASE_V1'
assert any(x.get('manufacturer') == 'ResMed' and x.get('model') == 'AirSense 11 AutoSet' for x in data.get('machines', []))
assert any(x.get('manufacturer') == 'ResMed' and x.get('accessory_model') == 'ClimateLineAir 11' for x in data.get('accessories', []))
n30i = next(x for x in data.get('masks', []) if x.get('manufacturer') == 'ResMed' and x.get('model') == 'AirFit N30i')
assert 'SW' in str(n30i.get('sizes','')).split('/')
print('PASS: PAP compatibility catalog -> machine/accessory/mask examples + ResMed SW size available')
