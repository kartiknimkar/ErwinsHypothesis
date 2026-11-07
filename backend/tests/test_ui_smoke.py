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
            # open the Format panel once per type and change a setting
            page.click("#btn-format"); page.wait_for_timeout(100); page.click("#btn-format")
        assert errors == [], errors
        browser.close()
