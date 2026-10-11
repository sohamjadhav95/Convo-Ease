def test_report_counts_pass_flagged_and_media(user, create_group, join_group, media_payloads):
    group_id = create_group(admin_username="admin1", rules="No insults.")
    join_group(group_id, username="member1")
    member = user("member1")
    member.post(f"/api/groups/{group_id}/messages", json={"message": "hello"})
    member.post(f"/api/groups/{group_id}/messages", json={"message": "bad phrase"})
    member.post(f"/api/groups/{group_id}/images", json={"image_data": media_payloads["good_image"], "mime_type": "image/png"})
    member.post(f"/api/groups/{group_id}/audio", json={"audio_data": media_payloads["good_audio"], "mime_type": "audio/wav"})
    deleted_id = member.post(f"/api/groups/{group_id}/messages", json={"message": "oops"}).get_json()["message_id"]
    member.delete(f"/api/groups/{group_id}/messages/{deleted_id}")

    response = user("admin1").get(f"/api/groups/{group_id}/report")

    assert response.status_code == 200
    report = response.get_json()["report"]
    # Deleted messages are not counted as passed or flagged.
    assert report["total_messages"] == 4
    assert report["pass_count"] == 3
    assert report["flagged_count"] == 1
    assert report["image_count"] == 1
    assert report["audio_count"] == 1
    assert sum(point["flagged"] for point in report["trend_points"]) == 1
    member_row = next(row for row in report["member_activity"] if row["username"] == "member1")
    assert member_row["flagged"] == 1


def test_report_is_admin_only(user, create_group, join_group):
    group_id = create_group(admin_username="admin1")
    join_group(group_id, username="member1")

    assert user("member1").get(f"/api/groups/{group_id}/report").status_code == 403


def test_rule_suggestions_return_fallback_when_rules_are_empty(user):
    response = user("admin").post("/api/rules/suggest", json={"rules": "", "group_name": "Study Group"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["suggestions"]
    assert "Be respectful" in payload["revised_rules"]


def test_rule_suggestions_use_mocked_ai_when_rules_exist(user):
    response = user("admin").post(
        "/api/rules/suggest",
        json={"rules": "Be respectful.", "group_name": "Study Group"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert "No insults or harassment." in payload["revised_rules"]
    assert len(payload["suggestions"]) >= 2


def test_health_endpoint(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.get_json()["database"] == "ok"
