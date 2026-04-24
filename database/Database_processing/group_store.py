"""
ConvoEase — Group Store
All group-related database operations: create, join, members, rules.
"""

import uuid
from datetime import datetime
from config import GROUPS_FILE, MEMBERS_FILE, CHATS_FILE, setup_logging
from .db_manager import DBManager
from .user_store import hash_password

logger = setup_logging("group_store")


class GroupStore:
    """Handles all group CRUD operations."""

    @staticmethod
    def _now():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def load_groups():
        return DBManager.read_csv(GROUPS_FILE)

    @staticmethod
    def load_members():
        return DBManager.read_csv(MEMBERS_FILE)

    @staticmethod
    def create_group(group_name, password, admin_username, initial_rules="Be respectful.", moderation_sensitivity="Moderate"):
        """Create a new group and add admin as first member. Returns (success, group_id)."""
        groups = GroupStore.load_groups()
        group_id = str(uuid.uuid4())[:6].upper()
        sensitivity = GroupStore.normalize_sensitivity(moderation_sensitivity)

        new_group = {
            "group_id": group_id,
            "group_name": group_name,
            "admin_username": admin_username,
            "password": hash_password(password) if password else "",
            "rules": initial_rules,
            "moderation_sensitivity": sensitivity,
            "created_at": GroupStore._now()
        }
        DBManager.append_row(GROUPS_FILE, new_group)
        GroupStore._add_member(group_id, admin_username)
        logger.info(f"Group created: {group_name} ({group_id}) by {admin_username}")
        return True, group_id

    @staticmethod
    def join_group(group_id, password, username):
        """Join an existing group. Returns (success, message)."""
        groups = GroupStore.load_groups()
        target = groups[groups["group_id"] == group_id]

        if target.empty:
            return False, "Group not found."

        stored = str(target.iloc[0]["password"] or "")
        if stored and stored != hash_password(password):
            return False, "Incorrect group password."

        members = GroupStore.load_members()
        if not members[(members["group_id"] == group_id) & (members["username"] == username)].empty:
            return True, "Already a member."

        GroupStore._add_member(group_id, username)
        logger.info(f"User '{username}' joined group {group_id}")
        return True, "Joined successfully."

    @staticmethod
    def _add_member(group_id, username):
        """Internal: add a member to a group."""
        new_member = {
            "group_id": group_id,
            "username": username,
            "joined_at": GroupStore._now()
        }
        DBManager.append_row(MEMBERS_FILE, new_member)

    @staticmethod
    def get_user_groups(username):
        """Get all groups a user belongs to. Returns list of dicts."""
        members = GroupStore.load_members()
        user_memberships = members[members["username"] == username]

        groups = GroupStore.load_groups()
        import pandas as pd
        result = pd.merge(user_memberships, groups, on="group_id")
        records = result[["group_id", "group_name", "admin_username"]].to_dict("records")

        from .message_store import MessageStore

        for record in records:
            recent = MessageStore.get_recent_messages(record["group_id"], limit=1, include_flagged=False)
            record["last_message"] = MessageStore._display_message(recent[-1]) if recent else ""

        return records

    @staticmethod
    def get_group_details(group_id):
        """Get full details for a group. Returns dict or None."""
        groups = GroupStore.load_groups()
        grp = groups[groups["group_id"] == group_id]
        if not grp.empty:
            data = grp.iloc[0].to_dict()
            data["moderation_sensitivity"] = GroupStore.normalize_sensitivity(
                data.get("moderation_sensitivity", "")
            )
            return data
        return None

    @staticmethod
    def update_group_rules(group_id, new_rules, moderation_sensitivity=None):
        """Update the rules and moderation sensitivity for a group."""
        groups = GroupStore.load_groups()
        groups.loc[groups["group_id"] == group_id, "rules"] = new_rules
        if moderation_sensitivity is not None:
            groups.loc[groups["group_id"] == group_id, "moderation_sensitivity"] = (
                GroupStore.normalize_sensitivity(moderation_sensitivity)
            )
        DBManager.write_csv(GROUPS_FILE, groups)
        logger.info(f"Rules updated for group {group_id}")

    @staticmethod
    def update_group_name(group_id, new_name, requesting_username):
        """Rename a group. Only the admin can do this. Returns (success, message)."""
        groups = GroupStore.load_groups()
        target = groups[groups["group_id"] == group_id]
        if target.empty:
            return False, "Group not found."
        if target.iloc[0]["admin_username"] != requesting_username:
            return False, "Only the admin can rename the group."

        groups.loc[groups["group_id"] == group_id, "group_name"] = new_name
        DBManager.write_csv(GROUPS_FILE, groups)
        logger.info(f"Group {group_id} renamed to '{new_name}' by {requesting_username}")
        return True, "Group renamed successfully."

    @staticmethod
    def get_group_members(group_id):
        """Get list of members for a group."""
        members = GroupStore.load_members()
        group_members = members[members["group_id"] == group_id]
        return group_members["username"].tolist()

    @staticmethod
    def leave_group(group_id, username):
        """Remove a non-admin member from a group. Returns (success, message)."""
        groups = GroupStore.load_groups()
        target = groups[groups["group_id"] == group_id]
        if target.empty:
            return False, "Group not found."

        if target.iloc[0]["admin_username"] == username:
            return False, "Admin cannot leave the group. Delete it instead."

        members = GroupStore.load_members()
        mask = (members["group_id"] == group_id) & (members["username"] == username)
        if mask.sum() == 0:
            return False, "You are not a member of this group."

        members = members[~mask]
        DBManager.write_csv(MEMBERS_FILE, members)
        logger.info(f"User '{username}' left group {group_id}")
        return True, "Left group successfully."

    @staticmethod
    def delete_group(group_id, requesting_username):
        """Delete a group entirely. Only the admin can do this. Returns (success, message)."""
        groups = GroupStore.load_groups()
        target = groups[groups["group_id"] == group_id]
        if target.empty:
            return False, "Group not found."

        if target.iloc[0]["admin_username"] != requesting_username:
            return False, "Only the group admin can delete this group."

        groups = groups[groups["group_id"] != group_id]
        DBManager.write_csv(GROUPS_FILE, groups)

        members = GroupStore.load_members()
        members = members[members["group_id"] != group_id]
        DBManager.write_csv(MEMBERS_FILE, members)

        chats = DBManager.read_csv(CHATS_FILE)
        chats = chats[chats["group_id"] != group_id]
        DBManager.write_csv(CHATS_FILE, chats)

        logger.info(f"Group {group_id} deleted by admin {requesting_username}")
        return True, "Group deleted successfully."

    @staticmethod
    def normalize_sensitivity(value):
        normalized = str(value or "Moderate").strip().lower()
        mapping = {
            "strict": "Strict",
            "moderate": "Moderate",
            "relaxed": "Relaxed",
        }
        return mapping.get(normalized, "Moderate")
