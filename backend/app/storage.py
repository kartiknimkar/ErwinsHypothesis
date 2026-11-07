"""Everything the app saves lives inside the app folder.

<app folder>/projects/   project files (*.ehp) + last-opened state
<app folder>/exports/    exported graphs (PNG/SVG)

The app folder defaults to the repository root and can be overridden with
the EH_HOME environment variable (used by tests).
"""
from __future__ import annotations

import base64
import json
import math
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

EXT = ".ehp"
_SAFE = re.compile(r"[^A-Za-z0-9 _\-().,µ]+")


def home() -> Path:
    """The app folder, where projects/ and exports/ live.

    - EH_HOME if set (tests, custom setups)
    - packaged Windows/Linux app: the folder containing ErwinsHypothesis.exe
    - packaged Mac app: the folder containing ErwinsHypothesis.app; if macOS is running the
      app from a temporary read-only copy (happens for downloaded, unsigned apps until they
      are moved), fall back to ~/Documents/Erwins Hypothesis
    - running from source: the repository root
    """
    env = os.environ.get("EH_HOME")
    if env:
        return Path(env).resolve()
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        if sys.platform == "darwin" and ".app/Contents/MacOS" in str(exe):
            app_dir = exe.parents[3]  # .../<folder>/ErwinsHypothesis.app/Contents/MacOS/exe
            if "/AppTranslocation/" in str(exe) or not os.access(app_dir, os.W_OK):
                return Path.home() / "Documents" / "Erwins Hypothesis"
            return app_dir
        return exe.parent
    return Path(__file__).resolve().parents[2]


def projects_dir() -> Path:
    d = home() / "projects"
    d.mkdir(parents=True, exist_ok=True)
    return d


def exports_dir() -> Path:
    d = home() / "exports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def safe_name(name: str, default: str = "Untitled") -> str:
    """Make a user-typed name safe to use as a file name (no paths, no odd characters)."""
    name = _SAFE.sub("", str(name or ""))
    name = re.sub(r"\.{2,}", ".", name).strip().strip(".")
    return name[:80] or default


def _inside(path: Path, folder: Path) -> Path:
    path = path.resolve()
    if folder.resolve() not in path.parents:
        raise ValueError("Invalid file name.")
    return path


# ---- projects ------------------------------------------------------------

def list_projects() -> list[dict]:
    out = []
    for p in projects_dir().glob("*" + EXT):
        st = p.stat()
        out.append({"name": p.stem, "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                    "size": st.st_size})
    out.sort(key=lambda d: d["modified"], reverse=True)
    return out


def project_path(name: str) -> Path:
    return _inside(projects_dir() / (safe_name(name) + EXT), projects_dir())


def load_project(name: str) -> dict:
    p = project_path(name)
    if not p.exists():
        raise FileNotFoundError(name)
    return json.loads(p.read_text(encoding="utf-8"))


def save_project(name: str, data: dict) -> str:
    name = safe_name(name)
    p = project_path(name)
    tmp = p.with_suffix(".tmp")
    # write then rename, so a crash mid-save never corrupts the file
    tmp.write_text(json.dumps({"app": "Erwin's Hypothesis", "version": 1, **data}, indent=1), encoding="utf-8")
    os.replace(tmp, p)
    set_last_project(name)
    return name


def delete_project(name: str) -> None:
    p = project_path(name)
    if p.exists():
        p.unlink()


def rename_project(old: str, new: str) -> str:
    new = safe_name(new)
    src, dst = project_path(old), project_path(new)
    if dst.exists() and dst != src:
        raise FileExistsError(new)
    if src.exists():
        os.replace(src, dst)
    set_last_project(new)
    return new


def _state_path() -> Path:
    return projects_dir() / ".state.json"


def get_last_project() -> str | None:
    try:
        name = json.loads(_state_path().read_text(encoding="utf-8")).get("last")
        return name if name and project_path(name).exists() else None
    except (OSError, ValueError):
        return None


def set_last_project(name: str) -> None:
    _state_path().write_text(json.dumps({"last": safe_name(name)}), encoding="utf-8")


# ---- exports -------------------------------------------------------------

def save_export(filename: str, data_url: str, fmt: str | None = None, dpi: int | None = None) -> str:
    """Save a graph sent from the interface as a data: URL. Returns the file name used.
    fmt="tiff" converts a PNG to an LZW-compressed TIFF; dpi is written into PNG/TIFF files
    so Word and journal systems show them at the intended print size."""
    m = re.match(r"^data:image/(png|svg\+xml)(;base64)?,(.*)$", data_url, re.S)
    if not m:
        raise ValueError("Unsupported image data.")
    ext = "png" if m.group(1) == "png" else "svg"
    payload = m.group(3)
    if m.group(2):
        raw = base64.b64decode(payload)
    else:
        from urllib.parse import unquote
        raw = unquote(payload).encode("utf-8")
    if ext == "png" and (fmt in ("tiff", "pdf") or dpi):
        import io
        from PIL import Image
        img = Image.open(io.BytesIO(raw))
        out = io.BytesIO()
        d_ = (int(dpi), int(dpi)) if dpi else (300, 300)
        if fmt == "tiff":
            img.convert("RGB").save(out, format="TIFF", compression="tiff_lzw", dpi=d_)
            ext = "tif"
        elif fmt == "pdf":
            # high-resolution image in a PDF page sized to the graph's print size (DPI sets the page size)
            img.convert("RGB").save(out, format="PDF", resolution=float(d_[0]))
            ext = "pdf"
        else:
            img.save(out, format="PNG", dpi=d_, optimize=True)
        raw = out.getvalue()
    base = safe_name(filename, "graph")
    d = exports_dir()
    path = d / f"{base}.{ext}"
    i = 2
    while path.exists():  # never overwrite an earlier export
        path = d / f"{base} ({i}).{ext}"
        i += 1
    _inside(path, d).write_bytes(raw)
    return path.name


def reveal(folder: str) -> None:
    """Open the projects or exports folder in Finder / File Explorer."""
    target = projects_dir() if folder == "projects" else exports_dir()
    if sys.platform.startswith("win"):
        os.startfile(target)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(target)])
    else:
        subprocess.Popen(["xdg-open", str(target)])


