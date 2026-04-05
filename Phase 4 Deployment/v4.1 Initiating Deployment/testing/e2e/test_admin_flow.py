import pytest

from .conftest import create_group, login, register_account


@pytest.mark.e2e
def test_admin_can_create_group_and_block_flagged_message(browser, live_server):
    page = browser.new_page()
    page.goto(live_server)

    register_account(page, "Admin User", "admin1", "secret123")
    login(page, "admin1", "secret123")
    create_group(page, "Moderation Demo", "roompass", "Be respectful. No insults.")

    page.locator("#message-input").fill("Hello team")
    page.locator("#btn-send").click()
    page.get_by_text("Hello team").wait_for()

    page.locator("#message-input").fill("bad insult")
    page.locator("#btn-send").click()
    page.get_by_text("blocked").wait_for()

    page.locator("#btn-admin-panel").click()
    page.get_by_role("button", name="Flagged").click()
    page.get_by_text("bad insult").wait_for()
