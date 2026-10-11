def test_pass_message_is_saved_and_visible(user, create_group, join_group):
    group_id = create_group()
    join_group(group_id, username="member1")
    member = user("member1")

    send_response = member.post(f"/api/groups/{group_id}/messages", json={"message": "Hello team"})
    visible_response = user("admin").get(f"/api/groups/{group_id}/messages")

    assert send_response.status_code == 200
    assert send_response.get_json()["status"] == "PASS"
    messages = visible_response.get_json()["messages"]
    assert [message["message"] for message in messages] == ["Hello team"]
    assert messages[0]["username"] == "member1"
    assert "group_rules" not in messages[0]


def test_sender_comes_from_session_not_request_body(user, create_group, join_group):
    group_id = create_group(admin_username="admin1")
    join_group(group_id, username="member1")

    user("member1").post(f"/api/groups/{group_id}/messages", json={"username": "admin1", "message": "Spoof attempt"})
    messages = user("admin1").get(f"/api/groups/{group_id}/messages").get_json()["messages"]

    assert messages[0]["username"] == "member1"


def test_flagged_message_is_hidden_from_visible_feed(user, create_group, join_group):
    group_id = create_group(rules="Be respectful. No insults.")
    join_group(group_id, username="member1")
    member = user("member1")

    flagged_response = member.post(f"/api/groups/{group_id}/messages", json={"message": "You are bad"})
    visible_response = user("admin").get(f"/api/groups/{group_id}/messages")
    admin_flagged_response = user("admin").get(f"/api/groups/{group_id}/messages/flagged")

    assert flagged_response.status_code == 200
    assert flagged_response.get_json()["status"] == "FLAGGED"
    assert visible_response.get_json()["messages"] == []
    assert len(admin_flagged_response.get_json()["flagged"]) == 1


def test_sender_can_see_their_own_held_message(user, create_group, join_group):
    group_id = create_group(rules="No insults.")
    join_group(group_id, username="member1")
    join_group(group_id, username="member2")
    user("member1").post(f"/api/groups/{group_id}/messages", json={"message": "you are bad"})

    own = user("member1").get(f"/api/groups/{group_id}/messages", query_string={"include_own_flagged": 1})
    other = user("member2").get(f"/api/groups/{group_id}/messages", query_string={"include_own_flagged": 1})

    assert [m["status"] for m in own.get_json()["messages"]] == ["FLAGGED"]
    assert other.get_json()["messages"] == []


def test_only_admin_sees_flagged_list(user, create_group, join_group):
    group_id = create_group(admin_username="admin1")
    join_group(group_id, username="member1")

    assert user("member1").get(f"/api/groups/{group_id}/messages/flagged").status_code == 403


def test_messages_after_cursor_and_limit(user, create_group):
    group_id = create_group(admin_username="admin1", rules="")
    admin = user("admin1")
    for index in range(5):
        admin.post(f"/api/groups/{group_id}/messages", json={"message": f"Message {index}"})

    latest_two = admin.get(f"/api/groups/{group_id}/messages", query_string={"limit": 2}).get_json()["messages"]
    after = admin.get(
        f"/api/groups/{group_id}/messages", query_string={"after": latest_two[0]["seq"]}
    ).get_json()["messages"]

    assert [m["message"] for m in latest_two] == ["Message 3", "Message 4"]
    assert [m["message"] for m in after] == ["Message 4"]


def test_message_length_is_limited(user, create_group):
    group_id = create_group(admin_username="admin1")
    response = user("admin1").post(f"/api/groups/{group_id}/messages", json={"message": "x" * 4001})

    assert response.status_code == 400


def test_only_sender_can_delete_message(user, create_group, join_group):
    group_id = create_group(admin_username="admin1")
    join_group(group_id, username="member1")
    message_id = user("member1").post(
        f"/api/groups/{group_id}/messages", json={"message": "Hello"}
    ).get_json()["message_id"]

    assert user("admin1").delete(f"/api/groups/{group_id}/messages/{message_id}").status_code == 403
    assert user("member1").delete(f"/api/groups/{group_id}/messages/{message_id}").status_code == 200
    messages = user("admin1").get(f"/api/groups/{group_id}/messages").get_json()["messages"]
    assert messages[0]["status"] == "DELETED"
    assert messages[0]["message"] == "[deleted]"


