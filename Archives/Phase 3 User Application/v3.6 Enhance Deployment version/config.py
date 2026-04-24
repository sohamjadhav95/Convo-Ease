"""
ConvoEase - Central Configuration
All paths, API settings, and logging are defined here.
No hardcoded system paths - everything is relative to this file's location.
"""

import os
import logging
from logging.handlers import RotatingFileHandler

# --- Paths -------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_DIR = os.path.join(BASE_DIR, "database", "Databases")
LOG_DIR = os.path.join(BASE_DIR, "logs")
FRONTEND_DIR = os.path.join(BASE_DIR, "Frontend")

MODELS_DIR = os.path.join(BASE_DIR, "Models")
TEXT_MODELS_DIR = os.path.join(MODELS_DIR, "Text")
IMAGE_MODELS_DIR = os.path.join(MODELS_DIR, "Image")
AUDIO_MODELS_DIR = os.path.join(MODELS_DIR, "Audio")

# Media storage - persists uploaded files across restarts
MEDIA_DIR = os.path.join(BASE_DIR, "database", "media")
MEDIA_IMAGE_DIR = os.path.join(MEDIA_DIR, "image")
MEDIA_AUDIO_DIR = os.path.join(MEDIA_DIR, "audio")
MEDIA_VIDEO_DIR = os.path.join(MEDIA_DIR, "video")

# CSV file paths
USERS_FILE = os.path.join(DATABASE_DIR, "users.csv")
GROUPS_FILE = os.path.join(DATABASE_DIR, "groups.csv")
MEMBERS_FILE = os.path.join(DATABASE_DIR, "group_members.csv")
CHATS_FILE = os.path.join(DATABASE_DIR, "group_chats.csv")

# --- API / Model Configuration -----------------------------------------------
# Set GROQ_API_KEY environment variable to override the default key.
_API_KEY = os.getenv(
    "GROQ_API_KEY",
    os.getenv("CONVOEASE_API_KEY", "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")
)
_API_BASE_URL = os.getenv(
    "GROQ_API_URL",
    os.getenv("CONVOEASE_API_URL", "https://api.groq.com/openai/v1")
)

GLOBAL_MODEL_MODE = os.getenv("CONVOEASE_MODEL_MODE", "api") # Can be "api" or "local", overridden by specific model configs below.

TEXT_MODEL_CONFIG = {
    "backend": os.getenv("CONVOEASE_TEXT_BACKEND", GLOBAL_MODEL_MODE),
    "api_key": _API_KEY,
    "base_url": _API_BASE_URL,
    "api_model_id": os.getenv("CONVOEASE_TEXT_MODEL_ID", "openai/gpt-oss-120b"),
    "local_model_path": os.getenv("CONVOEASE_TEXT_MODEL_PATH", TEXT_MODELS_DIR),
    "local_model_type": os.getenv("CONVOEASE_TEXT_MODEL_TYPE", "causal-lm"),
}

IMAGE_MODEL_CONFIG = {
    "backend": os.getenv("CONVOEASE_IMAGE_BACKEND", GLOBAL_MODEL_MODE),
    "api_key": _API_KEY,
    "base_url": _API_BASE_URL,
    "api_model_id": os.getenv("CONVOEASE_IMAGE_MODEL_ID", "meta-llama/llama-4-scout-17b-16e-instruct"),
    "local_model_path": os.getenv("CONVOEASE_IMAGE_MODEL_PATH", IMAGE_MODELS_DIR),
    "local_model_type": os.getenv("CONVOEASE_IMAGE_MODEL_TYPE", "image-text-to-text"),
}

AUDIO_MODEL_CONFIG = {
    "backend": os.getenv("CONVOEASE_AUDIO_BACKEND", GLOBAL_MODEL_MODE),
    "api_key": _API_KEY,
    "base_url": _API_BASE_URL,
    "api_model_id": os.getenv("CONVOEASE_AUDIO_MODEL_ID", "whisper-large-v3-turbo"),
    "local_model_path": os.getenv("CONVOEASE_AUDIO_MODEL_PATH", AUDIO_MODELS_DIR),
    "local_model_type": os.getenv("CONVOEASE_AUDIO_MODEL_TYPE", "automatic-speech-recognition"),
    "api_summary_model_id": os.getenv("CONVOEASE_AUDIO_SUMMARY_MODEL_ID", "llama-3.1-8b-instant"),
}

# Backwards-compatible aliases used across the current codebase.
MODEL_CONFIG = TEXT_MODEL_CONFIG
VISION_MODEL_CONFIG = IMAGE_MODEL_CONFIG

# --- Server Settings ---------------------------------------------------------
HOST = os.getenv("CONVOEASE_HOST", "0.0.0.0")
PORT = int(os.getenv("CONVOEASE_PORT", "5000"))
DEBUG = os.getenv("CONVOEASE_DEBUG", "true").lower() == "true"
SECRET_KEY = os.getenv("CONVOEASE_SECRET_KEY", "convoease-dev-secret-key-change-in-prod")

# --- Logging Setup -----------------------------------------------------------
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(DATABASE_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(TEXT_MODELS_DIR, exist_ok=True)
os.makedirs(IMAGE_MODELS_DIR, exist_ok=True)
os.makedirs(AUDIO_MODELS_DIR, exist_ok=True)
os.makedirs(MEDIA_IMAGE_DIR, exist_ok=True)
os.makedirs(MEDIA_AUDIO_DIR, exist_ok=True)
os.makedirs(MEDIA_VIDEO_DIR, exist_ok=True)

LOG_LEVEL = getattr(logging, os.getenv("CONVOEASE_LOG_LEVEL", "INFO").upper(), logging.INFO)


def setup_logging(name="convoease"):
    """Configure and return a logger with console + file handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)

    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "app.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger
