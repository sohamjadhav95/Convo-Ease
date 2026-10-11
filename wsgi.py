"""
Production entry point.

    gunicorn -c gunicorn.conf.py wsgi:app
"""

from main import create_app

app = create_app()
