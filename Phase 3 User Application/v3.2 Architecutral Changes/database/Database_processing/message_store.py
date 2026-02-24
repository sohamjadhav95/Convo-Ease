"""
ConvoEase — Message Store
All message-related database operations: save, load, flagged.
"""

import uuid
from datetime import datetime
from config import CHATS_FILE, setup_logging
from .db_manager import DBManager

logger = setup_logging("message_store")


class MessageStore:
    """Handles all message CRUD operations."""

    @staticmethod
    def _now():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def load_messages(group_id=None):
        """Load messages. If group_id is provided, filter by group."""
        df = DBManager.read_csv(CHATS_FILE)
        if group_id:
            df = df[df["group_id"] == group_id]
        return df

    @staticmethod
    def save_message(group_id, username, message, status, reason=""):
        """Save a new message to the database."""
        new_msg = {
            "message_id": str(uuid.uuid4()),
            "group_id": group_id,
            "username": username,
            "message": message,
            "status": status,
            "reason": reason,
            "timestamp": MessageStore._now()
        }
        DBManager.append_row(CHATS_FILE, new_msg)
        logger.info(f"Message saved: [{status}] {username} in group {group_id}")

    @staticmethod
    def get_visible_messages(group_id):
        """Get only PASS messages for a group, sorted by timestamp. Returns list of dicts."""
        msgs = MessageStore.load_messages(group_id)
        visible = msgs[msgs["status"] == "PASS"].sort_values("timestamp")
        return visible.to_dict("records")

    @staticmethod
    def get_flagged_messages(group_id):
        """Get only FLAGGED messages for a group. Returns list of dicts."""
        msgs = MessageStore.load_messages(group_id)
        flagged = msgs[msgs["status"] == "FLAGGED"]
        return flagged[["timestamp", "username", "message", "reason"]].to_dict("records")
