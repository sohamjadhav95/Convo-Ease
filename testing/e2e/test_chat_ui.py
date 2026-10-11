from playwright.sync_api import expect

from ui_helpers import create_group, image_file, join_group, register, send


def test_member_message_is_delivered_to_admin(live_server, new_page):
    admin, member = new_page(), new_page()
    register(admin, live_server, "Alice Moreno", "alice")
    group_id = create_group(admin, "Weekend Hikers")

    register(member, live_server, "Bob Chen", "bob")
    join_group(member, group_id.lower())
    send(member, "Anyone up for a trek on Sunday?")
    expect(member.locator(".msg.mine .bubble")).to_have_text("Anyone up for a trek on Sunday?")

    admin.goto(f"{live_server}/#/chats/{group_id}")
    expect(admin.locator(".msg .bubble").last).to_have_text("Anyone up for a trek on Sunday?")
    expect(admin.locator(".msg .sender").last).to_contain_text("Bob Chen")
    assert admin.js_errors == [] and member.js_errors == []


def test_held_message_is_only_shown_to_its_sender_and_can_be_appealed(live_server, new_page):
    admin, member = new_page(), new_page()
    register(admin, live_server, "Alice Moreno", "alice")
    group_id = create_group(admin, "Study Group", rules="No insults.")
    register(member, live_server, "Bob Chen", "bob")
    join_group(member, group_id)

    send(member, "that answer was bad")
    held = member.locator(".held-card")
    expect(held).to_contain_text("held by moderation")
    expect(held).to_contain_text("that answer was bad")

    admin.goto(f"{live_server}/#/chats/{group_id}")
    expect(admin.get_by_text("Say hello")).to_be_visible()
    expect(admin.locator(".held-card")).to_have_count(0)

    held.get_by_role("button", name="Appeal").click()
    member.get_by_label("Why should this be allowed?").fill("It was a quote with context from the lecture.")
    member.get_by_role("button", name="Send appeal").click()
    expect(held).to_contain_text("waiting for the admin")

    admin.goto(f"{live_server}/#/moderation/{group_id}")
    review = admin.locator(".review-item")
    expect(review).to_contain_text("It was a quote with context")
    review.get_by_role("button", name="Allow").click()
    expect(admin.get_by_text("No appeals waiting")).to_be_visible()

    admin.goto(f"{live_server}/#/chats/{group_id}")
    expect(admin.locator(".msg .bubble").last).to_have_text("that answer was bad")


def test_image_upload_and_catch_up(live_server, new_page, tmp_path):
    page = new_page()
    register(page, live_server, "Alice Moreno", "alice")
    create_group(page, "Design Team")
    send(page, "Mockups are in Figma")

    page.get_by_role("button", name="Attach").click()
    with page.expect_file_chooser() as chooser:
        page.get_by_role("menuitem", name="Photo or image").click()
    chooser.value.set_files(str(image_file(tmp_path)))
    expect(page.locator(".media-card .thumb")).to_have_count(1)
    expect(page.locator(".media-card .ai-note")).to_contain_text("A calm study desk setup.")

    page.get_by_role("button", name="Catch up").first.click()
    expect(page.locator("dialog li").first).to_be_visible()


def test_mobile_layout_shows_one_pane_at_a_time(live_server, new_page):
    page = new_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    register(page, live_server, "Alice Moreno", "alice")
    group_id = create_group(page, "Pocket Group")

    expect(page.get_by_role("button", name="Back to chats")).to_be_visible()
    page.get_by_role("button", name="Back to chats").click()
    expect(page.locator(".bottom-nav")).to_be_visible()
    expect(page.get_by_role("link", name="Pocket Group")).to_be_visible()
    page.get_by_role("link", name="Pocket Group").click()
    expect(page).to_have_url(f"{live_server}/#/chats/{group_id}")
