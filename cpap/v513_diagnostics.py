from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .edf import EDFFile
from .resmed import FileInfo, ResMedDataset, classify_event


_PATCH_MARKER = "_sleepmate_v513_diagnostics_installed"


def _cluster_has_therapy_payload(cluster: list[FileInfo]) -> bool:
    """Return True only when a ResMed file cluster contains real therapy evidence.

    Very short AirSense start/stop attempts can create CSL/EVE headers, and
    sometimes zero-record BRP/PLD/SA2 files, without any actual therapy samples.
    Those stubs are normal device behaviour and must not be reported as missing
    BRP/PLD data. If a cluster contains waveform/derived samples or a classified
    EVE event, it is considered a real therapy cluster and missing files remain a
    diagnostic warning.
    """
    for info in cluster:
        if info.kind in {"BRP", "PLD", "SA2"} and info.edf.duration_s > 0:
            return True
        if info.kind == "EVE":
            try:
                for ann in info.edf.read_annotations():
                    if classify_event(ann.description) is not None:
                        return True
            except Exception:
                # Be conservative when an EVE file cannot be decoded: do not
                # suppress a potentially real missing-file warning.
                return True
    return False


def _str_latest_summary_day(edf: EDFFile) -> str | None:
    """Return the newest ResMed therapy day physically covered by STR.EDF.

    STR.EDF is a daily summary file. Its filesystem mtime is meaningless after a
    SleepSync copy because root files and DATALOG files are copied sequentially.
    Use the EDF start date and number/duration of complete physical records instead.
    """
    if edf.actual_num_records <= 0 or edf.record_duration_s <= 0:
        return None
    latest = edf.start_time + timedelta(
        seconds=(edf.actual_num_records - 1) * edf.record_duration_s
    )
    return latest.strftime("%Y%m%d")


def _diagnostics_v513(self: ResMedDataset) -> dict[str, Any]:
    """ResMed diagnostics with content-based STR freshness and stub filtering."""
    rows: list[dict[str, Any]] = []
    damaged: list[dict[str, Any]] = []
    missing_required: list[dict[str, Any]] = []
    days = self.days()

    for day in days:
        files = self._files_for_day(day)
        if not files:
            continue
        clusters: list[list[FileInfo]] = []
        for info in sorted(files, key=lambda x: x.timestamp):
            if not clusters or (info.timestamp - clusters[-1][-1].timestamp).total_seconds() > 30:
                clusters.append([info])
            else:
                clusters[-1].append(info)
        for ci, cluster in enumerate(clusters, start=1):
            kinds = {x.kind for x in cluster}
            missing = [k for k in ("BRP", "PLD", "EVE") if k not in kinds]
            # A header-only/zero-duration AirSense start is not a therapy session.
            # Only report missing required files when the cluster has real payload.
            if missing and _cluster_has_therapy_payload(cluster):
                missing_required.append({
                    "day": day,
                    "session": ci,
                    "start": cluster[0].timestamp.isoformat(),
                    "missing": missing,
                    "present": sorted(kinds),
                })
        integ = self.integrity(day)
        for item in integ.get("problems", []):
            damaged.append({"day": day, **item})

    str_path = next(
        (p for p in self.root.iterdir() if p.is_file() and p.name.upper() == "STR.EDF"),
        None,
    )
    str_warning = None
    latest_datalog_day = max(days) if days else None
    if str_path is not None and str_path.is_file() and latest_datalog_day:
        try:
            str_edf = EDFFile(str_path)
            latest_str_day = _str_latest_summary_day(str_edf)
            if latest_str_day and latest_str_day < latest_datalog_day:
                str_warning = {
                    "file": str_path.name,
                    "message": (
                        f"Az STR.EDF napi összesítője csak {latest_str_day[:4]}.{latest_str_day[4:6]}.{latest_str_day[6:]} napig tart, "
                        f"miközben a DATALOG legfrissebb terápiás napja {latest_datalog_day[:4]}.{latest_datalog_day[4:6]}.{latest_datalog_day[6:]}. "
                        "A napi/terápiás adatokhoz továbbra is a DATALOG az elsődleges forrás."
                    ),
                    "latest_str_day": latest_str_day,
                    "latest_datalog_day": latest_datalog_day,
                }
        except Exception:
            # STR unreadability is intentionally not turned into a new warning here;
            # EDF integrity diagnostics remain focused on DATALOG therapy files.
            pass

    rows.append({
        "level": "INFO",
        "title": "Import napló",
        "message": f"{len(days)} ResMed nap és {sum(len(self._files_for_day(d)) for d in days)} EDF fájl látható a DATALOG alatt.",
    })
    rows.append({
        "level": "INFO",
        "title": "Utolsó sikeres frissítés",
        "message": self.last_refresh_at.isoformat(timespec="seconds"),
    })
    rows.append({
        "level": "WARN" if missing_required else "INFO",
        "title": "Hiányzó BRP / PLD / EVE",
        "message": f"{len(missing_required)} érintett szakasz." if missing_required else "Nem találtam hiányzó kötelező ResMed szakaszfájlt.",
    })
    rows.append({
        "level": "WARN" if damaged else "INFO",
        "title": "Sérült / csonka EDF",
        "message": f"{len(damaged)} problémás EDF." if damaged else "Nem találtam sérült vagy csonka EDF fájlt.",
    })
    if str_warning:
        rows.append({"level": "WARN", "title": "STR vs DATALOG", "message": str_warning["message"]})
    else:
        rows.append({"level": "INFO", "title": "STR vs DATALOG", "message": "Az STR.EDF tartalmi dátuma összhangban van a DATALOG terápiás napjaival."})

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": rows,
        "damaged_files": damaged,
        "missing_required": missing_required,
        "str_warning": str_warning,
        "errors": [r for r in rows if r["level"] == "WARN"],
        "last_successful_refresh": self.last_refresh_at.isoformat(timespec="seconds"),
        "days": len(days),
        "edf_files": sum(len(self._files_for_day(d)) for d in days),
    }


def install_v513_diagnostics() -> None:
    if getattr(ResMedDataset, _PATCH_MARKER, False):
        return
    ResMedDataset.diagnostics = _diagnostics_v513
    setattr(ResMedDataset, _PATCH_MARKER, True)
