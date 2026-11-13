"""Draw toolbar: boxes, brackets, arrows and text drawn on the graph are saved, editable and exported."""
import glob
import os

import pytest

sync_api = pytest.importorskip("playwright.sync_api")
from tests.test_ui_smoke import server  # noqa: F401,E402


def _user_shapes(page):
    return page.evaluate("document.getElementById('plot').layout.shapes.filter(s => s.editable).map(s => ({type: s.type, name: s.name || '', label: (s.label && s.label.text) || '', color: s.line && s.line.color}))")


def test_draw_box_bracket_arrow_and_export(server):  # noqa: F811
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
        page.wait_for_selector("#plot .main-svg")
        page.wait_for_timeout(700)
        assert page.is_visible("#draw-bar")
        x, y, w, h = page.eval_on_selector("#plot .draglayer .nsewdrag", "e => { const r = e.getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; }")
        before = len(_user_shapes(page))
        # a red box
        page.evaluate("() => { const c = document.getElementById('draw-color'); c.value = '#d62728'; c.dispatchEvent(new Event('change')); }")
        page.click('#draw-bar [data-draw="rect"]')
        page.mouse.move(x + w * 0.1, y + h * 0.6); page.mouse.down(); page.mouse.move(x + w * 0.3, y + h * 0.8, steps=8); page.mouse.up()
        page.wait_for_timeout(500)
        sh = _user_shapes(page)
        assert len(sh) == before + 1 and sh[-1]["type"] == "rect" and sh[-1]["color"].lower() == "#d62728"
        # back in select mode after drawing
        assert "on" in page.get_attribute('#draw-bar [data-draw="select"]', "class")
        # a bracket with a label
        page.click('#draw-bar [data-draw="bracket"]')
        page.mouse.move(x + w * 0.15, y + h * 0.1); page.mouse.down(); page.mouse.move(x + w * 0.8, y + h * 0.1, steps=10); page.mouse.up()
        page.wait_for_timeout(800)
        assert page.is_visible("#draw-label")
        page.fill("#draw-label", "P = 0.003")
        page.wait_for_timeout(500)
        sh = _user_shapes(page)
        assert sh[-1]["name"] == "bracket" and sh[-1]["label"] == "P = 0.003"
        # an arrow and a text label
        n_ann = page.evaluate("document.getElementById('plot').layout.annotations.length")
        page.click('#draw-bar [data-draw="arrow"]'); page.wait_for_timeout(300)
        page.click('#draw-bar [data-draw="text"]'); page.wait_for_timeout(300)
        assert page.evaluate("document.getElementById('plot').layout.annotations.length") == n_ann + 2
        assert page.evaluate("document.getElementById('plot').layout.annotations.some(a => a.showarrow && a.ax !== undefined)")
        # export: drawings are in the editable SVG
        exports = os.path.join(os.environ["EH_HOME"], "exports")
        old = set(glob.glob(os.path.join(exports, "*.svg")))
        page.click("#btn-svg")
        for _ in range(40):
            page.wait_for_timeout(150)
            new = set(glob.glob(os.path.join(exports, "*.svg"))) - old
            if new:
                break
        svg = open(new.pop(), encoding="utf-8").read()
        assert "P = 0.003" in svg and "#d62728" in svg
        # saved with the project
        page.wait_for_timeout(1200)
        page.reload(); page.wait_for_selector("#sheet-list li")
        page.click("#sheet-list li:has-text('three groups')")
        page.wait_for_selector("#plot .main-svg"); page.wait_for_timeout(700)
        sh = _user_shapes(page)
        assert len(sh) == before + 2 and sh[-1]["label"] == "P = 0.003"
        # select the box by clicking its edge, delete it with the Delete key, then undo
        page.evaluate("document.getElementById('plot')._fullLayout._activeShapeIndex = undefined")
        idx = page.evaluate("document.getElementById('plot').layout.shapes.findIndex(s => s.editable && s.type === 'rect')")
        page.evaluate(f"() => {{ const el = document.getElementById('plot'); el._fullLayout._activeShapeIndex = {idx}; el.dispatchEvent(new MouseEvent('mouseup')); }}")
        page.wait_for_timeout(200)
        assert page.is_enabled("#draw-del")
        page.keyboard.press("Delete")
        page.wait_for_timeout(400)
        assert [s["type"] for s in _user_shapes(page)].count("rect") == 0
        page.keyboard.press("Control+z")
        page.wait_for_timeout(600)
        assert [s["type"] for s in _user_shapes(page)].count("rect") == 1
        # clean up so other tests see the example unchanged
        page.click("#btn-format")
        page.click("#btn-clear-draw")
        while page.query_selector("#graph-format [data-note-del]"):
            page.click("#graph-format [data-note-del] >> nth=-1"); page.wait_for_timeout(150)
        page.click("#btn-format")
        page.wait_for_timeout(300)
        assert _user_shapes(page) == []
        assert errors == [], errors
        browser.close()


