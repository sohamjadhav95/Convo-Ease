def test_register_user_success(client, register_user):
    response = register_user("alice", full_name="Alice Johnson")

    assert response.status_code == 200
    assert response.get_json() == {"success": True, "message": "Registration successful."}


def test_duplicate_username_is_rejected(client, register_user):
    register_user("alice")
    response = register_user("alice", password="different")

    assert response.status_code == 409
    assert response.get_json()["success"] is False
    assert "already exists" in response.get_json()["message"]


def test_login_success_returns_public_user_payload(client, register_user):
    register_user("alice", password="secret123", full_name="Alice Johnson")
    response = client.post("/api/auth/login", json={"username": "alice", "password": "secret123"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["user"]["username"] == "alice"
    assert "password" not in payload["user"]


def test_login_requires_username_and_password(client):
    response = client.post("/api/auth/login", json={"username": "", "password": ""})

    assert response.status_code == 400
    assert response.get_json()["message"] == "Username and password required."
