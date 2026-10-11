from playwright.sync_api import expect

from ui_helpers import register, sign_in


def test_register_sign_out_and_sign_back_in(live_server, new_page):
    page = new_page()
    register(page, live_server, "Alice Moreno", "alice")

    expect(page.get_by_text("No groups yet")).to_be_visible()

    page.get_by_role("link", name="Settings").first.click()
    expect(page.get_by_text("@alice")).to_be_visible()
    page.get_by_role("button", name="Sign out").click()
    page.locator("dialog").get_by_role("button", name="Sign out").click()
    expect(page.get_by_text("Welcome back")).to_be_visible()

    sign_in(page, live_server, "alice")
    expect(page.locator(".shell")).to_be_visible()
    assert page.js_errors == []


def test_session_survives_reload(live_server, new_page):
    page = new_page()
    register(page, live_server, "Bob Chen", "bob")
    page.reload()
    expect(page.locator(".shell")).to_be_visible()


def test_wrong_password_shows_error(live_server, new_page):
    page = new_page()
    register(page, live_server, "Carol Singh", "carol")
    page.context.clear_cookies()

    sign_in(page, live_server, "carol", password="not-the-password")

    expect(page.get_by_role("alert")).to_contain_text("Invalid username or password")
