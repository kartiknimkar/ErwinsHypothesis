"""Workflow strip, workspace views, right-click menu, axis panel, shape order/copy-paste, copy a look, zoom."""
import pytest

sync_api = pytest.importorskip("playwright.sync_api")
from tests.test_ui_smoke import server  # noqa: F401,E402

BOX = "e => { const r = e.getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; }"


def _shapes(page):
    return page.evaluate("document.getElementById('plot').layout.shapes.filter(s => s.editable).map(s => ({type: s.type, opacity: s.opacity, color: s.line && s.line.color}))")


def test_workflow_views_and_graph_editing(server):  # noqa: F811
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:
            pytest.skip(f"no browser: {e}")
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(server)
        page.wait_for_selector("#sheet-list li")
        page.click("#sheet-list li:has-text('three groups')")
        page.wait_for_selector("#plot .main-svg")
        # workflow strip: data → analysis → result → checks
        page.wait_for_function("document.querySelectorAll('#flow-strip .flow-step').length === 4")
        txt = page.inner_text("#flow-strip")
        assert "18 values" in txt and "ANOVA" in txt and "P < 0.0001" in txt and "Checks" in txt
        page.click("#flow-strip .flow-step:has-text('Checks')")
        assert page.evaluate("document.querySelector('#results details.checklist').open")
        # views
        page.click('#view-switch [data-view="graph"]'); page.wait_for_timeout(400)
        assert not page.is_visible(".data-card") and page.is_visible("#graph-format")
        w_graph = page.evaluate("document.getElementById('plot').getBoundingClientRect().width")
        page.keyboard.press("Alt+2"); page.wait_for_timeout(300)
        assert page.is_visible(".data-card") and not page.is_visible("#plot")
        page.keyboard.press("Alt+1"); page.wait_for_timeout(400)
        assert page.is_visible(".data-card") and page.is_visible("#plot") and not page.is_visible("#graph-format")
        assert page.evaluate("document.getElementById('plot').getBoundingClientRect().width") < w_graph
        # zoom
        w0 = page.evaluate("document.getElementById('plot').getBoundingClientRect().width")
        page.click("#zoom-in"); page.wait_for_timeout(200)
        assert page.evaluate("document.getElementById('plot').getBoundingClientRect().width") > w0 * 1.2
        page.click("#zoom-fit"); page.wait_for_timeout(200)
        # right-click: add text exactly there
        x, y, w, h = page.eval_on_selector("#plot .draglayer .nsewdrag", BOX)
        n0 = page.evaluate("document.getElementById('plot').layout.annotations.length")
        page.mouse.click(x + w * 0.25, y + h * 0.75, button="right")
        assert page.is_visible("#graph-menu")
        page.click('#graph-menu [data-act="text"]'); page.wait_for_timeout(400)
        ann = page.evaluate("document.getElementById('plot').layout.annotations.slice(-1)[0]")
        assert page.evaluate("document.getElementById('plot').layout.annotations.length") == n0 + 1
        assert abs(ann["x"] - 0.25) < 0.03 and abs(ann["y"] - 0.25) < 0.03
        # draw a box, change opacity and order from the menu, copy/paste with the keyboard
        page.click('#draw-bar [data-draw="rect"]')
        page.mouse.move(x + w * 0.1, y + h * 0.5); page.mouse.down(); page.mouse.move(x + w * 0.3, y + h * 0.7, steps=6); page.mouse.up()
        page.wait_for_timeout(500)
        page.mouse.click(x + w * 0.2, y + h * 0.6)   # anywhere inside the box selects it
        page.wait_for_timeout(300)
        assert page.is_enabled("#draw-del")
        page.mouse.click(x + w * 0.6, y + h * 0.6, button="right")
        assert "Selected shape" in page.inner_text("#graph-menu")
        page.click('#graph-menu [data-act="op:0.5"]'); page.wait_for_timeout(300)
        assert _shapes(page)[-1]["opacity"] == 0.5
        page.keyboard.press("Control+c"); page.keyboard.press("Control+v"); page.wait_for_timeout(400)
        assert [s["type"] for s in _shapes(page)].count("rect") == 2
        # double-click the Y axis: range panel
        page.mouse.click(5, 400)
        page.mouse.dblclick(x - 25, y + h * 0.5); page.wait_for_timeout(300)
        assert page.is_visible("#axis-pop") and "Y axis" in page.inner_text("#axis-pop")
        page.fill('#axis-pop [data-ax="ymax"]', "40"); page.wait_for_timeout(500)
        assert page.evaluate("document.getElementById('plot')._fullLayout.yaxis.range[1]") >= 39
        page.click("#ax-auto"); page.wait_for_timeout(400)
        assert page.evaluate("document.getElementById('plot')._fullLayout.yaxis.range[1]") < 39
        page.keyboard.press("Escape")
        # copy this look, paste on another graph
        page.click("#btn-format"); page.select_option('#graph-format [data-g="fontFamily"]', "Georgia"); page.click("#btn-format")
        page.mouse.click(x + w * 0.6, y + h * 0.6, button="right"); page.click('#graph-menu [data-act="copylook"]')
        page.click("#sheet-list li:has-text('two groups')"); page.wait_for_selector("#plot .main-svg"); page.wait_for_timeout(500)
        x, y, w, h = page.eval_on_selector("#plot .draglayer .nsewdrag", BOX)
        page.mouse.click(x + w * 0.6, y + h * 0.6, button="right"); page.click('#graph-menu [data-act="pastelook"]'); page.wait_for_timeout(400)
        assert "Georgia" in page.evaluate("document.getElementById('plot').layout.font.family")
        page.evaluate("document.activeElement && document.activeElement.blur()")
        page.keyboard.press("Control+z"); page.wait_for_timeout(400)
        assert "Georgia" not in page.evaluate("document.getElementById('plot').layout.font.family")
        # tidy up the three-groups example for the other tests
        page.click("#sheet-list li:has-text('three groups')"); page.wait_for_selector("#plot .main-svg"); page.wait_for_timeout(400)
        page.click("#btn-format")
        page.select_option('#graph-format [data-g="fontFamily"]', "Arial")
        page.click("#btn-clear-draw")
        while page.query_selector("#graph-format [data-note-del]"):
            page.click("#graph-format [data-note-del] >> nth=-1"); page.wait_for_timeout(150)
        page.click("#btn-format")
        assert errors == [], errors
        browser.close()
