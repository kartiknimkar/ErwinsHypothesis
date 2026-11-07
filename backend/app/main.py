"""Local web server: serves the interface and runs analyses."""
from __future__ import annotations

import math
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import outliers, nested, anova2, contingency, curvefit, importer, multivar, stats, storage, survival

STATIC = Path(__file__).parent / "static"
PLOTLY_JS = STATIC / "vendor" / "plotly.min.js"  # plotly.js (MIT), bundled so the app works offline

app = FastAPI(title="Erwin's Hypothesis")


def _json_safe(obj):
    """Replace NaN/inf (not valid JSON) with None."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    return obj


class TTestRequest(BaseModel):
    a: list
    b: list
    name_a: str = "A"
    name_b: str = "B"
    kind: str = "unpaired"
    alpha: float = 0.05


class CompareRequest(BaseModel):
    groups: list            # list of lists of values
    names: list[str]
    kind: str = "unpaired"  # 2 groups: unpaired|welch|paired|mannwhitney; 3+: ordinary|welch|kruskal
    alpha: float = 0.05
    outliers: bool = False  # also run an outlier test on each group
    outlier_method: str = "grubbs"  # grubbs | rout
    q: float = 0.01                 # ROUT's Q (maximum false discovery rate)
    posthoc: str = "tukey"          # 3+ groups: tukey|dunnett|bonferroni|sidak|holm|lsd
    compare_to: str = "all"         # all | control (first column)


class SummaryRequest(BaseModel):
    groups: list            # [{name, mean, sd, n}]
    kind: str = "welch"
    err: str = "sd"         # "sd" or "sem": what the second column holds
    alpha: float = 0.05
    posthoc: str = "tukey"
    compare_to: str = "all"


@app.post("/api/summary")
def run_summary(req: SummaryRequest):
    try:
        res = stats.compare_summary(req.groups, kind=req.kind, alpha=req.alpha, err=req.err, posthoc=req.posthoc, compare_to=req.compare_to)
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return JSONResponse(_json_safe(res))


class ColStatsRequest(BaseModel):
    groups: list
    names: list[str]
    hypothetical: float | None = None
    alpha: float = 0.05


@app.post("/api/colstats")
def run_colstats(req: ColStatsRequest):
    try:
        cols = [(n, g) for n, g in zip(req.names, req.groups) if any(v is not None and str(v).strip() != "" for v in g)]
        if not cols:
            raise ValueError("Enter values in at least one column.")
        res = {"kind": "describe", "test_name": "Column statistics", "alpha": req.alpha, "hypothetical": req.hypothetical,
               "groups": [stats.column_stats(g, n, req.hypothetical, req.alpha) for n, g in cols]}
        res["n_groups"] = len(cols)
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return JSONResponse(_json_safe(res))


class FreqRequest(BaseModel):
    groups: list
    names: list[str]
    bin_width: float | None = None
    bin_start: float | None = None
    y: str = "count"
    cumulative: bool = False


@app.post("/api/freq")
def run_freq(req: FreqRequest):
    try:
        res = stats.frequency_distribution(req.groups, req.names, req.bin_width, req.bin_start, req.y, req.cumulative)
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return JSONResponse(_json_safe(res))


class NestedRequest(BaseModel):
    groups: list[str]          # group name of each subject (one row per subject)
    values: list[list]         # replicate values of each subject
    alpha: float = 0.05


@app.post("/api/nested")
def run_nested(req: NestedRequest):
    try:
        order: list[str] = []
        for gname in req.groups:
            if gname not in order:
                order.append(gname)
        vals = [[float(v) for v in row if v is not None and str(v).strip() != "" and math.isfinite(float(v))] for row in req.values]
        keep = [i for i, v in enumerate(vals) if v and str(req.groups[i]).strip()]
        if not keep:
            raise ValueError("Enter one row per subject: its group name, then its replicate values.")
        order = [o for o in order if any(req.groups[i] == o for i in keep)]
        res = nested.nested([order.index(req.groups[i]) for i in keep], [vals[i] for i in keep], order, req.alpha)
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return JSONResponse(_json_safe(res))


class RegressionRequest(BaseModel):
    x: list
    y: list
    alpha: float = 0.05


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/ttest")
def run_ttest(req: TTestRequest):
    try:
        res = stats.t_test(req.a, req.b, kind=req.kind, name_a=req.name_a,
                           name_b=req.name_b, alpha=req.alpha)
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return JSONResponse(_json_safe(res))


@app.post("/api/compare")
def run_compare(req: CompareRequest):
    """Compare 2 groups (t tests) or 3+ groups (ANOVA family). Empty columns are ignored."""
    try:
        cols = [(n, g) for n, g in zip(req.names, req.groups)
                if any(v is not None and str(v).strip() != "" for v in g)]
        if len(cols) < 2:
            raise ValueError("Enter data in at least 2 group columns.")
        names = [n for n, _ in cols]
        groups = [g for _, g in cols]
        if len(cols) == 2:
            kind = req.kind if req.kind in ("unpaired", "welch", "paired", "wilcoxon", "mannwhitney") else "unpaired"
            res = stats.t_test(groups[0], groups[1], kind=kind, name_a=names[0], name_b=names[1], alpha=req.alpha)
        elif req.kind in ("rm", "friedman"):
            res = anova2.repeated_measures(groups, names, kind=req.kind, alpha=req.alpha)
        else:
            kind = req.kind if req.kind in ("ordinary", "welch", "kruskal") else "ordinary"
            res = stats.one_way_anova(groups, names, kind=kind, alpha=req.alpha, posthoc=req.posthoc, compare_to=req.compare_to)
        res["n_groups"] = len(cols)
        if req.outliers:
            if req.outlier_method == "rout":
                res["outliers"] = [{"name": n, **outliers.rout_column(stats._clean(g).tolist(), req.q)} for n, g in zip(names, groups)]
            else:
                res["outliers"] = [{"name": n, "method": "grubbs", **stats.grubbs(g, alpha=0.05)} for n, g in zip(names, groups)]
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return JSONResponse(_json_safe(res))


class FitRequest(BaseModel):
    x: list
    ys: list                 # one list per Y replicate column, same length as x
    model: str = "linear"    # "linear" or a curvefit model id
    compare: str | None = None  # optional second curvefit model to compare with
    fixed: dict | None = None   # {parameter name: value} constraints
    equation: str | None = None # user-defined equation when model == "custom"
    initial: dict | None = None # starting values for a user-defined equation
    auc: bool = False           # also compute area under the curve of the data
    baseline: float = 0.0
    rout_q: float | None = None  # remove ROUT outliers before fitting (Q, e.g. 0.01)
    x_is_log: bool = False
    alpha: float = 0.05


class EquationRequest(BaseModel):
    equation: str


@app.post("/api/equation")
def check_equation(req: EquationRequest):
    """Check a user-typed equation and list its parameters (for the interface)."""
    from .equation import EquationError, parse
    try:
        _, params = parse(req.equation)
    except EquationError as e:
        return {"ok": False, "error": str(e), "params": []}
    return {"ok": True, "params": params}


@app.get("/api/models")
def models():
    return {"models": curvefit.list_models()}


def _flatten_xy(x, ys):
    px, py = [], []
    for col in ys:
        for vx, vy in zip(x, col):
            if vx is None or vy is None:
                continue
            try:
                fx, fy = float(vx), float(vy)
            except (TypeError, ValueError):
                continue
            if math.isfinite(fx) and math.isfinite(fy):
                px.append(fx); py.append(fy)
    return px, py


def _unknowns(x, ys):
    """Rows with Y values but no X are samples to read off the standard curve."""
    out = []
    for i, vx in enumerate(x):
        if vx is not None and str(vx).strip() != "":
            continue
        vals = []
        for col in ys:
            v = col[i] if i < len(col) else None
            try:
                f = float(v)
                if math.isfinite(f):
                    vals.append(f)
            except (TypeError, ValueError):
                pass
        if vals:
            out.append({"row": i + 1, "y": sum(vals) / len(vals), "n": len(vals)})
    return out


@app.post("/api/fit")
def run_fit(req: FitRequest):
    try:
        px, py = _flatten_xy(req.x, req.ys)
        removed = []
        if req.rout_q:
            om = curvefit.rout_mask(px, py, req.model, req.x_is_log, req.fixed, req.equation, req.initial, req.rout_q)
            removed = [{"x": a, "y": b} for a, b, o in zip(px, py, om) if o]
            px = [a for a, o in zip(px, om) if not o]; py = [b for b, o in zip(py, om) if not o]
        if req.model == "linear":
            res = stats.linear_regression(px, py, alpha=req.alpha)
            res["model"] = "linear"
        else:
            res = curvefit.fit(px, py, req.model, x_is_log=req.x_is_log, alpha=req.alpha, fixed=req.fixed,
                               equation=req.equation, initial=req.initial)
            if req.compare and req.compare in curvefit.MODELS and req.model in curvefit.MODELS and req.compare != req.model:
                try:
                    res["comparison"] = curvefit.compare(px, py, req.model, req.compare, x_is_log=req.x_is_log, alpha=req.alpha, fixed=req.fixed)
                except ValueError as e:
                    res["comparison"] = {"error": str(e)}
        if req.rout_q:
            res["outliers"], res["rout_q"] = removed, req.rout_q
        if req.auc:
            try:
                res["auc"] = stats.area_under_curve(px, py, baseline=req.baseline)
            except ValueError as e:
                res["auc"] = {"error": str(e)}
        unk = _unknowns(req.x, req.ys)
        if unk:
            res["x_was_log"] = bool(req.x_is_log)
            vals = curvefit.interpolate(res, [u["y"] for u in unk], equation=req.equation, initial=req.initial)
            res["unknowns"] = [{**u, **v} for u, v in zip(unk, vals)]
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return JSONResponse(_json_safe(res))


class FitMultiRequest(BaseModel):
    x: list
    ys: list
    names: list[str]
    model: str = "linear"
    x_is_log: bool = False
    alpha: float = 0.05
    fixed: dict | None = None
    compare: str | None = None   # parameter name or "all"
    equation: str | None = None
    initial: dict | None = None


@app.post("/api/fitmulti")
def run_fitmulti(req: FitMultiRequest):
    try:
        clean = lambda v: None if v is None or str(v).strip() == "" else float(v)  # noqa: E731
        x = [clean(v) for v in req.x]
        ys = [[clean(v) for v in col] for col in req.ys]
        res = curvefit.fit_multi(x, ys, req.names, req.model, x_is_log=req.x_is_log, alpha=req.alpha, fixed=req.fixed,
                                 compare=req.compare, equation=req.equation, initial=req.initial)
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return JSONResponse(_json_safe(res))


class TwoWayRequest(BaseModel):
    rows: list               # row-factor label for each data row (repeat a label for replicates)
    columns: list            # one list of values per column-factor level
    names: list[str]
    alpha: float = 0.05
    rm: bool = False         # repeated measures across rows (same subjects at every row name)
    compare: str = "within_rows"  # within_rows | within_cols | col_means | row_means (ordinary two-way)


@app.post("/api/twoway")
def run_twoway(req: TwoWayRequest):
    try:
        if req.rm:
            res = anova2.two_way_rm(req.rows, req.columns, req.names, alpha=req.alpha)
        else:
            res = anova2.two_way(req.rows, req.columns, req.names, alpha=req.alpha, compare=req.compare)
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return JSONResponse(_json_safe(res))


class ImportRequest(BaseModel):
    filename: str
    data: str                # base64 file contents
    sheet: str | None = None


@app.post("/api/import")
def import_file(req: ImportRequest):
    try:
        if req.filename.lower().endswith(".pzfx"):
            return importer.read_pzfx(req.data)
        return importer.read_table(req.filename, req.data, req.sheet)
    except (ValueError, UnicodeDecodeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


class MultiRequest(BaseModel):
    columns: list
    names: list[str]
    analysis: str = "correlation"   # correlation | roc | bland_altman
    method: str = "pearson"
    alpha: float = 0.05


@app.post("/api/multi")
def run_multi(req: MultiRequest):
    try:
        if req.analysis == "correlation":
            res = multivar.correlation_matrix(req.columns, req.names, req.method, req.alpha)
        elif req.analysis == "pca":
            res = multivar.pca(req.columns, req.names, standardize=req.method != "covariance")
        elif req.analysis == "cox":
            if len(req.columns) < 3:
                raise ValueError("Enter time in the first column, the event (1/0) in the second, and at least one predictor.")
            cols = [(n, c) for n, c in zip(req.names[2:], req.columns[2:]) if any(v is not None and str(v).strip() != "" for v in c)]
            if not cols:
                raise ValueError("Enter at least one predictor column with values (third column onward).")
            res = multivar.cox(req.columns[0], req.columns[1], [c for _, c in cols], [n for n, _ in cols], alpha=req.alpha)
        elif req.analysis in ("mlr", "logistic"):
            if len(req.columns) < 2:
                raise ValueError("Enter the outcome in the first column and at least one predictor.")
            cols = [(n, c) for n, c in zip(req.names[1:], req.columns[1:]) if any(v is not None and str(v).strip() != "" for v in c)]
            if not cols:
                raise ValueError("Enter at least one predictor column with values.")
            fn = multivar.multiple_linear if req.analysis == "mlr" else multivar.logistic
            res = fn(req.columns[0], [c for _, c in cols], req.names[0], [n for n, _ in cols], alpha=req.alpha)
        else:
            if len(req.columns) < 2:
                raise ValueError("Enter two columns.")
            fn = multivar.roc if req.analysis == "roc" else multivar.bland_altman
            res = fn(req.columns[0], req.columns[1], names=tuple(req.names[:2]), alpha=req.alpha)
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return JSONResponse(_json_safe(res))


class MultiTRequest(BaseModel):
    rows: list
    columns: list            # two lists (group A, group B)
    names: list[str]
    kind: str = "welch"
    q: float = 0.05


@app.post("/api/multit")
def run_multit(req: MultiTRequest):
    try:
        cols = [c for c in req.columns if any(v is not None and str(v).strip() != "" for v in c)]
        names = [n for n, c in zip(req.names, req.columns) if c in cols]
        if len(cols) != 2:
            raise ValueError("Multiple t tests compare exactly 2 columns. Remove the extra columns or use two-way ANOVA.")
        kind = req.kind if req.kind in ("welch", "unpaired", "mannwhitney") else "welch"
        res = anova2.multiple_t(req.rows, cols[0], cols[1], names=tuple(names), kind=kind, q=req.q)
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return JSONResponse(_json_safe(res))


class SurvivalRequest(BaseModel):
    times: list
    groups: list
    names: list[str]
    alpha: float = 0.05


@app.post("/api/survival")
def run_survival(req: SurvivalRequest):
    try:
        res = survival.analyze(req.times, dict(zip(req.names, req.groups)), alpha=req.alpha)
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return JSONResponse(_json_safe(res))


class ContingencyRequest(BaseModel):
    table: list
    rows: list[str]
    cols: list[str]
    alpha: float = 0.05
    analysis: str = "table"     # table | mcnemar | gof (table = [[observed, expected], ...])
    expected_pct: bool = False


@app.post("/api/contingency")
def run_contingency(req: ContingencyRequest):
    try:
        if req.analysis == "mcnemar":
            res = contingency.mcnemar(req.table, req.rows, req.cols, alpha=req.alpha)
        elif req.analysis == "gof":
            res = contingency.goodness_of_fit(req.rows, [r[0] if r else None for r in req.table],
                                              [r[1] if len(r) > 1 else None for r in req.table], req.expected_pct, req.alpha)
        else:
            res = contingency.analyze(req.table, req.rows, req.cols, alpha=req.alpha)
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return JSONResponse(_json_safe(res))


@app.post("/api/regression")
def run_regression(req: RegressionRequest):
    try:
        res = stats.linear_regression(req.x, req.y, alpha=req.alpha)
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return JSONResponse(_json_safe(res))


# ---- projects & exports (all stored inside the app folder) ----------------

class ProjectBody(BaseModel):
    data: dict


class RenameBody(BaseModel):
    new_name: str


class ExportBody(BaseModel):
    filename: str
    data_url: str
    fmt: str | None = None    # "tiff" to convert a PNG to TIFF
    dpi: int | None = None


@app.get("/api/projects")
def projects_list():
    return {"projects": storage.list_projects(), "last": storage.get_last_project(),
            "folder": str(storage.projects_dir())}


@app.get("/api/projects/{name}")
def project_get(name: str):
    try:
        data = storage.load_project(name)
    except FileNotFoundError:
        raise HTTPException(404, "Project not found.")
    except ValueError:
        raise HTTPException(400, "That project file is damaged or not an Erwin's Hypothesis project.")
    storage.set_last_project(name)
    return data


@app.put("/api/projects/{name}")
def project_put(name: str, body: ProjectBody):
    try:
        return {"name": storage.save_project(name, body.data)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/projects/{name}/rename")
def project_rename(name: str, body: RenameBody):
    try:
        return {"name": storage.rename_project(name, body.new_name)}
    except FileExistsError:
        raise HTTPException(409, "A project with that name already exists.")
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.delete("/api/projects/{name}")
def project_delete(name: str):
    try:
        storage.delete_project(name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.post("/api/exports")
def export_save(body: ExportBody):
    try:
        return {"file": storage.save_export(body.filename, body.data_url, fmt=body.fmt, dpi=body.dpi),
                "folder": str(storage.exports_dir())}
    except ValueError as e:
        raise HTTPException(400, str(e))


class XlsxExportBody(BaseModel):
    filename: str
    title: str
    results: list[list[str]]
    data_cols: list[str]
    data_rows: list[list[str]]


@app.post("/api/exports/xlsx")
def export_xlsx(body: XlsxExportBody):
    try:
        return {"file": storage.save_results_xlsx(body.filename, body.title, body.results, body.data_cols, body.data_rows),
                "folder": str(storage.exports_dir())}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/prefs")
def prefs_get():
    return storage.get_prefs()


@app.put("/api/prefs")
def prefs_put(body: dict):
    return storage.set_prefs(body)


@app.post("/api/reveal/{folder}")
def reveal(folder: str):
    if folder not in ("projects", "exports"):
        raise HTTPException(400, "Unknown folder.")
    try:
        storage.reveal(folder)
    except Exception:
        raise HTTPException(500, "Couldn't open the folder.")
    return {"ok": True}


@app.get("/vendor/plotly.min.js")
def plotly_js():
    return FileResponse(PLOTLY_JS, media_type="application/javascript")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")


def _is_running(url: str) -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(url + "/api/health", timeout=1) as r:
            return r.status == 200
    except Exception:
        return False


def main():
    import threading
    import time
    import webbrowser

    import uvicorn

    port = int(os.environ.get("EH_PORT", "8765"))
    url = f"http://127.0.0.1:{port}"
    open_browser = os.environ.get("EH_OPEN_BROWSER", "1") == "1"

    if _is_running(url):
        print("Erwin's Hypothesis is already running; opening it in your browser.")
        if open_browser:
            webbrowser.open(url)
        return

    def _open_when_ready():
        for _ in range(100):
            if _is_running(url):
                if open_browser:
                    webbrowser.open(url)
                return
            time.sleep(0.2)

    threading.Thread(target=_open_when_ready, daemon=True).start()
    print(f"\n  Erwin's Hypothesis is running at {url}")
    print(f"  Your projects folder: {storage.projects_dir()}")
    print("  Keep this window open while you use the app. Close it to quit.\n")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
