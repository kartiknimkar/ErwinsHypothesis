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
