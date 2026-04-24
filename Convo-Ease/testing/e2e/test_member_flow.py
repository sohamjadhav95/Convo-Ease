import pytest

from .conftest import create_group, join_group, login, register_account


@pytest.mark.e2e
def test_member_can_join_group_and_send_visible_message(browser, live_server):
    admin_page = browser.new_page()
    admin_page.goto(live_server)
    register_account(admin_page, "Admin User", "admin1", "secret123")
    login(admin_page, "admin1", "secret123")
    group_id = create_group(admin_page, "Study Group", "roompass", "Be respectful.")

    member_page = browser.new_page()
    member_page.goto(live_server)
    register_account(member_page, "Member User", "member1", "secret123")
    login(member_page, "member1", "secret123")
    join_group(member_page, group_id, "roompass")

    member_page.locator("#message-input").fill("Ready for the session")
    member_page.locator("#btn-send").click()
    admin_page.get_by_text("Ready for the session").wait_for()
