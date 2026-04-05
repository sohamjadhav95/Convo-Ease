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

    app = create_app()
    app.config.update(TESTING=True)

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        host, port = sock.getsockname()

    server = make_server(host, port, app)
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
        browser = p.chromium.launch()
        yield browser
        browser.close()


def register_account(page, full_name, username, password):
    page.get_by_role("button", name="Create Account").click()
    page.locator("#reg-fullname").fill(full_name)
    page.locator("#reg-username").fill(username)
    page.locator("#reg-password").fill(password)
    page.locator("#btn-register").click()
    page.get_by_text("Account created! Switch to Sign In.").wait_for()


def login(page, username, password):
    page.get_by_role("button", name="Sign In").click()
    page.locator("#login-username").fill(username)
    page.locator("#login-password").fill(password)
    page.locator("#btn-login").click()
    page.locator("#btn-new-chat").wait_for()


def create_group(page, group_name, password, rules):
    page.locator("#btn-new-chat").click()
    page.locator("#create-name").fill(group_name)
    page.locator("#create-password").fill(password)
    page.locator("#create-rules").fill(rules)
    with page.expect_response(lambda resp: resp.url.endswith("/api/groups") and resp.request.method == "POST") as resp_info:
        page.get_by_role("button", name="Create Group").click()
    return resp_info.value.json()["group_id"]


def join_group(page, group_id, password):
    page.locator("#btn-new-chat").click()
    page.get_by_role("button", name="Join Group").click()
    page.locator("#join-id").fill(group_id)
    page.locator("#join-password").fill(password)
    page.get_by_role("button", name="Join Group").nth(1).click()
