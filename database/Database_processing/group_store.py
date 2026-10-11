"""
ConvoEase — Group Store
All group-related database operations: create, join, members, rules.
"""

import secrets

from sqlalchemy import and_, delete, func, insert, select, update

from config import setup_logging
from .db_manager import DBManager, chat_groups, group_members, media, messages, utc_now
from .user_store import hash_password, is_legacy_hash, verify_password

logger = setup_logging("group_store")

# No 0/O or 1/I, so IDs are easy to read out loud and type.
_GROUP_ID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class GroupStore:
    """Handles all group CRUD operations."""

    @staticmethod
    def _new_group_id():
        for _ in range(20):
            group_id = "".join(secrets.choice(_GROUP_ID_ALPHABET) for _ in range(6))
            if not GroupStore.get_group_details(group_id):
                return group_id
        raise RuntimeError("Could not allocate a unique group ID.")

    @staticmethod
    def create_group(group_name, password, admin_username, initial_rules="Be respectful.", moderation_sensitivity="Moderate"):
        """Create a new group and add admin as first member. Returns (success, group_id)."""
        group_id = GroupStore._new_group_id()
        now = utc_now()
        with DBManager.begin() as conn:
            conn.execute(insert(chat_groups).values(
                group_id=group_id,
                group_name=group_name.strip()[:120],
                admin_username=admin_username,
                password=hash_password(password) if password else "",
                rules=initial_rules or "",
                moderation_sensitivity=GroupStore.normalize_sensitivity(moderation_sensitivity),
                created_at=now,
            ))
            conn.execute(insert(group_members).values(
                group_id=group_id, username=admin_username, joined_at=now, last_read_seq=0,
            ))
        logger.info("Group created: %s (%s) by %s", group_name, group_id, admin_username)
        return True, group_id

    @staticmethod
    def join_group(group_id, password, username):
        """Join an existing group. Returns (success, message)."""
        group = GroupStore.get_group_details(group_id)
        if not group:
            return False, "Group not found."

        stored = group.get("password") or ""
        if stored:
            if not verify_password(stored, password):
                return False, "Incorrect group password."
            if is_legacy_hash(stored):
                DBManager.execute(
                    update(chat_groups)
                    .where(chat_groups.c.group_id == group_id)
                    .values(password=hash_password(password))
                )

        if GroupStore.is_member(group_id, username):
            return True, "Already a member."

        DBManager.execute(insert(group_members).values(
            group_id=group_id, username=username, joined_at=utc_now(), last_read_seq=0,
        ))
        logger.info("User '%s' joined group %s", username, group_id)
        return True, "Joined successfully."

    @staticmethod
    def is_member(group_id, username):
        query = select(group_members.c.username).where(and_(
            group_members.c.group_id == group_id,
            group_members.c.username == username,
        ))
        return DBManager.fetch_one(query) is not None

    @staticmethod
    def get_user_groups(username):
        """Groups a user belongs to, with last message and unread count."""
        query = (
            select(
                chat_groups.c.group_id,
                chat_groups.c.group_name,
                chat_groups.c.admin_username,
                chat_groups.c.moderation_sensitivity,
                group_members.c.last_read_seq,
                group_members.c.joined_at,
            )
            .select_from(group_members.join(chat_groups, group_members.c.group_id == chat_groups.c.group_id))
            .where(group_members.c.username == username)
        )
        records = DBManager.fetch_all(query)
        if not records:
            return []

        group_ids = [record["group_id"] for record in records]
        visible = messages.c.status == "PASS"

        last_seq_rows = DBManager.fetch_all(
            select(messages.c.group_id, func.max(messages.c.seq).label("seq"))
            .where(and_(messages.c.group_id.in_(group_ids), visible))
            .group_by(messages.c.group_id)
        )
        last_seqs = [row["seq"] for row in last_seq_rows if row["seq"] is not None]
        last_rows = {}
        if last_seqs:
            for row in DBManager.fetch_all(select(messages).where(messages.c.seq.in_(last_seqs))):
                last_rows[row["group_id"]] = row

        from .message_store import MessageStore

        for record in records:
            last = last_rows.get(record["group_id"])
            record["last_message"] = MessageStore._display_message(last) if last else ""
            record["last_message_user"] = last["username"] if last else ""
            record["last_message_at"] = last["timestamp"] if last else ""
            record["last_seq"] = last["seq"] if last else 0
            record["is_admin"] = record["admin_username"] == username
            record["unread_count"] = DBManager.scalar(
                select(func.count()).select_from(messages).where(and_(
                    messages.c.group_id == record["group_id"],
                    visible,
                    messages.c.seq > (record["last_read_seq"] or 0),
                    messages.c.username != username,
                ))
            ) or 0
            record.pop("last_read_seq", None)

        records.sort(key=lambda r: r["last_message_at"] or r["joined_at"] or "", reverse=True)
        return records

    @staticmethod
    def mark_read(group_id, username, seq):
        DBManager.execute(
            update(group_members)
            .where(and_(
                group_members.c.group_id == group_id,
                group_members.c.username == username,
                group_members.c.last_read_seq < seq,
            ))
            .values(last_read_seq=seq)
        )

    @staticmethod
    def get_group_details(group_id):
        """Get full details for a group (including the password hash). Returns dict or None."""
        data = DBManager.fetch_one(select(chat_groups).where(chat_groups.c.group_id == group_id))
        if data:
            data["moderation_sensitivity"] = GroupStore.normalize_sensitivity(
                data.get("moderation_sensitivity", "")
            )
        return data

    @staticmethod
    def update_group_rules(group_id, new_rules, moderation_sensitivity=None):
        """Update the rules and moderation sensitivity for a group."""
        values = {"rules": new_rules or ""}
        if moderation_sensitivity is not None:
            values["moderation_sensitivity"] = GroupStore.normalize_sensitivity(moderation_sensitivity)
        DBManager.execute(update(chat_groups).where(chat_groups.c.group_id == group_id).values(**values))
        logger.info("Rules updated for group %s", group_id)

    @staticmethod
    def update_group_name(group_id, new_name, requesting_username):
        """Rename a group. Only the admin can do this. Returns (success, message)."""
        group = GroupStore.get_group_details(group_id)
        if not group:
            return False, "Group not found."
        if group["admin_username"] != requesting_username:
            return False, "Only the admin can rename the group."

        DBManager.execute(
            update(chat_groups).where(chat_groups.c.group_id == group_id).values(group_name=new_name.strip()[:120])
        )
        logger.info("Group %s renamed to '%s' by %s", group_id, new_name, requesting_username)
        return True, "Group renamed successfully."

    @staticmethod
    def get_group_members(group_id):
        """Usernames of a group's members, in join order."""
        rows = DBManager.fetch_all(
            select(group_members.c.username)
            .where(group_members.c.group_id == group_id)
            .order_by(group_members.c.joined_at, group_members.c.username)
        )
        return [row["username"] for row in rows]

    @staticmethod
    def leave_group(group_id, username):
        """Remove a non-admin member from a group. Returns (success, message)."""
        group = GroupStore.get_group_details(group_id)
        if not group:
            return False, "Group not found."
        if group["admin_username"] == username:
            return False, "Admin cannot leave the group. Delete it instead."
        if not GroupStore.is_member(group_id, username):
            return False, "You are not a member of this group."

        DBManager.execute(delete(group_members).where(and_(
            group_members.c.group_id == group_id,
            group_members.c.username == username,
        )))
        logger.info("User '%s' left group %s", username, group_id)
        return True, "Left group successfully."

    @staticmethod
    def delete_group(group_id, requesting_username):
        """Delete a group entirely. Only the admin can do this. Returns (success, message)."""
        group = GroupStore.get_group_details(group_id)
        if not group:
            return False, "Group not found."
        if group["admin_username"] != requesting_username:
            return False, "Only the group admin can delete this group."

        with DBManager.begin() as conn:
            conn.execute(delete(messages).where(messages.c.group_id == group_id))
            conn.execute(delete(media).where(media.c.group_id == group_id))
            conn.execute(delete(group_members).where(group_members.c.group_id == group_id))
            conn.execute(delete(chat_groups).where(chat_groups.c.group_id == group_id))

        logger.info("Group %s deleted by admin %s", group_id, requesting_username)
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
