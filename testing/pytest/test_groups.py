def test_create_group_adds_admin_membership(user, create_group):
    group_id = create_group(admin_username="admin1", group_name="Moderation Lab")
    admin = user("admin1")

    members_response = admin.get(f"/api/groups/{group_id}/members")
    groups_response = admin.get("/api/groups")

    assert members_response.status_code == 200
    assert members_response.get_json()["members"] == ["admin1"]
    assert members_response.get_json()["profiles"][0]["is_admin"] is True
    groups = groups_response.get_json()["groups"]
    assert groups[0]["group_id"] == group_id
    assert groups[0]["is_admin"] is True


def test_join_group_with_correct_password(create_group, join_group):
    group_id = create_group()
    response = join_group(group_id, username="member1")

    assert response.status_code == 200
    assert response.get_json()["message"] == "Joined successfully."


def test_join_group_without_password(create_group, join_group):
    # Regression: v4 (pandas 3) read empty passwords back as "nan" and rejected every join.
    group_id = create_group(password="")
    response = join_group(group_id, username="member1", password="")

    assert response.status_code == 200
    assert response.get_json()["success"] is True


def test_join_group_with_wrong_password_fails(create_group, join_group):
    group_id = create_group(password="topsecret")
    response = join_group(group_id, username="member1", password="wrong")

    assert response.status_code == 400
    assert response.get_json()["success"] is False
    assert "Incorrect group password" in response.get_json()["message"]


def test_join_group_id_is_case_insensitive(create_group, join_group):
    group_id = create_group()
    response = join_group(group_id.lower(), username="member1")

    assert response.status_code == 200


def test_group_details_hide_password_and_normalize_sensitivity(user, create_group):
    group_id = create_group(moderation_sensitivity="strict")
    response = user("admin").get(f"/api/groups/{group_id}")

    assert response.status_code == 200
    group = response.get_json()["group"]
    assert "password" not in group
    assert group["has_password"] is True
    assert group["moderation_sensitivity"] == "Strict"


def test_non_members_cannot_see_a_group(user, create_group):
    group_id = create_group()
    outsider = user("outsider")

    assert outsider.get(f"/api/groups/{group_id}").status_code == 403
    assert outsider.get(f"/api/groups/{group_id}/messages").status_code == 403
    assert outsider.get(f"/api/groups/{group_id}/members").status_code == 403
    assert outsider.post(f"/api/groups/{group_id}/messages", json={"message": "hi"}).status_code == 403


def test_only_admin_can_update_rules(user, create_group, join_group):
    group_id = create_group(admin_username="admin1")
    join_group(group_id, username="member1")

    # Claiming to be the admin in the body must not help.
    response = user("member1").put(
        f"/api/groups/{group_id}/rules",
        json={"rules": "No memes.", "username": "admin1", "moderation_sensitivity": "Relaxed"},
    )

    assert response.status_code == 403
    assert response.get_json()["message"] == "Only the group admin can do this."


def test_only_admin_can_rename_or_delete(user, create_group, join_group):
    group_id = create_group(admin_username="admin1")
    join_group(group_id, username="member1")
    member = user("member1")

    assert member.put(f"/api/groups/{group_id}/name", json={"group_name": "Mine now"}).status_code == 403
    assert member.delete(f"/api/groups/{group_id}").status_code == 403

    admin = user("admin1")
    assert admin.put(f"/api/groups/{group_id}/name", json={"group_name": "Renamed"}).status_code == 200
    assert admin.get(f"/api/groups/{group_id}").get_json()["group"]["group_name"] == "Renamed"
    assert admin.delete(f"/api/groups/{group_id}").status_code == 200
    assert admin.get(f"/api/groups/{group_id}").status_code == 404


def test_member_can_leave_but_admin_cannot(user, create_group, join_group):
    group_id = create_group(admin_username="admin1")
    join_group(group_id, username="member1")

    assert user("member1").post(f"/api/groups/{group_id}/leave").status_code == 200
    assert user("member1").get("/api/groups").get_json()["groups"] == []
    assert user("admin1").post(f"/api/groups/{group_id}/leave").status_code == 400


def test_unread_counts_track_what_each_member_has_seen(user, create_group, join_group):
    group_id = create_group(admin_username="admin1")
    join_group(group_id, username="member1")
    admin, member = user("admin1"), user("member1")

    admin.post(f"/api/groups/{group_id}/messages", json={"message": "Hello"})
    admin.post(f"/api/groups/{group_id}/messages", json={"message": "Agenda is up"})

    member_groups = member.get("/api/groups").get_json()["groups"]
    assert member_groups[0]["unread_count"] == 2
    assert member_groups[0]["last_message"] == "Agenda is up"
    assert admin.get("/api/groups").get_json()["groups"][0]["unread_count"] == 0

    member.get(f"/api/groups/{group_id}/messages")

    assert member.get("/api/groups").get_json()["groups"][0]["unread_count"] == 0
