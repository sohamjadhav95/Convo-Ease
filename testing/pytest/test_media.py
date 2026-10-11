import base64


def test_image_upload_pass_is_saved_and_served_to_members(user, create_group, join_group, media_payloads):
    group_id = create_group()
    join_group(group_id, username="member1")

    response = user("member1").post(
        f"/api/groups/{group_id}/images",
        json={"image_data": media_payloads["good_image"], "mime_type": "image/png"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "PASS"
    assert payload["media_url"].startswith("/media/image/")
    assert payload["media_url"].endswith(".png")

    served = user("admin").get(payload["media_url"])
    assert served.status_code == 200
    assert served.mimetype == "image/png"
    assert served.data == base64.b64decode(media_payloads["good_image"])


def test_media_is_private_to_group_members(user, create_group, client, media_payloads):
    group_id = create_group()
    media_url = user("admin").post(
        f"/api/groups/{group_id}/images", json={"image_data": media_payloads["good_image"]}
    ).get_json()["media_url"]

    assert client.get(media_url).status_code == 401
    assert user("outsider").get(media_url).status_code == 404


def test_non_image_upload_is_rejected(user, create_group):
    group_id = create_group()
    html = base64.b64encode(b"<script>alert(1)</script>").decode()

    response = user("admin").post(f"/api/groups/{group_id}/images", json={"image_data": html, "mime_type": "image/png"})

    assert response.status_code == 400


def test_flagged_image_is_not_visible_to_members(user, create_group, join_group, media_payloads):
    group_id = create_group(rules="No unsafe memes.")
    join_group(group_id, username="member1")

    response = user("member1").post(
        f"/api/groups/{group_id}/images",
        json={"image_data": media_payloads["bad_image"], "mime_type": "image/png"},
    )
    visible = user("admin").get(f"/api/groups/{group_id}/messages")
    flagged = user("admin").get(f"/api/groups/{group_id}/messages/flagged")

    assert response.status_code == 200
    assert response.get_json()["status"] == "FLAGGED"
    assert "media_url" not in response.get_json()
    assert visible.get_json()["messages"] == []
    assert flagged.get_json()["flagged"][0]["summary"] == "An insulting meme with unsafe text."


def test_audio_upload_pass_is_saved(user, create_group, join_group, media_payloads):
    group_id = create_group()
    join_group(group_id, username="member1")

    response = user("member1").post(
        f"/api/groups/{group_id}/audio",
        json={"audio_data": media_payloads["good_audio"], "mime_type": "audio/wav"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "PASS"
    assert payload["transcript"] == "Study group reminder for tomorrow."
    served = user("member1").get(payload["media_url"])
    assert served.status_code == 200
    assert served.mimetype == "audio/wav"


def test_browser_recording_webm_is_accepted(user, create_group, media_payloads):
    group_id = create_group()

    response = user("admin").post(
        f"/api/groups/{group_id}/audio",
        json={"audio_data": media_payloads["good_audio"], "mime_type": "audio/webm;codecs=opus"},
    )

    assert response.status_code == 200
    assert response.get_json()["media_url"].endswith(".webm")


def test_unsupported_audio_type_is_rejected(user, create_group, media_payloads):
    group_id = create_group()

    response = user("admin").post(
        f"/api/groups/{group_id}/audio",
        json={"audio_data": media_payloads["good_audio"], "mime_type": "text/html"},
    )

    assert response.status_code == 400


def test_flagged_audio_returns_structured_response(user, create_group, join_group, media_payloads):
    group_id = create_group(rules="No insults in any format.")
    join_group(group_id, username="member1")

    response = user("member1").post(
        f"/api/groups/{group_id}/audio",
        json={"audio_data": media_payloads["bad_audio"], "mime_type": "audio/wav"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "FLAGGED"
    assert payload["reason"] == "Test: flagged audio content"
    assert payload["transcript"] == "This audio contains a bad insult."
