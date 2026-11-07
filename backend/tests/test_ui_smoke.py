"""Opens every example analysis in a real (headless) browser and checks each one renders
results and a graph without JavaScript errors. Skipped when Playwright isn't installed."""
import socket
import threading
import time

import pytest

sync_api = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    import os
    os.environ["EH_HOME"] = str(tmp_path_factory.mktemp("home"))
    import uvicorn
    from app.main import app
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=srv.run, daemon=True); t.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    os.environ.pop("EH_HOME", None)


def test_every_example_renders(server):
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:  # no browser binaries on this machine
            pytest.skip(f"no browser: {e}")
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(server)
        page.wait_for_selector("#sheet-list li")
        names = page.eval_on_selector_all("#sheet-list li .t", "els => els.map(e => e.textContent)")
        assert len(names) >= 14
        for i, name in enumerate(names):
            page.click(f"#sheet-list li:nth-child({i + 1})")
            page.wait_for_function("document.querySelector('#results').textContent.trim().length > 0", timeout=15000)
            page.wait_for_timeout(300)
            summary = page.inner_text("#results")
            assert "Not enough to analyze" not in summary, f"{name}: {summary[:200]}"
            assert page.query_selector("#plot .main-svg") is not None, f"{name}: no graph"
            if "figure layout" not in name:
                rep = page.query_selector("#rep-results")
                assert rep is not None, f"{name}: no paper text"
                text = page.eval_on_selector("#results details.report", "e => e.textContent")
                for bad in ("undefined", "NaN", "null", "[object"):
                    assert bad not in text, f"{name}: '{bad}' in paper text: {text[:300]}"
            # open the Format panel once per type and change a setting
            page.click("#btn-format"); page.wait_for_timeout(100); page.click("#btn-format")
        assert errors == [], errors
        browser.close()


def test_guide_every_recommendation_creates_working_analysis(server):
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

        def walk(path):
            page.click("#btn-guide")
            for i in path:
                page.click(f'#guide-body [data-gi="{i}"]')
            if page.query_selector("#guide-create"):
                title = page.inner_text(".guide-rec b")
                page.click("#guide-create")
                assert page.input_value("#sheet-title") == title
                if page.is_visible("#btn-example"):
                    page.click("#btn-example")
                    try:
                        page.wait_for_function("(() => { const t = document.querySelector('#results').textContent;"
                                               " return t.trim().length > 0 && !t.includes('Not enough to analyze'); })()", timeout=15000)
                    except Exception:
                        raise AssertionError(f"{title}: {page.inner_text('#results')[:200]}")
                return 1
            n = len(page.query_selector_all("#guide-body [data-gi]"))
            page.click("#guide-close")
            return sum(walk(path + [i]) for i in range(n))

        leaves = walk([])
        assert leaves >= 20
        assert errors == [], errors
        browser.close()


def test_grid_block_selection_copy_delete_rows(server):
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:
            pytest.skip(f"no browser: {e}")
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        ctx.grant_permissions(["clipboard-read", "clipboard-write"])
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(server)
        page.wait_for_selector("#sheet-list li")
        page.click('#sheet-list li:has-text("Example: two groups")')
        page.wait_for_timeout(800)
        cell = lambda r, c: f'input[data-r="{r}"][data-c="{c}"]'  # noqa: E731
        col0 = lambda n: [page.input_value(cell(r, 0)) for r in range(n)]  # noqa: E731
        a = page.locator(cell(0, 0)).bounding_box(); z = page.locator(cell(2, 1)).bounding_box()
        page.mouse.move(a["x"] + 10, a["y"] + 5); page.mouse.down(); page.mouse.move(z["x"] + 10, z["y"] + 5, steps=5); page.mouse.up()
        assert page.locator("input.cell.sel").count() == 6
        page.keyboard.press("Control+c"); page.wait_for_timeout(150)
        assert page.evaluate("navigator.clipboard.readText()") == "4.2\t6.1\n5.1\t7.3\n3.8\t6.8"
        page.keyboard.press("Delete"); page.wait_for_timeout(200)
        assert col0(4) == ["", "", "", "4.9"]
        page.click("#btn-undo"); page.wait_for_timeout(200)
        assert col0(4) == ["4.2", "5.1", "3.8", "4.9"]
        page.click('[data-row="1"]', button="right"); page.click('#row-menu button[data-act="above"]'); page.wait_for_timeout(200)
        assert col0(3) == ["4.2", "", "5.1"]
        page.click('[data-row="1"]', button="right"); page.click('#row-menu button[data-act="delete"]'); page.wait_for_timeout(200)
        assert col0(3) == ["4.2", "5.1", "3.8"]
        assert errors == [], errors
        browser.close()
