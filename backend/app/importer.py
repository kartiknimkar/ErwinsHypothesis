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


# ---------------------------------------------------------------------------
# GraphPad Prism .pzfx files (XML). Each data table becomes one analysis.
# ---------------------------------------------------------------------------

def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _kids(el, name):
    return [c for c in el if _local(c.tag) == name]


def _text(el) -> str:
    return "".join(el.itertext()).strip() if el is not None else ""


def _subcolumns(col):
    """List of subcolumns; each a list of (value string, excluded flag)."""
    out = []
    for sc in _kids(col, "Subcolumn"):
        vals = []
        for d in _kids(sc, "d"):
            v = (d.text or "").strip()
            vals.append((v, d.get("Excluded") == "1"))
        out.append(vals)
    return out


def read_pzfx(data_b64: str) -> dict:
    import xml.etree.ElementTree as ET
    raw = base64.b64decode(data_b64)
    if b"<!ENTITY" in raw[:5000]:
        raise ValueError("This file contains XML entity declarations, which aren't allowed.")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        raise ValueError("That .pzfx file couldn't be read. Is it a Prism XML project (.pzfx, not .prism)?")
    tables, notes = [], []
    excluded_total = 0
    for t in root.iter():
        if _local(t.tag) not in ("Table", "HugeTable"):
            continue
        ttype = (t.get("TableType") or "").lower()
        yfmt = (t.get("YFormat") or "replicates").lower()
        title = _text(next(iter(_kids(t, "Title")), None)) or "Prism table"
        xcols = _kids(t, "XColumn") or _kids(t, "XAdvancedColumn")
        ycols = _kids(t, "YColumn")
        rowtitles = _kids(t, "RowTitlesColumn")
        if not ycols:
            continue
        ytitles = [_text(next(iter(_kids(c, "Title")), None)) or f"Column {i + 1}" for i, c in enumerate(ycols)]
        ysubs = [_subcolumns(c) for c in ycols]
        if yfmt not in ("replicates", ""):
            notes.append(f"“{title}”: values were entered as {yfmt.upper()} (summary data); only the first value (mean) of each was imported.")
            ysubs = [subs[:1] for subs in ysubs]

        def val(cell):
            nonlocal excluded_total
            v, ex = cell
            if ex and v:
                excluded_total += 1
                return ""
            return v

        nrows = max([len(sc) for subs in ysubs for sc in subs] + [0])
        cell = lambda subs, k, i: val(subs[k][i]) if k < len(subs) and i < len(subs[k]) else ""  # noqa: E731
        rlabels = []
        if rowtitles:
            rs = _subcolumns(rowtitles[0])
            rlabels = [v for v, _ in rs[0]] if rs else []
        xvals = []
        if xcols:
            xs = _subcolumns(xcols[0])
            xvals = [val(c) for c in xs[0]] if xs else []
        nrows = max(nrows, len(xvals), len(rlabels))

        if ttype == "xy":
            reps = max(len(s) for s in ysubs)
            if len(ycols) == 1:
                cols = [_text(next(iter(_kids(xcols[0], "Title")), None)) or "X" if xcols else "X"] + \
                       [ytitles[0] if k == 0 else f"Rep {k + 1}" for k in range(reps)]
                rows = [[xvals[i] if i < len(xvals) else ""] + [cell(ysubs[0], k, i) for k in range(reps)] for i in range(nrows)]
                tables.append({"title": title, "type": "regression", "cols": cols, "rows": rows, "options": {}})
            elif reps == 1:
                cols = ["X"] + ytitles
                rows = [[xvals[i] if i < len(xvals) else ""] + [cell(s, 0, i) for s in ysubs] for i in range(nrows)]
                tables.append({"title": title, "type": "regression", "cols": cols, "rows": rows, "options": {"yMode": "datasets"}})
            else:  # several data sets with replicates: one XY analysis per data set
                for yt, subs in zip(ytitles, ysubs):
                    cols = ["X", yt] + [f"Rep {k + 1}" for k in range(1, len(subs))]
                    rows = [[xvals[i] if i < len(xvals) else ""] + [cell(subs, k, i) for k in range(len(subs))] for i in range(nrows)]
                    tables.append({"title": f"{title}: {yt}", "type": "regression", "cols": cols, "rows": rows, "options": {}})
        elif ttype == "twoway":
            reps = max(len(s) for s in ysubs)
            rows = []
            for i in range(nrows):
                lab = rlabels[i] if i < len(rlabels) and rlabels[i] else f"Row {i + 1}"
                for k in range(reps):
                    vals = [cell(s, k, i) for s in ysubs]
                    if any(vals):
                        rows.append([lab] + vals)
            tables.append({"title": title, "type": "twoway", "cols": ["Row"] + ytitles, "rows": rows, "options": {}})
        elif ttype == "survival":
            rows = [[xvals[i] if i < len(xvals) else ""] + [cell(s, 0, i) for s in ysubs] for i in range(nrows)]
            tables.append({"title": title, "type": "survival", "cols": ["Time"] + ytitles, "rows": rows, "options": {}})
        elif ttype == "contingency":
            rows = [[rlabels[i] if i < len(rlabels) else f"Row {i + 1}"] + [cell(s, 0, i) for s in ysubs] for i in range(nrows)]
            tables.append({"title": title, "type": "contingency", "cols": ["Group"] + ytitles, "rows": rows, "options": {}})
        else:  # column ("OneWay") tables and anything else with plain columns
            flat_titles, flat = [], []
            for yt, subs in zip(ytitles, ysubs):
                for k, sc in enumerate(subs):
                    flat_titles.append(yt if len(subs) == 1 else f"{yt} {k + 1}")
                    flat.append([val(c) for c in sc])
            n = max([len(c) for c in flat] + [0])
            rows = [[c[i] if i < len(c) else "" for c in flat] for i in range(n)]
            kind = "multivar" if ttype in ("multiplevariables", "multiple variables") else "ttest"
            tables.append({"title": title, "type": kind, "cols": flat_titles, "rows": rows, "options": {}})
    if not tables:
        raise ValueError("No data tables were found in that Prism file.")
    if excluded_total:
        notes.append(f"{excluded_total} value(s) marked as excluded in Prism were left out.")
    return {"tables": tables, "notes": notes}
