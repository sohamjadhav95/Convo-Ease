import os
import socket
import sys
import threading
from pathlib import Path

import pytest
from werkzeug.serving import make_server


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testing.shared.harness import configure_test_environment, install_test_ai


pytestmark = pytest.mark.e2e


@pytest.fixture
def live_server(monkeypatch, tmp_path):
    install_test_ai(monkeypatch)
    configure_test_environment(tmp_path / "runtime", monkeypatch)

    from main import create_app

    app = create_app({"TESTING": True, "RATE_LIMITS_ENABLED": False})

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        host, port = sock.getsockname()

    server = make_server(host, port, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.fixture
def browser():
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as p:
        # Set PLAYWRIGHT_CHROMIUM_PATH to use a preinstalled Chromium.
        executable = os.getenv("PLAYWRIGHT_CHROMIUM_PATH") or None
        browser = p.chromium.launch(executable_path=executable)
        yield browser
        browser.close()


@pytest.fixture
def new_page(browser):
    contexts = []

    def _new_page(**options):
        context = browser.new_context(viewport=options.pop("viewport", {"width": 1366, "height": 860}), **options)
        contexts.append(context)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.js_errors = errors
        return page

    yield _new_page
    for context in contexts:
        context.close()
