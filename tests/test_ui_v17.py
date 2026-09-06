from pathlib import Path
import sys, tempfile
root=Path(__file__).resolve().parents[1]
js=(root/'web'/'app-core.js').read_text(encoding='utf-8')
compact=''.join(js.split())
html=(root/'web'/'index.html').read_text(encoding='utf-8')
sys.path.insert(0,str(root))
from cpap.resmed import ResMedDataset

# The application-data delete workflow remains an internal typed-confirmation modal.
segment=compact[compact.index('asyncfunctiondeleteSelectedData(){'):compact.index('asyncfunctionrefreshData()',compact.index('asyncfunctiondeleteSelectedData(){'))]
assert 'window.confirm' not in segment
assert "value!=='TÖRLÉS'" in segment
assert 'dataDeleteModal' in html and 'dataDeleteConfirmInput' in html

# Empty-state SVG must not use duplicated DOM ids/URL fills that can break when several pages exist in DOM.
empty_segment=compact[compact.index('functionemptySleepSvg()'):compact.index('functionupdateMeasurementEmptyStates()')]
assert '<defs>' not in empty_segment
assert 'url(#' not in empty_segment
assert 'fill="#83b7ff"' in empty_segment

# Equipment emptiness is based on equipment data, not on whether a treated-person profile already exists.
load_segment=compact[compact.index('asyncfunctionloadEquipmentPage(){'):compact.index('functionequipmentRecordName',compact.index('asyncfunctionloadEquipmentPage(){'))]
assert 'constfullyEmpty=!eq.available&&storedCount===0' in load_segment
assert "data-equipment-add" in js

# Missing Identification.json is a normal no-device state and must not surface as API error.
with tempfile.TemporaryDirectory() as td:
    r=Path(td); (r/'DATALOG').mkdir()
    eq=ResMedDataset(r).equipment()
    assert eq['available'] is False
    assert eq.get('reason')=='identification_missing'
    assert 'error' not in eq

print('PASS: v1.7 stable empty SVG + friendly equipment no-data state + no Identification.json error')
