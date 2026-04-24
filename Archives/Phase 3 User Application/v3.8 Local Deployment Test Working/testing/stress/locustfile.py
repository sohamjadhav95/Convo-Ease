import os
import threading
import uuid

from locust import HttpUser, between, task


BOOTSTRAP_LOCK = threading.Lock()
BOOTSTRAPPED = {"group_id": None}

GROUP_NAME = os.getenv("CONVOEASE_STRESS_GROUP_NAME", "Locust Demo Group")
GROUP_PASSWORD = os.getenv("CONVOEASE_STRESS_GROUP_PASSWORD", "roompass")
GROUP_RULES = os.getenv("CONVOEASE_STRESS_GROUP_RULES", "Be respectful. No insults.")
ADMIN_USERNAME = os.getenv("CONVOEASE_STRESS_ADMIN_USERNAME", "load_admin")
ADMIN_PASSWORD = os.getenv("CONVOEASE_STRESS_ADMIN_PASSWORD", "secret123")


def _safe_post(client, path, payload):
    response = client.post(path, json=payload, name=path)
    if response.status_code >= 400 and response.status_code != 409:
        response.failure(f"{path} failed with {response.status_code}: {response.text[:120]}")
    return response


def ensure_group(client):
    if BOOTSTRAPPED["group_id"]:
        return BOOTSTRAPPED["group_id"]

    with BOOTSTRAP_LOCK:
        if BOOTSTRAPPED["group_id"]:
            return BOOTSTRAPPED["group_id"]

        _safe_post(
            client,
            "/api/auth/register",
            {"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD, "full_name": "Load Admin"},
        )
        response = _safe_post(
            client,
            "/api/groups",
            {
                "group_name": GROUP_NAME,
                "password": GROUP_PASSWORD,
                "admin_username": ADMIN_USERNAME,
                "rules": GROUP_RULES,
                "moderation_sensitivity": "Moderate",
            },
        )
        if response.ok:
            BOOTSTRAPPED["group_id"] = response.json().get("group_id")
        return BOOTSTRAPPED["group_id"]


class ChatUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.username = f"load_{uuid.uuid4().hex[:8]}"
        self.password = "secret123"
        self.group_id = ensure_group(self.client)

        _safe_post(
            self.client,
            "/api/auth/register",
            {"username": self.username, "password": self.password, "full_name": self.username},
        )
        _safe_post(
            self.client,
            "/api/groups/join",
            {"group_id": self.group_id, "password": GROUP_PASSWORD, "username": self.username},
        )

    @task(3)
    def send_message(self):
        self.client.post(
            f"/api/groups/{self.group_id}/messages",
            json={"username": self.username, "message": "hello from locust"},
            name="/api/groups/[id]/messages POST",
        )

    @task(1)
    def read_messages(self):
        self.client.get(
            f"/api/groups/{self.group_id}/messages",
            name="/api/groups/[id]/messages GET",
        )

    @task(1)
    def fetch_report(self):
        self.client.get(
            f"/api/groups/{self.group_id}/report",
            name="/api/groups/[id]/report",
        )
