from pathlib import Path
import tempfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cpap.patient_store import PatientStore

with tempfile.TemporaryDirectory() as td:
    st = PatientStore(Path(td))
    st.save_profile({"name": "Teszt személy", "therapy_start_date": "2026-08-15"})
    dev = st.save_record("device", {"manufacturer": "ResMed", "model": "AirSense 11 AutoSet", "active": True})
    mask = st.save_record("mask", {"manufacturer": "ResMed", "model": "N30i", "size": "SW", "start_date": "2026-08-15", "replacement_interval": "1 hónap", "active": True})
    tube = st.save_record("accessory", {"category": "Fűtött gégecső", "manufacturer": "ResMed", "model": "ClimateLineAir 11", "device_id": dev["id"], "start_date": "2026-08-15", "replacement_interval": "6 hónap", "active": True})
    humid = st.save_record("accessory", {"category": "Párásító", "manufacturer": "ResMed", "model": "HumidAir 11", "device_id": dev["id"], "active": True})
    st.save_record("setup", {"device_id": dev["id"], "mask_id": mask["id"], "accessory_ids": [tube["id"], humid["id"]], "active": True})
    st.save_record("daily_assessment", {"id": "day-20260824", "day": "20260824", "sleep_quality": 8, "headache": "nincs"})
    bundle = st.export_bundle()
    assert bundle["measurement_data_included"] is False
    assert bundle["equipment_included"] is True
    assert len(bundle["data"]["daily_assessments"]) == 1
    assert len(bundle["data"]["setups"]) == 1
    st.delete_patient_only()
    result = st.import_bundle(bundle, "replace")
    restored = st.all_data()
    assert result["profile"] is True
    assert restored["profile"]["name"] == "Teszt személy"
    assert restored["setups"][0]["patient_id"] == "profile"
    assert len(restored["devices"]) == 1 and len(restored["masks"]) == 1
    assert len(restored["accessories"]) == 2
    assert len(restored["setups"][0]["accessory_ids"]) == 2
    assert restored["daily_assessments"][0]["sleep_quality"] == 8
    assert restored["masks"][0]["replacement_interval"] == "1 hónap"
    restored_tube = next(x for x in restored["accessories"] if x.get("model") == "ClimateLineAir 11")
    assert restored_tube["replacement_interval"] == "6 hónap"
print("PASS: treated-person backup/restore + equipment + daily assessment relationship")

# v3.9 selective equipment restore regression
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    src = PatientStore(root / 'src')
    src.save_profile({'name':'Exportált személy'})
    d = src.save_record('device', {'manufacturer':'ResMed','model':'AirSense 11 AutoSet','active':True})
    m = src.save_record('mask', {'manufacturer':'ResMed','model':'AirTouch N30i','size':'SW','active':True})
    a = src.save_record('accessory', {'category':'Fűtött gégecső','model':'ClimateLineAir 11','active':True})
    src.save_record('setup', {'device_id':d['id'],'mask_id':m['id'],'accessory_ids':[a['id']],'active':True})
    bundle = src.export_bundle()
    assert bundle['version'] == 2 and bundle['equipment_included'] is True
    assert bundle['equipment_counts'] == {'devices':1,'masks':1,'accessories':1,'setups':1}

    dst = PatientStore(root / 'dst')
    dst.save_profile({'name':'Régi személy'})
    dst.save_record('mask', {'model':'Megmaradó maszk','active':True})
    result = dst.import_bundle(bundle, 'replace', include_equipment=False)
    restored = dst.all_data()
    assert restored['profile']['name'] == 'Exportált személy'
    assert [x['model'] for x in restored['masks']] == ['Megmaradó maszk']
    assert result['equipment_imported'] == 0

    dst2 = PatientStore(root / 'dst2')
    result2 = dst2.import_bundle(bundle, 'replace', include_equipment=True)
    restored2 = dst2.all_data()
    assert len(restored2['devices']) == 1 and len(restored2['masks']) == 1
    assert len(restored2['accessories']) == 1 and len(restored2['setups']) == 1
    assert result2['equipment_imported'] == 4
print('PASS: v3.9 explicit equipment backup + optional equipment import')