def test_series_popover_and_table(server):  # noqa: F811
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
        page.click("#sheet-list li:has-text('two-way AN')")
        page.wait_for_selector("#plot .main-svg"); page.wait_for_timeout(800)
        pt = page.eval_on_selector("#plot .scatterlayer .point", "e => { const r = e.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }")
        page.mouse.click(*pt); page.wait_for_timeout(300)
        assert page.is_visible("#series-pop")
        name = page.inner_text("#series-pop .sp-head b")
        page.select_option('#series-pop [data-k="symbol"]', "diamond"); page.wait_for_timeout(250)
        page.select_option('#series-pop [data-k="pattern"]', "x"); page.wait_for_timeout(250)
        page.fill('#series-pop [data-k="size"]', "14"); page.wait_for_timeout(300)
        tr = page.evaluate("document.getElementById('plot').data.map(t => [t.type, t.marker && t.marker.symbol, t.marker && t.marker.size, t.marker && t.marker.pattern && t.marker.pattern.shape])")
        assert ["scatter", "diamond", 14, None] in tr and any(t[0] == "bar" and t[3] == "x" for t in tr)
        # only that series changed
        assert sum(1 for t in tr if t[1] == "diamond") == 1
        page.keyboard.press("Escape")
        assert not page.is_visible("#series-pop")
        # the Format table shows the same settings
        page.click("#btn-format")
        row = page.locator(f".series-tbl tr:has(td.sname:text-is('{name}'))")
        assert row.locator('[data-k="symbol"]').input_value() == "diamond"
        # hide via the table, then reset everything
        row.locator('[data-k="hidden"]').uncheck(); page.wait_for_timeout(300)
        assert page.evaluate("document.getElementById('plot').data.some(t => t.visible === false)")
        page.click("#btn-reset-colors"); page.wait_for_timeout(300)
        assert not page.evaluate("document.getElementById('plot').data.some(t => t.visible === false || (t.marker && t.marker.symbol === 'diamond'))")
        page.click("#btn-format")
        # legend entry opens the panel instead of hiding the series
        leg = page.eval_on_selector("#plot .legend .traces .legendtoggle", "e => { const r = e.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }")
        page.mouse.click(*leg); page.wait_for_timeout(300)
        assert page.is_visible("#series-pop")
        assert not page.evaluate("document.getElementById('plot').data.some(t => t.visible === 'legendonly')")
        page.keyboard.press("Escape")
        assert errors == [], errors
        browser.close()


def test_axis_frames_bold_titles_and_superscripts(server):  # noqa: F811
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
        page.wait_for_selector("#plot .main-svg"); page.wait_for_timeout(600)
        page.click("#btn-format")
        old = page.input_value('#graph-format [data-g="ylabel"]')
        page.select_option('#graph-format [data-g="frame"]', "offset"); page.wait_for_timeout(300)
        lay = page.evaluate("(() => { const l = document.getElementById('plot').layout; return [l.xaxis.anchor, l.xaxis.domain, l.yaxis.domain]; })()")
        assert lay[0] == "free" and lay[1][0] > 0 and lay[2][0] > 0
        page.select_option('#graph-format [data-g="frame"]', "box"); page.wait_for_timeout(300)
        assert page.evaluate("document.getElementById('plot').layout.yaxis.mirror") is True
        page.select_option('#graph-format [data-g="titleWeight"]', "bold"); page.wait_for_timeout(300)
        assert page.evaluate("document.getElementById('plot').layout.yaxis.title.font.weight") == "bold"
        # symbol button inserts into the last text box; ^{} becomes a superscript
        page.fill('#graph-format [data-g="ylabel"]', "Area (m^{2})")
        page.click('#graph-format [data-g="ylabel"]')
        page.keyboard.press("End"); page.keyboard.press("ArrowLeft"); page.keyboard.press("ArrowLeft")
        page.keyboard.press("ArrowLeft"); page.keyboard.press("ArrowLeft"); page.keyboard.press("ArrowLeft"); page.keyboard.press("ArrowLeft")
        page.click('#graph-format [data-sym="μ"]'); page.wait_for_timeout(300)
        assert page.input_value('#graph-format [data-g="ylabel"]') == "Area (μm^{2})"
        assert "<sup>2</sup>" in page.evaluate("document.getElementById('plot').layout.yaxis.title.text")
        assert page.query_selector("#plot .ytitle tspan") is not None
        # put things back for the other tests
        page.fill('#graph-format [data-g="ylabel"]', old)
        page.select_option('#graph-format [data-g="frame"]', "prism")
        page.select_option('#graph-format [data-g="titleWeight"]', "normal")
        page.wait_for_timeout(300)
        assert errors == [], errors
        browser.close()
