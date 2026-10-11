"""Gunicorn settings for production. Most hosts set PORT for you."""

import os

bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"

# Threads suit this app: most time is spent waiting on the AI provider.
worker_class = "gthread"
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
threads = int(os.getenv("GUNICORN_THREADS", "8"))

# AI calls (especially audio) can take a while.
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
graceful_timeout = 30
keepalive = 5

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
