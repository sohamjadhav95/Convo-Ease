"""
ConvoEase — local development server.

Usage:
    python run.py

Opens on http://localhost:5000 by default. Settings come from environment
variables or a .env file (see .env.example). For production use gunicorn:
    gunicorn -c gunicorn.conf.py wsgi:app
"""

import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import create_app
from config import (
    AI_PROVIDER_PRESETS,
    APP_VERSION,
    AUDIO_MODEL_CONFIG,
    DATABASE_URL,
    DEBUG,
    HOST,
    IMAGE_MODEL_CONFIG,
    LEGACY_CSV_DIR,
    PORT,
    TEXT_MODEL_CONFIG,
)


def _should_disable_reloader():
    backend_configs = (TEXT_MODEL_CONFIG, IMAGE_MODEL_CONFIG, AUDIO_MODEL_CONFIG)
    if not any(config.get("backend") == "local" for config in backend_configs):
        return False

    try:
        import torch
        return torch.cuda.is_available()
    except Exception:
        return True


def _describe(config):
    if config.get("backend") == "local":
        return "local model"
    label = AI_PROVIDER_PRESETS[config["provider"]]["label"]
    key = "key set" if config.get("api_key") else "NO API KEY"
    return f"{label} · {config.get('api_model_id') or '-'} ({key})"


def _legacy_data_hint(app):
    """Point people upgrading from v4 at the one-time CSV import."""
    from database.Database_processing.db_manager import DBManager, users
    from sqlalchemy import func, select

    users_csv = os.path.join(LEGACY_CSV_DIR, "users.csv")
    with app.app_context():
        empty = not DBManager.scalar(select(func.count()).select_from(users))
    if empty and os.path.exists(users_csv):
        print("  Found v4 CSV data. Import it once with:")
        print("    python scripts/import_legacy_csv.py")


if __name__ == "__main__":
    app = create_app()
    disable_reloader = _should_disable_reloader()
    use_reloader = DEBUG and not disable_reloader
    print(f"\n{'='*60}")
    print(f"  ConvoEase v{APP_VERSION}")
    print(f"  Running on http://localhost:{PORT}")
    print(f"  Database:  {DATABASE_URL.split('://', 1)[0]}")
    print(f"  Text AI:   {_describe(TEXT_MODEL_CONFIG)}")
    print(f"  Image AI:  {_describe(IMAGE_MODEL_CONFIG)}")
    print(f"  Audio AI:  {_describe(AUDIO_MODEL_CONFIG)}")
    print(f"  Debug mode: {DEBUG}")
    if disable_reloader:
        print("  Flask reloader: disabled for local model stability")
    _legacy_data_hint(app)
    print(f"{'='*60}\n")
    app.run(
        host=HOST,
        port=PORT,
        debug=DEBUG,
        use_reloader=use_reloader,
        use_debugger=DEBUG,
    )
