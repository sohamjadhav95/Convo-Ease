import json

def test_report_counts_pass_flagged_and_media(client, create_group, join_group, media_payloads):
    group_id = create_group(admin_username="admin1", rules="No insults.")
    join_group(group_id, username="member1")
    client.post(f"/api/groups/{group_id}/messages", json={"username": "member1", "message": "hello"})
    client.post(f"/api/groups/{group_id}/messages", json={"username": "member1", "message": "bad phrase"})
    client.post(
        f"/api/groups/{group_id}/images",
        json={"username": "member1", "image_data": media_payloads["good_image"], "mime_type": "image/png"},
    )
    client.post(
        f"/api/groups/{group_id}/audio",
        json={"username": "member1", "audio_data": media_payloads["good_audio"], "mime_type": "audio/wav"},
    )

    response = client.get(f"/api/groups/{group_id}/report")

    assert response.status_code == 200
    report = response.get_json()["report"]
    assert report["total_messages"] == 4
    assert report["pass_count"] == 3
    assert report["flagged_count"] == 1
    assert report["image_count"] == 1
    assert report["audio_count"] == 1


def test_rule_suggestions_return_fallback_when_rules_are_empty(client):
    response = client.post("/api/rules/suggest", json={"rules": "", "group_name": "Study Group"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["suggestions"]
    assert "Be respectful" in payload["revised_rules"]


def test_rule_suggestions_use_mocked_ai_when_rules_exist(client):
    response = client.post(
        "/api/rules/suggest",
        json={"rules": "Be respectful.", "group_name": "Study Group"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert "No insults or harassment." in payload["revised_rules"]
    assert len(payload["suggestions"]) >= 2


def test_settings_hide_internal_provider_details_and_emit_structured_logs(client, sandbox_paths):
    response = client.get("/api/settings")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert "system" in payload["settings"]
    assert "base_url" not in payload["settings"]
    assert "text" not in payload["settings"]
    assert "image" not in payload["settings"]
    assert "audio" not in payload["settings"]

    log_file = sandbox_paths["logs_dir"] / "app.jsonl"
    assert log_file.exists()

    entries = [
        json.loads(line)
        for line in log_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(entry["category"] == "api" and entry["action"] == "request_completed" for entry in entries)
    assert any(entry["category"] == "settings" and entry["action"] == "read" for entry in entries)
    assert all("request_id" in entry for entry in entries)
