# ConvoEase production image (~400 MB). Works on Render, Koyeb, Fly.io,
# Railway, Google Cloud Run and Hugging Face Spaces.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CONVOEASE_ENV=production \
    PORT=7860

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Run as an unprivileged user (uid 1000 is what Hugging Face Spaces expects).
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app/database \
    && chown -R app:app /app/database
USER app

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"7860\")}/healthz', timeout=4)"

CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
