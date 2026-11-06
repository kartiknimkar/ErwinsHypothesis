"""Local web server: serves the interface and runs analyses."""
from __future__ import annotations

import math
import os
from pathlib import Path

import plotly
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import stats

STATIC = Path(__file__).parent / "static"
PLOTLY_JS = Path(plotly.__file__).parent / "package_data" / "plotly.min.js"

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


@app.post("/api/regression")
def run_regression(req: RegressionRequest):
    try:
        res = stats.linear_regression(req.x, req.y, alpha=req.alpha)
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return JSONResponse(_json_safe(res))


@app.get("/vendor/plotly.min.js")
def plotly_js():
    # Served from the installed package so the app works fully offline.
    return FileResponse(PLOTLY_JS, media_type="application/javascript")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")


def main():
    import uvicorn
    port = int(os.environ.get("EH_PORT", "8765"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
