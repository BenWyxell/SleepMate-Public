from __future__ import annotations

from pathlib import Path
from statistics import mean
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, CondPageBreak, Spacer

from . import report_pdf as rp
from .o2ring_integration import get_service


_installed = False


def _oximetry_section(self: rp.SleepMateReport) -> None:
    service = get_service()
    rows: list[dict[str, Any]] = []
    for day in self.days:
        try:
            data = service.daily(day, max_points=2000)
        except Exception:
            continue
        if data.get("available") and data.get("summary"):
            rows.append({"day": day, **(data.get("summary") or {}), "matches": data.get("matches") or []})
    if not rows:
        return

    self._title("Oximetria és pulzus", "Wellue / Viatom O2Ring – kizárólag a PAP-terápiás szakaszokkal időben átfedő mérések.")
    def vals(key): return [float(r[key]) for r in rows if r.get(key) is not None]
    spo2_avg, spo2_min, t90, hr_avg, odi3, odi4 = vals("spo2_average"), vals("spo2_minimum"), vals("t90_seconds"), vals("heart_rate_average"), vals("odi3"), vals("odi4")
    coverage = vals("coverage_percent")
    metrics = [
        ("Átlagos SpO₂", rp.num(mean(spo2_avg),1,"%") if spo2_avg else "–", "CPAP-időre illesztve"),
        ("Legalacsonyabb SpO₂", rp.num(min(spo2_min),0,"%") if spo2_min else "–", "időszaki minimum"),
        ("T90 összesen", rp.seconds_hm(sum(t90)) if t90 else "–", "90% alatt töltött idő"),
        ("Átlagpulzus", rp.num(mean(hr_avg),1," bpm") if hr_avg else "–", "érvényes mintákból"),
        ("ODI3 / ODI4", f"{rp.num(mean(odi3),1)} / {rp.num(mean(odi4),1)}" if odi3 and odi4 else "–", "SleepMate számítás"),
        ("Oximetriai lefedettség", rp.num(mean(coverage),1,"%") if coverage else "–", f"{len(rows)} terápiás nap"),
    ]
    self._metric_cards(metrics, 3)
    self.story.append(Spacer(1, 5*mm))
    labels=[rp.hu_date(r.get("day")) for r in rows]
    self._chart_title("SpO₂ trend", "Napi átlag és minimum a CPAP-időszakokra illesztve.")
    self.story.append(self._line_chart([[r.get("spo2_average") for r in rows],[r.get("spo2_minimum") for r in rows]],labels,[self.chart_primary,self.chart_secondary],y_min=70,y_max=100))
    self.story.append(Spacer(1, 4*mm))
    self._chart_title("Pulzus és T90", "Átlagpulzus, illetve a 90% alatti oxigénszint időtartama.")
    self.story.append(self._line_chart([[r.get("heart_rate_average") for r in rows]],labels,[self.chart_primary],y_min=30))
    self.story.append(Spacer(1, 3*mm))
    t90_minutes=[(float(r.get("t90_seconds") or 0)/60.0) for r in rows]
    self.story.append(self._line_chart([t90_minutes],labels,[self.chart_secondary],y_min=0))
    self.story.append(Spacer(1, 4*mm))
    self.story.append(rp.Paragraph(
        "Az O2Ring-adatok időbélyeg alapján kerülnek a PAP-szakaszokra. A PAP előtti és utáni oximetriai minták ebben a jelentésblokkban nem szerepelnek. Az oximetriai mutatók kiegészítő tájékoztatást adnak, és nem helyettesítenek orvosi értékelést.",
        self.styles["small"],
    ))


def _build_with_oximetry(self: rp.SleepMateReport, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(str(out_path), pagesize=A4, leftMargin=18*mm, rightMargin=18*mm, topMargin=20*mm, bottomMargin=18*mm,
                          title='SleepMate PAP-terápiás jelentés', author='SleepMate', subject='PAP-terápiás jelentés')
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal')
    doc.addPageTemplates([PageTemplate(id='sleepmate', frames=[frame], onPage=self._page)])
    self._cover()
    if self.config.get('include_patient'): self._patient_page()
    if self.section_enabled('summary'): self._summary()
    if self.section_enabled('usage'): self._usage()
    if self.section_enabled('events'): self._events()
    if self.section_enabled('pressure_leak'): self._pressure_leak()
    if self.section_enabled('comparison') and self.compare_previous: self._comparison()
    if self.section_enabled('oximetry'): self._oximetry()
    if self.section_enabled('timeline'): self._timeline_section()
    if self.section_enabled('calendar'): self._calendar()
    if self.section_enabled('assessments'): self._assessments()
    if self.section_enabled('equipment'): self._equipment()
    if self.section_enabled('diagnosis'): self._diagnosis()
    if self.section_enabled('data_quality'): self._data_quality()
    if self.section_enabled('daily_table'):
        self.story.append(CondPageBreak(48*mm)); self._daily_table()
    if self.section_enabled('glossary'): self._glossary()
    doc.build(self.story)
    return out_path


def install_o2ring_report() -> None:
    global _installed
    if _installed: return
    rp.SleepMateReport._oximetry = _oximetry_section
    rp.SleepMateReport.build = _build_with_oximetry
    _installed = True


__all__ = ["install_o2ring_report"]
