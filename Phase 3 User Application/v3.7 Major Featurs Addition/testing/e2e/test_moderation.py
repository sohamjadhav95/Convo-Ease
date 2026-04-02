import pytest

from .conftest import create_group, join_group, login, register_account


@pytest.mark.e2e
def test_member_sees_block_banner_and_admin_sees_flagged_panel(browser, live_server):
    admin_page = browser.new_page()
    admin_page.goto(live_server)
    register_account(admin_page, "Admin User", "admin1", "secret123")
    login(admin_page, "admin1", "secret123")
    group_id = create_group(admin_page, "Moderation Group", "roompass", "Be respectful. No insults.")

    member_page = browser.new_page()
    member_page.goto(live_server)
    register_account(member_page, "Member User", "member1", "secret123")
    login(member_page, "member1", "secret123")
    join_group(member_page, group_id, "roompass")

    member_page.locator("#message-input").fill("bad insult")
    member_page.locator("#btn-send").click()
    member_page.get_by_text("blocked").wait_for()

    admin_page.locator("#btn-admin-panel").click()
    admin_page.get_by_role("button", name="Flagged").click()
    admin_page.get_by_text("bad insult").wait_for()
