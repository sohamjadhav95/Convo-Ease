"""
ConvoEase — Main Application
Flask app factory with REST API endpoints.

Who is calling is always taken from the signed session cookie set at login,
never from usernames sent in request bodies.
"""

import base64
import binascii
import io
import json
import logging
import os
import sys
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import timedelta
from functools import wraps

from flask import Flask, Response, g, jsonify, request, send_file, send_from_directory, session
from sqlalchemy import text as sql_text
from werkzeug.middleware.proxy_fix import ProxyFix

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    AI_PROVIDER,
    AI_PROVIDER_PRESETS,
    APP_VERSION,
    AUDIO_MODEL_CONFIG,
    FRONTEND_DIR,
    IMAGE_MODEL_CONFIG,
    MAX_AUDIO_BYTES,
    MAX_IMAGE_BYTES,
    MAX_REQUEST_BYTES,
    MEDIA_DIR,
    RATE_LIMITS_ENABLED,
    SECRET_KEY,
    SESSION_COOKIE_SECURE,
    SESSION_DAYS,
    TEXT_MODEL_CONFIG,
    TRUST_PROXY,
    log_event,
    setup_logging,
)
from database.Database_processing import DBManager, GroupStore, MediaStore, MessageStore, UserStore
from database.Database_processing.media_store import audio_format, sniff_image
from core_processing_engine import ProcessingEngine, TextModerationPlugin, ImageModerationPlugin, AudioModerationPlugin

logger = setup_logging("main")

MAX_MESSAGE_CHARS = 4000
DEFAULT_MESSAGE_PAGE = 200
MAX_MESSAGE_PAGE = 500

_SILENT_REQUEST_ROUTES = {
    "GET:/api/groups",
    "GET:/api/groups/<group_id>/messages",
    "GET:/api/auth/me",
}


def _request_context():
    return {
        "request_id": getattr(g, "request_id", "-"),
        "user": getattr(g, "request_user", "-"),
        "group_id": getattr(g, "request_group_id", "-"),
    }


def _bind_request_context(user=None, group_id=None):
    if user:
        g.request_user = user
    if group_id:
        g.request_group_id = group_id


def _payload_preview(value, limit=140):
    text = str(value or "").strip().replace("\n", " ")
    return text[:limit] + ("..." if len(text) > limit else "")


def _request_route_key():
    route_rule = getattr(request.url_rule, "rule", None)
    return f"{request.method}:{route_rule or request.path}"


def _should_skip_request_log():
    return request.path.startswith("/api/") and _request_route_key() in _SILENT_REQUEST_ROUTES


def _plugin_backend_name(plugin):
    if not plugin:
        return "-"
    return getattr(plugin, "backend", getattr(plugin, "config", {}).get("backend", "-"))


_BACKEND_FAILURE_MARKERS = (
    "moderation error:",
    "invalid api key",
    "temporarily unavailable",
    "processing error:",
)


def _is_backend_failure_reason(reason):
    text = str(reason or "").strip().lower()
    if not text:
        return False
    return any(marker in text for marker in _BACKEND_FAILURE_MARKERS)


def _is_system_moderation_result(result):
    result = result or {}
    return bool(result.get("system_error")) or _is_backend_failure_reason(result.get("reason", ""))


def _service_unavailable_message(kind):
    return f"{kind} moderation is temporarily unavailable. Please try again later."


def _extract_bullets(text, min_items=3, max_items=5):
    bullets = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(("-", "*", "•")):
            line = line[1:].strip()
        elif line[:2].isdigit() and line[2:3] in {".", ")"}:
            line = line[3:].strip()
        elif line[:1].isdigit() and line[1:2] in {".", ")"}:
            line = line[2:].strip()
        line = line.replace("**", "").strip()
        if line:
            bullets.append(line)
    return bullets[:max_items] if bullets else []


def _fallback_summary_items(timeline):
    if not timeline:
        return ["No recent conversation yet."]

    bullets = []
    participants = sorted({item["username"] for item in timeline if item.get("username")})
    if participants:
        bullets.append(f"Active participants: {', '.join(participants[:5])}.")

    latest = timeline[-3:]
    for item in latest:
        content = item.get("content", "").strip()
        if content:
            bullets.append(f"{item['username']} discussed: {content[:110]}")

    return bullets[:5]


def _fallback_rule_suggestions(rules_text):
    rules_lower = (rules_text or "").lower()
    suggestions = []

    if "respect" not in rules_lower and "harass" not in rules_lower:
        suggestions.append("Add a civility rule covering harassment, insults, and personal attacks.")
    if "spam" not in rules_lower:
        suggestions.append("Add a spam rule to prevent repeated or promotional messages.")
    if "off-topic" not in rules_lower and "relevant" not in rules_lower:
        suggestions.append("Clarify what counts as on-topic content for the group.")
    if "image" not in rules_lower and "audio" not in rules_lower:
        suggestions.append("Mention that uploaded images and audio must follow the same rules as text.")

    revised = (rules_text or "").strip()
    if revised and not revised.endswith("."):
        revised += "."
    if suggestions:
        revised += "\n- Be respectful and avoid harassment.\n- No spam or repeated promotional content.\n- Text, images, and audio must stay relevant to the group purpose."

    return {
        "suggestions": suggestions[:4],
        "revised_rules": revised.strip() or "Be respectful. No spam. Stay relevant to the group purpose.",
    }


def _normalize_sensitivity(value):
    normalized = str(value or "Moderate").strip().lower()
    mapping = {
        "strict": "Strict",
        "moderate": "Moderate",
        "relaxed": "Relaxed",
    }
    return mapping.get(normalized, "Moderate")