def _number_or_text(v: str):
    """Store numbers as real numbers in Excel so they can be used in formulas."""
    s = str(v).strip()
    try:
        f = float(s)
        if math.isfinite(f) and not s.lower().startswith(("nan", "inf", "-inf")):
            return int(f) if re.fullmatch(r"-?\d+", s) else f
    except ValueError:
        pass
    return s


def save_report(filename: str, html: str) -> str:
    """Write a project report (self-contained HTML) to the exports folder; never overwrites."""
    if len(html) > 60_000_000:
        raise ValueError("The report is too large.")
    base = safe_name(filename, "Report")
    d = exports_dir()
    path = d / f"{base}.html"
    i = 2
    while path.exists():
        path = d / f"{base} ({i}).html"
        i += 1
    _inside(path, d).write_text(html, encoding="utf-8")
    return path.name


def save_results_xlsx(filename: str, title: str, results: list[list[str]], data_cols: list[str],
                      data_rows: list[list[str]]) -> str:
    """Write an analysis to <exports>/<filename>.xlsx with a Results sheet and a Data sheet."""
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Results"
    ws.append([title])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append([])
    head = PatternFill("solid", fgColor="E9EEFD")
    for row in results:
        ws.append([_number_or_text(c) for c in row])
        r = ws.max_row
        if len(row) == 1 and row[0]:
            ws.cell(r, 1).font = Font(bold=True)
            if row[0].isupper():
                ws.cell(r, 1).fill = head
    ws.column_dimensions["A"].width = 46
    for col in "BCDEFGH":
        ws.column_dimensions[col].width = 18
    for row in ws.iter_rows(min_row=3):
        for c in row[1:]:
            c.alignment = Alignment(horizontal="right")
    wd = wb.create_sheet("Data")
    wd.append(list(data_cols))
    for c in wd[1]:
        c.font = Font(bold=True)
    for row in data_rows:
        if any(str(v).strip() for v in row):
            wd.append([_number_or_text(v) if str(v).strip() else None for v in row])
    for i in range(len(data_cols)):
        wd.column_dimensions[openpyxl.utils.get_column_letter(i + 1)].width = 16

    base = safe_name(filename, "results")
    d = exports_dir()
    path = d / f"{base}.xlsx"
    i = 2
    while path.exists():
        path = d / f"{base} ({i}).xlsx"
        i += 1
    wb.save(_inside(path, d))
    return path.name


def save_workbook(filename: str, analyses: list[dict]) -> str:
    """Every analysis of a project in one .xlsx: one sheet per analysis (results, then the data)."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill

    if not analyses:
        raise ValueError("No analyses to export.")
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    head = PatternFill("solid", fgColor="E9EEFD")
    used = set()
    for a in analyses:
        name = re.sub(r"[\[\]:*?/\\]", "", str(a.get("title") or "Analysis"))[:28].strip() or "Analysis"
        base, k = name, 2
        while name.lower() in used:
            name = f"{base[:25]} ({k})"; k += 1
        used.add(name.lower())
        ws = wb.create_sheet(name)
        ws.append([a.get("title") or name]); ws["A1"].font = Font(bold=True, size=14)
        ws.append([])
        for row in a.get("results") or []:
            ws.append([_number_or_text(c) for c in row])
            if len(row) == 1 and row[0]:
                ws.cell(ws.max_row, 1).font = Font(bold=True)
                if str(row[0]).isupper():
                    ws.cell(ws.max_row, 1).fill = head
        if a.get("data_cols"):
            ws.append([]); ws.append(["DATA"]); ws.cell(ws.max_row, 1).font = Font(bold=True); ws.cell(ws.max_row, 1).fill = head
            ws.append(list(a["data_cols"]))
            for c in ws[ws.max_row]:
                c.font = Font(bold=True)
            for row in a.get("data_rows") or []:
                if any(str(v).strip() for v in row):
                    ws.append([_number_or_text(v) if str(v).strip() else None for v in row])
        ws.column_dimensions["A"].width = 40
        for col in "BCDEFGHIJ":
            ws.column_dimensions[col].width = 16
    base = safe_name(filename, "project")
    d = exports_dir()
    path = d / f"{base}.xlsx"
    i = 2
    while path.exists():
        path = d / f"{base} ({i}).xlsx"
        i += 1
    wb.save(_inside(path, d))
    return path.name


def _prefs_path() -> Path:
    return projects_dir() / ".prefs.json"


def get_prefs() -> dict:
    try:
        return json.loads(_prefs_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def set_prefs(update: dict) -> dict:
    """Small interface preferences (e.g. dark mode), kept in the projects folder."""
    prefs = {**get_prefs(), **{k: v for k, v in update.items() if isinstance(k, str) and len(k) < 40}}
    _prefs_path().write_text(json.dumps(prefs), encoding="utf-8")
    return prefs
