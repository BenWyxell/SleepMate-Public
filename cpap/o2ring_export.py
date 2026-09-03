"""Complete, local O2Ring export for OSCAR, CSV and Excel."""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import shutil
from typing import Any, Callable
from xml.sax.saxutils import escape
import zipfile


EXPORT_COLUMNS = (
    "recording_id", "source_name", "timestamp", "datetime",
    "spo2", "heart_rate", "motion", "valid",
)


def _safe_vld_name(source_name: str, recording_id: str) -> str:
    name = Path(str(source_name or "").replace("\\", "/")).name.strip()
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")
    if not name:
        name = recording_id
    if not name.lower().endswith(".vld"):
        name += ".vld"
    return name


def _all_rows(recordings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for recording in recordings:
        recording_id = str(recording.get("recording_id") or "")
        source_name = str(recording.get("source_name") or "")
        for sample in recording.get("samples") or []:
            try:
                timestamp = float(sample.get("timestamp"))
            except (TypeError, ValueError):
                continue
            rows.append({
                "recording_id": recording_id,
                "source_name": source_name,
                "timestamp": timestamp,
                "datetime": datetime.fromtimestamp(timestamp, timezone.utc).astimezone().isoformat(timespec="seconds"),
                "spo2": sample.get("spo2"),
                "heart_rate": sample.get("heart_rate"),
                "motion": sample.get("motion"),
                "valid": bool(sample.get("valid", True)),
            })
    rows.sort(key=lambda row: (row["timestamp"], row["recording_id"]))
    return rows


def _cell(reference: str, value: Any, *, header: bool = False) -> str:
    style = ' s="1"' if header else ""
    if value is None:
        return f'<c r="{reference}"{style}/>'
    if isinstance(value, bool):
        return f'<c r="{reference}" t="b"{style}><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float)):
        return f'<c r="{reference}"{style}><v>{value}</v></c>'
    return f'<c r="{reference}" t="inlineStr"{style}><is><t>{escape(str(value))}</t></is></c>'


def _write_xlsx(path: Path, rows: list[dict[str, Any]]) -> None:
    letters = tuple(chr(ord("A") + index) for index in range(len(EXPORT_COLUMNS)))
    sheet_rows = [
        '<row r="1">' + "".join(
            _cell(f"{letter}1", column, header=True)
            for letter, column in zip(letters, EXPORT_COLUMNS)
        ) + "</row>"
    ]
    for row_index, row in enumerate(rows, 2):
        cells = "".join(
            _cell(f"{letter}{row_index}", row.get(column))
            for letter, column in zip(letters, EXPORT_COLUMNS)
        )
        sheet_rows.append(f'<row r="{row_index}">{cells}</row>')
    last_row = max(1, len(rows) + 1)
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<dimension ref="A1:H{last_row}"/><sheetViews><sheetView workbookViewId="0"/></sheetViews>'
        '<sheetFormatPr defaultRowHeight="15"/><sheetData>' + "".join(sheet_rows) +
        '</sheetData></worksheet>'
    )
    created = datetime.now().astimezone().isoformat(timespec="seconds")
    files = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>',
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>',
        "xl/workbook.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="O2Ring" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
        "xl/styles.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><numFmts count="0"/><fonts count="2"><font><sz val="11"/><name val="Calibri"/><family val="2"/></font><font><b/><sz val="11"/><name val="Calibri"/><family val="2"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles><dxfs count="0"/><tableStyles count="0" defaultTableStyle="TableStyleMedium2" defaultPivotStyle="PivotStyleLight16"/></styleSheet>',
        "xl/worksheets/sheet1.xml": sheet,
        "docProps/core.xml": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:creator>SleepMate</dc:creator><dcterms:created xsi:type="dcterms:W3CDTF">{escape(created)}</dcterms:created></cp:coreProperties>',
        "docProps/app.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>SleepMate</Application></Properties>',
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content.encode("utf-8"))


def export_o2ring_data(store, destination: str | Path,
                       *, now: Callable[[], datetime] | None = None) -> dict[str, Any]:
    destination = Path(destination).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    moment = (now or (lambda: datetime.now().astimezone()))()
    while True:
        stamp = moment.strftime("%Y-%m-%d_%H-%M-%S")
        root = destination / f"O2Ring_Export_{stamp}"
        try:
            root.mkdir()
            break
        except FileExistsError:
            moment += timedelta(seconds=1)

    oscar_dir = root / "OSCAR"
    csv_dir = root / "CSV"
    excel_dir = root / "Excel"
    oscar_dir.mkdir()
    csv_dir.mkdir()
    excel_dir.mkdir()

    recordings = store.list_recordings()
    rows = _all_rows(recordings)
    used_names: set[str] = set()
    raw_count = 0
    missing_raw = 0
    for recording in sorted(recordings, key=lambda item: float(item.get("start_ts") or 0)):
        recording_id = str(recording.get("recording_id") or "")
        source = store.raw_dir / f"{recording_id}.vld"
        if not source.is_file():
            missing_raw += 1
            continue
        target_name = _safe_vld_name(str(recording.get("source_name") or ""), recording_id)
        if target_name.casefold() in used_names:
            target_name = f"{Path(target_name).stem}_{recording_id}.vld"
        used_names.add(target_name.casefold())
        shutil.copyfile(source, oscar_dir / target_name)
        raw_count += 1

    csv_path = csv_dir / f"O2Ring_Export_{stamp}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPORT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    xlsx_path = excel_dir / f"O2Ring_Export_{stamp}.xlsx"
    _write_xlsx(xlsx_path, rows)
    return {
        "ok": True,
        "folder": str(root),
        "csv": str(csv_path),
        "xlsx": str(xlsx_path),
        "recordings": len(recordings),
        "samples": len(rows),
        "raw_files": raw_count,
        "missing_raw_files": missing_raw,
    }


__all__ = ["EXPORT_COLUMNS", "export_o2ring_data"]