def _run_appeal_review(run_text_task, message_row, group, appeal_text):
    fallback = {
        "status": "FLAGGED",
        "reason": "Original moderation decision stands pending admin review.",
    }
    original_reason = (
        message_row.get("initial_reason")
        or message_row.get("reason")
        or "Previously flagged by moderation."
    )
    sensitivity = _normalize_sensitivity(group.get("moderation_sensitivity", "Moderate"))
    ai_text = run_text_task(
        "You re-evaluate moderated chat messages after a user appeal.",
        (
            "Review the original moderation decision and the member's appeal. "
            "Use the group rules as primary authority and the group's moderation sensitivity as the strictness level. "
            "Return exactly one of these formats:\n"
            "PASS <reason>\n"
            "FLAGGED <reason>\n\n"
            f"Group rules:\n{group.get('rules', '')}\n\n"
            f"Moderation sensitivity: {sensitivity}\n"
            f"Original message: {MessageStore._display_message(message_row)}\n"
            f"Original flag reason: {original_reason}\n"
            f"Appeal explanation: {appeal_text}\n"
        ),
        fallback_text="",
    ).strip()

    if not ai_text:
        return fallback

    parsed = TextModerationPlugin._parse_response(ai_text)
    return {
        "status": "PASS" if parsed["allowed"] else "FLAGGED",
        "reason": parsed["reason"] or fallback["reason"],
    }


def safe_json(data, status=200):
    """Serialise data to a JSON Response."""
    return Response(
        json.dumps(data, default=str),
        status=status,
        mimetype="application/json"
    )


def _error(message, http_status, **extra):
    return safe_json({"success": False, "message": message, **extra}, status=http_status)


def _service_unavailable_response(kind):
    return safe_json(
        {
            "success": False,
            "status": "UNAVAILABLE",
            "message": _service_unavailable_message(kind),
        },
        status=503,
    )


def _json_body():
    return request.get_json(silent=True) or {}


def _decode_base64(payload):
    """Decode a base64 string (optionally a data: URL). Returns bytes or None."""
    payload = (payload or "").strip()
    if payload.startswith("data:") and "," in payload:
        payload = payload.split(",", 1)[1]
    try:
        return base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        return None


def _public_message(row):
    """Message fields sent to clients (the per-message rules snapshot stays server-side)."""
    item = dict(row)
    item.pop("group_rules", None)
    return item


class RateLimiter:
    """Sliding-window limiter kept in memory (per worker process)."""

    def __init__(self):
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key, limit, window_seconds):
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True


# Scripts only from this site; Google Fonts for typography and icons.
CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: blob:",
    "media-src 'self' blob:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])

# (max requests, window in seconds) per bucket
RATE_LIMITS = {
    "auth": (10, 60),      # per IP: login / register attempts
    "message": (30, 60),   # per user: text messages
    "media": (10, 60),     # per user: image / audio uploads
    "ai": (12, 60),        # per user: catch-up, rule suggestions, appeals
}


