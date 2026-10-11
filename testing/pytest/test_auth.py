import hashlib

from sqlalchemy import insert, select


def test_register_user_success_signs_in(client):
    response = client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "pass123", "full_name": "Alice Johnson"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["user"]["username"] == "alice"
    assert "password" not in payload["user"]
    assert client.get("/api/auth/me").get_json()["user"]["full_name"] == "Alice Johnson"


def test_duplicate_username_is_rejected_case_insensitively(client, user):
    user("alice")
    response = client.post(
        "/api/auth/register",
        json={"username": "Alice", "password": "different", "full_name": "Other"},
    )

    assert response.status_code == 409
    assert response.get_json()["success"] is False
    assert "already exists" in response.get_json()["message"]


def test_register_rejects_short_password_and_bad_username(client):
    short = client.post("/api/auth/register", json={"username": "bob", "password": "123", "full_name": "Bob"})
    bad_name = client.post("/api/auth/register", json={"username": "a b", "password": "pass123", "full_name": "Bob"})

    assert short.status_code == 400
    assert bad_name.status_code == 400


def test_login_success_returns_public_user_payload(client, user):
    user("alice", password="secret123", full_name="Alice Johnson")
    response = client.post("/api/auth/login", json={"username": "alice", "password": "secret123"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["user"]["username"] == "alice"
    assert "password" not in payload["user"]


def test_login_with_wrong_password_fails(client, user):
    user("alice", password="secret123")
    response = client.post("/api/auth/login", json={"username": "alice", "password": "nope-nope"})

    assert response.status_code == 401
    assert client.get("/api/auth/me").status_code == 401


def test_login_requires_username_and_password(client):
    response = client.post("/api/auth/login", json={"username": "", "password": ""})

    assert response.status_code == 400
    assert response.get_json()["message"] == "Username and password required."


def test_logout_ends_the_session(user):
    alice = user("alice")
    assert alice.get("/api/auth/me").status_code == 200

    alice.post("/api/auth/logout")

    assert alice.get("/api/auth/me").status_code == 401
    assert alice.get("/api/groups").status_code == 401


def test_api_requires_sign_in(client):
    assert client.get("/api/groups").status_code == 401
    assert client.post("/api/groups", json={"group_name": "x"}).status_code == 401
    assert client.post("/api/rules/suggest", json={"rules": "x"}).status_code == 401


def test_legacy_sha256_password_still_works_and_is_upgraded(client, app):
    from database.Database_processing.db_manager import DBManager, users

    legacy_hash = hashlib.sha256(b"oldpass1").hexdigest()
    DBManager.execute(insert(users).values(
        username="legacy", password=legacy_hash, full_name="Legacy User", bio="",
        profile_pic_color="#123456", avatar="", created_at="2026-01-01 00:00:00",
    ))

    response = client.post("/api/auth/login", json={"username": "legacy", "password": "oldpass1"})

    assert response.status_code == 200
    stored = DBManager.fetch_one(select(users.c.password).where(users.c.username == "legacy"))["password"]
    assert stored != legacy_hash
    assert client.post("/api/auth/login", json={"username": "legacy", "password": "oldpass1"}).status_code == 200


def test_change_password(user, client):
    alice = user("alice", password="first-pass")

    wrong = alice.put("/api/user/password", json={"current_password": "nope", "new_password": "second-pass"})
    right = alice.put("/api/user/password", json={"current_password": "first-pass", "new_password": "second-pass"})

    assert wrong.status_code == 400
    assert right.status_code == 200
    assert client.post("/api/auth/login", json={"username": "alice", "password": "second-pass"}).status_code == 200


def test_profile_update_only_changes_own_profile(user):
    alice = user("alice")
    user("bob", full_name="Bob Original")

    response = alice.put("/api/user/profile", json={"username": "bob", "full_name": "Hacked", "avatar": "fox"})

    assert response.status_code == 200
    assert response.get_json()["user"]["username"] == "alice"
    bob_profile = alice.get("/api/user/profile", query_string={"username": "bob"}).get_json()["profile"]
    assert bob_profile["full_name"] == "Bob Original"
