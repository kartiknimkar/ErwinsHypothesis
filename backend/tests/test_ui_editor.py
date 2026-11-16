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
        # four layouts; nothing is recalculated or lost when switching
        res_before = page.inner_text("#results")
        page.click('#view-switch [data-view="figure"]'); page.wait_for_timeout(400)
        assert not page.is_visible(".data-card") and not page.is_visible("#results") and page.is_visible("#plot")
        w_fig = page.evaluate("document.getElementById('plot').getBoundingClientRect().width")
        page.keyboard.press("Alt+1"); page.wait_for_timeout(300)
        assert page.is_visible("#grid") and not page.is_visible("#plot")
        page.keyboard.press("Alt+4"); page.wait_for_timeout(400)
        assert not page.is_visible("#grid") and page.is_visible("#plot") and page.is_visible("#results")
        assert page.evaluate("document.getElementById('results').closest('#pane-analysis') !== null")
        page.keyboard.press("Alt+3"); page.wait_for_timeout(400)
        assert page.is_visible("#grid") and page.is_visible("#plot") and page.is_visible("#results")
        assert page.inner_text("#results") == res_before
        assert page.evaluate("document.getElementById('plot').getBoundingClientRect().width") < w_fig
        # drag the divider: the data pane gets wider
        w_data = page.evaluate("document.querySelector('.data-card').getBoundingClientRect().width")
        d = page.eval_on_selector("#pane-divider", BOX)
        page.mouse.move(d[0] + 5, d[1] + 60); page.mouse.down(); page.mouse.move(d[0] + 125, d[1] + 60, steps=5); page.mouse.up()
        page.wait_for_timeout(300)
        assert page.evaluate("document.querySelector('.data-card').getBoundingClientRect().width") > w_data + 80
        page.dblclick("#pane-divider"); page.wait_for_timeout(300)
        # the stack: one section open at a time unless pinned; compact rail and back
        page.click('#stack [data-pin="data"]'); page.click('#stack [data-pin="analysis"]')   # unpin (pinned for automated runs)
        page.click('#stack [data-stk="style"]'); page.wait_for_timeout(250)
        assert page.is_visible("#style-preset") and not page.is_visible("#sheet-list") and page.is_visible(".dial")
        page.click('#stack [data-stk="export"]'); page.wait_for_timeout(250)
        assert page.is_visible("#btn-export-go") and not page.is_visible("#style-preset")
        page.keyboard.press("Alt+0"); page.wait_for_timeout(300)
        assert page.evaluate("document.getElementById('stack').getBoundingClientRect().width") < 60
        page.click('#stack [data-stk="figure"]'); page.wait_for_timeout(250)
        assert page.is_visible('#graph-format [data-g="title"]')
        page.mouse.click(900, 500); page.wait_for_timeout(200)
        assert not page.is_visible('#graph-format [data-g="title"]')
        page.keyboard.press("Alt+0")
        page.click('#stack [data-pin="data"]'); page.click('#stack [data-pin="analysis"]'); page.wait_for_timeout(200)
        assert page.is_visible("#sheet-list") and page.is_visible("#options")
        # the dial: arrow keys change the line width, typing sets it exactly
        page.click('#stack [data-stk="style"]'); page.wait_for_timeout(200)
        page.focus("#dial-linescale"); page.keyboard.press("ArrowUp"); page.wait_for_timeout(300)
        assert page.evaluate("document.getElementById('plot') && 1") and page.get_attribute("#dial-linescale", "data-value") == "1.25"
        page.fill("#dial-linescale input", "1"); page.keyboard.press("Enter"); page.wait_for_timeout(300)
        assert page.get_attribute("#dial-linescale", "data-value") == "1"
        page.click('#stack [data-stk="data"]')
        # themes change the app, never the figure
        bg0 = page.evaluate("getComputedStyle(document.getElementById('plot')).backgroundColor")
        font0 = page.evaluate("document.getElementById('plot').layout.font.color")
        page.select_option("#theme-select", "violet-dark"); page.wait_for_timeout(300)
        assert page.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(28, 23, 40)"
        assert page.evaluate("getComputedStyle(document.getElementById('plot')).backgroundColor") == bg0 == "rgb(255, 255, 255)"
        assert page.evaluate("document.getElementById('plot').layout.font.color") == font0
        page.select_option("#theme-select", "violet"); page.wait_for_timeout(200)
        # analysis search: fixed catalog, keyboard, sets up the existing options
        page.keyboard.press("Control+k")
        page.keyboard.type("one way anova"); page.wait_for_timeout(200)
        assert "One-way ANOVA" in page.inner_text("#method-results button.on")
        page.fill("#method-search", "zzzz"); page.wait_for_timeout(150)
        assert "No analysis here matches" in page.inner_text("#method-results")
        page.fill("#method-search", "kruskal"); page.wait_for_timeout(150)
        page.keyboard.press("Enter")
        page.wait_for_function("document.querySelector('#results').textContent.includes('Kruskal-Wallis')", timeout=10000)
        assert page.evaluate("document.getElementById('grid').querySelectorAll('input').length") > 10   # same data, same sheet
        page.evaluate("document.activeElement && document.activeElement.blur()")
        page.keyboard.press("Control+z")
        page.wait_for_function("document.querySelector('#results').textContent.includes('Ordinary one-way ANOVA')", timeout=10000)
        # no multi-panel figure offered
        page.click("#btn-new"); assert not page.is_visible('#new-menu [data-type="layout"]'); page.keyboard.press("Escape"); page.mouse.click(900, 80)
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
