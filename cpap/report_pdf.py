from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any
import calendar
import math
import os
import reportlab

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, CondPageBreak, Image, HRFlowable,
)
from reportlab.graphics.shapes import Drawing, String, Rect, Line, Circle
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.charts.barcharts import VerticalBarChart


NAVY = HexColor('#0B1730')
NAVY_2 = HexColor('#13243D')
BLUE = HexColor('#357DB1')
BLUE_LIGHT = HexColor('#DCEFFC')
GOLD = HexColor('#E3B95D')
GOLD_LIGHT = HexColor('#FFF3CF')
GREEN = HexColor('#2F9B69')
GREEN_LIGHT = HexColor('#DFF3E9')
ORANGE = HexColor('#D98B17')
RED = HexColor('#C54E52')
PURPLE = HexColor('#8D6BC2')
TEAL = HexColor('#3E9F9A')
OA_COLOR = HexColor('#FF806F')
CA_COLOR = HexColor('#A995FF')
H_COLOR = HexColor('#57D6A8')
RERA_COLOR = HexColor('#5EB4FF')
TEXT = HexColor('#1B2A3A')
MUTED = HexColor('#60758B')
LINE = HexColor('#D8E2EB')
PANEL = HexColor('#F7FAFC')
WHITE = colors.white


_FONT_READY = False
_FONT_SOURCE = ''


def _font_candidates():
    """Cross-platform font candidates. Never assumes a Linux-only path."""
    windir = Path(os.environ.get('WINDIR') or os.environ.get('SystemRoot') or r'C:\\Windows')
    reportlab_fonts = Path(reportlab.__file__).resolve().parent / 'fonts'
    return [
        # Windows 10/11 - SleepMate primary runtime.
        (windir / 'Fonts' / 'segoeui.ttf', windir / 'Fonts' / 'segoeuib.ttf', 'Windows Segoe UI'),
        (windir / 'Fonts' / 'arial.ttf', windir / 'Fonts' / 'arialbd.ttf', 'Windows Arial'),
        # Linux/dev/test environments.
        (Path('/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf'), Path('/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf'), 'Noto Sans'),
        (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'), Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'), 'DejaVu Sans'),
        # ReportLab ships Vera with its Python package, so this is a portable last-resort TTF.
        (reportlab_fonts / 'Vera.ttf', reportlab_fonts / 'VeraBd.ttf', 'ReportLab Vera'),
    ]


def _register_fonts():
    global _FONT_READY, _FONT_SOURCE
    if _FONT_READY:
        return
    errors = []
    for regular, bold, source in _font_candidates():
        if not (regular.exists() and bold.exists()):
            continue
        try:
            pdfmetrics.registerFont(TTFont('SleepSans', str(regular)))
            pdfmetrics.registerFont(TTFont('SleepSansBold', str(bold)))
            _FONT_SOURCE = source
            _FONT_READY = True
            return
        except Exception as exc:
            errors.append(f'{source}: {exc}')
    # This should be unreachable on normal ReportLab installs because Vera is packaged.
    detail = '; '.join(errors) if errors else 'nem található használható TTF betűkészlet'
    raise RuntimeError(f'A PDF-hez nem található használható betűkészlet. {detail}')


def hu_date(value: str | None) -> str:
    if not value:
        return '–'
    s = str(value)
    if len(s) >= 8 and '-' not in s:
        s = f'{s[:4]}-{s[4:6]}-{s[6:8]}'
    try:
        d = datetime.strptime(s[:10], '%Y-%m-%d')
        return d.strftime('%Y.%m.%d.')
    except Exception:
        return s


def seconds_hm(seconds: float | int | None) -> str:
    s = int(round(float(seconds or 0)))
    h, rem = divmod(max(0, s), 3600)
    m = rem // 60
    return f'{h} óra {m:02d} perc'


def num(v: Any, digits: int = 1, suffix: str = '') -> str:
    if v is None or v == '':
        return '–'
    try:
        out = f'{float(v):.{digits}f}'.replace('.', ',')
    except Exception:
        return str(v)
    return out + suffix


def fmt_taj(v: str | None) -> str:
    d = ''.join(ch for ch in str(v or '') if ch.isdigit())[:9]
    return f'{d[:3]} {d[3:6]} {d[6:]}' if len(d) == 9 else (d or '–')


def age_from_birth(value: str | None) -> int | None:
    if not value:
        return None
    try:
        d = datetime.strptime(value[:10], '%Y-%m-%d').date()
        n = datetime.now().date()
        return n.year - d.year - ((n.month, n.day) < (d.month, d.day))
    except Exception:
        return None


def _safe(value: Any) -> str:
    return str(value if value not in (None, '') else '–').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _date_code(value: str) -> str:
    return str(value or '').replace('-', '')[:8]


def _therapy_label(r: dict[str, Any] | None) -> str:
    if not r:
        return '–'
    mode = str(r.get('mode') or r.get('pressure_type') or '')
    if 'Fix' in mode:
        return f"Fix CPAP {num(r.get('fixed_pressure'),1)} cmH₂O"
    if 'APAP' in mode or 'Auto' in mode:
        return f"APAP {num(r.get('min_pressure'),1)}–{num(r.get('max_pressure'),1)} cmH₂O"
    return mode or '–'


