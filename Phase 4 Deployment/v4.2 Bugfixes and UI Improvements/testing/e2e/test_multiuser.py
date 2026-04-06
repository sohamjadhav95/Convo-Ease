import pytest

from .conftest import create_group, join_group, login, register_account


@pytest.mark.e2e
def test_three_users_receive_messages_without_reload(browser, live_server):
    admin_page = browser.new_page()
    admin_page.goto(live_server)
    register_account(admin_page, "Admin User", "admin1", "secret123")
    login(admin_page, "admin1", "secret123")
    group_id = create_group(admin_page, "Realtime Group", "roompass", "Be respectful.")

    member_one = browser.new_page()
    member_one.goto(live_server)
    register_account(member_one, "Member One", "member1", "secret123")
    login(member_one, "member1", "secret123")
    join_group(member_one, group_id, "roompass")

    member_two = browser.new_page()
    member_two.goto(live_server)
    register_account(member_two, "Member Two", "member2", "secret123")
    login(member_two, "member2", "secret123")
    join_group(member_two, group_id, "roompass")

    member_one.locator("#message-input").fill("Live update from member one")
    member_one.locator("#btn-send").click()

    admin_page.get_by_text("Live update from member one").wait_for()
    member_two.get_by_text("Live update from member one").wait_for()