def test_rule_update_affects_next_message_not_previous_ones(user, create_group, join_group):
    group_id = create_group(admin_username="admin1", rules="Be respectful.")
    join_group(group_id, username="member1")
    admin, member = user("admin1"), user("member1")

    first = member.post(f"/api/groups/{group_id}/messages", json={"message": "homework answer thread"})
    update = admin.put(
        f"/api/groups/{group_id}/rules",
        json={"rules": "No homework sharing.", "moderation_sensitivity": "Strict"},
    )
    second = member.post(f"/api/groups/{group_id}/messages", json={"message": "homework answer thread"})
    visible = admin.get(f"/api/groups/{group_id}/messages")
    flagged = admin.get(f"/api/groups/{group_id}/messages/flagged")

    assert first.get_json()["status"] == "PASS"
    assert update.status_code == 200
    assert second.get_json()["status"] == "FLAGGED"
    assert len(visible.get_json()["messages"]) == 1
    assert len(flagged.get_json()["flagged"]) == 1


def test_flagged_message_owner_can_appeal_and_admin_can_approve(user, create_group, join_group):
    group_id = create_group(admin_username="admin1", rules="No insults.")
    join_group(group_id, username="member1")
    admin, member = user("admin1"), user("member1")

    message_id = member.post(f"/api/groups/{group_id}/messages", json={"message": "bad quote"}).get_json()["message_id"]

    appeal_response = member.post(
        f"/api/groups/{group_id}/messages/{message_id}/appeal",
        json={"appeal_text": "This was a movie quote with context."},
    )
    member_review = member.post(
        f"/api/groups/{group_id}/messages/{message_id}/appeal/review",
        json={"decision": "approve"},
    )
    review_response = admin.post(
        f"/api/groups/{group_id}/messages/{message_id}/appeal/review",
        json={"decision": "approve", "admin_note": "Context accepted."},
    )
    visible = admin.get(f"/api/groups/{group_id}/messages")

    assert appeal_response.status_code == 200
    assert appeal_response.get_json()["appeal_status"] == "PENDING_ADMIN"
    assert member_review.status_code == 403
    assert review_response.status_code == 200
    assert review_response.get_json()["final_status"] == "PASS"
    assert len(visible.get_json()["messages"]) == 1


def test_only_message_owner_can_appeal(user, create_group, join_group):
    group_id = create_group(admin_username="admin1", rules="No insults.")
    join_group(group_id, username="member1")
    join_group(group_id, username="member2")
    message_id = user("member1").post(
        f"/api/groups/{group_id}/messages", json={"message": "bad phrase"}
    ).get_json()["message_id"]

    response = user("member2").post(
        f"/api/groups/{group_id}/messages/{message_id}/appeal",
        json={"appeal_text": "Let me appeal someone else's post."},
    )

    assert response.status_code == 403
    assert response.get_json()["message"] == "You can only appeal your own message."


def test_group_summary_returns_bullets(user, create_group, join_group):
    group_id = create_group()
    join_group(group_id, username="member1")
    user("member1").post(f"/api/groups/{group_id}/messages", json={"message": "Project update one"})
    user("admin").post(f"/api/groups/{group_id}/messages", json={"message": "Project update two"})

    response = user("member1").get(f"/api/groups/{group_id}/summary", query_string={"limit": 10})

    assert response.status_code == 200
    summary = response.get_json()["summary"]
    assert summary["headline"].startswith("Catch-up")
    assert len(summary["bullets"]) >= 3


def test_rate_limit_blocks_message_floods(app, user, create_group):
    app.config["RATE_LIMITS_ENABLED"] = True
    group_id = create_group(admin_username="admin1", rules="")
    admin = user("admin1")

    statuses = [
        admin.post(f"/api/groups/{group_id}/messages", json={"message": f"msg {i}"}).status_code
        for i in range(31)
    ]

    assert statuses[:30] == [200] * 30
    assert statuses[30] == 429
