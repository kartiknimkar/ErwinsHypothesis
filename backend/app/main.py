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

from . import stats, storage

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


# ---- projects & exports (all stored inside the app folder) ----------------

class ProjectBody(BaseModel):
    data: dict


class RenameBody(BaseModel):
    new_name: str


class ExportBody(BaseModel):
    filename: str
    data_url: str


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
        return {"file": storage.save_export(body.filename, body.data_url),
                "folder": str(storage.exports_dir())}
    except ValueError as e:
        raise HTTPException(400, str(e))


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
    # Served from the installed package so the app works fully offline.
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
