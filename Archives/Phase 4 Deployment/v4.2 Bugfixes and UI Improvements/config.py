"""
ConvoEase - Central Configuration
All paths, API settings, and logging are defined here.
No hardcoded system paths - everything is relative to this file's location.
"""

import json
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
# Hosted API credentials must come from environment variables.
_API_KEY = os.getenv(
    "GROQ_API_KEY",
    os.getenv("CONVOEASE_API_KEY", "")
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
    "local_device_preference": os.getenv("CONVOEASE_TEXT_DEVICE_PREFERENCE", "cuda"),
    "allow_cpu_offload": os.getenv("CONVOEASE_TEXT_ALLOW_CPU_OFFLOAD", "true"),
}

IMAGE_MODEL_CONFIG = {
    "backend": os.getenv("CONVOEASE_IMAGE_BACKEND", GLOBAL_MODEL_MODE),
    "api_key": _API_KEY,
    "base_url": _API_BASE_URL,
    "api_model_id": os.getenv("CONVOEASE_IMAGE_MODEL_ID", "meta-llama/llama-4-scout-17b-16e-instruct"),
    "local_model_path": os.getenv("CONVOEASE_IMAGE_MODEL_PATH", TEXT_MODELS_DIR),
    "local_model_type": os.getenv("CONVOEASE_IMAGE_MODEL_TYPE", "image-text-to-text"),
}

AUDIO_MODEL_CONFIG = {
    "backend": os.getenv("CONVOEASE_AUDIO_BACKEND", GLOBAL_MODEL_MODE),
    "api_key": _API_KEY,
    "base_url": _API_BASE_URL,
    "api_model_id": os.getenv("CONVOEASE_AUDIO_MODEL_ID", "whisper-large-v3-turbo"),
    "local_model_path": os.getenv("CONVOEASE_AUDIO_MODEL_PATH", AUDIO_MODELS_DIR),
    "whisper_model_size": os.getenv("CONVOEASE_WHISPER_SIZE", "base"),
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


class StructuredFormatter(logging.Formatter):
    """Formatter that keeps logs human-readable while exposing structured context."""

    DEFAULTS = {
        "category": "-",
        "event": "-",
        "request_id": "-",
        "user": "-",
        "group_id": "-",
        "message_id": "-",
        "status_code": "-",
        "details": "",
    }

    def format(self, record):
        for key, default in self.DEFAULTS.items():
            if not hasattr(record, key):
                setattr(record, key, default)

        if isinstance(record.details, (dict, list, tuple)):
            try:
                record.details = json.dumps(record.details, ensure_ascii=True, sort_keys=True)
            except TypeError:
                record.details = str(record.details)
        elif record.details in (None, "-"):
            record.details = ""

        return super().format(record)


class CategoryFilter(logging.Filter):
    def __init__(self, categories):
        super().__init__()
        self.categories = set(categories)

    def filter(self, record):
        return getattr(record, "category", "-") in self.categories


class MinLevelFilter(logging.Filter):
    def __init__(self, level):
        super().__init__()
        self.level = level

    def filter(self, record):
        return record.levelno >= self.level


def _build_handler(path, formatter, level=None, filters=None):
    handler = RotatingFileHandler(
        path,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    handler.setFormatter(formatter)
    if level is not None:
        handler.setLevel(level)
    for log_filter in filters or []:
        handler.addFilter(log_filter)
    return handler


def setup_logging(name="convoease"):
    """Configure and return a logger with console + file handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)
    logger.propagate = False

    if logger.handlers:
        return logger

    fmt = StructuredFormatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] "
        "[category=%(category)s event=%(event)s request=%(request_id)s user=%(user)s "
        "group=%(group_id)s message=%(message_id)s status=%(status_code)s] %(message)s %(details)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    logger.addHandler(_build_handler(os.path.join(LOG_DIR, "app.log"), fmt))
    logger.addHandler(_build_handler(
        os.path.join(LOG_DIR, "errors.log"),
        fmt,
        level=logging.WARNING,
        filters=[MinLevelFilter(logging.WARNING)],
    ))
    logger.addHandler(_build_handler(
        os.path.join(LOG_DIR, "moderation.log"),
        fmt,
        filters=[CategoryFilter({"moderation", "media", "appeal", "report"})],
    ))
    logger.addHandler(_build_handler(
        os.path.join(LOG_DIR, "audit.log"),
        fmt,
        filters=[CategoryFilter({"auth", "group", "settings", "system"})],
    ))
    if LOG_LEVEL == logging.DEBUG:
        logger.addHandler(_build_handler(
            os.path.join(LOG_DIR, "debug.log"),
            fmt,
            level=logging.DEBUG,
        ))

    return logger


def log_event(logger, level, event, message, category="application", **context):
    """Write a structured log entry without breaking normal logger usage."""
    details = context.pop("details", "")
    extra = {
        "category": category,
        "event": event,
        "request_id": context.pop("request_id", "-") or "-",
        "user": context.pop("user", "-") or "-",
        "group_id": context.pop("group_id", "-") or "-",
        "message_id": context.pop("message_id", "-") or "-",
        "status_code": context.pop("status_code", "-") or "-",
        "details": details or context or "",
    }
    logger.log(level, message, extra=extra)
