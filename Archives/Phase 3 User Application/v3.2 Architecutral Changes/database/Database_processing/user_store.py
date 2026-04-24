"""
ConvoEase — User Store
All user-related database operations: register, login, profile.
"""

import hashlib
import random
from datetime import datetime
from config import USERS_FILE, setup_logging
from .db_manager import DBManager

logger = setup_logging("user_store")


class UserStore:
    """Handles all user CRUD operations."""

    @staticmethod
    def _hash_password(password):
        return hashlib.sha256(password.encode()).hexdigest()

    @staticmethod
    def _generate_color():
        return "#{:06x}".format(random.randint(0, 0xFFFFFF))

    @staticmethod
    def _now():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def load_all():
        """Load all users from CSV."""
        return DBManager.read_csv(USERS_FILE)

    @staticmethod
    def register(username, password, full_name, bio=""):
        """Register a new user. Returns (success: bool, message: str)."""
        users = UserStore.load_all()
        if username in users["username"].values:
            logger.warning(f"Registration failed: username '{username}' already exists")
            return False, "Username already exists."

        new_user = {
            "username": username,
            "password": UserStore._hash_password(password),
            "full_name": full_name,
            "bio": bio,
            "profile_pic_color": UserStore._generate_color(),
            "created_at": UserStore._now()
        }
        DBManager.append_row(USERS_FILE, new_user)
        logger.info(f"User registered: {username}")
        return True, "Registration successful."

    @staticmethod
    def validate_login(username, password):
        """Validate login credentials. Returns (success: bool, user_dict | None)."""
        users = UserStore.load_all()
        hashed = UserStore._hash_password(password)
        match = users[(users["username"] == username) & (users["password"] == hashed)]
        if not match.empty:
            logger.info(f"Login successful: {username}")
            return True, match.iloc[0].to_dict()
        logger.warning(f"Login failed: {username}")
        return False, None

    @staticmethod
    def get_profile(username):
        """Get a user's profile data."""
        users = UserStore.load_all()
        user = users[users["username"] == username]
        if not user.empty:
            return user.iloc[0].to_dict()
        return None
