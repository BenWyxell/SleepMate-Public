from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
import json
import re
from typing import Any

from .edf import EDFFile


_FILE_RE = re.compile(r"^(\d{8}_\d{6})_([A-Za-z0-9]+)\.edf$", re.I)


@dataclass
class FileInfo:
    path: Path
    timestamp: datetime
    kind: str
    edf: EDFFile


@dataclass
class Session:
    start: datetime
    end: datetime
    duration_s: float
    files: dict[str, FileInfo]

    def json(self) -> dict[str, Any]:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "duration_s": self.duration_s,
            "duration_hms": format_duration(self.duration_s),
            "files": {k: v.path.name for k, v in self.files.items()},
        }


def format_duration(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def classify_event(desc: str) -> str | None:
    d = desc.strip().lower()
    if not d or d == "recording starts":
        return None
    if "obstructive" in d and "apnea" in d:
        return "OA"
    if ("central" in d and "apnea" in d) or "clear airway" in d:
        return "CA"
    if "hypopnea" in d:
        return "H"
    if d == "apnea" or "unclassified apnea" in d:
        return "UA"
    if "rera" in d or "arousal" in d:
        return "RERA"
    if "csr" in d or "cheyne" in d:
        return "CSR"
    return "OTHER"


class ResMedDataset:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.datalog = self.root / "DATALOG"
        if not self.datalog.is_dir():
            raise FileNotFoundError(f"DATALOG folder not found under: {self.root}")
        self._day_files_cache: dict[str, list[FileInfo]] = {}
        self._sessions_cache: dict[str, list[Session]] = {}
        self._events_cache: dict[str, list[dict[str, Any]]] = {}
        self._statistics_cache: dict[str, dict[str, Any]] = {}
        self._oximetry_cache: dict[str, dict[str, Any]] = {}
        self.last_refresh_at = datetime.now()

    def refresh(self) -> None:
        """Drop in-memory caches so newly copied EDF files become visible."""
        self._day_files_cache.clear()
        self._sessions_cache.clear()
        self._events_cache.clear()
        self._statistics_cache.clear()
        self._oximetry_cache.clear()
        self.last_refresh_at = datetime.now()

    def days(self) -> list[str]:
        return sorted(
            [p.name for p in self.datalog.iterdir() if p.is_dir() and re.fullmatch(r"\d{8}", p.name)],
            reverse=True,
        )

    def _files_for_day(self, day: str) -> list[FileInfo]:
        if day in self._day_files_cache:
            return self._day_files_cache[day]
        folder = self.datalog / day
        infos: list[FileInfo] = []
        if not folder.is_dir():
            return infos
        for p in sorted(folder.glob("*.edf")):
            m = _FILE_RE.match(p.name)
            if not m:
                continue
            try:
                ts = datetime.strptime(m.group(1), "%Y%m%d_%H%M%S")
                edf = EDFFile(p)
            except Exception:
                continue
            infos.append(FileInfo(p, ts, m.group(2).upper(), edf))
        self._day_files_cache[day] = infos
        return infos

    def sessions(self, day: str) -> list[Session]:
        if day in self._sessions_cache:
            return self._sessions_cache[day]
        infos = self._files_for_day(day)
        if not infos:
            return []

        # ResMed creates CSL/EVE a few seconds before BRP/PLD/SA2. Group files whose
        # starts are within 30 seconds into one physical therapy session.
        clusters: list[list[FileInfo]] = []
        for info in sorted(infos, key=lambda x: x.timestamp):
            if not clusters or (info.timestamp - clusters[-1][-1].timestamp).total_seconds() > 30:
                clusters.append([info])
            else:
                clusters[-1].append(info)

        sessions: list[Session] = []
        for cluster in clusters:
            by_kind = {x.kind: x for x in cluster}
            # BRP is the high resolution therapy waveform and is the best source for
            # actual machine-on duration. PLD/SA2 are fallbacks for rare sessions.
            duration_src = by_kind.get("BRP") or by_kind.get("PLD") or by_kind.get("SA2")
            if not duration_src or duration_src.edf.duration_s <= 0:
                continue
            start = duration_src.edf.start_time
            duration_s = duration_src.edf.duration_s
            sessions.append(Session(
                start=start,
                end=start + timedelta(seconds=duration_s),
                duration_s=duration_s,
                files=by_kind,
            ))
        self._sessions_cache[day] = sessions
        return sessions

    def events(self, day: str) -> list[dict[str, Any]]:
        if day in self._events_cache:
            return self._events_cache[day]
        events: list[dict[str, Any]] = []
        for info in self._files_for_day(day):
            if info.kind != "EVE":
                continue
            for ann in info.edf.read_annotations():
                kind = classify_event(ann.description)
                if kind is None:
                    continue
                ts = info.edf.start_time + timedelta(seconds=ann.onset_s)
                events.append({
                    "time": ts.isoformat(),
                    "onset_s": ann.onset_s,
                    "duration_s": ann.duration_s,
                    "type": kind,
                    "description": ann.description,
                    "source": info.path.name,
                })
        events = sorted(events, key=lambda x: x["time"])
        self._events_cache[day] = events
        return events

    def summary(self, day: str) -> dict[str, Any]:
        sessions = self.sessions(day)
        events = self.events(day)
        therapy_s = sum(s.duration_s for s in sessions)
        counts = {k: 0 for k in ["OA", "CA", "H", "UA", "RERA", "CSR", "OTHER"]}
        for e in events:
            counts[e["type"]] = counts.get(e["type"], 0) + 1
        ahi_events = counts["OA"] + counts["CA"] + counts["H"] + counts["UA"]
        ahi = ahi_events / (therapy_s / 3600.0) if therapy_s > 0 else 0.0

        integrity = self.integrity(day)
        return {
            "day": day,
            "date": datetime.strptime(day, "%Y%m%d").date().isoformat(),
            "therapy_seconds": therapy_s,
            "usage": format_duration(therapy_s),
            "ahi": round(ahi, 2),
            "counts": counts,
            "sessions": [s.json() for s in sessions],
            "events": events,
            "integrity": integrity,
            "oximetry": self.oximetry(day),
        }

    def integrity(self, day: str) -> dict[str, Any]:
        files = self._files_for_day(day)
        bad = []
        for f in files:
            if not f.edf.complete:
                bad.append({
                    "file": f.path.name,
                    "header_records": f.edf.header_num_records,
                    "actual_records": f.edf.actual_num_records,
                    "trailing_bytes": f.edf.trailing_bytes,
                })
        return {
            "edf_files": len(files),
            "complete": len(bad) == 0,
            "problems": bad,
        }


    def oximetry(self, day: str) -> dict[str, Any]:
        """Read optional pulse/SpO2 channels from ResMed SA2 files.

        AirSense devices commonly create SA2 files even when no oximeter is
        connected; those files contain zero placeholders. We therefore only
        expose physiologically plausible, non-zero samples and return null when
        there is no actual measurement.
        """
        if day in self._oximetry_cache:
            return self._oximetry_cache[day]

        spo2: list[float] = []
        pulse: list[float] = []
        for sess in self.sessions(day):
            fi = sess.files.get("SA2")
            if not fi:
                continue
            i_spo2 = fi.edf.find_signal("SpO2")
            if i_spo2 is not None:
                spo2.extend(v for v in fi.edf.read_signal(i_spo2) if 50 <= v <= 100)
            i_pulse = fi.edf.find_signal("Pulse")
            if i_pulse is not None:
                pulse.extend(v for v in fi.edf.read_signal(i_pulse) if 20 <= v <= 250)

        spo2.sort()
        pulse.sort()
        result = {
            "spo2_median": round(percentile_sorted(spo2, 50), 1) if spo2 else None,
            "spo2_min": round(spo2[0], 1) if spo2 else None,
            "pulse_median": round(percentile_sorted(pulse, 50), 1) if pulse else None,
            "pulse_min": round(pulse[0], 1) if pulse else None,
            "samples": min(len(spo2), len(pulse)) if spo2 and pulse else max(len(spo2), len(pulse)),
            "available": bool(spo2 or pulse),
        }
        self._oximetry_cache[day] = result
        return result

    def equipment(self) -> dict[str, Any]:
        """Read machine identity from the SD-card Identification.json.

        This is deliberately separate from therapy parsing: identification data
        describes the device, while DATALOG remains the source of truth for
        therapy sessions and statistics.
        """
        path = self.root / "Identification.json"
        if not path.is_file():
            # A hiányzó Identification.json üres / még nem szinkronizált állapotban
            # nem alkalmazáshiba. A Felszerelés oldal ilyenkor saját üres állapotot mutat.
            return {
                "available": False,
                "source": "Identification.json",
                "reason": "identification_missing",
                "message": "Még nincs automatikusan felismert készülék.",
            }
        try:
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
            profiles = raw.get("FlowGenerator", {}).get("IdentificationProfiles", {})
            product = profiles.get("Product", {}) or {}
            hardware = profiles.get("Hardware", {}) or {}
            software = profiles.get("Software", {}) or {}
            return {
                "available": True,
                "source": path.name,
                "manufacturer": "ResMed",
                "product_name": product.get("ProductName") or None,
                "product_code": product.get("ProductCode") or None,
                "serial_number": product.get("SerialNumber") or None,
                "geographic_identifier": product.get("ProductGeographicIdentifier") or None,
                "hardware_identifier": hardware.get("HardwareIdentifier") or None,
                "application_identifier": software.get("ApplicationIdentifier") or None,
                "configuration_identifier": software.get("ConfigurationIdentifier") or None,
                "data_version": software.get("DataVersionIdentifier"),
                "data_model_version": software.get("DataModelVersionIdentifier") or None,
            }
        except Exception as exc:
            # A felszerelési oldal maradjon használható akkor is, ha az azonosító fájl
            # hibás. A részletes technikai figyelmeztetés a diagnosztikában kezelhető.
            return {
                "available": False,
                "source": path.name,
                "reason": "identification_unreadable",
                "message": "A készülék automatikus azonosítása most nem sikerült.",
                "detail": f"{type(exc).__name__}: {exc}",
            }

    def diagnostics(self) -> dict[str, Any]:
        """Filesystem/integrity diagnostics for the Naplók page."""
        rows: list[dict[str, Any]] = []
        damaged: list[dict[str, Any]] = []
        missing_required: list[dict[str, Any]] = []
        newest_datalog_mtime = 0.0

        for day in self.days():
            files = self._files_for_day(day)
            if not files:
                continue
            folder = self.datalog / day
            try:
                newest_datalog_mtime = max(newest_datalog_mtime, max((f.path.stat().st_mtime for f in files), default=0.0))
            except OSError:
                pass
            clusters: list[list[FileInfo]] = []
            for info in sorted(files, key=lambda x: x.timestamp):
                if not clusters or (info.timestamp - clusters[-1][-1].timestamp).total_seconds() > 30:
                    clusters.append([info])
                else:
                    clusters[-1].append(info)
            for ci, cluster in enumerate(clusters, start=1):
                kinds = {x.kind for x in cluster}
                missing = [k for k in ('BRP','PLD','EVE') if k not in kinds]
                if missing:
                    missing_required.append({
                        'day': day,
                        'session': ci,
                        'start': cluster[0].timestamp.isoformat(),
                        'missing': missing,
                        'present': sorted(kinds),
                    })
            integ = self.integrity(day)
            for item in integ.get('problems', []):
                damaged.append({'day': day, **item})

        str_path = next((p for p in self.root.iterdir() if p.is_file() and p.name.upper() == 'STR.EDF'), None)
        str_warning = None
        if str_path is not None and str_path.is_file():
            try:
                if newest_datalog_mtime and str_path.stat().st_mtime < newest_datalog_mtime:
                    str_warning = {
                        'file': str_path.name,
                        'message': 'Az STR.edf régebbi, mint a DATALOG-ban lévő legfrissebb adat. A napi/terápiás adatokhoz továbbra is a DATALOG az elsődleges forrás.',
                        'modified_at': datetime.fromtimestamp(str_path.stat().st_mtime).isoformat(timespec='seconds'),
                    }
            except OSError:
                pass

        rows.append({'level':'INFO','title':'Import napló','message':f'{len(self.days())} ResMed nap és {sum(len(self._files_for_day(d)) for d in self.days())} EDF fájl látható a DATALOG alatt.'})
        rows.append({'level':'INFO','title':'Utolsó sikeres frissítés','message':self.last_refresh_at.isoformat(timespec='seconds')})
        rows.append({'level':'WARN' if missing_required else 'INFO','title':'Hiányzó BRP / PLD / EVE','message':f'{len(missing_required)} érintett szakasz.' if missing_required else 'Nem találtam hiányzó kötelező ResMed szakaszfájlt.'})
        rows.append({'level':'WARN' if damaged else 'INFO','title':'Sérült / csonka EDF','message':f'{len(damaged)} problémás EDF.' if damaged else 'Nem találtam sérült vagy csonka EDF fájlt.'})
        if str_warning:
            rows.append({'level':'WARN','title':'STR vs DATALOG','message':str_warning['message']})
        else:
            rows.append({'level':'INFO','title':'STR vs DATALOG','message':'Nem találtam STR figyelmeztetést.'})

        return {
            'generated_at': datetime.now().isoformat(timespec='seconds'),
            'summary': rows,
            'damaged_files': damaged,
            'missing_required': missing_required,
            'str_warning': str_warning,
            'errors': [r for r in rows if r['level'] == 'WARN'],
            'last_successful_refresh': self.last_refresh_at.isoformat(timespec='seconds'),
            'days': len(self.days()),
            'edf_files': sum(len(self._files_for_day(d)) for d in self.days()),
        }

    def day_table(self) -> list[dict[str, Any]]:
        """Compact one-row-per-ResMed-day overview for the Sessions page."""
        rows: list[dict[str, Any]] = []
        for day in self.days():
            s = self.summary(day)
            ox = s.get("oximetry") or {}
            stats = self.statistics(day)
            stat_map = {r["key"]: r for r in stats.get("rows", [])}
            rows.append({
                "day": day,
                "date": s["date"],
                "usage": s["usage"],
                "therapy_seconds": s["therapy_seconds"],
                "ahi": s["ahi"],
                "events": sum(s["counts"].get(k, 0) for k in ("OA", "CA", "H", "UA", "RERA")),
                "counts": s["counts"],
                "leak_p95": (stat_map.get("leak") or {}).get("p95"),
                "pressure_p95": (stat_map.get("pressure") or {}).get("p95"),
                "spo2": ox.get("spo2_median"),
                "hr": ox.get("pulse_median"),
                "integrity": s["integrity"],
            })
        return rows

    def statistics(self, day: str) -> dict[str, Any]:
        """Daily descriptive statistics from ResMed PLD channels.

        These are intentionally calculated from actual therapy-session samples,
        not wall-clock time and not STR.EDF summary values. This keeps the logic
        consistent with the session engine and makes the values independently
        reproducible from DATALOG.
        """
        if day in self._statistics_cache:
            return self._statistics_cache[day]

        specs = [
            ("pressure", "Nyomás", "Press"),
            ("epr_pressure", "EPAP / EPR nyomás", "EprPress"),
            ("mask_pressure", "Maszknyomás", "MaskPress"),
            ("leak", "Szivárgás", "Leak"),
            ("flow_lim", "Áramláskorlátozás", "FlowLim"),
            ("snore", "Horkolás", "Snore"),
            ("resp_rate", "Légzésszám", "RespRate"),
            ("tidal_volume", "Légzéstérfogat", "TidVol"),
            ("minute_vent", "Perctérfogat", "MinVent"),
        ]
        rows: list[dict[str, Any]] = []
        sessions = self.sessions(day)

        for key, title, prefix in specs:
            vals: list[float] = []
            unit = ""
            for sess in sessions:
                fi = sess.files.get("PLD")
                if not fi:
                    continue
                idx = fi.edf.find_signal(prefix)
                if idx is None:
                    continue
                raw = fi.edf.read_signal(idx)
                if not raw:
                    continue
                sig = fi.edf.signals[idx]
                factor = 1.0
                this_unit = sig.phys_dim
                if key == "leak" and this_unit == "L/s":
                    factor, this_unit = 60.0, "L/perc"
                elif key == "tidal_volume" and this_unit == "L":
                    factor, this_unit = 1000.0, "ml"
                converted = [v * factor for v in raw]
                # ResMed writes zero placeholders at a handful of session-edge
                # samples for derived respiratory channels. OSCAR excludes these
                # invalid placeholders from its descriptive statistics.
                if key in {"resp_rate", "tidal_volume", "minute_vent"}:
                    converted = [v for v in converted if v > 0]
                vals.extend(converted)
                unit = this_unit

            if not vals:
                continue
            vals.sort()
            rows.append({
                "key": key,
                "title": title,
                "unit": unit,
                "min": round(vals[0], 5),
                "median": round(percentile_sorted(vals, 50), 5),
                "p95": round(percentile_sorted(vals, 95), 5),
                "p995": round(percentile_sorted(vals, 99.5), 5),
                "max": round(vals[-1], 5),
                "samples": len(vals),
            })

        apnea_seconds = sum(
            float(e.get("duration_s") or 0.0)
            for e in self.events(day)
            if e.get("type") in {"OA", "CA", "UA"}
        )
        result = {
            "day": day,
            "rows": rows,
            "apnea_seconds": round(apnea_seconds, 3),
            "apnea_duration": format_duration(apnea_seconds),
        }
        self._statistics_cache[day] = result
        return result


    def period_therapy_stats(self, period: str = "30") -> dict[str, Any]:
        """Aggregate actual machine data over 7/30/90 days or all available days.

        Pressure statistics are calculated from the underlying PLD samples, not
        averaged from daily percentiles. AHI is weighted by actual therapy time.
        """
        days = sorted(self.days())
        if not days:
            return {"period": period, "days": 0, "therapy_seconds": 0, "ahi": None,
                    "pressure": None, "from": None, "to": None}
        latest = datetime.strptime(days[-1], "%Y%m%d").date()
        if str(period).lower() == "all":
            chosen = days
        else:
            try:
                n = max(1, int(period))
            except ValueError:
                n = 30
            cutoff = latest - timedelta(days=n - 1)
            chosen = [d for d in days if datetime.strptime(d, "%Y%m%d").date() >= cutoff]

        pressure_vals: list[float] = []
        therapy_s = 0.0
        ahi_events = 0
        for day in chosen:
            summary = self.summary(day)
            therapy_s += float(summary.get("therapy_seconds") or 0)
            counts = summary.get("counts") or {}
            ahi_events += sum(int(counts.get(k) or 0) for k in ("OA", "CA", "H", "UA"))
            for sess in self.sessions(day):
                fi = sess.files.get("PLD")
                if not fi:
                    continue
                idx = fi.edf.find_signal("Press")
                if idx is None:
                    continue
                vals = fi.edf.read_signal(idx)
                if vals:
                    pressure_vals.extend(float(v) for v in vals if v >= 0)

        ahi = ahi_events / (therapy_s / 3600.0) if therapy_s > 0 else None
        pressure = None
        if pressure_vals:
            pressure_vals.sort()
            pressure = {
                "average": round(sum(pressure_vals) / len(pressure_vals), 3),
                "median": round(percentile_sorted(pressure_vals, 50), 3),
                "p95": round(percentile_sorted(pressure_vals, 95), 3),
                "max": round(pressure_vals[-1], 3),
                "samples": len(pressure_vals),
                "unit": "cmH2O",
            }
        return {
            "period": str(period),
            "days": len(chosen),
            "therapy_seconds": round(therapy_s, 3),
            "ahi": round(ahi, 2) if ahi is not None else None,
            "pressure": pressure,
            "from": chosen[0] if chosen else None,
            "to": chosen[-1] if chosen else None,
        }

    def dashboard_overview(self, period: str = "30") -> dict[str, Any]:
        """Compact dashboard data for latest sleep and longitudinal trends."""
        days = sorted(self.days())
        if not days:
            return {"period": str(period), "rows": [], "latest": None, "aggregate": {}}
        latest_day = days[-1]
        latest_date = datetime.strptime(latest_day, "%Y%m%d").date()
        if str(period).lower() == "all":
            chosen = days
        else:
            try:
                n = max(1, int(period))
            except ValueError:
                n = 30
            cutoff = latest_date - timedelta(days=n - 1)
            chosen = [d for d in days if datetime.strptime(d, "%Y%m%d").date() >= cutoff]

        rows: list[dict[str, Any]] = []
        total_therapy = 0.0
        total_ahi_events = 0
        four_hour_days = 0
        for day in chosen:
            sm = self.summary(day)
            st = self.statistics(day)
            stat_map = {r["key"]: r for r in st.get("rows", [])}
            therapy_s = float(sm.get("therapy_seconds") or 0)
            counts = sm.get("counts") or {}
            ahi_events = sum(int(counts.get(k) or 0) for k in ("OA", "CA", "H", "UA"))
            total_therapy += therapy_s
            total_ahi_events += ahi_events
            if therapy_s >= 4 * 3600:
                four_hour_days += 1
            hours = therapy_s / 3600.0 if therapy_s else 0.0
            def stat(key: str, field: str):
                obj = stat_map.get(key)
                return obj.get(field) if obj else None
            rows.append({
                "day": day, "date": sm.get("date"),
                "therapy_seconds": therapy_s, "usage_hours": round(hours, 3),
                "ahi": sm.get("ahi"),
                "events": sum(int(counts.get(k) or 0) for k in ("OA", "CA", "H", "UA", "RERA")),
                "event_index": {k: round((int(counts.get(k) or 0) / hours), 3) if hours else 0.0 for k in ("OA", "CA", "H", "RERA")},
                "counts": counts,
                "pressure_median": stat("pressure", "median"),
                "pressure_p95": stat("pressure", "p95"),
                "leak_median": stat("leak", "median"),
                "leak_p95": stat("leak", "p95"),
                "resp_rate_median": stat("resp_rate", "median"),
                "tidal_volume_median": stat("tidal_volume", "median"),
                "minute_vent_median": stat("minute_vent", "median"),
                "spo2_median": (sm.get("oximetry") or {}).get("spo2_median"),
                "pulse_median": (sm.get("oximetry") or {}).get("pulse_median"),
            })

        weighted_ahi = total_ahi_events / (total_therapy / 3600.0) if total_therapy else None
        latest_summary = self.summary(latest_day)
        latest_stats = self.statistics(latest_day)
        latest_map = {r["key"]: r for r in latest_stats.get("rows", [])}
        return {
            "period": str(period),
            "from": chosen[0] if chosen else None, "to": chosen[-1] if chosen else None,
            "rows": rows,
            "latest": {
                "summary": latest_summary,
                "stats": latest_stats,
                "key_stats": {
                    "pressure_median": (latest_map.get("pressure") or {}).get("median"),
                    "pressure_p95": (latest_map.get("pressure") or {}).get("p95"),
                    "pressure_max": (latest_map.get("pressure") or {}).get("max"),
                    "leak_p95": (latest_map.get("leak") or {}).get("p95"),
                    "resp_rate_median": (latest_map.get("resp_rate") or {}).get("median"),
                    "tidal_volume_median": (latest_map.get("tidal_volume") or {}).get("median"),
                    "minute_vent_median": (latest_map.get("minute_vent") or {}).get("median"),
                },
            },
            "aggregate": {
                "days": len(chosen),
                "therapy_seconds": round(total_therapy, 3),
                "average_usage_seconds": round(total_therapy / len(chosen), 3) if chosen else 0,
                "ahi": round(weighted_ahi, 2) if weighted_ahi is not None else None,
                "four_hour_days": four_hour_days,
                "four_hour_percent": round(100 * four_hour_days / len(chosen), 1) if chosen else 0,
            },
        }

    def _days_in_range(self, start: str, end: str) -> list[str]:
        """Return available ResMed days inside an inclusive ISO/date-code range."""
        def norm(v: str) -> str:
            return str(v or "").replace("-", "")[:8]
        a, b = norm(start), norm(end)
        if a and b and a > b:
            a, b = b, a
        return [d for d in sorted(self.days()) if (not a or d >= a) and (not b or d <= b)]

    def _aggregate_days(self, chosen: list[str]) -> dict[str, Any]:
        if not chosen:
            return {
                "days": 0, "from": None, "to": None, "therapy_seconds": 0,
                "average_usage_seconds": 0, "ahi": None, "event_index": {k: None for k in ("OA","CA","H","RERA")},
                "pressure_median": None, "pressure_p95": None, "leak_median": None, "leak_p95": None,
            }
        therapy_s = 0.0
        counts_total = {k: 0 for k in ("OA","CA","H","UA","RERA")}
        pressure_vals: list[float] = []
        leak_vals: list[float] = []
        for day in chosen:
            sm = self.summary(day)
            therapy_s += float(sm.get("therapy_seconds") or 0)
            c = sm.get("counts") or {}
            for k in counts_total:
                counts_total[k] += int(c.get(k) or 0)
            for sess in self.sessions(day):
                fi = sess.files.get("PLD")
                if not fi:
                    continue
                pidx = fi.edf.find_signal("Press")
                if pidx is not None:
                    pressure_vals.extend(float(v) for v in fi.edf.read_signal(pidx) if float(v) >= 0)
                lidx = fi.edf.find_signal("Leak")
                if lidx is not None:
                    factor = 60.0 if fi.edf.signals[lidx].phys_dim == "L/s" else 1.0
                    leak_vals.extend(float(v) * factor for v in fi.edf.read_signal(lidx) if float(v) >= 0)
        hours = therapy_s / 3600.0 if therapy_s else 0.0
        ahi_events = sum(counts_total[k] for k in ("OA","CA","H","UA"))
        pressure_vals.sort(); leak_vals.sort()
        return {
            "days": len(chosen), "from": chosen[0], "to": chosen[-1],
            "therapy_seconds": round(therapy_s, 3),
            "average_usage_seconds": round(therapy_s / len(chosen), 3),
            "ahi": round(ahi_events / hours, 3) if hours else None,
            "event_index": {k: round(counts_total[k] / hours, 3) if hours else None for k in ("OA","CA","H","RERA")},
            "counts": counts_total,
            "pressure_median": round(percentile_sorted(pressure_vals, 50), 3) if pressure_vals else None,
            "pressure_p95": round(percentile_sorted(pressure_vals, 95), 3) if pressure_vals else None,
            "leak_median": round(percentile_sorted(leak_vals, 50), 3) if leak_vals else None,
            "leak_p95": round(percentile_sorted(leak_vals, 95), 3) if leak_vals else None,
        }

    def compare_periods(self, a_start: str, a_end: str, b_start: str, b_end: str) -> dict[str, Any]:
        """Compare two inclusive date ranges from the actual EDF therapy data."""
        a_days = self._days_in_range(a_start, a_end)
        b_days = self._days_in_range(b_start, b_end)
        a = self._aggregate_days(a_days)
        b = self._aggregate_days(b_days)
        def delta(key: str):
            av, bv = a.get(key), b.get(key)
            if av is None or bv is None:
                return None
            return round(float(bv) - float(av), 3)
        event_delta = {}
        for k in ("OA","CA","H","RERA"):
            av = (a.get("event_index") or {}).get(k); bv = (b.get("event_index") or {}).get(k)
            event_delta[k] = round(float(bv)-float(av),3) if av is not None and bv is not None else None
        return {
            "period_a": a, "period_b": b,
            "delta": {
                "ahi": delta("ahi"), "average_usage_seconds": delta("average_usage_seconds"),
                "pressure_p95": delta("pressure_p95"), "leak_p95": delta("leak_p95"),
                "event_index": event_delta,
            }
        }

    def signal(
        self,
        day: str,
        signal_name: str,
        max_points: int = 8000,
        range_start_s: float | None = None,
        range_end_s: float | None = None,
    ) -> dict[str, Any]:
        """Return one signal across every therapy session for a ResMed day.

        The optional range is expressed in seconds relative to the first therapy
        session. Using relative seconds intentionally avoids browser/server
        timezone differences while zooming.
        """
        aliases = {
            "flow": [("BRP", "Flow")],
            "pressure": [("BRP", "Press"), ("PLD", "Press")],
            "mask_pressure": [("PLD", "MaskPress")],
            "leak": [("PLD", "Leak")],
            "resp_rate": [("PLD", "RespRate")],
            "tidal_volume": [("PLD", "TidVol")],
            "minute_vent": [("PLD", "MinVent")],
            "snore": [("PLD", "Snore")],
            "flow_lim": [("PLD", "FlowLim")],
            "epr_pressure": [("PLD", "EprPress")],
        }
        if signal_name not in aliases:
            raise KeyError(signal_name)

        sessions = self.sessions(day)
        if not sessions:
            return {"name": signal_name, "label": signal_name, "unit": "", "series": []}

        day_start = sessions[0].start
        range_start = day_start + timedelta(seconds=range_start_s) if range_start_s is not None else None
        range_end = day_start + timedelta(seconds=range_end_s) if range_end_s is not None else None
        if range_start and range_end and range_end < range_start:
            range_start, range_end = range_end, range_start

        candidates: list[tuple[Session, FileInfo, int]] = []
        for sess in sessions:
            if range_start is not None and sess.end < range_start:
                continue
            if range_end is not None and sess.start > range_end:
                continue
            for file_kind, prefix in aliases[signal_name]:
                fi = sess.files.get(file_kind)
                if not fi:
                    continue
                idx = fi.edf.find_signal(prefix)
                if idx is not None:
                    candidates.append((sess, fi, idx))
                    break

        series: list[dict[str, Any]] = []
        unit = ""
        label = signal_name
        points_per_series = max(80, max_points // max(1, len(candidates)))

        for sess, selected, selected_idx in candidates:
            dt_s = selected.edf.signal_sample_interval_s(selected_idx)
            if dt_s <= 0:
                continue

            # Decode only the records intersecting the selected zoom window.
            # On a high-resolution Flow channel this is much faster than decoding
            # an entire 6-8 hour session for every zoom operation.
            local_start_s = None
            local_end_s = None
            if range_start is not None:
                local_start_s = max(0.0, (range_start - selected.edf.start_time).total_seconds())
            if range_end is not None:
                local_end_s = min(selected.edf.duration_s, (range_end - selected.edf.start_time).total_seconds())
            values, first_idx = selected.edf.read_signal_range(
                selected_idx, start_s=local_start_s, end_s=local_end_s
            )
            if not values:
                continue
            pts = downsample(values, max_points=points_per_series)

            sig_hdr = selected.edf.signals[selected_idx]
            label = sig_hdr.label
            unit = sig_hdr.phys_dim

            # Present common ResMed channels in the same human-friendly units
            # used by OSCAR: flow/leak L/min and tidal volume mL.
            factor = 1.0
            if signal_name in ("flow", "leak") and unit == "L/s":
                factor, unit = 60.0, "L/perc"
            elif signal_name == "tidal_volume" and unit == "L":
                factor, unit = 1000.0, "ml"

            series.append({
                "start": selected.edf.start_time.isoformat(),
                "sample_interval_s": dt_s,
                "points": [
                    [round((first_idx + i) * dt_s, 4), round(v * factor, 5)]
                    for i, v in pts
                ],
                "source": selected.path.name,
            })
        return {"name": signal_name, "label": label, "unit": unit, "series": series}


def percentile_sorted(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    pos = (len(values) - 1) * pct / 100.0
    lo = int(pos)
    hi = min(len(values) - 1, lo + 1)
    frac = pos - lo
    return values[lo] * (1.0 - frac) + values[hi] * frac


def downsample(values: list[float], max_points: int = 5000) -> list[tuple[int, float]]:
    """Min/max envelope downsampling.

    For dense CPAP waveforms this preserves local peaks much better than taking
    every Nth sample. Returned indexes always refer to the original sample index.
    """
    n = len(values)
    if n <= max_points or max_points < 4:
        return list(enumerate(values))

    # Two points (min and max) per bucket, ordered by original index.
    buckets = max_points // 2
    width = n / buckets
    out: list[tuple[int, float]] = []
    for b in range(buckets):
        a = int(b * width)
        z = min(n, int((b + 1) * width))
        if z <= a:
            continue
        segment = values[a:z]
        min_rel = min(range(len(segment)), key=segment.__getitem__)
        max_rel = max(range(len(segment)), key=segment.__getitem__)
        pair = [(a + min_rel, segment[min_rel]), (a + max_rel, segment[max_rel])]
        pair.sort(key=lambda x: x[0])
        out.extend(pair)
    return out
