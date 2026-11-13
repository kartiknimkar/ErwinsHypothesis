"""Editable SVG export: clean structure for Illustrator / Inkscape / PowerPoint, and it looks the same."""
import glob
import os
import re
import shutil
import subprocess
import xml.dom.minidom as minidom

import pytest

sync_api = pytest.importorskip("playwright.sync_api")
from tests.test_ui_smoke import server  # noqa: F401,E402


def _export(page, exports):
    before = set(glob.glob(os.path.join(exports, "*.svg")))
    page.click("#btn-svg")
    for _ in range(40):
        page.wait_for_timeout(150)
        new = set(glob.glob(os.path.join(exports, "*.svg"))) - before
        if new:
            return open(new.pop(), encoding="utf-8").read()
    raise AssertionError("no SVG written")


def test_svg_is_clean_and_fully_editable(server, tmp_path):  # noqa: F811
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:
            pytest.skip(f"no browser: {e}")
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(server)
        page.wait_for_selector("#sheet-list li")
        exports = os.path.join(os.environ["EH_HOME"], "exports")
        for title, groups in [("two groups", ["Control – points", "Treated – points", "Control – error bar"]),
                              ("two-way AN", ["Bars", "X axis line", "Y axis ticks and labels"]),
                              ("dose-response", ["Fitted curve", "Data – mean", "X axis title"])]:
            page.click(f"#sheet-list li:has-text('{title}')")
            page.wait_for_selector("#plot .main-svg")
            page.wait_for_timeout(600)
            n_points = page.evaluate("document.querySelectorAll('#plot .scatterlayer .point').length")
            svg = _export(page, exports)
            doc = minidom.parseString(svg)  # well-formed XML
            root = doc.documentElement
            assert root.getAttribute("width").endswith("pt") and root.getAttribute("viewBox")
            assert ' class="' not in svg and ' style="' not in svg and "data-unformatted" not in svg
            assert not re.search(r'clip-path="url\(#(?!edge-clip)', svg), "unexpected clipping mask"
            names = [e.getAttribute("data-name") for e in doc.getElementsByTagName("*") if e.getAttribute("data-name")]
            for g in groups:
                assert g in names, (title, g, names)
            # every point is its own object (round points as real circles)
            shapes = len(doc.getElementsByTagName("circle")) + svg.count("<path")
            assert len(doc.getElementsByTagName("circle")) >= min(n_points, 1) and shapes >= n_points
            # text stays text, one font name
            texts = [t for t in doc.getElementsByTagName("text")]
            assert len(texts) > 5 and all(t.getAttribute("font-family") in ("Arial", "") for t in texts)
            assert all(t.childNodes for t in texts)
            # no invisible click-catchers
            for el in doc.getElementsByTagName("rect"):
                assert not (el.getAttribute("fill") == "none" and not el.getAttribute("stroke"))
            # looks the same as Plotly's own SVG (rendered with a different engine)
            if shutil.which("rsvg-convert"):
                np = pytest.importorskip("numpy")
                Image = pytest.importorskip("PIL.Image")
                raw = page.evaluate("""async () => { const u = await Plotly.toImage(document.getElementById('plot'), {format: 'svg', width: 528, height: 403});
                  return decodeURIComponent(u.replace(/^data:image\\/svg\\+xml,/, '')); }""")
                clean = page.evaluate("async () => window.__eh.editableSVG(document.getElementById('plot'), 528, 403, {fontFamily: 'Arial'}, 't')")
                arr = []
                for k, s in (("raw", raw), ("clean", clean)):
                    f = tmp_path / f"{k}.svg"; f.write_text(s, encoding="utf-8")
                    subprocess.run(["rsvg-convert", "-w", "528", "-h", "403", "-b", "white", str(f), "-o", str(tmp_path / f"{k}.png")], check=True)
                    arr.append(np.asarray(Image.open(tmp_path / f"{k}.png").convert("L"), float))
                assert (np.abs(arr[0] - arr[1]) > 60).mean() < 0.001, title
        # data outside a manual axis range: dropped, only a crossing curve keeps a clip
        page.click("#sheet-list li:has-text('dose-response')")
        page.wait_for_selector("#plot .main-svg")
        clean = page.evaluate("""async () => { const d = document.getElementById('plot');
          await Plotly.relayout(d, {'yaxis.range': [0, 60], 'yaxis.autorange': false});
          return window.__eh.editableSVG(d, 528, 403, {fontFamily: 'Arial'}, 't'); }""")
        assert clean.count("<clipPath") <= 2 and clean.count("<circle") < 9
        page.evaluate("Plotly.relayout(document.getElementById('plot'), {'yaxis.autorange': true})")
        page.wait_for_timeout(400)
        assert errors == [], errors
        browser.close()
