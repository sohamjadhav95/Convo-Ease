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
from config import HOST, PORT, DEBUG

if __name__ == "__main__":
    app = create_app()
    print(f"\n{'='*50}")
    print(f"  ConvoEase v3.5")
    print(f"  Running on http://localhost:{PORT}")
    print(f"  Debug mode: {DEBUG}")
    print(f"{'='*50}\n")
    app.run(host=HOST, port=PORT, debug=DEBUG)
