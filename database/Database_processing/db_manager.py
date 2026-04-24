"""
ConvoEase - Database Manager
Central utilities for CSV database initialization, reading, and writing.
"""

import os
import threading
import tempfile
import pandas as pd
from config import DATABASE_DIR, USERS_FILE, GROUPS_FILE, MEMBERS_FILE, CHATS_FILE, setup_logging

logger = setup_logging("db_manager")

# Schema definitions - single source of truth for CSV columns
SCHEMAS = {
    "users": {
        "path": USERS_FILE,
        "columns": ["username", "password", "full_name", "bio", "profile_pic_color", "avatar", "created_at"]
    },
    "groups": {
        "path": GROUPS_FILE,
        "columns": [
            "group_id", "group_name", "admin_username", "password", "rules",
            "moderation_sensitivity", "created_at"
        ]
    },
    "members": {
        "path": MEMBERS_FILE,
        "columns": ["group_id", "username", "joined_at"]
    },
    "chats": {
        "path": CHATS_FILE,
        "columns": [
            "message_id", "group_id", "username", "message", "status", "reason",
            "summary", "media_url", "group_rules", "timestamp",
            "initial_status", "initial_reason",
            "detected_language", "language_confidence", "translated_message",
            "appeal_status", "appeal_text", "appeal_ai_status", "appeal_ai_reason",
            "appeal_submitted_at", "appeal_reviewed_by", "appeal_reviewed_at", "appeal_admin_note"
        ]
    }
}

# Per-file locks. A dict keyed by absolute path -> RLock.
# RLock because some flows may safely re-enter the same file lock in one thread.
_FILE_LOCKS = {}
_FILE_LOCKS_LOCK = threading.Lock()


def _lock_for(path):
    """Return the RLock guarding a given CSV file, creating it if needed."""
    abs_path = os.path.abspath(path)
    with _FILE_LOCKS_LOCK:
        if abs_path not in _FILE_LOCKS:
            _FILE_LOCKS[abs_path] = threading.RLock()
        return _FILE_LOCKS[abs_path]


class DBManager:
    """Handles database directory creation & CSV initialization."""

    @staticmethod
    def initialize():
        """Create database directory and empty CSV files if they don't exist."""
        os.makedirs(DATABASE_DIR, exist_ok=True)
        for name, schema in SCHEMAS.items():
            with _lock_for(schema["path"]):
                if not os.path.exists(schema["path"]):
                    pd.DataFrame(columns=schema["columns"]).to_csv(
                        schema["path"], index=False, encoding="utf-8"
                    )
                    logger.info(f"Created empty database file: {schema['path']}")
                else:
                    DBManager._migrate_schema(schema["path"], schema["columns"])

    @staticmethod
    def _migrate_schema(file_path, columns):
        """Add any missing schema columns to existing CSV files.
        Caller is expected to hold _lock_for(file_path).
        """
        df = pd.read_csv(file_path, encoding="utf-8")
        changed = False
        for column in columns:
            if column not in df.columns:
                df[column] = ""
                changed = True
        if changed:
            ordered = [c for c in columns if c in df.columns] + [c for c in df.columns if c not in columns]
            df = df[ordered]
            DBManager._atomic_write(file_path, df)
            logger.info(f"Migrated schema for: {file_path}")

    @staticmethod
    def read_csv(file_path, as_string=True):
        """Read a CSV file and return a DataFrame. Returns empty DataFrame with
        correct schema if missing. Thread-safe under the per-file lock.
        """
        with _lock_for(file_path):
            for name, schema in SCHEMAS.items():
                if schema["path"] == file_path:
                    if os.path.exists(file_path):
                        df = pd.read_csv(file_path, encoding="utf-8")
                        if as_string:
                            df = df.astype(str)
                            df = df.replace("nan", "")
                        return df
                    return pd.DataFrame(columns=schema["columns"])

            if os.path.exists(file_path):
                df = pd.read_csv(file_path, encoding="utf-8")
                return df.astype(str) if as_string else df
            return pd.DataFrame()

    @staticmethod
    def write_csv(file_path, dataframe):
        """Write a DataFrame to a CSV file atomically (tempfile + os.replace).
        Thread-safe under the per-file lock.
        """
        with _lock_for(file_path):
            DBManager._atomic_write(file_path, dataframe)

    @staticmethod
    def _atomic_write(file_path, dataframe):
        """Write to a temp file in the same directory, then atomic replace.
        Caller must already hold _lock_for(file_path).
        """
        abs_path = os.path.abspath(file_path)
        directory = os.path.dirname(abs_path) or "."
        fd, tmp_path = tempfile.mkstemp(
            prefix=".tmp_", suffix=".csv", dir=directory
        )
        try:
            os.close(fd)
            dataframe.to_csv(tmp_path, index=False, encoding="utf-8")
            os.replace(tmp_path, abs_path)
        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise

    @staticmethod
    def append_row(file_path, row_dict):
        """Append a single row to a CSV file. Read-modify-write is now safe
        because it holds the per-file RLock for the entire operation.
        """
        with _lock_for(file_path):
            df = DBManager.read_csv(file_path, as_string=False)
            new_row = pd.DataFrame([row_dict])
            df = pd.concat([df, new_row], ignore_index=True)
            DBManager._atomic_write(file_path, df)
