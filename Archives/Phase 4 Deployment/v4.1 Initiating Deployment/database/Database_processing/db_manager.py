"""
ConvoEase — Database Manager
Central utilities for CSV database initialization, reading, and writing.
"""

import os
import pandas as pd
from config import DATABASE_DIR, USERS_FILE, GROUPS_FILE, MEMBERS_FILE, CHATS_FILE, setup_logging

logger = setup_logging("db_manager")

# Schema definitions — single source of truth for CSV columns
SCHEMAS = {
    "users": {
        "path": USERS_FILE,
        "columns": ["username", "password", "full_name", "bio", "profile_pic_color", "created_at"]
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


class DBManager:
    """Handles database directory creation & CSV initialization."""

    @staticmethod
    def initialize():
        """Create database directory and empty CSV files if they don't exist."""
        os.makedirs(DATABASE_DIR, exist_ok=True)
        for name, schema in SCHEMAS.items():
            if not os.path.exists(schema["path"]):
                pd.DataFrame(columns=schema["columns"]).to_csv(schema["path"], index=False, encoding="utf-8")
                logger.info(f"Created empty database file: {schema['path']}")
            else:
                DBManager._migrate_schema(schema["path"], schema["columns"])

    @staticmethod
    def _migrate_schema(file_path, columns):
        """Add any missing schema columns to existing CSV files."""
        df = pd.read_csv(file_path, encoding="utf-8")
        changed = False
        for column in columns:
            if column not in df.columns:
                df[column] = ""
                changed = True
        if changed:
            ordered = [c for c in columns if c in df.columns] + [c for c in df.columns if c not in columns]
            df = df[ordered]
            df.to_csv(file_path, index=False, encoding="utf-8")
            logger.info(f"Migrated schema for: {file_path}")

    @staticmethod
    def read_csv(file_path, as_string=True):
        """Read a CSV file and return a DataFrame. Returns empty DataFrame with correct schema if missing."""
        # Find matching schema
        for name, schema in SCHEMAS.items():
            if schema["path"] == file_path:
                if os.path.exists(file_path):
                    df = pd.read_csv(file_path, encoding="utf-8")
                    if as_string:
                        df = df.astype(str)
                        # Replace 'nan' strings with empty strings
                        df = df.replace("nan", "")
                    return df
                return pd.DataFrame(columns=schema["columns"])
        
        # Fallback for unknown files
        if os.path.exists(file_path):
            df = pd.read_csv(file_path, encoding="utf-8")
            return df.astype(str) if as_string else df
        return pd.DataFrame()

    @staticmethod
    def write_csv(file_path, dataframe):
        """Write a DataFrame to a CSV file (overwrites)."""
        dataframe.to_csv(file_path, index=False, encoding="utf-8")

    @staticmethod
    def append_row(file_path, row_dict):
        """Append a single row to a CSV file."""
        df = DBManager.read_csv(file_path, as_string=False)
        new_row = pd.DataFrame([row_dict])
        df = pd.concat([df, new_row], ignore_index=True)
        DBManager.write_csv(file_path, df)
