from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
import urllib.parse

from . import sleep_analysis as sa

_installed = False

def _range_from_period(rows: list[dict[str, Any]], period_raw: str):
    if not rows:
        return None, None, "Nincs adat"
    latest = datetime.fromisoformat(rows[-1]["date"]).date()
    period_raw = str(period_raw or "all").lower().strip()
    if period_raw == "all": return None, None, "Teljes időszak"
    if period_raw == "prev7": return latest - timedelta(days=13), latest - timedelta(days=7), "Előző 7 nap"
    if period_raw == "prev30": return latest - timedelta(days=59), latest - timedelta(days=30), "Előző 30 nap"
    if period_raw.startswith("range:"):
        parts = period_raw.split(":", 2)
        if len(parts) != 3: raise ValueError("Az egyedi dátumtartomány formátuma hibás.")
        start = datetime.fromisoformat(parts[1]).date(); end = datetime.fromisoformat(parts[2]).date()
        if start > end: start, end = end, start
        return start, end, "Egyedi időszak"
    if period_raw == "day": return latest, latest, "Legutóbbi alvásnap"
    if period_raw == "prev_week": return latest - timedelta(days=13), latest - timedelta(days=7), "Előző 7 nap"
    if period_raw == "prev_month": return latest - timedelta(days=59), latest - timedelta(days=30), "Előző 30 nap"
    try: days = max(1, int(period_raw))
    except ValueError: return None, None, "Teljes időszak"
    return latest - timedelta(days=days - 1), latest, f"Utolsó {days} nap"

def analyze(self: sa.SleepAnalysisService, dataset, period: str = "all") -> dict[str, Any]:
    full = self._full_payload(dataset); all_rows = list(full.get("rows") or []); period_raw = str(period or "all").lower().strip()
    start, end, label = _range_from_period(all_rows, period_raw); rows = all_rows
    if start is not None and end is not None: rows = [row for row in rows if start <= datetime.fromisoformat(row["date"]).date() <= end]
    main_days = [r for r in rows if float(r.get("main_seconds") or 0) > 0]
    total_s = sum(float(r.get("total_seconds") or 0) for r in rows); main_s = sum(float(r.get("main_seconds") or 0) for r in rows)
    nap_s = sum(float(r.get("nap_seconds") or 0) for r in rows); short_s = sum(float(r.get("short_seconds") or 0) for r in rows)
    summary = {"days":len(rows),"main_days":len(main_days),"main_seconds":round(main_s,3),"nap_seconds":round(nap_s,3),"short_seconds":round(short_s,3),"total_seconds":round(total_s,3),"average_main_seconds":round(main_s/len(main_days),3) if main_days else 0,"average_total_seconds":round(total_s/len(rows),3) if rows else 0,"nap_count":sum(int(r.get("nap_count") or 0) for r in rows),"short_count":sum(int(r.get("short_count") or 0) for r in rows),"fragmented_main_days":sum(1 for r in rows if int(r.get("main_parts") or 0)>1)}
    return {"generated_at":full.get("generated_at"),"period":period_raw,"filter":{"label":label,"start":start.isoformat() if start else (rows[0]["date"] if rows else None),"end":end.isoformat() if end else (rows[-1]["date"] if rows else None)},"settings":full.get("settings"),"learned":full.get("learned"),"overrides":full.get("overrides"),"summary":summary,"rows":rows,"latest":rows[-1] if rows else None}

def _install_shell_loader(app_module) -> None:
    handler_cls = app_module.Handler; previous_get = handler_cls.do_GET
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            try:
                index_path = app_module.WEB / "index.html"; text = index_path.read_text(encoding="utf-8"); scripts: list[str] = []
                if "sleepmate-sleep.js" not in text: scripts.append('<script src="/sleepmate-sleep.js?v=5.2.6"></script>')
                if "sleepmate-sleep-v523.js" not in text: scripts.append('<script src="/sleepmate-sleep-v523.js?v=5.2.6"></script>')
                if "sleepmate-chart-v523.js" not in text: scripts.append('<script src="/sleepmate-chart-v523.js?v=5.2.14"></script>')
                if "sleepmate-sleep-v524.js" not in text: scripts.append('<script src="/sleepmate-sleep-v524.js?v=5.2.6"></script>')
                if "sleepmate-sleep-refresh-v5212.js" not in text: scripts.append('<script src="/sleepmate-sleep-refresh-v5212.js?v=5.2.12"></script>')
                if "o2ring.js" not in text: scripts.append('<script src="/o2ring.js?v=5.3.0"></script>')
                if "o2ring-report-ui.js" not in text: scripts.append('<script src="/o2ring-report-ui.js?v=5.3.0"></script>')
                if scripts:
                    marker="</body>"; inject="\n"+"\n".join(scripts)+"\n"; text=text.replace(marker,inject+marker,1) if marker in text else text+inject
                body=text.encode("utf-8"); self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Content-Length",str(len(body))); self.send_header("Cache-Control","no-cache"); self.end_headers(); self.wfile.write(body); return
            except Exception: pass
        return previous_get(self)
    handler_cls.do_GET = do_GET

def install_sleep_analysis_v522(app_module) -> None:
    global _installed
    if _installed: return
    sa.SleepAnalysisService.analyze = analyze
    from .sleep_refresh_v5212 import install_sleep_refresh_v5212
    install_sleep_refresh_v5212(app_module); _install_shell_loader(app_module); _installed = True

__all__ = ["install_sleep_analysis_v522", "analyze", "_range_from_period"]
