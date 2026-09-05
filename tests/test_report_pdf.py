from pathlib import Path
import tempfile, shutil, sys

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from cpap.resmed import ResMedDataset
from cpap.patient_store import PatientStore
from cpap.report_pdf import generate_report_pdf, _register_fonts, _FONT_SOURCE
from pypdf import PdfReader

work=Path(tempfile.mkdtemp(prefix='sleepmate_report_test_'))
try:
    ds=ResMedDataset(BASE/'testdata')
    ps=PatientStore(work)
    ps.save_profile({'name':'Teszt Személy','birth_date':'1980-01-01','therapy_start_date':'2026-08-15'})
    ps.save_record('prescription',{'effective_from':'2026-08-16','mode':'APAP / AutoCPAP','min_pressure':7,'max_pressure':12})
    opts={
        'sections':['summary','usage','events','pressure_leak','calendar','data_quality','daily_table','glossary'],
        'include_patient':True,'patient_fields':['name','age','therapy_start','prescription'],
        'compare_previous':False,'theme':'sleepmate'
    }
    out=work/'report.pdf'
    generate_report_pdf(ds,ps,'2026-08-20','2026-08-24',opts,BASE,out)
    clinical=work/'clinical.pdf'
    generate_report_pdf(ds,ps,'2026-08-20','2026-08-24',{**opts,'theme':'clinical'},BASE,clinical)
    _register_fonts()
    raw=out.read_bytes()
    assert raw.startswith(b'%PDF-'), 'Nem PDF készült.'
    assert len(raw)>50_000, 'A PDF gyanúsan kicsi.'
    assert clinical.read_bytes()!=raw, 'A SleepMate és Klinikai témák nem különülnek el.'
    pages=len(PdfReader(str(out)).pages)
    assert pages<=7, f'A kis tesztjelentés indokolatlanul hosszú: {pages} oldal.'
    # Cross-platform regression: generation must not depend on a hard-coded Linux font path.
    assert b'/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf' not in raw
    html=(BASE/'web'/'index.html').read_text(encoding='utf-8')
    js=(BASE/'web'/'app.js').read_text(encoding='utf-8')
    assert 'reportPdfModal' in html and 'PDF jelentés készítése' in html
    assert "'/api/report/pdf'" in js or '"/api/report/pdf"' in js
    
    pdfsrc=(BASE/'cpap'/'report_pdf.py').read_text(encoding='utf-8')
    assert 'from reportlab.graphics.charts.piecharts import Pie' not in pdfsrc
    assert "['Hétfő','Kedd','Szerda','Csütörtök','Péntek','Szombat','Vasárnap']" in pdfsrc
    assert 'width=450,height=178' in pdfsrc and 'pbox,lbox' not in pdfsrc
    print(f'PASS: v4.0 full-cover + dedicated patient page + stacked PDF charts ({pages} pages)')
finally:
    shutil.rmtree(work,ignore_errors=True)
