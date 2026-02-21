"""
ConvoEase — Central Configuration
All paths, API settings, and logging are defined here.
No hardcoded system paths — everything is relative to this file's location.
"""

import os
import logging
from logging.handlers import RotatingFileHandler

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_DIR = os.path.join(BASE_DIR, "database", "Databases")
LOG_DIR = os.path.join(BASE_DIR, "logs")
FRONTEND_DIR = os.path.join(BASE_DIR, "Frontend")

# CSV file paths
USERS_FILE = os.path.join(DATABASE_DIR, "users.csv")
GROUPS_FILE = os.path.join(DATABASE_DIR, "groups.csv")
MEMBERS_FILE = os.path.join(DATABASE_DIR, "group_members.csv")
CHATS_FILE = os.path.join(DATABASE_DIR, "group_chats.csv")

# ─── API / Model Configuration ───────────────────────────────────────────────
# Set CONVOEASE_API_KEY environment variable to override the default key.
MODEL_CONFIG = {
    "mode": os.getenv("CONVOEASE_MODEL_MODE", "api"),  # "api" or "local"

    # --- API mode settings ---
    "api_key": os.getenv(
        "CONVOEASE_API_KEY",
        "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"
    ),
    "base_url": os.getenv("CONVOEASE_API_URL", "https://openrouter.ai/api/v1"),
    "model": os.getenv("CONVOEASE_MODEL_NAME", "openai/gpt-oss-120b:free"),

    # --- Local mode settings (future) ---
    "model_path": os.getenv("CONVOEASE_LOCAL_MODEL_PATH", ""),
    "model_type": os.getenv("CONVOEASE_LOCAL_MODEL_TYPE", ""),
}

# ─── Server Settings ─────────────────────────────────────────────────────────
HOST = os.getenv("CONVOEASE_HOST", "0.0.0.0")
PORT = int(os.getenv("CONVOEASE_PORT", "5000"))
DEBUG = os.getenv("CONVOEASE_DEBUG", "true").lower() == "true"
SECRET_KEY = os.getenv("CONVOEASE_SECRET_KEY", "convoease-dev-secret-key-change-in-prod")

# ─── Logging Setup ───────────────────────────────────────────────────────────
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(DATABASE_DIR, exist_ok=True)

LOG_LEVEL = getattr(logging, os.getenv("CONVOEASE_LOG_LEVEL", "INFO").upper(), logging.INFO)

def setup_logging(name="convoease"):
    """Configure and return a logger with console + file handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    # File handler with rotation (5 MB max, keep 3 backups)
    file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "app.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger
