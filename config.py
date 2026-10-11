"""
ConvoEase - Central Configuration
All paths, database, AI provider, server, and logging settings live here.
Everything can be overridden with environment variables (or a local .env file).
"""

APP_VERSION = "5.0"

import json
import os
import logging
from logging.handlers import RotatingFileHandler

try:  # Load a local .env file when python-dotenv is installed.
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:  # pragma: no cover - optional dependency
    pass


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


# --- Environment -------------------------------------------------------------
ENV = os.getenv("CONVOEASE_ENV", "development").strip().lower()
IS_PRODUCTION = ENV == "production"

# --- Paths -------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "Frontend")
DATA_DIR = os.getenv("CONVOEASE_DATA_DIR", os.path.join(BASE_DIR, "database"))
LOG_DIR = os.getenv("CONVOEASE_LOG_DIR", os.path.join(BASE_DIR, "logs"))

MODELS_DIR = os.path.join(BASE_DIR, "Models")
TEXT_MODELS_DIR = os.path.join(MODELS_DIR, "Text")
IMAGE_MODELS_DIR = os.path.join(MODELS_DIR, "Image")
AUDIO_MODELS_DIR = os.path.join(MODELS_DIR, "Audio")

# Legacy storage (v4 and earlier). Only used by the one-time CSV import and as a
# read-only fallback for media files that were never imported into the database.
LEGACY_CSV_DIR = os.path.join(BASE_DIR, "database", "Databases")
MEDIA_DIR = os.path.join(BASE_DIR, "database", "media")

# --- Database ----------------------------------------------------------------
# Local default: a SQLite file. In production, point DATABASE_URL at a hosted
# Postgres database (Neon, Supabase, Render...) so data survives redeploys.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or (
    "sqlite:///" + os.path.join(DATA_DIR, "convoease.db")
)

# --- Upload limits -----------------------------------------------------------
MAX_IMAGE_BYTES = int(os.getenv("CONVOEASE_MAX_IMAGE_MB", "8")) * 1024 * 1024
MAX_AUDIO_BYTES = int(os.getenv("CONVOEASE_MAX_AUDIO_MB", "10")) * 1024 * 1024
# Requests carry base64 (about 4/3 of the raw size) plus some JSON overhead.
MAX_REQUEST_BYTES = int(max(MAX_IMAGE_BYTES, MAX_AUDIO_BYTES) * 1.4) + 64 * 1024

# --- AI provider configuration -----------------------------------------------
# Every provider below speaks the OpenAI-compatible chat API, so one code path
# serves all of them. Pick one with CONVOEASE_AI_PROVIDER, or let it be picked
# from whichever API key is set.
AI_PROVIDER_PRESETS = {
    "gemini": {
        "label": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_envs": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "text_model": "gemini-3.5-flash-lite",
        "image_model": "gemini-3.5-flash-lite",
        "audio_model": "gemini-3.5-flash-lite",
        # Gemini understands audio directly inside a chat request,
        # but only as WAV or MP3 (the web app converts recordings to WAV).
        "audio_mode": "chat",
        "audio_formats": ("wav", "mp3"),
    },
    "groq": {
        "label": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "key_envs": ("GROQ_API_KEY",),
        "text_model": "openai/gpt-oss-120b",
        "image_model": "meta-llama/llama-4-scout-17b-16e-instruct",
        "audio_model": "whisper-large-v3-turbo",
        "audio_mode": "transcription",
    },
    "nvidia": {
        "label": "NVIDIA NIM",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "key_envs": ("NVIDIA_API_KEY", "NVIDIA_NIM_API_KEY"),
        "text_model": "openai/gpt-oss-120b",
        "image_model": "meta/llama-3.2-90b-vision-instruct",
        # NVIDIA's hosted API has no OpenAI-style speech endpoint. Use local
        # Whisper or set CONVOEASE_AUDIO_PROVIDER to another provider.
        "audio_model": "",
        "audio_mode": "none",
    },
    "custom": {
        "label": "Custom OpenAI-compatible API",
        "base_url": "",
        "key_envs": (),
        "text_model": "",
        "image_model": "",
        "audio_model": "",
        "audio_mode": "transcription",
    },
}


def _first_env(names):
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _default_provider():
    configured = os.getenv("CONVOEASE_AI_PROVIDER", "").strip().lower()
    if configured:
        return configured
    for name in ("gemini", "nvidia", "groq"):
        if _first_env(AI_PROVIDER_PRESETS[name]["key_envs"]):
            return name
    return "gemini"


AI_PROVIDER = _default_provider()
if AI_PROVIDER not in AI_PROVIDER_PRESETS:
    raise ValueError(
        f"Unknown CONVOEASE_AI_PROVIDER '{AI_PROVIDER}'. "
        f"Choose one of: {', '.join(AI_PROVIDER_PRESETS)}."
    )


def _provider_settings(provider):
    preset = AI_PROVIDER_PRESETS[provider]
    is_main = provider == AI_PROVIDER
    api_key = _first_env(preset["key_envs"])
    base_url = preset["base_url"]
    if is_main:
        # Generic overrides apply to the main provider only.
        api_key = os.getenv("CONVOEASE_API_KEY", "").strip() or api_key
        base_url = os.getenv("CONVOEASE_API_URL", "").strip() or base_url
    return preset, api_key, base_url


def _modality_config(modality):
    upper = modality.upper()
    provider = os.getenv(f"CONVOEASE_{upper}_PROVIDER", "").strip().lower() or AI_PROVIDER
    if provider not in AI_PROVIDER_PRESETS:
        raise ValueError(f"Unknown CONVOEASE_{upper}_PROVIDER '{provider}'.")
    preset, api_key, base_url = _provider_settings(provider)
    return {
        "provider": provider,
        "provider_label": preset["label"],
        "api_key": api_key,
        "base_url": base_url,
        "api_model_id": os.getenv(f"CONVOEASE_{upper}_MODEL_ID", "").strip() or preset[f"{modality}_model"],
        "api_timeout_seconds": int(os.getenv("CONVOEASE_API_TIMEOUT", "60")),
        "audio_formats": preset.get("audio_formats", ()),
        "reasoning_effort": os.getenv("CONVOEASE_REASONING_EFFORT", "").strip().lower(),
        "audio_mode": preset["audio_mode"],
    }


# "api" (default) uses the hosted provider. "local" runs Hugging Face / Whisper
# models on this machine and needs the packages in requirements-local.txt.
GLOBAL_MODEL_MODE = os.getenv("CONVOEASE_MODEL_MODE", "api").strip().lower()

TEXT_MODEL_CONFIG = {
    **_modality_config("text"),
    "backend": os.getenv("CONVOEASE_TEXT_BACKEND", GLOBAL_MODEL_MODE).strip().lower(),
    "local_model_path": os.getenv("CONVOEASE_TEXT_MODEL_PATH", TEXT_MODELS_DIR),
    "local_model_type": os.getenv("CONVOEASE_TEXT_MODEL_TYPE", "causal-lm"),
    "local_device_preference": os.getenv("CONVOEASE_TEXT_DEVICE_PREFERENCE", "cuda"),
    "allow_cpu_offload": os.getenv("CONVOEASE_TEXT_ALLOW_CPU_OFFLOAD", "true"),
}

IMAGE_MODEL_CONFIG = {
    **_modality_config("image"),
    "backend": os.getenv("CONVOEASE_IMAGE_BACKEND", GLOBAL_MODEL_MODE).strip().lower(),
    "local_model_path": os.getenv("CONVOEASE_IMAGE_MODEL_PATH", TEXT_MODELS_DIR),
    "local_model_type": os.getenv("CONVOEASE_IMAGE_MODEL_TYPE", "image-text-to-text"),
}

_audio_api = _modality_config("audio")
AUDIO_MODEL_CONFIG = {
    **_audio_api,
    # A provider without a speech API falls back to local Whisper.
    "backend": os.getenv(
        "CONVOEASE_AUDIO_BACKEND",
        "local" if _audio_api["audio_mode"] == "none" else GLOBAL_MODEL_MODE,
    ).strip().lower(),
    "local_model_path": os.getenv("CONVOEASE_AUDIO_MODEL_PATH", AUDIO_MODELS_DIR),
    "whisper_model_size": os.getenv("CONVOEASE_WHISPER_SIZE", "base"),
    "local_model_type": os.getenv("CONVOEASE_AUDIO_MODEL_TYPE", "automatic-speech-recognition"),
    # Transcript summaries run on the text model unless overridden.
    "api_summary_model_id": os.getenv("CONVOEASE_AUDIO_SUMMARY_MODEL_ID", "").strip()
    or TEXT_MODEL_CONFIG["api_model_id"],
}

# Backwards-compatible aliases used across the codebase.
MODEL_CONFIG = TEXT_MODEL_CONFIG
VISION_MODEL_CONFIG = IMAGE_MODEL_CONFIG

# --- Server Settings ---------------------------------------------------------
HOST = os.getenv("CONVOEASE_HOST", "0.0.0.0")
PORT = int(os.getenv("PORT") or os.getenv("CONVOEASE_PORT", "5000"))
DEBUG = _env_bool("CONVOEASE_DEBUG", default=not IS_PRODUCTION)
_DEV_SECRET = "convoease-dev-secret-key-change-in-prod"
SECRET_KEY = os.getenv("CONVOEASE_SECRET_KEY", "").strip() or _DEV_SECRET
if IS_PRODUCTION and SECRET_KEY == _DEV_SECRET:
    raise RuntimeError(
        "CONVOEASE_SECRET_KEY must be set in production. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
# Cookies are sent only over HTTPS in production.
SESSION_COOKIE_SECURE = _env_bool("CONVOEASE_SECURE_COOKIES", default=IS_PRODUCTION)
SESSION_DAYS = int(os.getenv("CONVOEASE_SESSION_DAYS", "30"))
# Behind a hosting proxy (Render, Koyeb, HF Spaces...) the client IP arrives in
# X-Forwarded-For; trust one proxy hop so rate limits see real client IPs.
TRUST_PROXY = _env_bool("CONVOEASE_TRUST_PROXY", default=IS_PRODUCTION)
# Simple per-user / per-IP request limits that protect your free AI quota.
RATE_LIMITS_ENABLED = _env_bool("CONVOEASE_RATE_LIMITS", default=True)

# --- Logging Setup -----------------------------------------------------------
# Hosted platforms collect stdout, so file logs are off by default in production.
LOG_TO_FILE = _env_bool("CONVOEASE_LOG_TO_FILE", default=not IS_PRODUCTION)
LOG_LEVEL = getattr(logging, os.getenv("CONVOEASE_LOG_LEVEL", "INFO").upper(), logging.INFO)

if DATABASE_URL.startswith("sqlite:///"):
    os.makedirs(os.path.dirname(os.path.abspath(DATABASE_URL[len("sqlite:///"):])), exist_ok=True)
if LOG_TO_FILE:
    os.makedirs(LOG_DIR, exist_ok=True)


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
    """Configure and return a logger with console (+ optional file) handlers."""
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

    if not LOG_TO_FILE:
        return logger

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
