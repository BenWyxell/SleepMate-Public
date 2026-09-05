from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cpap.resmed import ResMedDataset

root = Path(__file__).resolve().parents[1]
ds = ResMedDataset(root / "testdata")
s = ds.summary("20260824")
assert s["usage"] == "03:42:00", s
assert s["counts"]["OA"] == 2, s
assert s["counts"]["CA"] == 0, s
assert s["counts"]["H"] == 0, s
assert s["ahi"] == 0.54, s
assert s["integrity"]["complete"] is True, s
print("PASS: 20260824 -> Usage 03:42:00, OA 2, AHI 0.54, EDF complete")
flow = ds.signal("20260824", "flow", max_points=1000, range_start_s=7*3600, range_end_s=9*3600)
assert flow["unit"] == "L/perc", flow["unit"]
assert len(flow["series"]) == 1, len(flow["series"])
leak = ds.signal("20260824", "leak", max_points=1000, range_start_s=7*3600, range_end_s=9*3600)
assert leak["unit"] == "L/perc", leak["unit"]
tv = ds.signal("20260824", "tidal_volume", max_points=1000, range_start_s=7*3600, range_end_s=9*3600)
assert tv["unit"] == "ml", tv["unit"]
print("PASS: zoom-range signal API + OSCAR-like units")
st = ds.statistics("20260824")
rows = {r["key"]: r for r in st["rows"]}
assert rows["pressure"]["median"] == 7.12, rows["pressure"]
assert rows["pressure"]["p95"] == 8.98, rows["pressure"]
assert rows["epr_pressure"]["p995"] == 6.54, rows["epr_pressure"]
assert rows["leak"]["p95"] == 14.4, rows["leak"]
assert rows["flow_lim"]["p995"] == 0.22, rows["flow_lim"]
assert rows["snore"]["p995"] == 0.06, rows["snore"]
assert rows["resp_rate"]["min"] == 4.8, rows["resp_rate"]
assert rows["tidal_volume"]["median"] == 260.0, rows["tidal_volume"]
assert st["apnea_duration"] == "00:00:22", st
print("PASS: OSCAR-reference daily statistics + total apnea time")
ox = s["oximetry"]
assert ox["available"] is False, ox
rows_overview = ds.day_table()
assert rows_overview[0]["day"] == "20260824", rows_overview
assert rows_overview[0]["usage"] == "03:42:00", rows_overview[0]
assert rows_overview[0]["events"] == 3, rows_overview[0]
assert rows_overview[0]["spo2"] is None and rows_overview[0]["hr"] is None, rows_overview[0]
print("PASS: sessions table + SA2 zero-placeholder handling")
eq = ds.equipment()
assert eq["available"] is True, eq
assert eq["product_name"] == "AirSense 11 AutoSet", eq
assert eq["product_code"] == "39517", eq
print("PASS: Identification.json equipment recognition")
ov = ds.dashboard_overview("30")
assert ov["latest"]["summary"]["usage"] == "03:42:00", ov["latest"]
assert ov["latest"]["key_stats"]["leak_p95"] == 14.4, ov["latest"]["key_stats"]
assert ov["aggregate"]["ahi"] == 0.54, ov["aggregate"]
assert rows_overview[0]["leak_p95"] == 14.4, rows_overview[0]
assert rows_overview[0]["pressure_p95"] == 8.98, rows_overview[0]
diag = ds.diagnostics()
assert diag["damaged_files"] == [], diag
assert diag["missing_required"] == [], diag
print("PASS: v1.0 latest sleep + calendar payload + diagnostics")