def create_app(test_config=None):
    """Application factory — creates and configures the Flask app."""
    app = Flask(
        __name__,
        static_folder=None,
    )
    app.config.update(
        SECRET_KEY=SECRET_KEY,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=SESSION_COOKIE_SECURE,
        SESSION_COOKIE_NAME="convoease_session",
        PERMANENT_SESSION_LIFETIME=timedelta(days=SESSION_DAYS),
        MAX_CONTENT_LENGTH=MAX_REQUEST_BYTES,
        RATE_LIMITS_ENABLED=RATE_LIMITS_ENABLED,
        DATABASE_URL=None,
    )
    if test_config:
        app.config.update(test_config)
    if TRUST_PROXY:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    limiter = RateLimiter()

    def rate_limited(bucket, key):
        if not app.config.get("RATE_LIMITS_ENABLED", True):
            return None
        limit, window = RATE_LIMITS[bucket]
        if limiter.allow(f"{bucket}:{key}", limit, window):
            return None
        return _error("Too many requests. Please slow down and try again in a minute.", 429, status="RATE_LIMITED")

    @app.before_request
    def attach_request_metadata():
        g.request_id = str(uuid.uuid4())[:8]
        g.request_started_at = time.perf_counter()
        g.request_user = session.get("username", "-")
        g.request_group_id = request.view_args.get("group_id", "-") if request.view_args else "-"
        g.skip_request_log = _should_skip_request_log()
        if request.path.startswith("/api/") and not g.skip_request_log:
            log_event(
                logger,
                logging.INFO,
                "request_started",
                f"{request.method} {request.path}",
                category="request",
                request_id=g.request_id,
                user=g.request_user,
                group_id=g.request_group_id,
                details={"remote_addr": request.remote_addr or "-"},
            )

    @app.after_request
    def finalize_response(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        if response.mimetype == "text/html":
            response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        if request.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        if request.path.startswith("/api/") and (
            not getattr(g, "skip_request_log", False) or response.status_code >= 400
        ):
            duration_ms = round((time.perf_counter() - getattr(g, "request_started_at", time.perf_counter())) * 1000, 2)
            level = logging.WARNING if response.status_code >= 400 else logging.INFO
            log_event(
                logger,
                level,
                "request_completed",
                f"{request.method} {request.path}",
                category="request",
                request_id=getattr(g, "request_id", "-"),
                user=getattr(g, "request_user", "-"),
                group_id=getattr(g, "request_group_id", "-"),
                status_code=response.status_code,
                details={"duration_ms": duration_ms},
            )
        return response

    @app.errorhandler(413)
    def too_large(_exc):
        limit_mb = max(MAX_IMAGE_BYTES, MAX_AUDIO_BYTES) // (1024 * 1024)
        return _error(f"Upload is too large (max {limit_mb} MB).", 413)

    # ── Initialize Database ──────────────────────────────────────────────
    DBManager.initialize(app.config.get("DATABASE_URL"))
    log_event(logger, logging.INFO, "database_initialized", "Database initialized", category="system")

    # ── Initialize Processing Engine ─────────────────────────────────────
    engine = ProcessingEngine()
    plugin_health = {}

    def register_processing_plugin(plugin_name, factory, config=None, level=logging.WARNING):
        backend = (config or {}).get("backend", "-")
        try:
            plugin = factory()
            engine.register_plugin(plugin)
            plugin_health[plugin_name] = {"status": "ready", "backend": backend}
            log_event(
                logger,
                logging.INFO,
                "plugin_ready",
                f"{plugin_name} initialized",
                category="system",
                details={"plugin": plugin_name, "backend": backend},
            )
            return plugin
        except Exception as exc:
            plugin_health[plugin_name] = {
                "status": "unavailable",
                "backend": backend,
                "error": str(exc),
            }
            log_event(
                logger,
                level,
                "plugin_unavailable",
                f"{plugin_name} unavailable",
                category="system",
                details={"plugin": plugin_name, "backend": backend, "error": str(exc)},
            )
            return None

    text_plugin = register_processing_plugin(
        "text_moderation",
        lambda: TextModerationPlugin(TEXT_MODEL_CONFIG),
        TEXT_MODEL_CONFIG,
        level=logging.ERROR,
    )
    register_processing_plugin(
        "image_moderation",
        lambda: ImageModerationPlugin(
            TEXT_MODEL_CONFIG,
            IMAGE_MODEL_CONFIG,
            text_moderator=text_plugin,
        ),
        IMAGE_MODEL_CONFIG,
    )
    register_processing_plugin(
        "audio_moderation",
        lambda: AudioModerationPlugin(
            TEXT_MODEL_CONFIG,
            AUDIO_MODEL_CONFIG,
            text_moderator=text_plugin,
        ),
        AUDIO_MODEL_CONFIG,
    )

    app.config["PROCESSING_PLUGIN_HEALTH"] = plugin_health

    log_event(
        logger,
        logging.INFO,
        "engine_ready",
        "Processing engine initialized",
        category="system",
        details={"plugins": engine.list_plugins(), "health": plugin_health},
    )

    def run_text_task(system_prompt, user_prompt, fallback_text=""):
        text_plugin = engine.get_plugin("text_moderation")
        if not text_plugin:
            return fallback_text
        try:
            # Generous token budget: some models "think" before answering.
            return text_plugin.generate_text(system_prompt, user_prompt, max_new_tokens=1024, temperature=0.2)
        except Exception as exc:
            logger.error("Text task failed: %s", exc)
            return fallback_text

    # ── Auth helpers ─────────────────────────────────────────────────────

    def current_user():
        return session.get("username")

    def login_required(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            username = current_user()
            if not username:
                return _error("Please sign in to continue.", 401, status="UNAUTHENTICATED")
            g.request_user = username
            return view(*args, **kwargs)
        return wrapper

    def load_group(group_id, admin_only=False):
        """Return (group, None) when the caller may access it, else (None, error_response)."""
        _bind_request_context(group_id=group_id)
        group = GroupStore.get_group_details(group_id)
        if not group:
            return None, _error("Group not found.", 404)
        username = current_user()
        if not GroupStore.is_member(group_id, username):
            return None, _error("You are not a member of this group.", 403)
        if admin_only and group.get("admin_username") != username:
            return None, _error("Only the group admin can do this.", 403)
        return group, None

    def start_session(username):
        session.clear()
        session["username"] = username
        session.permanent = True

    def recent_context(group_id):
        recent = MessageStore.get_recent_messages(group_id, limit=6)
        return [f"{m['username']}: {MessageStore._display_message(m)}" for m in recent]

    # ── Static / Frontend Routes ─────────────────────────────────────────

    @app.route("/")
    def serve_index():
        response = send_from_directory(FRONTEND_DIR, "index.html")
        response.headers["Cache-Control"] = "no-cache"
        return response

    @app.route("/media/<kind>/<media_id>")
    @login_required
    def serve_media(kind, media_id):
        """Serve an uploaded image or audio file to members of its group."""
        if kind not in {"image", "audio"}:
            return _error("Not found.", 404)

        row = MediaStore.get(kind, media_id)
        if row:
            group_id = row["group_id"]
        else:
            # Legacy (pre-v5) file on disk: find its group through the message.
            owner = MessageStore.find_by_media_url(f"/media/{kind}/{media_id}")
            group_id = owner["group_id"] if owner else None

        if not group_id or not GroupStore.is_member(group_id, current_user()):
            return _error("Not found.", 404)

        if row:
            response = send_file(
                io.BytesIO(row["data"]),
                mimetype=row["mime_type"],
                conditional=True,
                etag=media_id,
                max_age=31536000,
            )
        else:
            response = send_from_directory(MEDIA_DIR, f"{kind}/{media_id}", max_age=31536000)
        response.headers["Cache-Control"] = "private, max-age=31536000, immutable"
        return response

    @app.route("/<path:path>")
    def serve_static(path):
        if path.startswith("api/"):
            return _error("Not found.", 404)
        return send_from_directory(FRONTEND_DIR, path, max_age=3600)

    # ══════════════════════════════════════════════════════════════════════
    # HEALTH
    # ══════════════════════════════════════════════════════════════════════

    @app.route("/healthz")
    def healthz():
        """Liveness/readiness probe for hosting platforms."""
        try:
            with DBManager.engine().connect() as conn:
                conn.execute(sql_text("SELECT 1"))
            database = "ok"
        except Exception as exc:
            logger.error("Health check database failure: %s", exc)
            database = "error"
        status = 200 if database == "ok" else 503
        return safe_json({
            "status": "ok" if status == 200 else "degraded",
            "version": APP_VERSION,
            "database": database,
            "ai": {name: info["status"] for name, info in plugin_health.items()},
        }, status=status)

    # ══════════════════════════════════════════════════════════════════════
    # AUTH API
    # ══════════════════════════════════════════════════════════════════════

    @app.route("/api/auth/register", methods=["POST"])
    def api_register():
        limited = rate_limited("auth", request.remote_addr)
        if limited:
            return limited
        data = _json_body()
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", ""))
        full_name = str(data.get("full_name", "")).strip()
        bio = str(data.get("bio", "")).strip()

        if not all([username, password.strip(), full_name]):
            return _error("All fields required.", 400)
        if username.lower() == password.strip().lower():
            return _error("Username and password cannot be the same.", 400)

        success, message = UserStore.register(username, password, full_name, bio)
        _bind_request_context(user=username)
        log_event(
            logger,
            logging.INFO if success else logging.WARNING,
            "register_attempt",
            "User registration processed",
            category="auth",
            **_request_context(),
            status_code=200 if success else 409,
            details={"success": success},
        )
        if not success:
            status = 409 if "exists" in message else 400
            return _error(message, status)

        start_session(username)
        return safe_json({"success": True, "message": message, "user": UserStore.get_profile(username)})

    @app.route("/api/auth/login", methods=["POST"])
    def api_login():
        limited = rate_limited("auth", request.remote_addr)
        if limited:
            return limited
        data = _json_body()
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", ""))

        if not all([username, password]):
            return _error("Username and password required.", 400)

        success, user_data = UserStore.validate_login(username, password)
        _bind_request_context(user=username)
        log_event(
            logger,
            logging.INFO if success else logging.WARNING,
            "login_attempt",
            "User login processed",
            category="auth",
            **_request_context(),
            status_code=200 if success else 401,
            details={"success": success},
        )
        if success:
            start_session(username)
            return safe_json({"success": True, "user": user_data})
        return _error("Invalid username or password.", 401)

    @app.route("/api/auth/logout", methods=["POST"])
    def api_logout():
        session.clear()
        return safe_json({"success": True})

    @app.route("/api/auth/me", methods=["GET"])
    @login_required
    def api_me():
        profile = UserStore.get_profile(current_user())
        if not profile:
            session.clear()
            return _error("Please sign in to continue.", 401, status="UNAUTHENTICATED")
        return safe_json({"success": True, "user": profile})

    # ══════════════════════════════════════════════════════════════════════
    # GROUPS API
    # ══════════════════════════════════════════════════════════════════════

    @app.route("/api/groups", methods=["GET"])
    @login_required
    def api_get_groups():
        groups = GroupStore.get_user_groups(current_user())
        return safe_json({"success": True, "groups": groups})

    @app.route("/api/groups", methods=["POST"])
    @login_required
    def api_create_group():
        data = _json_body()
        name = str(data.get("group_name", "")).strip()
        password = str(data.get("password", "")).strip()
        admin = current_user()
        rules = str(data.get("rules", "Be respectful.")).strip()
        moderation_sensitivity = _normalize_sensitivity(data.get("moderation_sensitivity", "Moderate"))

        if not name:
            return _error("Group name required.", 400)

        success, group_id = GroupStore.create_group(name, password, admin, rules, moderation_sensitivity)
        _bind_request_context(user=admin, group_id=group_id)
        log_event(
            logger,
            logging.INFO,
            "group_created",
            "Group created successfully",
            category="group",
            **_request_context(),
            details={"group_name": name, "moderation_sensitivity": moderation_sensitivity},
        )
        return safe_json({"success": success, "group_id": group_id})

    @app.route("/api/groups/join", methods=["POST"])
    @login_required
    def api_join_group():
        limited = rate_limited("auth", f"join:{current_user()}")
        if limited:
            return limited
        data = _json_body()
        group_id = str(data.get("group_id", "")).strip().upper()
        password = str(data.get("password", "")).strip()
        username = current_user()

        if not group_id:
            return _error("Group ID required.", 400)

        _bind_request_context(user=username, group_id=group_id)
        success, message = GroupStore.join_group(group_id, password, username)
        log_event(
            logger,
            logging.INFO if success else logging.WARNING,
            "group_join",
            "Group join request processed",
            category="group",
            **_request_context(),
            status_code=200 if success else 400,
            details={"success": success},
        )
        status = 200 if success else 400
        return safe_json({"success": success, "message": message, "group_id": group_id}, status=status)

    @app.route("/api/groups/<group_id>", methods=["GET"])
    @login_required
    def api_group_details(group_id):
        group, error = load_group(group_id)
        if error:
            return error
        details = dict(group)
        details["has_password"] = bool(details.pop("password", ""))
        details["is_admin"] = details.get("admin_username") == current_user()
        details["member_count"] = len(GroupStore.get_group_members(group_id))
        return safe_json({"success": True, "group": details})

    @app.route("/api/groups/<group_id>/rules", methods=["PUT"])
    @login_required
    def api_update_rules(group_id):
        group, error = load_group(group_id, admin_only=True)
        if error:
            return error
        data = _json_body()
        new_rules = str(data.get("rules", "")).strip()
        moderation_sensitivity = _normalize_sensitivity(
            data.get("moderation_sensitivity", group.get("moderation_sensitivity", "Moderate"))
        )

        GroupStore.update_group_rules(group_id, new_rules, moderation_sensitivity)
        log_event(
            logger,
            logging.INFO,
            "rules_updated",
            "Group moderation rules updated",
            category="group",
            **_request_context(),
            details={
                "moderation_sensitivity": moderation_sensitivity,
                "rules_preview": _payload_preview(new_rules),
            },
        )
        return safe_json({"success": True, "message": "Rules updated."})

    @app.route("/api/groups/<group_id>/name", methods=["PUT"])
    @login_required
    def api_update_group_name(group_id):
        _group, error = load_group(group_id, admin_only=True)
        if error:
            return error
        new_name = str(_json_body().get("group_name", "")).strip()
        if not new_name:
            return _error("Group name required.", 400)

        success, message = GroupStore.update_group_name(group_id, new_name, current_user())
        if success:
            log_event(
                logger, logging.INFO, "group_renamed",
                "Group renamed", category="group",
                **_request_context(),
                details={"new_name": new_name},
            )
        return safe_json({"success": success, "message": message}, status=200 if success else 403)

    @app.route("/api/groups/<group_id>/members", methods=["GET"])
    @login_required
    def api_group_members(group_id):
        group, error = load_group(group_id)
        if error:
            return error
        members = GroupStore.get_group_members(group_id)
        profiles = UserStore.get_profiles(members)
        member_profiles = []
        for username in members:
            profile = profiles.get(username) or {"username": username, "full_name": username}
            member_profiles.append({**profile, "is_admin": username == group.get("admin_username")})
        return safe_json({"success": True, "members": members, "profiles": member_profiles})

    @app.route("/api/groups/<group_id>/leave", methods=["POST"])
    @login_required
    def api_leave_group(group_id):
        username = current_user()
        _bind_request_context(user=username, group_id=group_id)
        success, message = GroupStore.leave_group(group_id, username)
        log_event(
            logger,
            logging.INFO if success else logging.WARNING,
            "group_leave",
            "Group leave request processed",
            category="group",
            **_request_context(),
            status_code=200 if success else 400,
            details={"success": success},
        )
        return safe_json({"success": success, "message": message}, status=200 if success else 400)

    @app.route("/api/groups/<group_id>", methods=["DELETE"])
    @login_required
    def api_delete_group(group_id):
        _group, error = load_group(group_id, admin_only=True)
        if error:
            return error
        success, message = GroupStore.delete_group(group_id, current_user())
        log_event(
            logger,
            logging.INFO if success else logging.WARNING,
            "group_deleted",
            "Group deletion request processed",
            category="group",
            **_request_context(),
            status_code=200 if success else 403,
            details={"success": success},
        )
        return safe_json({"success": success, "message": message}, status=200 if success else 403)

    # ══════════════════════════════════════════════════════════════════════
    # MESSAGES API
    # ══════════════════════════════════════════════════════════════════════

    @app.route("/api/groups/<group_id>/messages", methods=["GET"])
    @login_required
    def api_get_messages(group_id):
        """Visible messages, oldest first.

        Query params:
            after               only messages with seq greater than this
            before              only messages with seq lower than this (older pages)
            limit               newest N messages (default 200, max 500)
            include_own_flagged 1 to include the caller's held messages
        """
        _group, error = load_group(group_id)
        if error:
            return error
        try:
            after = max(0, int(request.args.get("after", "0")))
            before = max(0, int(request.args.get("before", "0")))
        except ValueError:
            after = before = 0
        try:
            limit = max(1, min(int(request.args.get("limit", DEFAULT_MESSAGE_PAGE)), MAX_MESSAGE_PAGE))
        except ValueError:
            limit = DEFAULT_MESSAGE_PAGE
        username = current_user()
        own_flagged = username if request.args.get("include_own_flagged") in {"1", "true"} else None

        rows = MessageStore.get_visible_messages(
            group_id, after_seq=after, before_seq=before, limit=limit, own_flagged_for=own_flagged
        )
        if rows and not before:
            GroupStore.mark_read(group_id, username, max(row["seq"] for row in rows))
        return safe_json({"success": True, "messages": [_public_message(row) for row in rows]})

    @app.route("/api/groups/<group_id>/messages/flagged", methods=["GET"])
    @login_required
    def api_get_flagged(group_id):
        _group, error = load_group(group_id, admin_only=True)
        if error:
            return error
        flagged = MessageStore.get_flagged_messages(group_id)
        return safe_json({"success": True, "flagged": [_public_message(row) for row in flagged]})

    @app.route("/api/groups/<group_id>/messages/<message_id>", methods=["DELETE"])
    @login_required
    def api_delete_message(group_id, message_id):
        _group, error = load_group(group_id)
        if error:
            return error
        success, message = MessageStore.soft_delete_message(group_id, message_id, current_user())
        if success:
            log_event(
                logger, logging.INFO, "message_deleted",
                "Message soft-deleted by sender", category="moderation",
                **_request_context(), message_id=message_id,
            )
        return safe_json({"success": success, "message": message}, status=200 if success else 403)

    @app.route("/api/groups/<group_id>/messages", methods=["POST"])
    @login_required
    def api_send_message(group_id):
        group, error = load_group(group_id)
        if error:
            return error
        username = current_user()
        limited = rate_limited("message", username)
        if limited:
            return limited
        message = str(_json_body().get("message", "")).strip()

        if not message:
            return _error("Message required.", 400)
        if len(message) > MAX_MESSAGE_CHARS:
            return _error(f"Message is too long (max {MAX_MESSAGE_CHARS} characters).", 400)

        rules = group.get("rules", "")
        moderation_sensitivity = group.get("moderation_sensitivity", "Moderate")
        text_plugin = engine.get_plugin("text_moderation")
        text_backend = _plugin_backend_name(text_plugin)

        if rules and not text_plugin:
            log_event(
                logger,
                logging.ERROR,
                "text_moderation_unavailable",
                "Text message blocked because moderation backend is unavailable",
                category="moderation",
                **_request_context(),
                details={
                    "configured_backend": TEXT_MODEL_CONFIG.get("backend", "-"),
                    "backend": text_backend,
                    "message_preview": _payload_preview(message),
                },
            )
            return _service_unavailable_response("Text")

        moderation_result = {"allowed": True, "reason": ""}
        if text_plugin and rules:
            try:
                moderation_result = engine.process("text_moderation", {
                    "message": message,
                    "rules": rules,
                    "recent_messages": recent_context(group_id),
                    "moderation_sensitivity": moderation_sensitivity,
                })
            except Exception as e:
                log_event(
                    logger,
                    logging.ERROR,
                    "text_moderation_error",
                    "Text moderation failed",
                    category="moderation",
                    **_request_context(),
                    details={"error": str(e), "backend": text_backend},
                )
                return _service_unavailable_response("Text")

        if _is_system_moderation_result(moderation_result):
            log_event(
                logger,
                logging.ERROR,
                "text_moderation_unavailable",
                "Text moderation returned a system failure",
                category="moderation",
                **_request_context(),
                details={
                    "backend": text_backend,
                    "reason": moderation_result.get("reason", ""),
                    "message_preview": _payload_preview(message),
                },
            )
            return _service_unavailable_response("Text")

        if moderation_result["allowed"]:
            msg_id = MessageStore.save_message(
                group_id,
                username,
                message,
                "PASS",
                group_rules=rules,
                initial_status="PASS",
                initial_reason="",
            )
            log_event(
                logger,
                logging.INFO,
                "text_message_passed",
                "Text message accepted",
                category="moderation",
                **_request_context(),
                message_id=msg_id,
                details={
                    "backend": text_backend,
                    "message_preview": _payload_preview(message),
                },
            )
            return safe_json({"success": True, "status": "PASS", "message_id": msg_id})

        msg_id = MessageStore.save_message(
            group_id,
            username,
            message,
            "FLAGGED",
            moderation_result["reason"],
            group_rules=rules,
            initial_status="FLAGGED",
            initial_reason=moderation_result["reason"],
        )
        log_event(
            logger,
            logging.WARNING,
            "text_message_flagged",
            "Text message flagged",
            category="moderation",
            **_request_context(),
            message_id=msg_id,
            details={
                "backend": text_backend,
                "message_preview": _payload_preview(message),
                "reason": moderation_result["reason"],
            },
        )
        return safe_json({
            "success": False,
            "status": "FLAGGED",
            "reason": moderation_result["reason"],
            "message_id": msg_id,
        })

    @app.route("/api/groups/<group_id>/messages/<message_id>/appeal", methods=["POST"])
    @login_required
    def api_submit_appeal(group_id, message_id):
        group, error = load_group(group_id)
        if error:
            return error
        username = current_user()
        appeal_text = str(_json_body().get("appeal_text", "")).strip()

        if not appeal_text:
            return _error("Please explain why the message should be allowed.", 400)

        message_row = MessageStore.get_message(group_id, message_id)
        if not message_row:
            return _error("Message not found.", 404)
        if message_row.get("username") != username:
            return _error("You can only appeal your own message.", 403)
        if message_row.get("status") != "FLAGGED":
            return _error("Only flagged messages can be appealed.", 400)
        if str(message_row.get("appeal_status", "")).upper() == "PENDING_ADMIN":
            return _error("An appeal is already pending.", 400)
        limited = rate_limited("ai", username)
        if limited:
            return limited

        appeal_result = _run_appeal_review(run_text_task, message_row, group, appeal_text[:2000])
        MessageStore.submit_appeal(group_id, message_id, appeal_text[:2000], appeal_result)
        log_event(
            logger,
            logging.INFO,
            "appeal_submitted",
            "Message appeal submitted",
            category="appeal",
            **_request_context(),
            message_id=message_id,
            details={
                "appeal_ai_status": appeal_result["status"],
                "appeal_ai_reason": appeal_result["reason"],
            },
        )
        return safe_json({
            "success": True,
            "appeal_status": "PENDING_ADMIN",
            "ai_status": appeal_result["status"],
            "ai_reason": appeal_result["reason"],
        })

    @app.route("/api/groups/<group_id>/messages/<message_id>/appeal/review", methods=["POST"])
    @login_required
    def api_review_appeal(group_id, message_id):
        _group, error = load_group(group_id, admin_only=True)
        if error:
            return error
        data = _json_body()
        decision = str(data.get("decision", "")).strip().lower()
        admin_note = str(data.get("admin_note", "")).strip()[:1000]

        if decision not in {"approve", "reject"}:
            return _error("Decision must be approve or reject.", 400)

        message_row = MessageStore.get_message(group_id, message_id)
        if not message_row:
            return _error("Message not found.", 404)
        if str(message_row.get("appeal_status", "")).upper() != "PENDING_ADMIN":
            return _error("No pending appeal for this message.", 400)

        approved = decision == "approve"
        MessageStore.resolve_appeal(group_id, message_id, approved, current_user(), admin_note)
        log_event(
            logger,
            logging.INFO,
            "appeal_reviewed",
            "Message appeal reviewed by admin",
            category="appeal",
            **_request_context(),
            message_id=message_id,
            details={"decision": decision, "admin_note": _payload_preview(admin_note)},
        )
        return safe_json({
            "success": True,
            "appeal_status": "APPROVED" if approved else "REJECTED",
            "final_status": "PASS" if approved else "FLAGGED",
        })

    # ══════════════════════════════════════════════════════════════════════
    # IMAGE MESSAGES API
    # ══════════════════════════════════════════════════════════════════════

    @app.route("/api/groups/<group_id>/images", methods=["POST"])
    @login_required
    def api_send_image(group_id):
        """
        Accept a base64-encoded image, describe it with the vision model,
        then moderate the description against group rules.

        Request body (JSON):
            image_data (str)  — base64-encoded image bytes
            mime_type  (str)  — optional; the real type is detected from the bytes

        Response:
            success, status ("PASS"/"FLAGGED"), reason, summary, media_url
        """
        group, error = load_group(group_id)
        if error:
            return error
        username = current_user()
        limited = rate_limited("media", username)
        if limited:
            return limited

        raw_bytes = _decode_base64(_json_body().get("image_data", ""))
        if not raw_bytes:
            return _error("Image data required.", 400)
        if len(raw_bytes) > MAX_IMAGE_BYTES:
            return _error(f"Image is too large (max {MAX_IMAGE_BYTES // (1024 * 1024)} MB).", 413)
        mime_type, ext = sniff_image(raw_bytes)
        if not mime_type:
            return _error("Unsupported image. Use PNG, JPEG, GIF, WebP or BMP.", 400)

        image_plugin = engine.get_plugin("image_moderation")
        image_backend = _plugin_backend_name(image_plugin)
        if not image_plugin:
            return _service_unavailable_response("Image")

        rules = group.get("rules", "")
        try:
            result = engine.process("image_moderation", {
                "image_data": base64.b64encode(raw_bytes).decode("ascii"),
                "mime_type": mime_type,
                "rules": rules,
                "recent_messages": recent_context(group_id),
                "moderation_sensitivity": group.get("moderation_sensitivity", "Moderate"),
            })
        except Exception as e:
            log_event(
                logger,
                logging.ERROR,
                "image_moderation_error",
                "Image moderation failed",
                category="media",
                **_request_context(),
                details={"error": str(e), "mime_type": mime_type, "backend": image_backend},
            )
            return _service_unavailable_response("Image")

        if _is_system_moderation_result(result):
            log_event(
                logger,
                logging.ERROR,
                "image_moderation_unavailable",
                "Image moderation returned a system failure",
                category="media",
                **_request_context(),
                details={"backend": image_backend, "mime_type": mime_type, "reason": result.get("reason", "")},
            )
            return _service_unavailable_response("Image")

        media_url = MediaStore.save("image", group_id, username, raw_bytes, mime_type, ext)
        summary_text = result.get("summary") or ""
        status = "PASS" if result["allowed"] else "FLAGGED"
        reason = "" if result["allowed"] else result["reason"]
        msg_id = MessageStore.save_message(
            group_id, username, "[IMAGE]", status,
            reason=reason, summary=summary_text, media_url=media_url, group_rules=rules,
        )
        log_event(
            logger,
            logging.INFO if result["allowed"] else logging.WARNING,
            "image_message_passed" if result["allowed"] else "image_message_flagged",
            "Image message accepted" if result["allowed"] else "Image message flagged",
            category="moderation",
            **_request_context(),
            message_id=msg_id,
            details={"backend": image_backend, "reason": reason, "summary_preview": _payload_preview(summary_text)},
        )
        payload = {
            "success": bool(result["allowed"]),
            "status": status,
            "message_id": msg_id,
            "summary": summary_text,
        }
        if result["allowed"]:
            payload["media_url"] = media_url
        else:
            payload["reason"] = reason
        return safe_json(payload)

    # ══════════════════════════════════════════════════════════════════════
    # AUDIO MESSAGES API
    # ══════════════════════════════════════════════════════════════════════

    @app.route("/api/groups/<group_id>/audio", methods=["POST"])
    @login_required
    def api_send_audio(group_id):
        """
        Accept a base64-encoded audio clip, transcribe it, summarize the
        transcript, then moderate the summary against group rules.

        Request body (JSON):
            audio_data (str) — base64-encoded audio bytes
            mime_type  (str) — e.g. "audio/wav", "audio/webm" (default: audio/wav)

        Response:
            success, status ("PASS"/"FLAGGED"), reason, summary, transcript, media_url
        """
        group, error = load_group(group_id)
        if error:
            return error
        username = current_user()
        limited = rate_limited("media", username)
        if limited:
            return limited

        data = _json_body()
        raw_bytes = _decode_base64(data.get("audio_data", ""))
        if not raw_bytes:
            return _error("Audio data required.", 400)
        if len(raw_bytes) > MAX_AUDIO_BYTES:
            return _error(f"Audio is too large (max {MAX_AUDIO_BYTES // (1024 * 1024)} MB).", 413)
        ext, mime_type = audio_format(str(data.get("mime_type", "audio/wav")))
        if not ext:
            return _error("Unsupported audio format.", 400)
        accepted = AUDIO_MODEL_CONFIG.get("audio_formats") if AUDIO_MODEL_CONFIG.get("backend") == "api" else ()
        if accepted and ext not in accepted:
            return _error(f"Please send {' or '.join(f.upper() for f in accepted)} audio.", 400)

        audio_plugin = engine.get_plugin("audio_moderation")
        audio_backend = _plugin_backend_name(audio_plugin)
        if not audio_plugin:
            return _service_unavailable_response("Audio")

        rules = group.get("rules", "")
        try:
            result = engine.process("audio_moderation", {
                "audio_data": base64.b64encode(raw_bytes).decode("ascii"),
                "mime_type": mime_type,
                "rules": rules,
                "recent_messages": recent_context(group_id),
                "moderation_sensitivity": group.get("moderation_sensitivity", "Moderate"),
            })
        except Exception as e:
            log_event(
                logger,
                logging.ERROR,
                "audio_moderation_error",
                "Audio moderation failed",
                category="media",
                **_request_context(),
                details={"error": str(e), "mime_type": mime_type, "backend": audio_backend},
            )
            return _service_unavailable_response("Audio")

        if _is_system_moderation_result(result):
            log_event(
                logger,
                logging.ERROR,
                "audio_moderation_unavailable",
                "Audio moderation returned a system failure",
                category="media",
                **_request_context(),
                details={"backend": audio_backend, "mime_type": mime_type, "reason": result.get("reason", "")},
            )
            return _service_unavailable_response("Audio")

        media_url = MediaStore.save("audio", group_id, username, raw_bytes, mime_type, ext)
        summary_text = result.get("summary", "")
        transcript = result.get("transcript", "")
        status = "PASS" if result["allowed"] else "FLAGGED"
        reason = "" if result["allowed"] else result["reason"]
        msg_id = MessageStore.save_message(
            group_id, username, "[AUDIO]", status,
            reason=reason, summary=summary_text, media_url=media_url, group_rules=rules,
        )
        log_event(
            logger,
            logging.INFO if result["allowed"] else logging.WARNING,
            "audio_message_passed" if result["allowed"] else "audio_message_flagged",
            "Audio message accepted" if result["allowed"] else "Audio message flagged",
            category="moderation",
            **_request_context(),
            message_id=msg_id,
            details={
                "backend": audio_backend,
                "reason": reason,
                "summary_preview": _payload_preview(summary_text),
                "transcript_preview": _payload_preview(transcript),
            },
        )
        payload = {
            "success": bool(result["allowed"]),
            "status": status,
            "message_id": msg_id,
            "summary": summary_text,
            "transcript": transcript,
        }
        if result["allowed"]:
            payload["media_url"] = media_url
        else:
            payload["reason"] = reason
        return safe_json(payload)

    # ══════════════════════════════════════════════════════════════════════
    # MODERATION REPORT API
    # ══════════════════════════════════════════════════════════════════════

    @app.route("/api/groups/<group_id>/report", methods=["GET"])
    @login_required
    def api_moderation_report(group_id):
        """Full moderation analytics report for the group admin."""
        _group, error = load_group(group_id, admin_only=True)
        if error:
            return error

        report = MessageStore.get_moderation_report(group_id)
        log_event(
            logger,
            logging.INFO,
            "report_generated",
            "Moderation report generated",
            category="report",
            **_request_context(),
            details={
                "total_messages": report.get("total_messages", 0),
                "flagged_count": report.get("flagged_count", 0),
            },
        )
        return safe_json({"success": True, "report": report})

    @app.route("/api/groups/<group_id>/summary", methods=["GET"])
    @login_required
    def api_group_summary(group_id):
        _group, error = load_group(group_id)
        if error:
            return error

        try:
            limit = max(5, min(int(request.args.get("limit", "25")), 60))
        except ValueError:
            limit = 25

        timeline = MessageStore.build_summary_payload(group_id, limit=limit)
        fallback_items = _fallback_summary_items(timeline)

        if not timeline:
            return safe_json({
                "success": True,
                "summary": {
                    "headline": "No recent activity",
                    "bullets": fallback_items,
                    "limit": limit,
                }
            })

        limited = rate_limited("ai", current_user())
        if limited:
            return limited

        transcript = "\n".join([
            f"{item['timestamp']} | {item['username']} | {item['type']}: {item['content']}"
            for item in timeline
        ])
        ai_text = run_text_task(
            "You summarize group chats for users who need a quick catch-up.",
            (
                "Summarize the recent conversation into 3 to 5 concise bullet points. "
                "Focus on decisions, updates, open questions, and current direction. "
                "Do not mention every message. Keep it factual. "
                "Start every bullet with '- '.\n\n"
                f"Conversation:\n{transcript}"
            ),
            fallback_text="\n".join(f"- {item}" for item in fallback_items)
        )
        bullets = _extract_bullets(ai_text) or fallback_items

        return safe_json({
            "success": True,
            "summary": {
                "headline": f"Catch-up from the last {len(timeline)} messages",
                "bullets": bullets,
                "limit": limit,
            }
        })

    @app.route("/api/rules/suggest", methods=["POST"])
    @login_required
    def api_suggest_rules():
        data = _json_body()
        rules = str(data.get("rules", "") or "").strip()[:4000]
        group_name = str(data.get("group_name", "") or "").strip()[:120]

        fallback = _fallback_rule_suggestions(rules)
        if not rules:
            return safe_json({
                "success": True,
                "suggestions": fallback["suggestions"],
                "revised_rules": fallback["revised_rules"],
            })

        limited = rate_limited("ai", current_user())
        if limited:
            return limited

        ai_text = run_text_task(
            "You improve moderation rules for online group chats.",
            (
                "Review these group rules and suggest improvements. "
                "Return exactly this format:\n"
                "SUGGESTIONS:\n"
                "- ...\n"
                "- ...\n"
                "REVISED_RULES:\n"
                "<improved rules text>\n\n"
                f"Group name: {group_name or 'Unnamed group'}\n"
                f"Current rules:\n{rules}"
            ),
            fallback_text=""
        )

        if "REVISED_RULES:" not in ai_text:
            return safe_json({
                "success": True,
                "suggestions": fallback["suggestions"],
                "revised_rules": fallback["revised_rules"],
            })

        suggestions_part, revised_part = ai_text.split("REVISED_RULES:", 1)
        suggestions_part = suggestions_part.replace("SUGGESTIONS:", "")
        suggestions = _extract_bullets(suggestions_part, min_items=2, max_items=4) or fallback["suggestions"]
        revised_rules = revised_part.replace("**", "").strip() or fallback["revised_rules"]

        return safe_json({
            "success": True,
            "suggestions": suggestions,
            "revised_rules": revised_rules,
        })

    @app.route("/api/rules/extract", methods=["POST"])
    @login_required
    def api_extract_rules():
        """Extract text from an uploaded .txt or .pdf file for use as group rules."""
        if "file" not in request.files:
            return _error("No file provided.", 400)

        MAX_EXTRACT_BYTES = 5 * 1024 * 1024
        file = request.files["file"]
        filename = (file.filename or "").lower()

        if filename.endswith(".txt"):
            raw = file.read(MAX_EXTRACT_BYTES + 1)
            if len(raw) > MAX_EXTRACT_BYTES:
                return _error("File too large. Max 5 MB.", 413)
            text = raw.decode("utf-8", errors="replace").strip()
        elif filename.endswith(".pdf"):
            try:
                import pdfplumber
            except ImportError:
                return _error("PDF support requires pdfplumber (pip install pdfplumber).", 500)
            pdf_bytes = file.read(MAX_EXTRACT_BYTES + 1)
            if len(pdf_bytes) > MAX_EXTRACT_BYTES:
                return _error("File too large. Max 5 MB.", 413)
            try:
                text_parts = []
                with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                    for page in pdf.pages[:30]:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(page_text.strip())
                text = "\n".join(text_parts).strip()
            except Exception as exc:
                logger.warning("PDF rules extraction failed: %s", exc)
                return _error("Could not read that PDF.", 400)
        else:
            return _error("Only .txt and .pdf files are supported.", 400)

        if not text:
            return _error("File appears to be empty.", 400)

        max_rules_length = 4000
        if len(text) > max_rules_length:
            text = text[:max_rules_length].rsplit(" ", 1)[0] + "\n[Truncated - original document was too long]"

        return safe_json({"success": True, "extracted_text": text})

    # ══════════════════════════════════════════════════════════════════════
    # SETTINGS / PROFILE API
    # ══════════════════════════════════════════════════════════════════════

    @app.route("/api/settings", methods=["GET"])
    def api_get_settings():
        """User-facing application settings (no secrets or internals)."""
        ready = {name: info["status"] == "ready" for name, info in plugin_health.items()}
        safe_config = {
            "moderation_status": "Active" if ready.get("text_moderation") else "Unavailable",
            "workspace_mode": "Protected",
            "content_types": [
                label for label, plugin in (
                    ("Text", "text_moderation"), ("Image", "image_moderation"), ("Audio", "audio_moderation")
                ) if ready.get(plugin)
            ],
            "features": [
                "Real-time moderation",
                "Appeal review flow",
                "Admin analytics dashboard",
            ],
            "ai_provider": AI_PROVIDER_PRESETS[AI_PROVIDER]["label"],
            "capabilities": {
                "text": bool(ready.get("text_moderation")),
                "image": bool(ready.get("image_moderation")),
                "audio": bool(ready.get("audio_moderation")),
            },
            "audio_formats": list(AUDIO_MODEL_CONFIG.get("audio_formats") or []),
            "limits": {
                "message_chars": MAX_MESSAGE_CHARS,
                "image_mb": MAX_IMAGE_BYTES // (1024 * 1024),
                "audio_mb": MAX_AUDIO_BYTES // (1024 * 1024),
            },
            "app_version": APP_VERSION,
            "plugin_count": len(engine.list_plugins()),
        }
        return safe_json({"success": True, "settings": safe_config})

    @app.route("/api/user/profile", methods=["GET"])
    @login_required
    def api_user_profile():
        username = request.args.get("username", "").strip() or current_user()
        profile = UserStore.get_profile(username)
        if profile:
            return safe_json({"success": True, "profile": profile})
        return _error("User not found.", 404)

    @app.route("/api/user/profile", methods=["PUT"])
    @login_required
    def api_update_profile():
        data = _json_body()
        username = current_user()
        success, message = UserStore.update_profile(
            username, data.get("full_name"), data.get("bio"), data.get("avatar")
        )
        if success:
            log_event(
                logger, logging.INFO, "profile_updated",
                "User profile updated", category="auth",
                **_request_context(),
            )
        return safe_json(
            {"success": success, "message": message, "user": UserStore.get_profile(username)},
            status=200 if success else 404,
        )

    @app.route("/api/user/password", methods=["PUT"])
    @login_required
    def api_change_password():
        limited = rate_limited("auth", request.remote_addr)
        if limited:
            return limited
        data = _json_body()
        success, message = UserStore.change_password(
            current_user(), str(data.get("current_password", "")), str(data.get("new_password", ""))
        )
        return safe_json({"success": success, "message": message}, status=200 if success else 400)

    logger.info("ConvoEase application initialized successfully")
    return app
