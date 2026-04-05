def test_create_group_adds_admin_membership(client, create_group):
    group_id = create_group(admin_username="admin1", group_name="Moderation Lab")

    members_response = client.get(f"/api/groups/{group_id}/members")
    groups_response = client.get("/api/groups", query_string={"username": "admin1"})

    assert members_response.status_code == 200
    assert members_response.get_json()["members"] == ["admin1"]
    assert groups_response.get_json()["groups"][0]["group_id"] == group_id


def test_join_group_with_correct_password(client, create_group, join_group):
    group_id = create_group()
    response = join_group(group_id, username="member1")

    assert response.status_code == 200
    assert response.get_json()["message"] == "Joined successfully."


def test_join_group_with_wrong_password_fails(client, create_group, join_group):
    group_id = create_group(password="topsecret")
    response = join_group(group_id, username="member1", password="wrong")

    assert response.status_code == 400
    assert response.get_json()["success"] is False
    assert "Incorrect group password" in response.get_json()["message"]


def test_group_details_hide_password_and_normalize_sensitivity(client, create_group):
    group_id = create_group(moderation_sensitivity="strict")
    response = client.get(f"/api/groups/{group_id}")

    assert response.status_code == 200
    group = response.get_json()["group"]
    assert "password" not in group
    assert group["moderation_sensitivity"] == "Strict"


def test_only_admin_can_update_rules(client, create_group, join_group):
    group_id = create_group(admin_username="admin1")
    join_group(group_id, username="member1")

    response = client.put(
        f"/api/groups/{group_id}/rules",
        json={"rules": "No memes.", "username": "member1", "moderation_sensitivity": "Relaxed"},
    )

    assert response.status_code == 403
    assert response.get_json()["message"] == "Only admin can update rules."
