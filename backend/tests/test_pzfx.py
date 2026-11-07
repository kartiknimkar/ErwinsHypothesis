"""Prism .pzfx import, using files that follow Prism's XML layout."""
import base64

import pytest
from fastapi.testclient import TestClient

from app import importer
from app.main import app

NS = 'xmlns="http://graphpad.com/prism/Prism.htm"'


def col(tag, title, subs, extra=""):
    sc = "".join("<Subcolumn>" + "".join(
        f'<d Excluded="1">{v[1:]}</d>' if isinstance(v, str) and v.startswith("!") else f"<d>{v}</d>" if v != "" else "<d/>"
        for v in s) + "</Subcolumn>" for s in subs)
    return f'<{tag} Subcolumns="{len(subs)}" {extra}><Title>{title}</Title>{sc}</{tag}>'


PZFX = f"""<?xml version="1.0" encoding="UTF-8"?>
<GraphPadPrismFile {NS} PrismXMLVersion="5.00">
<Created><OriginalVersion CreatedByProgram="GraphPad Prism" CreatedByVersion="9.0"/></Created>
<TableSequence><Ref ID="Table0"/><Ref ID="Table1"/></TableSequence>
<Table ID="Table0" XFormat="none" TableType="OneWay" EVFormat="AsteriskAfterNumber">
 <Title>Body weight</Title>
 {col("YColumn", "Control", [[20.1, 21.3, 19.8, "!35.0"]])}
 {col("YColumn", "Treated", [[23.4, 24.0, 22.9, 23.7]])}
</Table>
<Table ID="Table1" XFormat="numbers" YFormat="replicates" Replicates="2" TableType="XY">
 <Title>Dose response</Title>
 {col("XColumn", "Dose (nM)", [[0.1, 1, 10, 100]])}
 {col("YColumn", "Response", [[98, 80, 30, 6], [96, 77, 33, 5]])}
</Table>
<Table ID="Table2" XFormat="none" YFormat="replicates" Replicates="2" TableType="TwoWay">
 <Title>Sex x drug</Title>
 <RowTitlesColumn Width="80"><Subcolumn><d>Male</d><d>Female</d></Subcolumn></RowTitlesColumn>
 {col("YColumn", "Vehicle", [[5.1, 6.0], [4.8, 6.3]])}
 {col("YColumn", "Drug", [[6.9, 7.0], [7.4, 7.7]])}
</Table>
<Table ID="Table3" XFormat="numbers" TableType="Survival">
 <Title>Survival</Title>
 {col("XColumn", "Days", [[3, 5, 8, 4, 9]])}
 {col("YColumn", "A", [[1, 0, 1, "", ""]])}
 {col("YColumn", "B", [["", "", "", 1, 1]])}
</Table>
<Table ID="Table4" TableType="Contingency">
 <Title>Response</Title>
 <RowTitlesColumn><Subcolumn><d>Treated</d><d>Placebo</d></Subcolumn></RowTitlesColumn>
 {col("YColumn", "Yes", [[38, 23]])}
 {col("YColumn", "No", [[12, 27]])}
</Table>
<Table ID="Table5" XFormat="numbers" YFormat="SD" TableType="XY">
 <Title>Means only</Title>
 {col("XColumn", "Time", [[0, 1, 2]])}
 {col("YColumn", "A", [[1, 2, 3], [0.1, 0.2, 0.3]])}
 {col("YColumn", "B", [[2, 3, 4], [0.1, 0.1, 0.1]])}
</Table>
</GraphPadPrismFile>"""


def b64(s):
    return base64.b64encode(s.encode()).decode()


def test_every_table_type_maps_to_an_analysis():
    r = importer.read_pzfx(b64(PZFX))
    t = {x["title"]: x for x in r["tables"]}
    bw = t["Body weight"]
    assert bw["type"] == "ttest" and bw["cols"] == ["Control", "Treated"]
    assert [row[0] for row in bw["rows"]] == ["20.1", "21.3", "19.8", ""]  # excluded value dropped
    dr = t["Dose response"]
    assert dr["type"] == "regression" and dr["cols"] == ["Dose (nM)", "Response", "Rep 2"] and dr["rows"][1] == ["1", "80", "77"]
    tw = t["Sex x drug"]
    assert tw["type"] == "twoway" and tw["rows"] == [["Male", "5.1", "6.9"], ["Male", "4.8", "7.4"], ["Female", "6.0", "7.0"], ["Female", "6.3", "7.7"]]
    sv = t["Survival"]
    assert sv["cols"] == ["Time", "A", "B"] and sv["rows"][3] == ["4", "", "1"]
    ct = t["Response"]
    assert ct["type"] == "contingency" and ct["rows"] == [["Treated", "38", "12"], ["Placebo", "23", "27"]]
    mo = t["Means only"]
    assert mo["options"] == {"yMode": "datasets"} and mo["rows"][2] == ["2", "3", "4"]
    assert any("excluded" in n for n in r["notes"]) and any("SD" in n for n in r["notes"])


def test_bad_files_rejected():
    with pytest.raises(ValueError):
        importer.read_pzfx(b64("not xml"))
    with pytest.raises(ValueError):
        importer.read_pzfx(b64('<?xml version="1.0"?><!DOCTYPE a [<!ENTITY x "y">]><a>&x;</a>'))
    with pytest.raises(ValueError):
        importer.read_pzfx(b64(f"<GraphPadPrismFile {NS}></GraphPadPrismFile>"))


def test_endpoint_routes_pzfx():
    c = TestClient(app)
    r = c.post("/api/import", json={"filename": "Project.pzfx", "data": b64(PZFX)}).json()
    assert len(r["tables"]) == 6


def test_nested_and_mean_sd_n_tables():
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<GraphPadPrismFile {NS} PrismXMLVersion="5.00">
<Table ID="Table0" TableType="Nested" YFormat="replicates">
 <Title>Cells per mouse</Title>
 {col("YColumn", "Control", [[10.2, 11.1, 9.6], [12.4, 11.9, ""], [9.1, "!20", 8.7]])}
 {col("YColumn", "Drug", [[13.8, 14.6, 13.1], [12.2, 12.9, 13.5]])}
</Table>
<Table ID="Table1" TableType="OneWay" YFormat="SDN">
 <Title>From a paper</Title>
 {col("YColumn", "Control", [[4.6], [0.6], [8]])}
 {col("YColumn", "Drug", [[6.7], [0.7], [8]])}
</Table>
</GraphPadPrismFile>"""
    res = importer.read_pzfx(base64.b64encode(xml.encode()).decode())
    nested, summ = res["tables"]
    assert nested["type"] == "nested" and len(nested["rows"]) == 5
    assert nested["rows"][0] == ["Control", "10.2", "11.1", "9.6"] and nested["rows"][2][2] == ""  # excluded value dropped
    assert summ["type"] == "summary" and summ["rows"] == [["Control", "4.6", "0.6", "8"], ["Drug", "6.7", "0.7", "8"]]
    assert summ["options"]["err"] == "sd"
