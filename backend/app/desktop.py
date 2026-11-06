"""Desktop entry point: runs the local server and shows the app in its own window.

Uses pywebview (Edge WebView2 on Windows, WebKit on macOS). If a window can't be
created, it falls back to opening the user's web browser, like run.bat does.
"""
from __future__ import annotations

import logging
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser


def _free_port(preferred: int) -> int:
    for port in (preferred, 0):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue
    return preferred


def _wait_ready(url: str, timeout: float = 30) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(url + "/api/health", timeout=1) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.15)
    return False


def _setup_logging():
    """In the packaged app there is no console window, so keep a log in the app folder."""
    from .storage import home
    log_dir = home() / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(filename=log_dir / "app.log", level=logging.INFO,
                            format="%(asctime)s %(levelname)s %(message)s")
        if getattr(sys, "frozen", False) and sys.stdout is None:
            f = open(log_dir / "output.log", "a", encoding="utf-8", buffering=1)
            sys.stdout = sys.stderr = f
    except OSError:
        pass


def main():
    _setup_logging()
    import uvicorn

    from .main import app

    port = _free_port(int(os.environ.get("EH_PORT", "8765")))
    url = f"http://127.0.0.1:{port}"
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", log_config=None)
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    if not _wait_ready(url):
        logging.error("Server did not start")
        raise SystemExit("Erwin's Hypothesis couldn't start its engine.")
    logging.info("Server running at %s", url)

    if os.environ.get("EH_NO_WINDOW") != "1":
        try:
            import webview  # pywebview
            webview.create_window("Erwin's Hypothesis", url, width=1440, height=920, min_size=(980, 640),
                                  text_select=True)
            webview.start()
            server.should_exit = True
            return
        except Exception as e:  # no webview runtime available: use the browser instead
            logging.warning("Window mode unavailable (%s); opening the browser", e)

    webbrowser.open(url)
    print(f"Erwin's Hypothesis is running at {url}. Close this window to quit.")
    try:
        while t.is_alive():
            t.join(0.5)
    except KeyboardInterrupt:
        server.should_exit = True


if __name__ == "__main__":
    main()
