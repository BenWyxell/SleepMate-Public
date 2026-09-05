from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

def test_daily_o2_cards_use_one_stable_decimal_format() -> None:
    app = read("web/app-core.js")
    assert "Number(spo2Value).toLocaleString('hu-HU',{minimumFractionDigits:1,maximumFractionDigits:1})" in app
    assert "Number(hrValue).toLocaleString('hu-HU',{minimumFractionDigits:1,maximumFractionDigits:1})" in app
    assert "Number(spo2Value).toLocaleString('hu-HU',{maximumFractionDigits:1})" not in app
    assert "Number(hrValue).toLocaleString('hu-HU',{maximumFractionDigits:1})" not in app

    o2 = read("web/o2ring.js")
    assert "id('spo2').textContent=`${fmt(spo2,1)}%`" in o2
    assert "id('hr').textContent=`${fmt(hr,1)}`" in o2

def test_phone_daily_ahi_spans_both_bento_columns() -> None:
    css = read("web/dashboard-pwa-v5312.css")
    assert ".daily-core-grid{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important" in css
    assert ".daily-primary-stat.ahi{--daily-accent:var(--dash-teal);grid-column:1/-1!important}" in css
