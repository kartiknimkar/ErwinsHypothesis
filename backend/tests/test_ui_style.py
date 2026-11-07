"""Graph styling (Format panel) applies to every graph type without errors, and SVG export
keeps text as editable <text> in the chosen font. Skipped when Playwright isn't installed."""
import glob
import os

import pytest

sync_api = pytest.importorskip("playwright.sync_api")
from tests.test_ui_smoke import server  # noqa: F401,E402  (shared fixture)

STYLE = {"fontFamily": "Times New Roman", "pointSymbol": "square-open", "pattern": "vary", "barOpacity": "0.3",
         "tickDir": "inside", "bg": "transparent", "legendPos": "outside"}


def _style(page):
    page.click("#btn-format")
    for k, v in STYLE.items():
        page.select_option(f'#graph-format [data-g="{k}"]', v)
    page.check('#graph-format [data-g="grid"]')
    page.fill('#graph-format [data-g="lineScale"]', "2")
    page.dispatch_event('#graph-format [data-g="lineScale"]', "input")
    page.click("#btn-format")


def test_styles_apply_to_every_graph_and_svg_is_editable(server):  # noqa: F811
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
        n = len(page.query_selector_all("#sheet-list li"))
        for i in range(n):
            page.click(f"#sheet-list li:nth-child({i + 1})")
            page.wait_for_function("document.querySelector('#results').textContent.trim().length > 0", timeout=15000)
            page.wait_for_timeout(200)
            _style(page)
            page.wait_for_timeout(200)
            assert page.query_selector("#plot .main-svg") is not None
        assert errors == [], errors
        # first example (compare groups) → violin plot, then SVG
        page.click("#sheet-list li:nth-child(1)")
        page.wait_for_timeout(500)
        page.click("#btn-format"); page.select_option('#graph-format [data-g="style"]', "violin"); page.click("#btn-format")
        page.wait_for_timeout(400)
        assert page.query_selector("#plot .violinlayer path") is not None
        fonts = page.eval_on_selector_all("#plot text", "els => els.map(e => e.style.fontFamily).join('|')")
        assert "Times New Roman" in fonts
        exports = os.path.join(os.environ["EH_HOME"], "exports")
        before = set(glob.glob(os.path.join(exports, "*.svg")))
        page.click("#btn-svg")
        page.wait_for_selector("#toast:not([hidden])")
        page.wait_for_timeout(300)
        new = set(glob.glob(os.path.join(exports, "*.svg"))) - before
        assert new, "no SVG written"
        svg = open(new.pop(), encoding="utf-8").read()
        assert svg.count("<text") > 5 and "Times New Roman" in svg
        # figure layout → one combined, editable SVG
        layout = page.eval_on_selector_all("#sheet-list li .t", "els => els.findIndex(e => /figure layout/i.test(e.textContent))")
        if layout >= 0:
            page.click(f"#sheet-list li:nth-child({layout + 1})")
            page.wait_for_timeout(1500)
            before = set(glob.glob(os.path.join(exports, "*.svg")))
            page.click("#btn-svg")
            page.wait_for_timeout(1500)
            new = set(glob.glob(os.path.join(exports, "*.svg"))) - before
            assert new, "no layout SVG written"
            svg = open(new.pop(), encoding="utf-8").read()
            assert svg.count('<g id="panel-') >= 2 and "<text" in svg
        assert errors == [], errors
        browser.close()


def test_horizontal_stacked_labels_and_on_graph_edits(server):  # noqa: F811
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
        page.click("#sheet-list li:has-text('three groups')")
        page.wait_for_timeout(600)
        page.click("#btn-format")
        page.check('#graph-format [data-g="horizontal"]')
        page.click("#btn-add-note")
        page.fill('#graph-format [data-note="0"]', "n = 6 per group")
        page.wait_for_timeout(500)
        assert page.evaluate("document.getElementById('plot').layout.yaxis.ticktext.length") == 3
        assert "n = 6 per group" in page.inner_text("#plot")
        page.click("#sheet-list li:has-text('two-way')")
        page.wait_for_timeout(600)
        page.select_option('#graph-format [data-g="style"]', "stacked")
        page.wait_for_timeout(500)
        assert page.evaluate("document.getElementById('plot').layout.barmode") == "stack"
        # edits made directly on the graph are kept
        page.evaluate("Plotly.restyle(document.getElementById('plot'), {name: 'Renamed'}, [0])")
        page.evaluate("Plotly.relayout(document.getElementById('plot'), {'yaxis.title.text': 'Edited Y'})")
        page.wait_for_timeout(300)
        page.click("#sheet-list li:has-text('three groups')")
        page.wait_for_timeout(400)
        page.click("#sheet-list li:has-text('two-way')")
        page.wait_for_timeout(700)
        assert "Renamed" in page.evaluate("document.getElementById('plot').data.map(t => t.name)")
        assert page.evaluate("document.getElementById('plot').layout.yaxis.title.text") == "Edited Y"
        page.click("#btn-reset-edits")
        page.wait_for_timeout(500)
        assert "Renamed" not in page.evaluate("document.getElementById('plot').data.map(t => t.name)")
        # broken Y axis: two stacked y axes, traces drawn on both
        page.click("#sheet-list li:has-text('three groups')")
        page.wait_for_timeout(500)
        page.uncheck('#graph-format [data-g="horizontal"]')
        page.select_option('#graph-format [data-g="style"]', "bars")
        page.fill('#graph-format [data-g="breakFrom"]', "3")
        page.fill('#graph-format [data-g="breakTo"]', "9")
        page.check('#graph-format [data-g="minorTicks"]')
        page.wait_for_timeout(500)
        lay = page.evaluate("(() => { const l = document.getElementById('plot').layout; return [l.yaxis.range, l.yaxis2 && l.yaxis2.range]; })()")
        assert lay[0][1] == 3 and lay[1][0] == 9
        assert errors == [], errors
        browser.close()
