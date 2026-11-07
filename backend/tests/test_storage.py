"""Saving must stay inside the app folder."""
import base64

import pytest
from fastapi.testclient import TestClient

from app import storage
from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("EH_HOME", str(tmp_path))
    return TestClient(app), tmp_path


def test_project_roundtrip(client):
    c, home = client
    data = {"sheets": [{"id": "a", "type": "ttest", "title": "T"}], "activeId": "a"}
    r = c.put("/api/projects/My Study", json={"data": data})
    assert r.status_code == 200 and r.json()["name"] == "My Study"
    assert (home / "projects" / "My Study.ehp").exists()
    listing = c.get("/api/projects").json()
    assert [p["name"] for p in listing["projects"]] == ["My Study"]
    assert listing["last"] == "My Study"
    assert c.get("/api/projects/My Study").json()["sheets"][0]["title"] == "T"


def test_rename_and_delete(client):
    c, home = client
    c.put("/api/projects/A", json={"data": {"sheets": []}})
    c.put("/api/projects/B", json={"data": {"sheets": []}})
    assert c.post("/api/projects/A/rename", json={"new_name": "B"}).status_code == 409
    assert c.post("/api/projects/A/rename", json={"new_name": "C"}).json()["name"] == "C"
    assert not (home / "projects" / "A.ehp").exists()
    c.delete("/api/projects/C")
    assert not (home / "projects" / "C.ehp").exists()


@pytest.mark.parametrize("bad", ["../escape", "..\\escape", "/etc/passwd", "a/../../b", "C:\\x"])
def test_names_cannot_escape_folder(client, bad):
    c, home = client
    name = storage.save_project(bad, {"sheets": []})
    saved = list((home / "projects").glob("*.ehp"))
    assert len(saved) == 1 and saved[0].parent == home / "projects"
    assert "/" not in name and "\\" not in name and ".." not in name
    assert not (home.parent / "escape.ehp").exists()


def test_export_png_and_svg(client):
    c, home = client
    png = "data:image/png;base64," + base64.b64encode(b"\x89PNG fake").decode()
    r1 = c.post("/api/exports", json={"filename": "Graph 1", "data_url": png}).json()
    r2 = c.post("/api/exports", json={"filename": "Graph 1", "data_url": png}).json()
    assert r1["file"] == "Graph 1.png" and r2["file"] == "Graph 1 (2).png"  # no overwrite
    svg = "data:image/svg+xml,%3Csvg%3E%3C%2Fsvg%3E"
    r3 = c.post("/api/exports", json={"filename": "../../x", "data_url": svg}).json()
    assert (home / "exports" / r3["file"]).read_text() == "<svg></svg>"
    assert c.post("/api/exports", json={"filename": "x", "data_url": "data:text/html,hi"}).status_code == 400


def test_results_xlsx(client):
    import openpyxl
    c, home = client
    r = c.post("/api/exports/xlsx", json={"filename": "P - T", "title": "T", "results": [["P value", "0.003"], [], ["TUKEY"]],
                                          "data_cols": ["A", "B"], "data_rows": [["1", "2.5"], ["", ""], ["x", "3"]]}).json()
    wb = openpyxl.load_workbook(home / "exports" / r["file"])
    assert wb.sheetnames == ["Results", "Data"]
    assert wb["Results"]["B3"].value == 0.003  # stored as a real number
    assert [[c.value for c in row] for row in wb["Data"].iter_rows()] == [["A", "B"], [1, 2.5], ["x", 3]]


def test_tiff_and_png_dpi(client):
    import io
    from PIL import Image
    c, home = client
    buf = io.BytesIO(); Image.new("RGBA", (40, 30), (255, 0, 0, 255)).save(buf, format="PNG")
    url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    t = c.post("/api/exports", json={"filename": "g", "data_url": url, "fmt": "tiff", "dpi": 600}).json()
    assert t["file"] == "g.tif"
    im = Image.open(home / "exports" / "g.tif")
    assert im.format == "TIFF" and im.size == (40, 30) and round(im.info["dpi"][0]) == 600
    p = c.post("/api/exports", json={"filename": "g", "data_url": url, "dpi": 300}).json()
    assert round(Image.open(home / "exports" / p["file"]).info["dpi"][0]) == 300
