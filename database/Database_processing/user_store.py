"""
ConvoEase — User Store
All user-related database operations: register, login, profile.
"""

import hashlib
import hmac
import random
import re

from sqlalchemy import func, insert, select, update
from werkzeug.security import check_password_hash, generate_password_hash

from config import setup_logging
from .db_manager import DBManager, users, utc_now

logger = setup_logging("user_store")

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
_LEGACY_HASH = re.compile(r"^[0-9a-f]{64}$")


def hash_password(password):
    """Salted, slow hash (scrypt) shared by user and group passwords."""
    return generate_password_hash(password or "")


def is_legacy_hash(stored):
    """v4 and earlier stored an unsalted SHA-256 hex digest."""
    return bool(_LEGACY_HASH.match(stored or ""))


def verify_password(stored, password):
    stored = stored or ""
    if not stored:
        return False
    if is_legacy_hash(stored):
        candidate = hashlib.sha256((password or "").encode()).hexdigest()
        return hmac.compare_digest(stored, candidate)
    try:
        return check_password_hash(stored, password or "")
    except (ValueError, TypeError):
        return False


def public_profile(row):
    """User fields that are safe to show to other people."""
    if not row:
        return None
    return {
        "username": row["username"],
        "full_name": row.get("full_name", ""),
        "bio": row.get("bio", ""),
        "profile_pic_color": row.get("profile_pic_color", ""),
        "avatar": row.get("avatar", ""),
        "created_at": row.get("created_at", ""),
    }


class UserStore:
    """Handles all user CRUD operations."""

    @staticmethod
    def _generate_color():
        return "#{:06x}".format(random.randint(0, 0xFFFFFF))

    @staticmethod
    def validate_username(username):
        if not USERNAME_PATTERN.match(username or ""):
            return "Username must be 3-32 characters: letters, numbers, dot, dash or underscore."
        return ""

    @staticmethod
    def _get_row(username):
        return DBManager.fetch_one(select(users).where(users.c.username == username))

    @staticmethod
    def register(username, password, full_name, bio=""):
        """Register a new user. Returns (success: bool, message: str)."""
        problem = UserStore.validate_username(username)
        if problem:
            return False, problem
        if len(password or "") < 6:
            return False, "Password must be at least 6 characters."
        if username.lower() == password.lower():
            return False, "Username and password cannot be the same."
        if UserStore._username_taken(username):
            logger.warning("Registration failed: username '%s' already exists", username)
            return False, "Username already exists."

        DBManager.execute(insert(users).values(
            username=username,
            password=hash_password(password),
            full_name=(full_name or "").strip()[:120],
            bio=(bio or "").strip(),
            profile_pic_color=UserStore._generate_color(),
            avatar="",
            created_at=utc_now(),
        ))
        logger.info("User registered: %s", username)
        return True, "Registration successful."

    @staticmethod
    def _username_taken(username):
        # Usernames are compared case-insensitively so "Alice" can't shadow "alice".
        query = select(users.c.username).where(func.lower(users.c.username) == username.lower())
        return DBManager.fetch_one(query) is not None

    @staticmethod
    def validate_login(username, password):
        """Validate login credentials. Returns (success: bool, user_dict | None)."""
        row = UserStore._get_row(username)
        if not row or not verify_password(row["password"], password):
            logger.warning("Login failed: %s", username)
            return False, None

        if is_legacy_hash(row["password"]):
            # Upgrade old unsalted hashes the first time the user logs in.
            DBManager.execute(
                update(users).where(users.c.username == username).values(password=hash_password(password))
            )
        logger.info("Login successful: %s", username)
        return True, public_profile(row)

    @staticmethod
    def get_profile(username):
        """Get a user's public profile data."""
        return public_profile(UserStore._get_row(username))

    @staticmethod
    def get_profiles(usernames):
        """Public profiles for several users, keyed by username."""
        names = sorted(set(usernames))
        if not names:
            return {}
        rows = DBManager.fetch_all(select(users).where(users.c.username.in_(names)))
        return {row["username"]: public_profile(row) for row in rows}

    @staticmethod
    def update_profile(username, full_name=None, bio=None, avatar=None):
        """Update user profile fields. Returns (success, message)."""
        if not UserStore._get_row(username):
            return False, "User not found."

        values = {}
        if full_name is not None and full_name.strip():
            values["full_name"] = full_name.strip()[:120]
        if bio is not None:
            values["bio"] = bio.strip()[:500]
        if avatar is not None:
            values["avatar"] = avatar.strip()[:32]
        if values:
            DBManager.execute(update(users).where(users.c.username == username).values(**values))
        logger.info("Profile updated for user: %s", username)
        return True, "Profile updated."

    @staticmethod
    def change_password(username, current_password, new_password):
        """Returns (success, message)."""
        row = UserStore._get_row(username)
        if not row or not verify_password(row["password"], current_password):
            return False, "Current password is incorrect."
        if len(new_password or "") < 6:
            return False, "New password must be at least 6 characters."
        if new_password.lower() == username.lower():
            return False, "Username and password cannot be the same."
        DBManager.execute(
            update(users).where(users.c.username == username).values(password=hash_password(new_password))
        )
        logger.info("Password changed for user: %s", username)
        return True, "Password updated."
