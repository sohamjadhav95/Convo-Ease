def test_pass_message_is_saved_and_visible(client, create_group, join_group):
    group_id = create_group()
    join_group(group_id, username="member1")

    send_response = client.post(
        f"/api/groups/{group_id}/messages",
        json={"username": "member1", "message": "Hello team"},
    )
    visible_response = client.get(f"/api/groups/{group_id}/messages")

    assert send_response.status_code == 200
    assert send_response.get_json()["status"] == "PASS"
    assert [message["message"] for message in visible_response.get_json()["messages"]] == ["Hello team"]


def test_flagged_message_is_hidden_from_visible_feed(client, create_group, join_group):
    group_id = create_group(rules="Be respectful. No insults.")
    join_group(group_id, username="member1")

    flagged_response = client.post(
        f"/api/groups/{group_id}/messages",
        json={"username": "member1", "message": "You are bad"},
    )
    visible_response = client.get(f"/api/groups/{group_id}/messages")
    admin_flagged_response = client.get(f"/api/groups/{group_id}/messages/flagged")

    assert flagged_response.status_code == 200
    assert flagged_response.get_json()["status"] == "FLAGGED"
    assert visible_response.get_json()["messages"] == []
    assert len(admin_flagged_response.get_json()["flagged"]) == 1


def test_rule_update_affects_next_message_not_previous_ones(client, create_group, join_group):
    group_id = create_group(admin_username="admin1", rules="Be respectful.")
    join_group(group_id, username="member1")

    first = client.post(
        f"/api/groups/{group_id}/messages",
        json={"username": "member1", "message": "homework answer thread"},
    )
    update = client.put(
        f"/api/groups/{group_id}/rules",
        json={"rules": "No homework sharing.", "username": "admin1", "moderation_sensitivity": "Strict"},
    )
    second = client.post(
        f"/api/groups/{group_id}/messages",
        json={"username": "member1", "message": "homework answer thread"},
    )
    visible = client.get(f"/api/groups/{group_id}/messages")
    flagged = client.get(f"/api/groups/{group_id}/messages/flagged")

    assert first.get_json()["status"] == "PASS"
    assert update.status_code == 200
    assert second.get_json()["status"] == "FLAGGED"
    assert len(visible.get_json()["messages"]) == 1
    assert len(flagged.get_json()["flagged"]) == 1


def test_flagged_message_owner_can_appeal_and_admin_can_approve(client, create_group, join_group):
    group_id = create_group(admin_username="admin1", rules="No insults.")
    join_group(group_id, username="member1")

    flagged_response = client.post(
        f"/api/groups/{group_id}/messages",
        json={"username": "member1", "message": "bad quote"},
    )
    message_id = flagged_response.get_json()["message_id"]

    appeal_response = client.post(
        f"/api/groups/{group_id}/messages/{message_id}/appeal",
        json={"username": "member1", "appeal_text": "This was a movie quote with context."},
    )
    review_response = client.post(
        f"/api/groups/{group_id}/messages/{message_id}/appeal/review",
        json={"username": "admin1", "decision": "approve", "admin_note": "Context accepted."},
    )
    visible = client.get(f"/api/groups/{group_id}/messages")

    assert appeal_response.status_code == 200
    assert appeal_response.get_json()["appeal_status"] == "PENDING_ADMIN"
    assert review_response.status_code == 200
    assert review_response.get_json()["final_status"] == "PASS"
    assert len(visible.get_json()["messages"]) == 1


def test_only_message_owner_can_appeal(client, create_group, join_group):
    group_id = create_group(admin_username="admin1", rules="No insults.")
    join_group(group_id, username="member1")
    join_group(group_id, username="member2")
    flagged_response = client.post(
        f"/api/groups/{group_id}/messages",
        json={"username": "member1", "message": "bad phrase"},
    )
    message_id = flagged_response.get_json()["message_id"]

    response = client.post(
        f"/api/groups/{group_id}/messages/{message_id}/appeal",
        json={"username": "member2", "appeal_text": "Let me appeal someone else's post."},
    )

    assert response.status_code == 403
    assert response.get_json()["message"] == "You can only appeal your own message."


def test_group_summary_returns_bullets(client, create_group, join_group):
    group_id = create_group()
    join_group(group_id, username="member1")
    client.post(f"/api/groups/{group_id}/messages", json={"username": "member1", "message": "Project update one"})
    client.post(f"/api/groups/{group_id}/messages", json={"username": "admin", "message": "Project update two"})

    response = client.get(f"/api/groups/{group_id}/summary", query_string={"limit": 10})

    assert response.status_code == 200
    summary = response.get_json()["summary"]
    assert summary["headline"].startswith("Catch-up")
    assert len(summary["bullets"]) >= 3
