import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testing.shared.harness import audio_payload, configure_test_environment, image_payload, install_test_ai


@pytest.fixture
def sandbox_paths(tmp_path, monkeypatch):
    install_test_ai(monkeypatch)
    return configure_test_environment(tmp_path / "runtime", monkeypatch)


@pytest.fixture
def app(sandbox_paths):
    from main import create_app

    return create_app({"TESTING": True, "RATE_LIMITS_ENABLED": False})


@pytest.fixture
def client(app):
    """An anonymous (signed-out) client."""
    return app.test_client()


@pytest.fixture
def user(app):
    """user("alice") -> a test client signed in as alice (registered on first use)."""
    clients = {}

    def _user(username, password="pass123", full_name=None):
        if username not in clients:
            session_client = app.test_client()
            response = session_client.post(
                "/api/auth/register",
                json={"username": username, "password": password, "full_name": full_name or username.title()},
            )
            if response.status_code == 409:
                response = session_client.post(
                    "/api/auth/login", json={"username": username, "password": password}
                )
            assert response.status_code == 200, response.get_json()
            clients[username] = session_client
        return clients[username]

    return _user


@pytest.fixture
def create_group(user):
    def _create(admin_username="admin", group_name="Study Group", password="secret", rules="Be respectful. No insults.", moderation_sensitivity="Moderate"):
        response = user(admin_username).post(
            "/api/groups",
            json={
                "group_name": group_name,
                "password": password,
                "rules": rules,
                "moderation_sensitivity": moderation_sensitivity,
            },
        )
        assert response.status_code == 200
        return response.get_json()["group_id"]

    return _create


@pytest.fixture
def join_group(user):
    def _join(group_id, username="member", password="secret"):
        return user(username).post("/api/groups/join", json={"group_id": group_id, "password": password})

    return _join


@pytest.fixture
def media_payloads():
    return {
        "good_image": image_payload("goodimage"),
        "bad_image": image_payload("badimage"),
        "good_audio": audio_payload("goodaudio"),
        "bad_audio": audio_payload("badaudio"),
    }
