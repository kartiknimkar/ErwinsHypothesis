import base64
import io

import openpyxl
import pytest
from fastapi.testclient import TestClient

from app import importer
from app.main import app

b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731


def xlsx_bytes():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Results"
    ws.append([None, None, None])
    ws.append([None, "Control", "Treated"])
    ws.append([None, 4.2, 6.1])
    ws.append([None, 5, None])
    wb.create_sheet("Notes").append(["hello"])
    buf = io.BytesIO(); wb.save(buf)
    return buf.getvalue()


def test_xlsx_trims_and_lists_sheets():
    r = importer.read_table("data.xlsx", b64(xlsx_bytes()))
    assert r["sheets"] == ["Results", "Notes"] and r["sheet"] == "Results"
    assert r["rows"] == [["Control", "Treated"], ["4.2", "6.1"], ["5", ""]]
    assert importer.read_table("data.xlsx", b64(xlsx_bytes()), "Notes")["rows"] == [["hello"]]


@pytest.mark.parametrize("text,expected", [
    ("a,b\n1,2\n3.5,4\n", [["a", "b"], ["1", "2"], ["3.5", "4"]]),
    ("a\tb\n1\t2\n", [["a", "b"], ["1", "2"]]),
    ("a;b\n1,5;2\n", [["a", "b"], ["1.5", "2"]]),
])
def test_text_formats(text, expected):
    assert importer.read_table("d.csv", b64(text.encode()))["rows"] == expected


def test_bad_files():
    with pytest.raises(ValueError):
        importer.read_table("d.xlsx", b64(b"not excel"))
    with pytest.raises(ValueError):
        importer.read_table("d.xls", b64(b"old"))
    c = TestClient(app)
    assert c.post("/api/import", json={"filename": "d.xls", "data": b64(b"x")}).status_code == 400
    assert c.post("/api/import", json={"filename": "d.csv", "data": b64(b"x,y\n1,2")}).json()["rows"][1] == ["1", "2"]
