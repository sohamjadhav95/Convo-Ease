import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testing.shared.harness import configure_test_environment, encode_payload, install_test_ai


@pytest.fixture
def sandbox_paths(tmp_path, monkeypatch):
    install_test_ai(monkeypatch)
    return configure_test_environment(tmp_path / "runtime", monkeypatch)


@pytest.fixture
def app(sandbox_paths):
    from main import create_app

    app = create_app()
    app.config.update(TESTING=True)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def register_user(client):
    def _register(username, password="pass123", full_name=None, bio=""):
        return client.post(
            "/api/auth/register",
            json={
                "username": username,
                "password": password,
                "full_name": full_name or username.title(),
                "bio": bio,
            },
        )

    return _register


@pytest.fixture
def create_group(client, register_user):
    def _create(admin_username="admin", group_name="Study Group", password="secret", rules="Be respectful. No insults.", moderation_sensitivity="Moderate"):
        register_user(admin_username)
        response = client.post(
            "/api/groups",
            json={
                "group_name": group_name,
                "password": password,
                "admin_username": admin_username,
                "rules": rules,
                "moderation_sensitivity": moderation_sensitivity,
            },
        )
        assert response.status_code == 200
        return response.get_json()["group_id"]

    return _create


@pytest.fixture
def join_group(client, register_user):
    def _join(group_id, username="member", password="secret"):
        register_user(username)
        return client.post(
            "/api/groups/join",
            json={"group_id": group_id, "password": password, "username": username},
        )

    return _join


@pytest.fixture
def media_payloads():
    return {
        "good_image": encode_payload("goodimage"),
        "bad_image": encode_payload("badimage"),
        "good_audio": encode_payload("goodaudio"),
        "bad_audio": encode_payload("badaudio"),
    }