def _current_prescription(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    today = datetime.now().date().isoformat()
    ordered = sorted(rows, key=lambda x: str(x.get('effective_from') or ''), reverse=True)
    for r in ordered:
        if (not r.get('effective_from') or r.get('effective_from') <= today) and (not r.get('effective_to') or r.get('effective_to') >= today):
            return r
    return ordered[0]


def _record_name(r: dict[str, Any], kind: str) -> str:
    if kind == 'device':
        return ' '.join(x for x in [str(r.get('manufacturer') or ''), str(r.get('model') or '')] if x).strip() or 'PAP-készülék'
    if kind == 'mask':
        size = f" ({r.get('size')})" if r.get('size') else ''
        return (' '.join(x for x in [str(r.get('manufacturer') or ''), str(r.get('model') or '')] if x).strip() or 'Maszk') + size
    if kind == 'accessory':
        return ' '.join(x for x in [str(r.get('manufacturer') or ''), str(r.get('model') or r.get('category') or '')] if x).strip() or 'Kiegészítő'
    return '–'


def _timeline(patient: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    def push(date, kind, title, detail=''):
        if date:
            out.append({'date': str(date), 'kind': kind, 'title': title, 'detail': detail})
    profile = patient.get('profile') or {}
    push(profile.get('therapy_start_date'), 'start', 'PAP-terápia kezdete', 'A terápia megkezdésének rögzített dátuma.')
    for r in patient.get('prescriptions') or []:
        push(r.get('effective_from'), 'prescription', 'Terápiás előírás módosítása', _therapy_label(r))
    for r in patient.get('titrations') or []:
        push(r.get('date'), 'titration', 'Titrálás', _therapy_label(r))
    for r in patient.get('devices') or []:
        push(r.get('start_date'), 'device', 'Készülék használatba véve', _record_name(r, 'device'))
    for r in patient.get('masks') or []:
        push(r.get('start_date'), 'mask', 'Maszk használatba véve', _record_name(r, 'mask'))
    for r in patient.get('accessories') or []:
        push(r.get('start_date'), 'accessory', 'Kiegészítő használatba véve', _record_name(r, 'accessory'))
    for r in patient.get('medications') or []:
        med = ' '.join(x for x in [str(r.get('name') or 'Gyógyszer'), str(r.get('strength') or '')] if x).strip()
        push(r.get('start_date'), 'medication', 'Gyógyszer kezdete', med)
        push(r.get('end_date'), 'medication', 'Gyógyszer befejezése', med)
    for r in patient.get('weights') or []:
        detail = ' • '.join(x for x in [f"{r.get('weight')} kg" if r.get('weight') else '', f"BMI {r.get('bmi')}" if r.get('bmi') else ''] if x)
        push(r.get('date'), 'weight', 'Testsúly / BMI változás', detail)
    for r in patient.get('controls') or []:
        push(r.get('date'), 'control', 'Kontrollvizsgálat', str(r.get('note') or r.get('institution') or 'Kontroll'))
    for r in patient.get('timeline_events') or []:
        push(r.get('date'), 'custom', str(r.get('title') or r.get('event_type') or 'Saját terápiás esemény'), str(r.get('note') or ''))
    return sorted(out, key=lambda x: x['date'])


@dataclass
class ReportContext:
    dataset: Any
    patient_store: Any
    start: str
    end: str
    config: dict[str, Any]
    base_dir: Path


class SleepMateReport:
    def __init__(self, ctx: ReportContext):
        _register_fonts()
        self.ctx = ctx
        self.dataset = ctx.dataset
        self.patient_store = ctx.patient_store
        self.config = ctx.config or {}
        self.start_code = _date_code(ctx.start)
        self.end_code = _date_code(ctx.end)
        if self.start_code and self.end_code and self.start_code > self.end_code:
            self.start_code, self.end_code = self.end_code, self.start_code
        self.patient = self.patient_store.all_data() if self.patient_store else {}
        self.all_rows = self.dataset.dashboard_overview('all').get('rows') or []
        self.rows = [r for r in self.all_rows if (not self.start_code or r.get('day','') >= self.start_code) and (not self.end_code or r.get('day','') <= self.end_code)]
        self.days = [r.get('day') for r in self.rows]
        self.aggregate = self.dataset._aggregate_days(self.days)
        self.diag = self.dataset.diagnostics()
        self.timeline = _timeline(self.patient)
        self.current_rx = _current_prescription(self.patient.get('prescriptions') or [])
        self.sections = set(self.config.get('sections') or [])
        self.patient_fields = set(self.config.get('patient_fields') or [])
        self.theme = str(self.config.get('theme') or 'sleepmate')
        if self.theme == 'clinical':
            self.primary = HexColor('#314A55')
            self.accent = HexColor('#2F7A80')
            self.secondary = HexColor('#6B8791')
            self.panel_fill = HexColor('#F5F7F8')
            self.summary_fill = HexColor('#EEF4F4')
            self.card_border = HexColor('#C8D4D8')
            self.header_text = HexColor('#22343D')
            self.chart_primary = HexColor('#2F7A80')
            self.chart_secondary = HexColor('#7BA2A6')
            self.event_colors = [HexColor('#B95C5E'), HexColor('#7E70A9'), HexColor('#4F9A7D'), HexColor('#4C8FA5')]
            self.pressure_colors = [HexColor('#526F78'), HexColor('#2F7A80')]
            self.leak_colors = [HexColor('#A97932'), HexColor('#C39A4B')]
        else:
            self.primary = NAVY
            self.accent = GOLD
            self.secondary = BLUE
            self.panel_fill = HexColor('#F8FAFD')
            self.summary_fill = GOLD_LIGHT
            self.card_border = HexColor('#D8E2EB')
            self.header_text = NAVY
            self.chart_primary = BLUE
            self.chart_secondary = GOLD
            self.event_colors = [OA_COLOR, CA_COLOR, H_COLOR, RERA_COLOR]
            self.pressure_colors = [HexColor('#786ED2'), HexColor('#C663D4')]
            self.leak_colors = [HexColor('#E1B853'), HexColor('#D98B17')]
        self.compare_previous = bool(self.config.get('compare_previous'))
        self.story: list[Any] = []
        self.styles = self._styles()
        self.logo_path = ctx.base_dir / 'web' / 'assets' / 'sleepmate-icon.png'

    def _styles(self):
        ss = getSampleStyleSheet()
        return {
            'body': ParagraphStyle('BodySM', parent=ss['BodyText'], fontName='SleepSans', fontSize=9.2, leading=13.2, textColor=TEXT, spaceAfter=5),
            'small': ParagraphStyle('SmallSM', parent=ss['BodyText'], fontName='SleepSans', fontSize=7.8, leading=10.5, textColor=MUTED),
            'h1': ParagraphStyle('H1SM', parent=ss['Heading1'], fontName='SleepSansBold', fontSize=18 if self.theme == 'clinical' else 19, leading=22, textColor=self.header_text, spaceAfter=5),
            'h2': ParagraphStyle('H2SM', parent=ss['Heading2'], fontName='SleepSansBold', fontSize=12.5, leading=16, textColor=self.header_text, spaceBefore=5, spaceAfter=6),
            'h3': ParagraphStyle('H3SM', parent=ss['Heading3'], fontName='SleepSansBold', fontSize=10.2, leading=13, textColor=self.header_text, spaceAfter=3),
            'center': ParagraphStyle('CenterSM', parent=ss['BodyText'], fontName='SleepSans', alignment=TA_CENTER, fontSize=9, leading=12, textColor=TEXT),
            'cover_title': ParagraphStyle('CoverTitle', parent=ss['Heading1'], fontName='SleepSansBold', alignment=TA_LEFT if self.theme == 'clinical' else TA_CENTER, fontSize=23 if self.theme == 'clinical' else 26, leading=29, textColor=self.header_text),
            'cover_sub': ParagraphStyle('CoverSub', parent=ss['BodyText'], fontName='SleepSans', alignment=TA_LEFT if self.theme == 'clinical' else TA_CENTER, fontSize=10.5 if self.theme == 'clinical' else 12, leading=15, textColor=MUTED),
            'metric_value': ParagraphStyle('MetricValue', parent=ss['BodyText'], fontName='SleepSansBold', alignment=TA_CENTER, fontSize=15.5, leading=18, textColor=self.header_text),
            'metric_label': ParagraphStyle('MetricLabel', parent=ss['BodyText'], fontName='SleepSans', alignment=TA_CENTER, fontSize=7.5, leading=10, textColor=MUTED),
        }

    def section_enabled(self, name: str) -> bool:
        return name in self.sections

    def _page(self, canvas, doc):
        canvas.saveState()
        w, h = A4
        logo = str(self.logo_path) if self.logo_path.exists() else None
        if doc.page == 1:
            # v4.0: valódi, széltől szélig futó borító. Nincs margó, fejléc vagy lábléc.
            bg = HexColor('#09182D') if self.theme != 'clinical' else HexColor('#203A43')
            canvas.setFillColor(bg)
            canvas.rect(0, 0, w, h, fill=1, stroke=0)
            # dekoratív, nyugodt éjszakai rétegek
            canvas.setFillColor(HexColor('#112E52') if self.theme != 'clinical' else HexColor('#2C5960'))
            canvas.circle(w + 5*mm, h - 28*mm, 74*mm, fill=1, stroke=0)
            canvas.setFillColor(HexColor('#183C67') if self.theme != 'clinical' else HexColor('#376C72'))
            canvas.circle(-20*mm, 25*mm, 62*mm, fill=1, stroke=0)
            canvas.setFillColor(self.accent)
            canvas.rect(0, 0, w, 5*mm, fill=1, stroke=0)
            # finom csillagpontok / vizuális ritmus
            canvas.setFillColor(HexColor('#6CA7D8') if self.theme != 'clinical' else HexColor('#76AEB0'))
            for x, y, r in [(22,258,1.0),(41,239,.7),(166,244,.8),(184,220,1.1),(30,73,.8),(177,58,.7)]:
                canvas.circle(x*mm, y*mm, r*mm, fill=1, stroke=0)
            if logo:
                try:
                    canvas.drawImage(logo, 22*mm, h-79*mm, 39*mm, 39*mm, mask='auto', preserveAspectRatio=True, anchor='c')
                except Exception:
                    pass
            canvas.setFillColor(WHITE)
            canvas.setFont('SleepSansBold', 29)
            canvas.drawString(22*mm, h-101*mm, 'SleepMate')
            canvas.setFillColor(self.accent)
            canvas.setFont('SleepSansBold', 11)
            canvas.drawString(22*mm, h-112*mm, 'PAP-TERÁPIÁS JELENTÉS')
            canvas.setFillColor(HexColor('#DCE8F3'))
            canvas.setFont('SleepSans', 13)
            canvas.drawString(22*mm, h-128*mm, f'{hu_date(self.start_code)} - {hu_date(self.end_code)}')
            # Leírás - rövid, borítóhoz illő, több soros szöveg
            canvas.setFillColor(HexColor('#C6D5E4'))
            canvas.setFont('SleepSans', 10)
            cover_lines = [
                'Áttekinthető, nyomtatható összefoglaló a kiválasztott',
                'PAP-terápiás időszakról: használat, események, nyomás,',
                'szivárgás és a rögzített terápiás háttéradatok egy helyen.',
            ]
            yy = h - 149*mm
            for line in cover_lines:
                canvas.drawString(22*mm, yy, line)
                yy -= 5.5*mm
            canvas.setStrokeColor(HexColor('#365A7D') if self.theme != 'clinical' else HexColor('#5A8185'))
            canvas.setLineWidth(.7)
            canvas.line(22*mm, 36*mm, w-22*mm, 36*mm)
            canvas.setFillColor(HexColor('#9FB6CB'))
            canvas.setFont('SleepSans', 7.5)
            canvas.drawString(22*mm, 27*mm, 'SleepMate • Értsd jobban a terápiád')
            canvas.drawRightString(w-22*mm, 27*mm, 'Objektív, nem AI-generált terápiás összesítés')
            canvas.restoreState()
            return
        if self.theme == 'clinical':
            canvas.setFillColor(WHITE)
            canvas.rect(0, h - 17*mm, w, 17*mm, fill=1, stroke=0)
            if logo:
                try: canvas.drawImage(logo, 18*mm, h-13.5*mm, 9*mm, 9*mm, mask='auto', preserveAspectRatio=True)
                except Exception: pass
            canvas.setFillColor(self.accent); canvas.setFont('SleepSansBold', 8.8)
            canvas.drawString(30*mm, h-8.2*mm, 'SleepMate Clinical')
            canvas.setFillColor(MUTED); canvas.setFont('SleepSans', 6.7)
            canvas.drawString(30*mm, h-11.8*mm, 'PAP-terápiás jelentés')
            canvas.setFillColor(self.header_text); canvas.setFont('SleepSansBold', 7.1)
            canvas.drawRightString(w-18*mm, h-8.8*mm, f'{hu_date(self.start_code)} - {hu_date(self.end_code)}')
            canvas.setStrokeColor(self.accent); canvas.setLineWidth(1.15)
            canvas.line(18*mm, h-16.1*mm, w-18*mm, h-16.1*mm)
        else:
            canvas.setFillColor(self.primary)
            canvas.rect(0, h - 18*mm, w, 18*mm, fill=1, stroke=0)
            canvas.setFillColor(self.accent); canvas.rect(0, h-18*mm, 3.5*mm, 18*mm, fill=1, stroke=0)
            if logo:
                try: canvas.drawImage(logo, 18*mm, h-14.5*mm, 10*mm, 10*mm, mask='auto', preserveAspectRatio=True)
                except Exception: pass
            canvas.setFillColor(WHITE); canvas.setFont('SleepSansBold', 9.2)
            canvas.drawString(31*mm, h-8.6*mm, 'SleepMate')
            canvas.setFillColor(HexColor('#BFD1E6')); canvas.setFont('SleepSans', 6.8)
            canvas.drawString(31*mm, h-12.3*mm, 'PAP-terápiás jelentés')
            canvas.setFillColor(self.accent); canvas.setFont('SleepSansBold', 7.1)
            canvas.drawRightString(w-18*mm, h-9.3*mm, f'{hu_date(self.start_code)} - {hu_date(self.end_code)}')
            canvas.setStrokeColor(self.accent); canvas.setLineWidth(.8)
            canvas.line(18*mm, h-17.0*mm, w-18*mm, h-17.0*mm)
        canvas.setStrokeColor(self.card_border); canvas.setLineWidth(.55)
        canvas.line(18*mm, 12*mm, w-18*mm, 12*mm)
        canvas.setFont('SleepSans', 6.8); canvas.setFillColor(MUTED)
        if self.theme == 'clinical':
            canvas.drawString(18*mm, 7.4*mm, 'SleepMate Clinical • objektív, nem AI-generált terápiás összesítés')
        else:
            canvas.drawString(18*mm, 7.4*mm, 'SleepMate • Értsd jobban a terápiád')
        canvas.drawRightString(w-18*mm, 7.4*mm, f'{doc.page}. oldal')
        canvas.restoreState()

    def build(self, out_path: Path) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        doc = BaseDocTemplate(
            str(out_path), pagesize=A4, leftMargin=18*mm, rightMargin=18*mm,
            topMargin=20*mm, bottomMargin=18*mm, title='SleepMate PAP-terápiás jelentés',
            author='SleepMate', subject='PAP-terápiás jelentés',
        )
        frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal')
        doc.addPageTemplates([PageTemplate(id='sleepmate', frames=[frame], onPage=self._page)])
        self._cover()
        if self.config.get('include_patient'):
            self._patient_page()
        if self.section_enabled('summary'): self._summary()
        if self.section_enabled('usage'): self._usage()
        if self.section_enabled('events'): self._events()
        if self.section_enabled('pressure_leak'): self._pressure_leak()
        if self.section_enabled('comparison') and self.compare_previous: self._comparison()
        if self.section_enabled('timeline'): self._timeline_section()
        if self.section_enabled('calendar'): self._calendar()
        if self.section_enabled('assessments'): self._assessments()
        if self.section_enabled('equipment'): self._equipment()
        if self.section_enabled('diagnosis'): self._diagnosis()
        if self.section_enabled('data_quality'): self._data_quality()
        if self.section_enabled('daily_table'):
            self.story.append(CondPageBreak(48*mm))
            self._daily_table()
        if self.section_enabled('glossary'): self._glossary()
        doc.build(self.story)
        return out_path

    def _cover(self):
        # A borító minden elemét az onPage callback rajzolja, így valóban full-bleed lehet.
        self.story.append(PageBreak())

    def _patient_page(self):
        data = self._patient_cover_rows()
        self.story.append(Spacer(1, 3*mm))
        self.story.append(Paragraph('Kezelt személy és terápiás háttér', self.styles['h1']))
        self.story.append(Paragraph('A jelentésbe kiválasztott személyes és terápiás háttéradatok.', self.styles['small']))
        self.story.append(Spacer(1, 4*mm))
        if not data:
            self.story.append(Paragraph('Ehhez a jelentéshez nem lett betegadat kiválasztva.', self.styles['body']))
            self.story.append(PageBreak())
            return
        cells=[]
        for k,v in data:
            cell=Table([
                [Paragraph(_safe(k).upper(), self.styles['metric_label'])],
                [Paragraph(_safe(v), self.styles['body'])],
            ], colWidths=[79*mm])
            cell.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,-1),self.panel_fill),('BOX',(0,0),(-1,-1),.55,self.card_border),
                ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
                ('TOPPADDING',(0,0),(-1,-1),4.5),('BOTTOMPADDING',(0,0),(-1,-1),4.5),
            ]))
            cells.append(cell)
        rows=[]
        for i in range(0,len(cells),2):
            pair=cells[i:i+2]
            while len(pair)<2: pair.append('')
            rows.append(pair)
        tbl=Table(rows,colWidths=[83*mm,83*mm],hAlign='LEFT')
        tbl.setStyle(TableStyle([
            ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),2),('RIGHTPADDING',(0,0),(-1,-1),2),
            ('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2),
        ]))
        self.story.append(tbl)
        self.story.append(Spacer(1, 5*mm))
        note=Table([[Paragraph('<b>A jelentésről</b><br/>A dokumentum a SleepMate által feldolgozott PAP-adatok és a kezelt személyhez helyben rögzített metaadatok összefoglalója. Nem helyettesít orvosi diagnózist vagy terápiás döntést.', self.styles['small'])]], colWidths=[166*mm])
        note.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),self.summary_fill),('BOX',(0,0),(-1,-1),.55,self.card_border),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
        self.story.append(note)
        self.story.append(PageBreak())

    def _patient_cover_rows(self):
        p = self.patient.get('profile') or {}
        rows=[]
        if 'name' in self.patient_fields: rows.append(('Kezelt személy', p.get('name') or '–'))
        if 'birth_date' in self.patient_fields: rows.append(('Születési dátum', hu_date(p.get('birth_date'))))
        if 'age' in self.patient_fields:
            age=age_from_birth(p.get('birth_date')); rows.append(('Életkor', f'{age} év' if age is not None else '–'))
        if 'taj' in self.patient_fields: rows.append(('TAJ', fmt_taj(p.get('taj'))))
        if 'diagnosis' in self.patient_fields:
            d=sorted(self.patient.get('diagnoses') or [], key=lambda x:str(x.get('date') or ''), reverse=True)
            rows.append(('Diagnózis', (d[0].get('diagnosis') or d[0].get('diagnosis_type')) if d else '–'))
        if 'diagnosis_date' in self.patient_fields: rows.append(('Diagnózis dátuma', hu_date(p.get('diagnosis_date'))))
        if 'diagnostic_ahi' in self.patient_fields:
            d=sorted(self.patient.get('diagnoses') or [], key=lambda x:str(x.get('date') or ''), reverse=True)
            rows.append(('Diagnosztikai AHI', num(d[0].get('ahi'),1,' /óra') if d else '–'))
        if 'therapy_start' in self.patient_fields: rows.append(('PAP-terápia kezdete', hu_date(p.get('therapy_start_date'))))
        if 'doctor' in self.patient_fields: rows.append(('Kezelőorvos', p.get('doctor_name') or '–'))
        if 'institution' in self.patient_fields: rows.append(('Kezelőintézmény', p.get('institution') or '–'))
        if 'prescription' in self.patient_fields: rows.append(('Aktuális terápiás előírás', _therapy_label(self.current_rx)))
        if 'device' in self.patient_fields:
            ds=[x for x in self.patient.get('devices') or [] if x.get('active')]; r=(ds or self.patient.get('devices') or [None])[0]
            rows.append(('Aktuális készülék', _record_name(r,'device') if r else '–'))
        if 'mask' in self.patient_fields:
            ms=[x for x in self.patient.get('masks') or [] if x.get('active')]; r=(ms or self.patient.get('masks') or [None])[0]
            rows.append(('Aktuális maszk', _record_name(r,'mask') if r else '–'))
        if 'medications' in self.patient_fields:
            meds=[x for x in self.patient.get('medications') or [] if x.get('active')]
            rows.append(('Aktív gyógyszerek', ', '.join(' '.join(y for y in [str(x.get('name') or ''),str(x.get('strength') or '')] if y).strip() for x in meds) or '–'))
        return rows

    def _title(self, text: str, subtitle: str | None = None):
        self.story.append(CondPageBreak(42*mm))
        self.story.append(Spacer(1, 3*mm))
        if self.theme == 'clinical':
            self.story.append(HRFlowable(width='100%', thickness=.8, color=self.accent, hAlign='LEFT'))
            self.story.append(Spacer(1, 2*mm))
        self.story.append(Paragraph(text, self.styles['h1']))
        if subtitle: self.story.append(Paragraph(subtitle, self.styles['small']))
        self.story.append(Spacer(1, 1.5*mm))

    def _metric_cards(self, metrics: list[tuple[str,str,str]], columns=3):
        rows=[]
        for i in range(0,len(metrics),columns):
            row=[]
            for label,value,note in metrics[i:i+columns]:
                row.append(Table([[Paragraph(_safe(value),self.styles['metric_value'])],[Paragraph(_safe(label),self.styles['metric_label'])],[Paragraph(_safe(note),self.styles['small'])]], colWidths=[self._metric_width(columns)]))
            while len(row)<columns: row.append('')
            rows.append(row)
        tbl=Table(rows,colWidths=[self._metric_width(columns)]*columns,hAlign='LEFT')
        style=[('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]
        tbl.setStyle(TableStyle(style))
        for r in range(len(rows)):
            for c in range(columns):
                cell=rows[r][c]
                if cell!='':
                    cell.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),self.panel_fill),('BOX',(0,0),(-1,-1),0.6,self.card_border),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
        self.story.append(tbl)

    def _metric_width(self, cols): return (A4[0]-36*mm)/cols-2*mm

    def _summary(self):
        self._title('Összefoglaló', 'A kiválasztott időszak legfontosabb, közvetlenül számított terápiás mutatói.')
        days=len(self.rows); therapy=float(self.aggregate.get('therapy_seconds') or 0); avg_usage=therapy/days if days else 0
        four=sum(1 for r in self.rows if float(r.get('therapy_seconds') or 0)>=14400)
        metrics=[
            ('Összesített AHI', num(self.aggregate.get('ahi'),2,' /óra'),'terápiás idővel súlyozva'),
            ('Átlagos használat', seconds_hm(avg_usage),'terápiás napra vetítve'),
            ('4+ órás napok', f'{(100*four/days if days else 0):.0f}%'.replace('.',','), f'{four} / {days} terápiás nap'),
            ('Szivárgás P95', num(self.aggregate.get('leak_p95'),1,' L/perc'),'összes mintából'),
            ('Nyomás P95', num(self.aggregate.get('pressure_p95'),1,' cmH₂O'),'összes mintából'),
            ('Terápiás napok', str(days), f'{hu_date(self.start_code)} – {hu_date(self.end_code)}'),
        ]
        self._metric_cards(metrics,3)
        self.story.append(Spacer(1,5*mm))
        parts=[]
        ahi=self.aggregate.get('ahi'); leak=self.aggregate.get('leak_p95')
        if ahi is not None:
            parts.append(f"Az időszak összesített AHI értéke <b>{num(ahi,2)} /óra</b>." + (' Ez alacsony eseményterhelést jelez.' if ahi < 5 else ' Ez emelkedett eseményterhelést jelez.'))
        if days:
            parts.append(f"A napi átlagos használati idő <b>{seconds_hm(avg_usage)}</b>, a 4 órát elérő napok aránya <b>{100*four/days:.0f}%</b>.")
        if leak is not None: parts.append(f"A teljes időszak szivárgás P95 értéke <b>{num(leak,1)} L/perc</b>.")
        if self.current_rx: parts.append(f"A rögzített aktuális előírás: <b>{_safe(_therapy_label(self.current_rx))}</b>.")
        box=Table([[Paragraph(' '.join(parts) or 'A kiválasztott időszakhoz nincs elegendő összesíthető adat.', self.styles['body'])]], colWidths=[A4[0]-38*mm])
        box.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),self.summary_fill),('BOX',(0,0),(-1,-1),0.7,self.card_border),('LEFTPADDING',(0,0),(-1,-1),12),('RIGHTPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)]))
        self.story.append(box)
        self.story.append(Spacer(1,5*mm))

    def _chart_title(self, title: str, subtitle=''):
        self.story.append(Paragraph(title,self.styles['h2']))
        if subtitle:self.story.append(Paragraph(subtitle,self.styles['small']))

    def _chart_value_label(self, value: float | None) -> str:
        if value is None:
            return '–'
        try:
            v = float(value)
        except Exception:
            return str(value)
        digits = 1 if abs(v) >= 10 else 2
        return num(v, digits)

    def _line_chart(self, values_list: list[list[float | None]], labels: list[str], colors_list: list[Any], width=470, height=170, y_min=None, y_max=None):
        d = Drawing(width, height)
        lp = LinePlot(); lp.x = 42; lp.y = 34; lp.width = width - 58; lp.height = height - 70
        series = []
        flat = []
        for vals in values_list:
            pts = []
            for i, v in enumerate(vals):
                if v is None:
                    continue
                fv = float(v)
                pts.append((i, fv))
                flat.append(fv)
            series.append(pts)
        lp.data = series
        if not flat:
            flat = [0.0]
        data_min = min(flat)
        data_max = max(flat)
        span = max(data_max - data_min, 1.0)
        auto_min = 0 if data_min >= 0 else data_min - span * 0.10
        auto_max = data_max + span * 0.16
        final_y_min = y_min if y_min is not None else auto_min
        final_y_max = y_max if y_max is not None else auto_max
        if final_y_max <= final_y_min:
            final_y_max = final_y_min + 1
        lp.yValueAxis.valueMin = final_y_min
        lp.yValueAxis.valueMax = final_y_max
        lp.yValueAxis.visibleGrid = True; lp.yValueAxis.gridStrokeColor = HexColor('#E4EBF1'); lp.yValueAxis.gridStrokeWidth = .4
        lp.yValueAxis.labelTextFormat = lambda x: str(round(x,1)).replace('.',',')
        lp.yValueAxis.labels.fontName='SleepSans'; lp.yValueAxis.labels.fontSize=6.5; lp.yValueAxis.labels.fillColor=MUTED
        lp.xValueAxis.valueMin = -0.15; lp.xValueAxis.valueMax = max(1, len(self.rows) - .85); lp.xValueAxis.valueStep = max(1, math.ceil(max(1, len(self.rows)-1) / 6))
        lp.xValueAxis.labels.fontName='SleepSans'; lp.xValueAxis.labels.fontSize=6.2; lp.xValueAxis.labels.fillColor=MUTED
        lp.xValueAxis.labelTextFormat = lambda x: (labels[int(round(x))] if labels and 0 <= int(round(x)) < len(labels) and abs(x-int(round(x))) < .45 else '')
        for i, c in enumerate(colors_list):
            lp.lines[i].strokeColor = c; lp.lines[i].strokeWidth = 1.7; lp.lines[i].symbol = None
        d.add(lp)

        def x_to_canvas(idx: int) -> float:
            denom = max(lp.xValueAxis.valueMax - lp.xValueAxis.valueMin, 1e-9)
            return lp.x + ((idx - lp.xValueAxis.valueMin) / denom) * lp.width

        def y_to_canvas(val: float) -> float:
            denom = max(final_y_max - final_y_min, 1e-9)
            return lp.y + ((val - final_y_min) / denom) * lp.height

        max_labels = 10
        label_step = max(1, math.ceil(max(1, len(labels)) / max_labels))
        for si, pts in enumerate(series):
            c = colors_list[min(si, len(colors_list)-1)]
            for idx, val in pts:
                if len(labels) > max_labels and idx % label_step != 0 and idx not in {0, len(labels)-1}:
                    continue
                x = x_to_canvas(idx)
                y = y_to_canvas(val)
                d.add(Circle(x, y, 2.2, fillColor=c, strokeColor=WHITE, strokeWidth=.45))
                label_y = y + 7 + (si * 9)
                label_x = x - 8
                d.add(String(label_x, label_y, self._chart_value_label(val), fontName='SleepSans', fontSize=6.4, fillColor=c))

        lx=48; ly=height-13
        for i,(name,c) in enumerate(zip(self._legend_names or [],colors_list)):
            d.add(Line(lx,ly,lx+14,ly,strokeColor=c,strokeWidth=2))
            d.add(String(lx+18,ly-3,name,fontName='SleepSans',fontSize=7,fillColor=TEXT))
            lx+=90
        return d

    def _bar_chart(self, values: list[float], labels: list[str], color=GREEN, width=470, height=170, reference: float | None=None):
        d = Drawing(width, height)
        bc = VerticalBarChart(); bc.x = 42; bc.y = 34; bc.width = width - 58; bc.height = height - 55
        vals = [float(v or 0) for v in values]
        vmax = max(vals + ([float(reference)] if reference is not None else [0.0]))
        vmax = max(vmax * 1.18, 1.0)
        bc.data=[vals]; bc.valueAxis.valueMin=0; bc.valueAxis.valueMax=vmax; bc.valueAxis.visibleGrid=True; bc.valueAxis.gridStrokeColor=HexColor('#E4EBF1'); bc.valueAxis.labels.fontName='SleepSans'; bc.valueAxis.labels.fontSize=6.5; bc.valueAxis.labels.fillColor=MUTED
        bc.categoryAxis.categoryNames=labels; bc.categoryAxis.labels.fontName='SleepSans'; bc.categoryAxis.labels.fontSize=6; bc.categoryAxis.labels.angle=0
        bc.bars[0].fillColor=color; bc.bars[0].strokeColor=None; bc.barSpacing=3
        d.add(bc)
        bar_count = max(len(vals), 1)
        group_width = bc.width / bar_count
        bar_width = group_width * 0.62
        bar_label_step = max(1, math.ceil(max(1, len(vals)) / 12))
        for i, val in enumerate(vals):
            if len(vals) > 12 and i % bar_label_step != 0 and i not in {0, len(vals)-1}:
                continue
            x = bc.x + (i * group_width) + ((group_width - bar_width) / 2) + (bar_width / 2)
            y = bc.y + (bc.height * (val / vmax if vmax else 0))
            d.add(String(x - 8, y + 6, self._chart_value_label(val), fontName='SleepSans', fontSize=6.4, fillColor=color))
        if reference is not None:
            y = bc.y + bc.height * (float(reference) / vmax if vmax else 0)
            d.add(Line(bc.x,y,bc.x+bc.width,y,strokeColor=ORANGE,strokeWidth=.8,strokeDashArray=[3,2]))
            d.add(String(bc.x+bc.width-45,y+3,'4 óra',fontName='SleepSans',fontSize=6.5,fillColor=ORANGE))
        return d

    def _usage(self):
        self._title('Használat és compliance')
        labels=[hu_date(r.get('day'))[5:10] for r in self.rows]
        vals=[round(float(r.get('therapy_seconds') or 0)/3600,2) for r in self.rows]
        self.story.append(self._bar_chart(vals,labels,self.chart_primary,reference=4))
        days=len(vals); four=sum(1 for v in vals if v>=4)
        info=[
            ['Terápiás napok',str(days)],['4+ órás napok',f'{four} ({(100*four/days if days else 0):.0f}%)'],
            ['Átlagos használat',seconds_hm(sum(float(r.get('therapy_seconds') or 0) for r in self.rows)/days if days else 0)],
            ['Minimum',seconds_hm(min((float(r.get('therapy_seconds') or 0) for r in self.rows),default=0))],
            ['Maximum',seconds_hm(max((float(r.get('therapy_seconds') or 0) for r in self.rows),default=0))],
        ]
        self.story.append(self._two_col_info(info))
        self.story.append(Spacer(1,5*mm))

    def _events(self):
        self._title('AHI és légzési események')
        labels=[hu_date(r.get('day'))[5:10] for r in self.rows]
        self._legend_names=['AHI']
        self.story.append(self._line_chart([[r.get('ahi') for r in self.rows]],labels,[self.chart_primary]))
        counts={k:sum(int((r.get('counts') or {}).get(k) or 0) for r in self.rows) for k in ('OA','CA','H','RERA')}
        hours=float(self.aggregate.get('therapy_seconds') or 0)/3600
        total=sum(counts.values())
        rows=[['Eseménytípus','Darab','Index (/óra)','Rövid jelentés']]
        meanings={
            'OA':'Obstruktív apnoe',
            'CA':'Centrális apnoe',
            'H':'Hipopnoe',
            'RERA':'Légzési erőfeszítéshez társuló mikroébredés',
        }
        for k in ('OA','CA','H','RERA'):
            rows.append([k,str(counts[k]),num(counts[k]/hours if hours else None,2),meanings[k]])
        rows.append(['Összesen',str(total),num(total/hours if hours else None,2),'A négy felsorolt eseménytípus összege'])
        self.story.append(self._table(rows,[30*mm,25*mm,34*mm,85*mm],header=True,font_size=7.1))
        self.story.append(Spacer(1,5*mm))

    def _pressure_leak(self):
        self._title('Nyomás és szivárgás', 'A medián és P95 értékek együtt mutatják a terápia jellemző és magasabb tartományait.')
        labels=[hu_date(r.get('day'))[5:10] for r in self.rows]
        self._legend_names=['Medián','P95']
        pressure_chart=self._line_chart(
            [[r.get('pressure_median') for r in self.rows],[r.get('pressure_p95') for r in self.rows]],
            labels,self.pressure_colors,width=450,height=178
        )
        pressure_note = f'Előírás: {_therapy_label(self.current_rx)}' if self.current_rx else 'Nincs rögzített aktuális előírás.'
        pbox=Table([
            [Paragraph('Nyomás trend',self.styles['h2'])],
            [pressure_chart],
            [Paragraph(_safe(pressure_note),self.styles['small'])],
        ],colWidths=[166*mm],hAlign='LEFT')
        pbox.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),self.panel_fill),('BOX',(0,0),(-1,-1),.6,self.card_border),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),('VALIGN',(0,0),(-1,-1),'TOP')]))
        self.story.append(KeepTogether([pbox]))
        self.story.append(Spacer(1,5*mm))

        # A második grafikon külön blokk és külön oldalrész: nem zsugorítjuk kétoszlopos elrendezésbe.
        self.story.append(CondPageBreak(72*mm))
        self._legend_names=['Medián','P95']
        leak_chart=self._line_chart(
            [[r.get('leak_median') for r in self.rows],[r.get('leak_p95') for r in self.rows]],
            labels,self.leak_colors,width=450,height=178
        )
        lbox=Table([
            [Paragraph('Szivárgás trend',self.styles['h2'])],
            [leak_chart],
            [Paragraph('A P95 megmutatja a magasabb szivárgási tartományt, nem csak egyetlen csúcsértéket.',self.styles['small'])],
        ],colWidths=[166*mm],hAlign='LEFT')
        lbox.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),self.panel_fill),('BOX',(0,0),(-1,-1),.6,self.card_border),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),('VALIGN',(0,0),(-1,-1),'TOP')]))
        self.story.append(KeepTogether([lbox]))
        self.story.append(Spacer(1,5*mm))

    def _comparison(self):
        if not self.start_code or not self.end_code:return
        a=datetime.strptime(self.start_code,'%Y%m%d').date();b=datetime.strptime(self.end_code,'%Y%m%d').date();span=(b-a).days+1
        prev_end=a-timedelta(days=1);prev_start=prev_end-timedelta(days=span-1)
        cmp=self.dataset.compare_periods(prev_start.isoformat(),prev_end.isoformat(),a.isoformat(),b.isoformat())
        pa,pb=cmp.get('period_a') or {},cmp.get('period_b') or {}
        if not pa.get('days'): return
        self._title('Összehasonlítás az előző azonos hosszúságú időszakkal',f'{hu_date(prev_start.isoformat())} – {hu_date(prev_end.isoformat())}  ↔  {hu_date(a.isoformat())} – {hu_date(b.isoformat())}')
        def arrow(old,new,unit='',digits=1,lower_better=False):
            if old is None or new is None:return '–'
            d=float(new)-float(old); pct=(d/float(old)*100) if old not in (0,None) else None
            sym='↓' if d<0 else ('↑' if d>0 else '→')
            return f'{num(old,digits,unit)} → <b>{num(new,digits,unit)}</b> {sym}' + (f' {abs(pct):.0f}%'.replace('.',',') if pct is not None else '')
        data=[
            ['Mutató','Előző → jelenlegi'],
            ['AHI',arrow(pa.get('ahi'),pb.get('ahi'),' /óra',2,True)],
            ['Átlagos használat',f"{seconds_hm(pa.get('average_usage_seconds'))} → <b>{seconds_hm(pb.get('average_usage_seconds'))}</b>"],
            ['Szivárgás P95',arrow(pa.get('leak_p95'),pb.get('leak_p95'),' L/perc',1,True)],
            ['Nyomás P95',arrow(pa.get('pressure_p95'),pb.get('pressure_p95'),' cmH₂O',1)],
            ['OA index',arrow((pa.get('event_index') or {}).get('OA'),(pb.get('event_index') or {}).get('OA'),' /óra',2,True)],
            ['CA index',arrow((pa.get('event_index') or {}).get('CA'),(pb.get('event_index') or {}).get('CA'),' /óra',2,True)],
            ['H index',arrow((pa.get('event_index') or {}).get('H'),(pb.get('event_index') or {}).get('H'),' /óra',2,True)],
            ['RERA index',arrow((pa.get('event_index') or {}).get('RERA'),(pb.get('event_index') or {}).get('RERA'),' /óra',2,True)],
        ]
        # allow bold tags
        formatted=[[Paragraph(str(c),self.styles['body']) for c in row] for row in data]
        t=Table(formatted,colWidths=[55*mm,115*mm]);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),self.primary),('TEXTCOLOR',(0,0),(-1,0),WHITE),('BOX',(0,0),(-1,-1),.5,self.card_border),('INNERGRID',(0,0),(-1,-1),.3,self.card_border),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]));self.story.append(t);self.story.append(Spacer(1,5*mm))

    def _timeline_section(self):
        selected=[x for x in self.timeline if (not self.start_code or _date_code(x['date'])>=self.start_code) and (not self.end_code or _date_code(x['date'])<=self.end_code)]
        if not selected:return
        self._title('Terápiaváltozások idővonala')
        rows=[]
        icon={'start':'☾','prescription':'⚙','titration':'↕','device':'▣','mask':'◉','accessory':'+','medication':'✚','weight':'⚖','control':'⌂','custom':'✦'}
        for x in selected:
            rows.append([Paragraph(icon.get(x['kind'],'•'),self.styles['center']),Paragraph(f"<b>{hu_date(x['date'])}</b><br/>{_safe(x['title'])}",self.styles['body']),Paragraph(_safe(x['detail']),self.styles['small'])])
        t=Table(rows,colWidths=[10*mm,55*mm,105*mm]);t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(1,0),(-1,-2),.35,self.card_border),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('BACKGROUND',(0,0),(0,-1),self.summary_fill)]));self.story.append(t);self.story.append(Spacer(1,5*mm))

    def _calendar(self):
        if not self.rows:return
        self._title('Napi eredmények - naptár')
        by_month={}
        for r in self.rows: by_month.setdefault(str(r['day'])[:6],[]).append(r)
        for month,rows in sorted(by_month.items()):
            y,m=int(month[:4]),int(month[4:6])
            self.story.append(CondPageBreak(58*mm))
            self.story.append(Paragraph(f'{y}. {m:02d}.',self.styles['h2']))
            mapping={int(r['day'][6:8]):r for r in rows}
            cal=calendar.Calendar(firstweekday=0).monthdayscalendar(y,m)
            weekday_names=['Hétfő','Kedd','Szerda','Csütörtök','Péntek','Szombat','Vasárnap']
            grid=[[Paragraph(x,ParagraphStyle('CalHead'+x,parent=self.styles['center'],fontName='SleepSansBold',fontSize=7.1,leading=9,textColor=WHITE)) for x in weekday_names]]
            outside_cells=[]
            no_data_cells=[]
            for wi,week in enumerate(cal, start=1):
                rr=[]
                for ci,d in enumerate(week):
                    if not d:
                        rr.append('')
                        outside_cells.append((ci,wi))
                        continue
                    r=mapping.get(d)
                    if not r:
                        rr.append(Paragraph(f'<b>{d}</b><br/><font color="#7B8794">nincs adat</font>',self.styles['small']))
                        no_data_cells.append((ci,wi))
                        continue
                    ahi=r.get('ahi'); leak=r.get('leak_p95'); usage=float(r.get('therapy_seconds') or 0)
                    rr.append(Paragraph(f'<b>{d}</b><br/>AHI {num(ahi,2)}<br/>{seconds_hm(usage).replace(" óra ",":").replace(" perc","")}<br/>Sziv. {num(leak,1)}',self.styles['small']))
                grid.append(rr)
            t=Table(grid,colWidths=[24*mm]*7,rowHeights=[8*mm]+[21*mm]*(len(grid)-1),repeatRows=1,hAlign='LEFT')
            style=[
                ('BACKGROUND',(0,0),(-1,0),self.primary),('TEXTCOLOR',(0,0),(-1,0),WHITE),
                ('BOX',(0,0),(-1,-1),.45,self.card_border),('INNERGRID',(0,0),(-1,-1),.3,self.card_border),
                ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),
                ('TOPPADDING',(0,1),(-1,-1),3),('BOTTOMPADDING',(0,1),(-1,-1),3),
            ]
            for c,ridx in outside_cells:
                style.append(('BACKGROUND',(c,ridx),(c,ridx),HexColor('#E5E9EE')))
            for c,ridx in no_data_cells:
                style.append(('BACKGROUND',(c,ridx),(c,ridx),HexColor('#F0F2F5')))
            t.setStyle(TableStyle(style))
            self.story.append(KeepTogether([t]))
            self.story.append(Spacer(1,6*mm))
        self.story.append(Spacer(1,5*mm))

    def _assessments(self):
        rows=[x for x in self.patient.get('daily_assessments') or [] if (not self.start_code or _date_code(x.get('day',''))>=self.start_code) and (not self.end_code or _date_code(x.get('day',''))<=self.end_code)]
        if not rows:return
        self._title('Saját napi értékelések')
        qualities=[float(x.get('sleep_quality')) for x in rows if x.get('sleep_quality') not in ('',None)]
        awak=[float(x.get('awakenings')) for x in rows if x.get('awakenings') not in ('',None)]
        self._metric_cards([
            ('Átlagos alvásminőség',num(sum(qualities)/len(qualities) if qualities else None,1,' / 10'),f'{len(qualities)} rögzített nap'),
            ('Átlagos ébredésszám',num(sum(awak)/len(awak) if awak else None,1),f'{len(awak)} rögzített nap'),
            ('Értékelt napok',str(len(rows)),'saját bevitel'),
        ],3)
        data=[['Dátum','Alvásminőség','Ébredés','Fejfájás','Fáradtság','Tünetek']]
        for x in sorted(rows,key=lambda z:str(z.get('day') or '')):
            sym=', '.join(y for y in [('szájszárazság' if x.get('dry_mouth') else ''),('orrdugulás' if x.get('congestion') else '')] if y) or '–'
            data.append([hu_date(x.get('day')),str(x.get('sleep_quality') or '–'),str(x.get('awakenings') or '–'),str(x.get('headache') or '–'),str(x.get('fatigue') or '–'),sym])
        self.story.append(self._table(data,[27*mm,30*mm,23*mm,29*mm,29*mm,39*mm],header=True));self.story.append(Spacer(1,5*mm))

    def _equipment(self):
        ds=self.patient.get('devices') or [];ms=self.patient.get('masks') or [];acs=self.patient.get('accessories') or []
        if not (ds or ms or acs):return
        self._title('Felszerelés')
        data=[['Típus','Megnevezés','Használat kezdete','Állapot']]
        for kind,label,rows in [('device','Készülék',ds),('mask','Maszk',ms),('accessory','Kiegészítő',acs)]:
            for r in rows:
                data.append([label,_record_name(r,kind),hu_date(r.get('start_date')),'Aktív' if r.get('active') else 'Korábbi'])
        self.story.append(self._table(data,[28*mm,78*mm,38*mm,30*mm],header=True));self.story.append(Spacer(1,5*mm))

    def _diagnosis(self):
        diagnoses=self.patient.get('diagnoses') or [];titr=self.patient.get('titrations') or []
        if not (diagnoses or titr):return
        self._title('Diagnosztika és titrálások')
        if diagnoses:
            data=[['Dátum','Típus','AHI','ODI','SpO₂ min.','Megjegyzés']]
            for r in sorted(diagnoses,key=lambda x:str(x.get('date') or ''),reverse=True):data.append([hu_date(r.get('date')),r.get('diagnosis_type') or '–',num(r.get('ahi'),1),num(r.get('odi'),1),num(r.get('spo2_min'),1,'%'),r.get('diagnosis') or '–'])
            self.story.append(Paragraph('Diagnózis / vizsgálatok',self.styles['h2']));self.story.append(self._table(data,[25*mm,24*mm,18*mm,18*mm,22*mm,67*mm],header=True));self.story.append(Spacer(1,5*mm))
        if titr:
            data=[['Dátum','Típus','Javasolt nyomás','AHI','CAI','SpO₂ min.']]
            for r in sorted(titr,key=lambda x:str(x.get('date') or ''),reverse=True):data.append([hu_date(r.get('date')),r.get('type') or '–',_therapy_label(r),num(r.get('ahi'),1),num(r.get('central_ahi'),1),num(r.get('spo2_min'),1,'%')])
            self.story.append(Paragraph('Titrálások',self.styles['h2']));self.story.append(self._table(data,[25*mm,32*mm,50*mm,18*mm,18*mm,28*mm],header=True))
        self.story.append(Spacer(1,5*mm))

    def _data_quality(self):
        self._title('Adatminőség')
        damaged=len(self.diag.get('damaged_files') or []); missing=len(self.diag.get('missing_required') or []); edf=int(self.diag.get('edf_files') or 0)
        items=[('Részletes EDF-fájlok',f'{edf} fájl',edf>0),('Sérült / csonka EDF',f'{damaged} probléma',damaged==0),('Hiányzó BRP / PLD / EVE',f'{missing} szakasz',missing==0),('SpO₂ / pulzus', 'rendelkezésre áll' if any(r.get('spo2_median') is not None for r in self.rows) else 'nem áll rendelkezésre', any(r.get('spo2_median') is not None for r in self.rows))]
        rows=[]
        for label,value,ok in items: rows.append([Paragraph('✓' if ok else '!',self.styles['center']),Paragraph(_safe(label),self.styles['body']),Paragraph(_safe(value),self.styles['body'])])
        t=Table(rows,colWidths=[12*mm,80*mm,80*mm]);t.setStyle(TableStyle([('BACKGROUND',(0,0),(0,-1),GREEN_LIGHT),('BOX',(0,0),(-1,-1),.5,LINE),('INNERGRID',(0,0),(-1,-1),.3,LINE),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]));self.story.append(t)
        if self.diag.get('str_warning'): self.story.append(Spacer(1,4*mm));self.story.append(Paragraph('Figyelmeztetés: '+_safe(self.diag['str_warning']),self.styles['small']))
        self.story.append(Spacer(1,5*mm))

    def _daily_table(self):
        self._title('Részletes napi táblázat', 'Melléklet - napi terápiás összesítés.')
        data=[['Dátum','Használat','AHI','OA','CA','H','RERA','Sziv. P95','Nyomás P50','Nyomás P95']]
        for r in self.rows:
            c=r.get('counts') or {};data.append([hu_date(r.get('day')),seconds_hm(r.get('therapy_seconds')).replace(' óra ',':').replace(' perc',''),num(r.get('ahi'),2),str(c.get('OA',0)),str(c.get('CA',0)),str(c.get('H',0)),str(c.get('RERA',0)),num(r.get('leak_p95'),1),num(r.get('pressure_median'),1),num(r.get('pressure_p95'),1)])
        self.story.append(self._table(data,[23*mm,22*mm,16*mm,12*mm,12*mm,12*mm,14*mm,21*mm,22*mm,22*mm],header=True,font_size=6.5))

    def _glossary(self):
        self.story.append(Spacer(1,6*mm));self.story.append(Paragraph('Értelmezési kulcs',self.styles['h2']))
        rows=[['AHI','Az óránkénti apnoe- és hipopnoe-események száma.'],['P95','Az érték a vizsgált minták 95%-ában ezen a szinten vagy ez alatt volt.'],['OA','Obstruktív apnoe.'],['CA','Centrális apnoe.'],['H','Hipopnoe.'],['RERA','Fokozott légzési erőfeszítéshez kapcsolódó mikroébredés.']]
        self.story.append(self._table(rows,[28*mm,145*mm],header=False))

    def _two_col_info(self, items):
        cells=[]
        for label,value in items: cells.append(Table([[Paragraph(_safe(label),self.styles['small'])],[Paragraph(_safe(value),self.styles['h3'])]],colWidths=[52*mm]))
        rows=[]
        for i in range(0,len(cells),3):rows.append(cells[i:i+3]+['']*(3-len(cells[i:i+3])))
        t=Table(rows,colWidths=[58*mm]*3);t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3),('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3)]));return t

    def _table(self, data, widths, header=False, font_size=7.4):
        out=[]
        for ri,row in enumerate(data):
            st=ParagraphStyle('Tbl'+str(ri),fontName='SleepSansBold' if header and ri==0 else 'SleepSans',fontSize=font_size,leading=font_size+2.4,textColor=WHITE if header and ri==0 else TEXT)
            out.append([Paragraph(_safe(c),st) for c in row])
        t=Table(out,colWidths=widths,repeatRows=1 if header else 0,hAlign='LEFT')
        style=[('BOX',(0,0),(-1,-1),.45,self.card_border),('INNERGRID',(0,0),(-1,-1),.25,self.card_border),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]
        if header: style += [('BACKGROUND',(0,0),(-1,0),self.primary)]
        for i in range(1 if header else 0,len(out)):
            if i%2==0:style.append(('BACKGROUND',(0,i),(-1,i),self.panel_fill))
        t.setStyle(TableStyle(style));return t


def generate_report_pdf(dataset, patient_store, start: str, end: str, config: dict[str, Any], base_dir: Path, out_path: Path) -> Path:
    if not dataset.days():
        raise ValueError('Nincs PDF-be foglalható terápiás adat.')
    report = SleepMateReport(ReportContext(dataset, patient_store, start, end, config, base_dir))
    if not report.rows:
        raise ValueError('A kiválasztott időszakban nincs terápiás adat.')
    return report.build(out_path)
