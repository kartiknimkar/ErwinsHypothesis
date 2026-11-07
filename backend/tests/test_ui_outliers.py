"""ROUT options in the interface: groups and XY fits run, report and draw without errors."""
import pytest

sync_api = pytest.importorskip("playwright.sync_api")
from tests.test_ui_smoke import server  # noqa: F401,E402


def test_rout_options_in_groups_and_xy(server):  # noqa: F811
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
        page.click("#sheet-list li:nth-child(1)")
        page.wait_for_timeout(500)
        # put an obvious outlier into the first group
        page.check('#options [data-opt="outliers"]')
        page.wait_for_selector("#opt-outmethod")
        page.wait_for_function("document.querySelector('#results').textContent.includes('ROUT')", timeout=10000)
        page.select_option("#opt-routq", "0.05")
        page.wait_for_timeout(600)
        assert "Q = 5%" in page.inner_text("#results")
        assert "ROUT method" in page.eval_on_selector("#results details.report", "e => e.textContent")
        page.select_option("#opt-outmethod", "grubbs")
        page.wait_for_function("document.querySelector('#results').textContent.includes('Grubbs')", timeout=10000)
        # XY dose-response with ROUT
        idx = page.eval_on_selector_all("#sheet-list li .t", "els => els.findIndex(e => /dose-respon/i.test(e.textContent))")
        page.click(f"#sheet-list li:nth-child({idx + 1})")
        page.wait_for_timeout(600)
        page.check('#options [data-opt="rout"]')
        page.wait_for_function("/ROUT/.test(document.querySelector('#results').textContent)", timeout=15000)
        assert page.query_selector("#plot .main-svg") is not None
        assert errors == [], errors
        browser.close()


def test_posthoc_choices(server):  # noqa: F811
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
        page.wait_for_selector("#opt-cmpto")
        page.select_option("#opt-cmpto", "control")
        page.wait_for_function("document.querySelector('#results').textContent.includes('Dunnett')", timeout=10000)
        assert page.input_value("#opt-posthoc") == "dunnett"
        page.select_option("#opt-posthoc", "holm")
        page.wait_for_function("document.querySelector('#results').textContent.includes('Holm-Šídák')", timeout=10000)
        assert "Holm-Šídák" in page.eval_on_selector("#results details.report", "e => e.textContent")
        page.select_option("#opt-cmpto", "all")
        page.wait_for_function("document.querySelector('#results').textContent.includes('Holm')", timeout=10000)
        assert errors == [], errors
        browser.close()


def test_twoway_comparison_choices(server):  # noqa: F811
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
        page.wait_for_selector("#opt-twcmp")
        for v, word in (("within_cols", "rows within each column"), ("col_means", "column means"), ("row_means", "row means"), ("within_rows", "columns within each row")):
            page.select_option("#opt-twcmp", v)
            page.wait_for_function(f"document.querySelector('#results').textContent.includes({word!r})", timeout=10000)
            assert page.query_selector("#plot .main-svg") is not None
        assert errors == [], errors
        browser.close()


def test_survival_risk_table_and_tests(server):  # noqa: F811
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
        page.click("#sheet-list li:has-text('survival')")
        page.wait_for_function("document.querySelector('#results').textContent.includes('Gehan-Breslow-Wilcoxon')", timeout=10000)
        page.click("#btn-format"); page.check('#graph-format [data-g="riskTable"]')
        page.wait_for_timeout(500)
        assert "Number at risk" in page.inner_text("#plot")
        assert errors == [], errors
        browser.close()


def test_residual_plot_and_runs(server):  # noqa: F811
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
        page.click("#sheet-list li:has-text('dose-respon')")
        page.wait_for_function("document.querySelector('#results').textContent.includes('Runs test')", timeout=10000)
        page.click("#btn-format"); page.select_option('#graph-format [data-g="xyPlot"]', "resid")
        page.wait_for_timeout(500)
        assert "Residual" in page.inner_text("#plot")
        assert errors == [], errors
        browser.close()


def test_new_transforms(server):  # noqa: F811
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
        cell = lambda r, c: page.input_value(f'#grid input[data-r="{r}"][data-c="{c}"]')
        for op, check in (("subfirst", lambda: cell(0, 0) == "0" and cell(0, 1) == "0"),
                          ("fraction", lambda: abs(sum(float(cell(r, 0)) for r in range(8)) - 100) < 1e-6),
                          ("subcol", lambda: page.eval_on_selector_all("#grid thead th", "e => e.length") >= 2 and abs(float(cell(0, 0)) - 1.9) < 1e-9),
                          ("zscore", lambda: abs(sum(float(cell(r, 0)) for r in range(8))) < 1e-6),
                          ("transpose", lambda: cell(1, 0) == "6.1"),
                          ("rowstats", lambda: cell(0, 0) == "Row 1" and cell(0, 3) == "2" and abs(float(cell(0, 1)) - 5.15) < 1e-9)):
            page.click("#sheet-list li:has-text('Example: two groups')")
            page.wait_for_timeout(300)
            page.click("#btn-transform")
            page.check(f'#tf-body input[value="{op}"]')
            page.click("#tf-apply")
            page.wait_for_timeout(500)
            assert check(), op
        assert errors == [], errors
        browser.close()


