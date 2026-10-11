"""Page helpers for the Material UI browser tests."""

import base64

from testing.shared.harness import PNG_HEADER


def register(page, base_url, full_name, username, password="secret-pass"):
    page.goto(base_url)
    page.get_by_role("button", name="Create account").first.click()
    page.get_by_label("Full name").fill(full_name)
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password", exact=True).fill(password)
    page.locator("form button[type=submit]").click()
    page.locator(".shell").wait_for()


def sign_in(page, base_url, username, password="secret-pass"):
    page.goto(base_url)
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password", exact=True).fill(password)
    page.locator("form button[type=submit]").click()


def open_new_group(page):
    # Desktop has a FAB in the navigation rail; phones have one above the list.
    page.locator("button[aria-label='Create or join a group']:visible, .list-fab:visible").first.click()


def create_group(page, name, rules="Be respectful. No insults.", password=""):
    open_new_group(page)
    dialog = page.locator("dialog")
    dialog.get_by_label("Group name").fill(name)
    dialog.get_by_label("Group rules").fill(rules)
    if password:
        dialog.get_by_label("Password (optional)").fill(password)
    dialog.get_by_role("button", name="Create group", exact=True).click()
    group_id = page.locator("dialog .id-box .mono").inner_text().strip()
    page.locator("dialog").get_by_role("button", name="Done").click()
    return group_id


def join_group(page, group_id, password=""):
    open_new_group(page)
    dialog = page.locator("dialog")
    dialog.get_by_role("button", name="Join", exact=True).click()
    dialog.get_by_label("Group ID").fill(group_id)
    if password:
        dialog.get_by_label("Password (if the group has one)").fill(password)
    dialog.get_by_role("button", name="Join group", exact=True).click()
    page.locator(".composer textarea").wait_for()


def send(page, text):
    box = page.get_by_label("Message", exact=True)
    box.fill(text)
    box.press("Enter")


def image_file(tmp_path, marker="goodimage"):
    # A real 1x1 PNG followed by a marker the fake AI looks for.
    pixel = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    path = tmp_path / f"{marker}.png"
    path.write_bytes(pixel + marker.encode())
    assert pixel.startswith(PNG_HEADER)
    return path
