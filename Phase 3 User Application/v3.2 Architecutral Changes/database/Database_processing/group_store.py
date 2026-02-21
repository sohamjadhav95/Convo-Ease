"""
ConvoEase — Group Store
All group-related database operations: create, join, members, rules.
"""

import uuid
from datetime import datetime
from config import GROUPS_FILE, MEMBERS_FILE, setup_logging
from .db_manager import DBManager

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
    def create_group(group_name, password, admin_username, initial_rules="Be respectful."):
        """Create a new group and add admin as first member. Returns (success, group_id)."""
        groups = GroupStore.load_groups()
        group_id = str(uuid.uuid4())[:6].upper()

        new_group = {
            "group_id": group_id,
            "group_name": group_name,
            "admin_username": admin_username,
            "password": password,
            "rules": initial_rules,
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

        if target.iloc[0]["password"] != password:
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
        return result[["group_id", "group_name", "admin_username"]].to_dict("records")

    @staticmethod
    def get_group_details(group_id):
        """Get full details for a group. Returns dict or None."""
        groups = GroupStore.load_groups()
        grp = groups[groups["group_id"] == group_id]
        if not grp.empty:
            return grp.iloc[0].to_dict()
        return None

    @staticmethod
    def update_group_rules(group_id, new_rules):
        """Update the rules for a group."""
        groups = GroupStore.load_groups()
        groups.loc[groups["group_id"] == group_id, "rules"] = new_rules
        DBManager.write_csv(GROUPS_FILE, groups)
        logger.info(f"Rules updated for group {group_id}")

    @staticmethod
    def get_group_members(group_id):
        """Get list of members for a group."""
        members = GroupStore.load_members()
        group_members = members[members["group_id"] == group_id]
        return group_members["username"].tolist()
