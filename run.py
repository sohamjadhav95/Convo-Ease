"""
ConvoEase — Application Entry Point
Run this file to start the server.

Usage:
    python run.py

The server will start on http://localhost:5000 by default.
Configure host/port via environment variables:
    CONVOEASE_HOST (default: 0.0.0.0)
    CONVOEASE_PORT (default: 5000)
    CONVOEASE_DEBUG (default: true)
"""

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import create_app
from config import HOST, PORT, DEBUG, TEXT_MODEL_CONFIG, IMAGE_MODEL_CONFIG, AUDIO_MODEL_CONFIG


def _should_disable_reloader():
    backend_configs = (TEXT_MODEL_CONFIG, IMAGE_MODEL_CONFIG, AUDIO_MODEL_CONFIG)
    if not any(config.get("backend") == "local" for config in backend_configs):
        return False

    try:
        import torch
        return torch.cuda.is_available()
    except Exception:
        return True

if __name__ == "__main__":
    app = create_app()
    disable_reloader = _should_disable_reloader()
    use_reloader = DEBUG and not disable_reloader
    print(f"\n{'='*50}")
    print(f"  ConvoEase v3.5")
    print(f"  Running on http://localhost:{PORT}")
    print(f"  Debug mode: {DEBUG}")
    if disable_reloader:
        print("  Flask reloader: disabled for local model stability")
    print(f"{'='*50}\n")
    app.run(
        host=HOST,
        port=PORT,
        debug=DEBUG,
        use_reloader=use_reloader,
        use_debugger=DEBUG,
    )
