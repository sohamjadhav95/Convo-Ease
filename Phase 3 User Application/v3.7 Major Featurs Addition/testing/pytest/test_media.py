def test_image_upload_pass_is_saved(client, create_group, join_group, sandbox_paths, media_payloads):
    group_id = create_group()
    join_group(group_id, username="member1")

    response = client.post(
        f"/api/groups/{group_id}/images",
        json={"username": "member1", "image_data": media_payloads["good_image"], "mime_type": "image/png"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "PASS"
    assert payload["media_url"].startswith("/media/image/")
    assert any(sandbox_paths["image_dir"].iterdir())


def test_flagged_image_is_not_visible_to_members(client, create_group, join_group, media_payloads):
    group_id = create_group(rules="No unsafe memes.")
    join_group(group_id, username="member1")

    response = client.post(
        f"/api/groups/{group_id}/images",
        json={"username": "member1", "image_data": media_payloads["bad_image"], "mime_type": "image/png"},
    )
    visible = client.get(f"/api/groups/{group_id}/messages")
    flagged = client.get(f"/api/groups/{group_id}/messages/flagged")

    assert response.status_code == 200
    assert response.get_json()["status"] == "FLAGGED"
    assert visible.get_json()["messages"] == []
    assert flagged.get_json()["flagged"][0]["summary"] == "An insulting meme with unsafe text."


def test_audio_upload_pass_is_saved(client, create_group, join_group, sandbox_paths, media_payloads):
    group_id = create_group()
    join_group(group_id, username="member1")

    response = client.post(
        f"/api/groups/{group_id}/audio",
        json={"username": "member1", "audio_data": media_payloads["good_audio"], "mime_type": "audio/wav"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "PASS"
    assert payload["transcript"] == "Study group reminder for tomorrow."
    assert any(sandbox_paths["audio_dir"].iterdir())


def test_flagged_audio_returns_structured_response(client, create_group, join_group, sandbox_paths, media_payloads):
    group_id = create_group(rules="No insults in any format.")
    join_group(group_id, username="member1")

    response = client.post(
        f"/api/groups/{group_id}/audio",
        json={"username": "member1", "audio_data": media_payloads["bad_audio"], "mime_type": "audio/wav"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "FLAGGED"
    assert payload["reason"] == "Test: flagged audio content"
    assert payload["transcript"] == "This audio contains a bad insult."
    assert any(sandbox_paths["audio_dir"].iterdir())