def test_sort_and_fill_series(server):  # noqa: F811
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
        page.click("#sheet-list li:has-text('Example: two groups')")
        page.wait_for_timeout(300)
        cell = lambda r, c: page.input_value(f'#grid input[data-r="{r}"][data-c="{c}"]')
        page.click('#grid input[data-r="0"][data-c="0"]', button="right")
        page.click('#row-menu button[data-act="asc"]')
        page.wait_for_timeout(300)
        col = [float(cell(r, 0)) for r in range(8)]
        assert col == sorted(col)
        assert cell(0, 1) == "6.8"  # whole rows move: 3.8 was paired with 6.8
        page.click('#grid input[data-r="0"][data-c="1"]', button="right")
        page.fill("#fill-start", "100"); page.select_option("#fill-op", "mul"); page.fill("#fill-step", "0.5"); page.fill("#fill-to", "4")
        page.click('#row-menu button[data-act="fill"]')
        page.wait_for_timeout(300)
        assert [cell(r, 1) for r in range(4)] == ["100", "50", "25", "12.5"]
        page.keyboard.press("Control+z")
        page.wait_for_timeout(300)
        assert cell(0, 1) == "6.8"
        assert errors == [], errors
        browser.close()


def test_two_way_both_repeated(server):  # noqa: F811
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
        page.click("#sheet-list li:has-text('time course')")
        page.wait_for_selector('#options [data-opt="rmBoth"]')
        page.check('#options [data-opt="rmBoth"]')
        page.wait_for_function("document.querySelector('#results').textContent.includes('Both factors repeated')", timeout=10000)
        assert "both factors within subjects" in page.eval_on_selector("#results details.report", "e => e.textContent")
        assert errors == [], errors
        browser.close()


def test_error_direction_and_survival_modes(server):  # noqa: F811
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
        page.click("#sheet-list li:has-text('Example: two groups')")
        page.wait_for_timeout(500)
        page.click("#btn-format")
        page.select_option('#graph-format [data-g="style"]', "bars")
        page.select_option('#graph-format [data-g="errDir"]', "up")
        page.wait_for_timeout(400)
        sym = page.evaluate("document.getElementById('plot').data.filter(t => t.type === 'bar').map(t => t.error_y && t.error_y.symmetric)")
        assert sym and all(v is False for v in sym)
        page.click("#sheet-list li:has-text('Example: survival')")
        page.wait_for_timeout(600)
        page.select_option('#graph-format [data-g="survMode"]', "death")
        page.check('#graph-format [data-g="medianLines"]')
        page.wait_for_timeout(400)
        assert "Percent death" in page.inner_text("#plot")
        assert page.evaluate("document.getElementById('plot').layout.shapes.length") >= 2
        assert errors == [], errors
        browser.close()


def test_help_panel(server):  # noqa: F811
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:
            pytest.skip(f"no browser: {e}")
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(server)
        page.wait_for_selector("#sheet-list li")
        page.click("#btn-help")
        assert page.is_visible("#help-backdrop") and "Undo / redo" in page.inner_text("#help-backdrop")
        page.keyboard.press("Escape")
        assert not page.is_visible("#help-backdrop")
        page.evaluate("document.activeElement && document.activeElement.blur()")
        page.keyboard.press("?")
        assert page.is_visible("#help-backdrop")
        browser.close()


def test_large_table_renders_in_chunks(server):  # noqa: F811
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
        page.click("#sheet-list li:has-text('Example: two groups')")
        page.wait_for_timeout(300)
        tsv = "\n".join(f"{i % 7 + 1}\t{i % 5 + 2}" for i in range(2000))
        page.evaluate("""(tsv) => { const el = document.querySelector('#grid input[data-r="0"][data-c="0"]'); el.focus();
          const dt = new DataTransfer(); dt.setData('text/plain', tsv); el.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true})); }""", tsv)
        page.wait_for_function("document.querySelector('#results').textContent.includes('n')", timeout=20000)
        page.wait_for_timeout(500)
        assert "Showing 400 of" in page.inner_text("#grid")
        page.eval_on_selector(".grid-wrap", "w => { w.scrollTop = w.scrollHeight; w.dispatchEvent(new Event('scroll')); }")
        page.wait_for_timeout(300)
        assert page.evaluate("document.querySelectorAll('#grid tbody tr').length") > 790
        assert "2,000" in page.inner_text("#results") or "2000" in page.inner_text("#results")
        assert errors == [], errors
        browser.close()


def test_undo_covers_format_and_options(server):  # noqa: F811
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
        page.click("#sheet-list li:has-text('Example: two groups')")
        page.wait_for_timeout(400)
        if page.is_hidden("#graph-format"):
            page.click("#btn-format")
        orig = page.input_value('#graph-format [data-g="style"]')  # the server is shared, so earlier tests may have changed it
        new = "box" if orig != "box" else "violin"
        page.select_option('#graph-format [data-g="style"]', new)
        page.wait_for_timeout(1600)  # let the undo group close
        page.click('#options button[data-set="mode:describe"]')
        page.wait_for_timeout(500)
        assert "Describe" in page.inner_text("#options .seg button.on")
        page.click("#btn-undo")
        page.wait_for_timeout(400)
        assert "Compare" in page.inner_text("#options .seg button.on")
        page.click("#btn-undo")
        page.wait_for_timeout(400)
        assert page.input_value('#graph-format [data-g="style"]') == orig
        page.click("#btn-redo")
        page.wait_for_timeout(400)
        assert page.input_value('#graph-format [data-g="style"]') == new
        assert errors == [], errors
        browser.close()
