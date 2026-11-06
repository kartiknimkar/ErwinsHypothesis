"""Read tables from CSV / TSV / TXT / Excel (.xlsx) files into rows of strings."""
from __future__ import annotations

import base64
import csv
import io
import math
from datetime import date, datetime

MAX_ROWS, MAX_COLS = 5000, 60


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        if math.isnan(v):
            return ""
        return repr(int(v)) if v.is_integer() and abs(v) < 1e15 else repr(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return str(v).strip()


def _trim(rows):
    rows = [[_cell(v) for v in r][:MAX_COLS] for r in rows[:MAX_ROWS]]
    while rows and not any(rows[-1]):
        rows.pop()
    while rows and not any(rows[0]):
        rows.pop(0)
    width = max((max((i + 1 for i, v in enumerate(r) if v), default=0) for r in rows), default=0)
    # drop fully empty leading columns
    lead = 0
    while lead < width and not any(r[lead] if lead < len(r) else "" for r in rows):
        lead += 1
    return [[(r[i] if i < len(r) else "") for i in range(lead, width)] for r in rows]


def read_table(filename: str, data_b64: str, sheet: str | None = None) -> dict:
    raw = base64.b64decode(data_b64)
    name = filename.lower()
    if name.endswith((".xlsx", ".xlsm")):
        import openpyxl
        try:
            wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        except Exception:
            raise ValueError("That Excel file couldn't be read. Is it a .xlsx file?")
        names = wb.sheetnames
        ws = wb[sheet] if sheet in names else wb[names[0]]
        rows = _trim([list(r) for r in ws.iter_rows(values_only=True)])
        return {"rows": rows, "sheets": names, "sheet": ws.title}
    if name.endswith(".xls"):
        raise ValueError("Old .xls files aren't supported. In Excel, use File → Save As → .xlsx, then import that.")
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    sample = text[:5000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
        delim = dialect.delimiter
    except csv.Error:
        delim = "\t" if "\t" in sample else ","
    rows = _trim(list(csv.reader(io.StringIO(text), delimiter=delim)))
    # European-style decimals ("1,5") when ';' is the separator
    if delim == ";":
        rows = [[v.replace(",", ".") if v.replace(",", "", 1).replace("-", "", 1).isdigit() else v for v in r] for r in rows]
    return {"rows": rows, "sheets": None, "sheet": None}
