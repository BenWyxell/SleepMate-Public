from __future__ import annotations

from pathlib import Path


VERSION = "5.3.11"


def replace_required(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise SystemExit(f"Missing release marker: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    version_file = Path("cpap/version.py")
    text = version_file.read_text(encoding="utf-8")
    text = replace_required(text, 'APP_VERSION = "5.3.10"', 'APP_VERSION = "5.3.11"', "APP_VERSION")
    version_file.write_text(text, encoding="utf-8")

    for path in (Path("web/service-worker.js"), Path("web/service-worker-v508-base.js")):
        sw = path.read_text(encoding="utf-8")
        sw = sw.replace("sleepmate-shell-v5.3.10-o2-hydration-1", "sleepmate-shell-v5.3.11-o2-hydration-1")
        sw = sw.replace(
            "active caches are v5.3.9:",
            "active shell cache is v5.3.11; API cache compatibility remains v5.3.9:",
        )
        path.write_text(sw, encoding="utf-8")

    for path in Path("tests").rglob("*.py"):
        test = path.read_text(encoding="utf-8")
        if "5.3.10" in test:
            path.write_text(test.replace("5.3.10", "5.3.11"), encoding="utf-8")

    patch_file = Path("cpap/v530_features.py")
    patch = patch_file.read_text(encoding="utf-8")
    marker = '    text = _replace_required(text, old_draw, new_draw, "Dashboard O2 AHI-style renderer")\n\n'
    if "Dashboard O2 AHI-style layout" not in patch:
        if marker not in patch:
            raise SystemExit("Dashboard O2 renderer marker missing")
        old_section = '''function ensureDashboardO2Section(){const agg=q('#dashboardOverviewView .aggregate-cards');if(!agg)return null;let sec=id('smDashboardO2V534');if(!sec){sec=document.createElement('section');sec.id='smDashboardO2V534';sec.className='panel sm-dashboard-o2-v534';sec.dataset.o2ringFeature='1';sec.innerHTML='<div class="panel-head"><div><h3>Oximetriai összegzés</h3><span>CPAP-idővel átfedő O2Ring-adatok.</span></div><button id="smDashO2Open">Oximetria →</button></div><div class="sm-dashboard-o2-cards"><div><span>Medián SpO₂</span><b id="smDashO2Avg">—</b></div><div><span>Minimum SpO₂</span><b id="smDashO2Min">—</b></div><div><span>Medián pulzus</span><b id="smDashHrAvg">—</b></div><div><span>Átlag T90</span><b id="smDashT90">—</b></div></div><div class="sm-dashboard-o2-mini"><article><header>SpO₂ trend</header><div class="sm-o2-chart-wrap"><canvas id="smDashO2Trend"></canvas></div></article><article><header>Pulzus trend</header><div class="sm-o2-chart-wrap"><canvas id="smDashHrTrend"></canvas></div></article></div><div id="smDashO2Empty" class="o2r-empty hidden">Ebben az időszakban még nincs illesztett O2Ring adat.</div>';agg.insertAdjacentElement('afterend',sec);id('smDashO2Open').onclick=()=>openOximetry('recordings')}return sec}'''
        new_section = '''function ensureDashboardO2Section(){const agg=q('#dashboardOverviewView .aggregate-cards');if(!agg)return null;let sec=id('smDashboardO2V534');if(!sec){sec=document.createElement('section');sec.id='smDashboardO2V534';sec.className='sm-dashboard-o2-v534';sec.dataset.o2ringFeature='1';sec.innerHTML=`<section class="panel sm-dashboard-o2-summary"><div class="panel-head"><div><h3>Oximetriai összegzés</h3><span>CPAP-idővel átfedő O2Ring-adatok.</span></div><button id="smDashO2Open">Oximetria →</button></div><div class="sm-dashboard-o2-cards"><div><span>Medián SpO₂</span><b id="smDashO2Avg">—</b></div><div><span>Minimum SpO₂</span><b id="smDashO2Min">—</b></div><div><span>Medián pulzus</span><b id="smDashHrAvg">—</b></div><div><span>Átlag T90</span><b id="smDashT90">—</b></div></div><div id="smDashO2Empty" class="o2r-empty hidden">Ebben az időszakban még nincs illesztett O2Ring adat.</div></section><section class="trend-grid sm-dashboard-o2-trends"><article class="panel trend-card"><div class="panel-head"><h3>SpO₂ trend</h3><span>medián</span></div><canvas id="smDashO2Trend"></canvas></article><article class="panel trend-card"><div class="panel-head"><h3>Pulzus trend</h3><span>medián bpm</span></div><canvas id="smDashHrTrend"></canvas></article></section>`;agg.insertAdjacentElement('afterend',sec);id('smDashO2Open').onclick=()=>openOximetry('recordings')}return sec}'''
        addition = (
            '    old_section = """' + old_section + '"""\n'
            '    new_section = """' + new_section + '"""\n'
            '    text = _replace_required(text, old_section, new_section, "Dashboard O2 AHI-style layout")\n\n'
        )
        patch = patch.replace(marker, marker + addition, 1)
    patch_file.write_text(patch, encoding="utf-8")

    release_note = Path("release-notes/v5.3.11.md")
    latest = release_note.read_text(encoding="utf-8").rstrip()
    if not latest.startswith("# SleepMate 5.3.11\n"):
        raise SystemExit("Unexpected v5.3.11 release note header")
    if "Release build: **5.3.11**." not in latest or "Kiadási csatorna: **stable**." not in latest:
        raise SystemExit("Missing v5.3.11 release identity markers")

    notes = Path("RELEASE_NOTES.md")
    current = notes.read_text(encoding="utf-8")
    if current.startswith("# SleepMate 5.3.11\n"):
        _, sep, rest = current.partition("\n---\n")
        notes.write_text(latest + ("\n\n---\n" + rest if sep else "\n"), encoding="utf-8")
    else:
        notes.write_text(latest + "\n\n---\n" + current, encoding="utf-8")

    Path(__file__).unlink()


if __name__ == "__main__":
    main()
