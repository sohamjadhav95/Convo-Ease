"""
ConvoEase — Main Application
Flask app factory with REST API endpoints.
All orchestration logic, route definitions, and app configuration lives here.
"""

import os
import sys
import math
import json
import base64
import logging
import time
import uuid
from flask import Flask, request, jsonify, send_from_directory, Response, g
from flask_cors import CORS

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    APP_VERSION,
    FRONTEND_DIR,
    SECRET_KEY,
    TEXT_MODEL_CONFIG,
    IMAGE_MODEL_CONFIG,
    AUDIO_MODEL_CONFIG,
    MEDIA_DIR,
    MEDIA_IMAGE_DIR,
    MEDIA_AUDIO_DIR,
    setup_logging,
    log_event,
)
from database.Database_processing import DBManager, UserStore, GroupStore, MessageStore
from core_processing_engine import ProcessingEngine, TextModerationPlugin, ImageModerationPlugin, AudioModerationPlugin

logger = setup_logging("main")

_SILENT_REQUEST_ROUTES = {
    "GET:/api/groups",
    "GET:/api/groups/<group_id>/messages",
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
            f"Original message: {message_row.get('message', '')}\n"
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

def sanitize_json(obj):
    """
    Recursively sanitize an object for safe JSON serialisation.
    Handles:
      - float NaN / Infinity  → None
      - numpy scalar types (int64, float64, bool_, str_) → native Python
      - dict / list           → recurse
    This is required on Windows deployments where pandas to_dict() can emit
    numpy scalars and NaN floats that json.dumps rejects by default.
    """
    # Handle numpy scalars if numpy is available
    try:
        import numpy as np
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
        if isinstance(obj, (np.floating,)):
            v = float(obj)
            return None if (math.isnan(v) or math.isinf(v)) else v
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, (np.str_,)):
            return str(obj)
        if isinstance(obj, np.ndarray):
            return [sanitize_json(i) for i in obj.tolist()]
    except ImportError:
        # numpy not installed — fall through to plain float check
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None

    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: sanitize_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_json(v) for v in obj]
    return obj


def safe_json(data, status=200):
    """Serialise data to a Flask Response, sanitizing NaN / numpy types first."""
    return Response(
        json.dumps(sanitize_json(data)),
        status=status,
        mimetype="application/json"
    )


def _service_unavailable_response(kind):
    return safe_json(
        {
            "success": False,
            "status": "UNAVAILABLE",
            "message": _service_unavailable_message(kind),
        },
        status=503,
    )


_ALLOWED_AUDIO_EXT = {"mp3", "m4a", "wav", "ogg", "opus", "flac", "webm", "aac"}
_ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "gif", "webp", "bmp"}


def _normalize_audio_extension(mime_type):
    fmt = (mime_type or "").split("/")[-1].split(";")[0].lower().strip() or "wav"
    aliases = {
        "mpeg": "mp3",
        "mp4": "m4a",
        "x-m4a": "m4a",
        "x-wav": "wav",
        "wave": "wav",
    }
    fmt = aliases.get(fmt, fmt)
    return fmt if fmt in _ALLOWED_AUDIO_EXT else "wav"


def _sanitize_media_ext(mime_type, default="png"):
    """
    Derive a safe filesystem extension from an image mime_type.
    Whitelist-validated so a malicious client cannot smuggle path/XSS
    characters into media_url.
    """
    raw = (mime_type or "").split("/")[-1].split(";")[0].split("+")[0].lower().strip()
    if raw == "jpeg":
        raw = "jpg"
    return raw if raw in _ALLOWED_IMAGE_EXT else default

def create_app():
    """Application factory — creates and configures the Flask app."""
    app = Flask(
        __name__,
        static_folder=FRONTEND_DIR,
        static_url_path=""
    )
    app.secret_key = SECRET_KEY
    CORS(app)

    @app.before_request
    def attach_request_metadata():
        g.request_id = str(uuid.uuid4())[:8]
        g.request_started_at = time.perf_counter()
        g.request_user = request.args.get("username", "-")
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
                details={"remote_addr": request.remote_addr or "-", "query": request.args.to_dict(flat=True)},
            )

    @app.after_request
    def log_response(response):
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

    # ── Initialize Database ──────────────────────────────────────────────
    DBManager.initialize()
    log_event(logger, logging.INFO, "database_initialized", "CSV database initialized", category="system")

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
            return text_plugin.generate_text(system_prompt, user_prompt, max_new_tokens=280, temperature=0.2)
        except Exception as exc:
            logger.error("Text task failed: %s", exc)
            return fallback_text

    # ── Static / Frontend Routes ─────────────────────────────────────────

    @app.route("/")
    def serve_index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.route("/media/<path:filepath>")
    def serve_media(filepath):
        """Serve uploaded media files (images, audio, video) from the media directory.
        IMPORTANT: This must be registered BEFORE the catch-all /<path:path> route.
        """
        return send_from_directory(MEDIA_DIR, filepath)

    @app.route("/<path:path>")
    def serve_static(path):
        return send_from_directory(FRONTEND_DIR, path)


    # ══════════════════════════════════════════════════════════════════════
    # AUTH API
    # ══════════════════════════════════════════════════════════════════════

    @app.route("/api/auth/register", methods=["POST"])
    def api_register():
        data = request.get_json()
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        full_name = data.get("full_name", "").strip()
        bio = data.get("bio", "").strip()

        if not all([username, password, full_name]):
            return jsonify({"success": False, "message": "All fields required."}), 400
        if username.lower() == password.lower():
            return jsonify({"success": False, "message": "Username and password cannot be the same."}), 400

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
            details={"full_name": full_name, "success": success},
        )
        status = 200 if success else 409
        return jsonify({"success": success, "message": message}), status

    @app.route("/api/auth/login", methods=["POST"])
    def api_login():
        data = request.get_json()
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()

        if not all([username, password]):
            return jsonify({"success": False, "message": "Username and password required."}), 400

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
            user_data.pop("password", None)
            return safe_json({"success": True, "user": user_data})
        return jsonify({"success": False, "message": "Invalid credentials."}), 401

    # ══════════════════════════════════════════════════════════════════════
    # GROUPS API
    # ══════════════════════════════════════════════════════════════════════

    @app.route("/api/groups", methods=["GET"])
    def api_get_groups():
        username = request.args.get("username", "")
        if not username:
            return jsonify({"success": False, "message": "Username required."}), 400
        _bind_request_context(user=username)
        groups = GroupStore.get_user_groups(username)
        return safe_json({"success": True, "groups": groups})

    @app.route("/api/groups", methods=["POST"])
    def api_create_group():
        data = request.get_json()
        name = data.get("group_name", "").strip()
        password = data.get("password", "").strip()
        admin = data.get("admin_username", "").strip()
        rules = data.get("rules", "Be respectful.").strip()
        moderation_sensitivity = _normalize_sensitivity(data.get("moderation_sensitivity", "Moderate"))

        if not all([name, admin]):
            return jsonify({"success": False, "message": "Group name and admin required."}), 400

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
        return jsonify({"success": success, "group_id": group_id}), 200

    @app.route("/api/groups/join", methods=["POST"])
    def api_join_group():
        data = request.get_json()
        group_id = data.get("group_id", "").strip()
        password = data.get("password", "").strip()
        username = data.get("username", "").strip()

        if not all([group_id, username]):
            return jsonify({"success": False, "message": "Group ID and username required."}), 400

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
        return jsonify({"success": success, "message": message}), status

    @app.route("/api/groups/<group_id>", methods=["GET"])
    def api_group_details(group_id):
        _bind_request_context(group_id=group_id)
        details = GroupStore.get_group_details(group_id)
        if details:
            details.pop("password", None)
            return safe_json({"success": True, "group": details})
        return safe_json({"success": False, "message": "Group not found."}, status=404)

    @app.route("/api/groups/<group_id>/rules", methods=["PUT"])
    def api_update_rules(group_id):
        data = request.get_json()
        new_rules = data.get("rules", "")
        requesting_user = data.get("username", "")
        moderation_sensitivity = _normalize_sensitivity(data.get("moderation_sensitivity", "Moderate"))
        _bind_request_context(user=requesting_user, group_id=group_id)

        details = GroupStore.get_group_details(group_id)
        if not details:
            return jsonify({"success": False, "message": "Group not found."}), 404
        if details.get("admin_username") != requesting_user:
            return jsonify({"success": False, "message": "Only admin can update rules."}), 403

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
        return jsonify({"success": True, "message": "Rules updated."}), 200

    @app.route("/api/groups/<group_id>/name", methods=["PUT"])
    def api_update_group_name(group_id):
        data = request.get_json() or {}
        new_name = data.get("group_name", "").strip()
        username = data.get("username", "").strip()

        if not all([new_name, username]):
            return jsonify({"success": False, "message": "Group name and username required."}), 400

        _bind_request_context(user=username, group_id=group_id)
        success, message = GroupStore.update_group_name(group_id, new_name, username)
        if success:
            log_event(
                logger, logging.INFO, "group_renamed",
                "Group renamed", category="group",
                **_request_context(),
                details={"new_name": new_name},
            )
        status = 200 if success else 403
        return jsonify({"success": success, "message": message}), status

    @app.route("/api/groups/<group_id>/members", methods=["GET"])
    def api_group_members(group_id):
        _bind_request_context(group_id=group_id)
        members = GroupStore.get_group_members(group_id)
        return safe_json({"success": True, "members": members})

    @app.route("/api/groups/<group_id>/leave", methods=["POST"])
    def api_leave_group(group_id):
        data = request.get_json() or {}
        username = data.get("username", "").strip()

        if not username:
            return jsonify({"success": False, "message": "Username required."}), 400

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
        status = 200 if success else 400
        return jsonify({"success": success, "message": message}), status

    @app.route("/api/groups/<group_id>", methods=["DELETE"])
    def api_delete_group(group_id):
        data = request.get_json() or {}
        username = data.get("username", "").strip()

        if not username:
            return jsonify({"success": False, "message": "Username required."}), 400

        _bind_request_context(user=username, group_id=group_id)
        success, message = GroupStore.delete_group(group_id, username)
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
        status = 200 if success else 403
        return jsonify({"success": success, "message": message}), status

    # ══════════════════════════════════════════════════════════════════════
    # MESSAGES API
    # ══════════════════════════════════════════════════════════════════════

    @app.route("/api/groups/<group_id>/messages", methods=["GET"])
    def api_get_messages(group_id):
        _bind_request_context(group_id=group_id)
        messages = MessageStore.get_visible_messages(group_id)
        return safe_json({"success": True, "messages": messages})

    @app.route("/api/groups/<group_id>/messages/flagged", methods=["GET"])
    def api_get_flagged(group_id):
        _bind_request_context(group_id=group_id)
        flagged = MessageStore.get_flagged_messages(group_id)
        return safe_json({"success": True, "flagged": flagged})

    @app.route("/api/groups/<group_id>/messages/<message_id>", methods=["DELETE"])
    def api_delete_message(group_id, message_id):
        data = request.get_json() or {}
        username = data.get("username", "").strip()

        if not username:
            return jsonify({"success": False, "message": "Username required."}), 400

        _bind_request_context(user=username, group_id=group_id)
        success, message = MessageStore.soft_delete_message(group_id, message_id, username)
        if success:
            log_event(
                logger, logging.INFO, "message_deleted",
                "Message soft-deleted by sender", category="moderation",
                **_request_context(), message_id=message_id,
            )
        status = 200 if success else 403
        return jsonify({"success": success, "message": message}), status

    @app.route("/api/groups/<group_id>/messages", methods=["POST"])
    def api_send_message(group_id):
        data = request.get_json()
        username = data.get("username", "").strip()
        message = data.get("message", "").strip()

        if not all([username, message]):
            return jsonify({"success": False, "message": "Username and message required."}), 400

        _bind_request_context(user=username, group_id=group_id)
        group = GroupStore.get_group_details(group_id)
        if not group:
            return jsonify({"success": False, "message": "Group not found."}), 404

        rules = group.get("rules", "")
        moderation_sensitivity = group.get("moderation_sensitivity", "Moderate")
        recent = MessageStore.get_visible_messages(group_id)
        recent_context = [f"{m['username']}: {m['message']}" for m in recent[-6:]]
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
            return jsonify({
                "success": False,
                "status": "UNAVAILABLE",
                "message": _service_unavailable_message("Text"),
            }), 503

        moderation_result = {"allowed": True, "reason": ""}
        if text_plugin and rules:
            try:
                moderation_result = engine.process("text_moderation", {
                    "message": message,
                    "rules": rules,
                    "recent_messages": recent_context,
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
            return jsonify({"success": True, "status": "PASS", "message_id": msg_id}), 200
        else:
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
            return jsonify({
                "success": False,
                "status": "FLAGGED",
                "reason": moderation_result["reason"],
                "message_id": msg_id,
            }), 200

    @app.route("/api/groups/<group_id>/messages/<message_id>/appeal", methods=["POST"])
    def api_submit_appeal(group_id, message_id):
        data = request.get_json() or {}
        username = data.get("username", "").strip()
        appeal_text = data.get("appeal_text", "").strip()
        _bind_request_context(user=username, group_id=group_id)

        if not all([username, appeal_text]):
            return jsonify({"success": False, "message": "Username and appeal_text required."}), 400

        group = GroupStore.get_group_details(group_id)
        if not group:
            return jsonify({"success": False, "message": "Group not found."}), 404

        message_row = MessageStore.get_message(group_id, message_id)
        if not message_row:
            return jsonify({"success": False, "message": "Message not found."}), 404
        if message_row.get("username") != username:
            return jsonify({"success": False, "message": "You can only appeal your own message."}), 403
        if message_row.get("status") != "FLAGGED":
            return jsonify({"success": False, "message": "Only flagged messages can be appealed."}), 400
        if str(message_row.get("appeal_status", "")).upper() == "PENDING_ADMIN":
            return jsonify({"success": False, "message": "An appeal is already pending."}), 400

        appeal_result = _run_appeal_review(run_text_task, message_row, group, appeal_text)
        MessageStore.submit_appeal(group_id, message_id, appeal_text, appeal_result)
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
        return jsonify({
            "success": True,
            "appeal_status": "PENDING_ADMIN",
            "ai_status": appeal_result["status"],
            "ai_reason": appeal_result["reason"],
        }), 200

    @app.route("/api/groups/<group_id>/messages/<message_id>/appeal/review", methods=["POST"])
    def api_review_appeal(group_id, message_id):
        data = request.get_json() or {}
        username = data.get("username", "").strip()
        decision = str(data.get("decision", "")).strip().lower()
        admin_note = data.get("admin_note", "").strip()
        _bind_request_context(user=username, group_id=group_id)

        if decision not in {"approve", "reject"}:
            return jsonify({"success": False, "message": "Decision must be approve or reject."}), 400

        group = GroupStore.get_group_details(group_id)
        if not group:
            return jsonify({"success": False, "message": "Group not found."}), 404
        if group.get("admin_username") != username:
            return jsonify({"success": False, "message": "Only admin can review appeals."}), 403

        message_row = MessageStore.get_message(group_id, message_id)
        if not message_row:
            return jsonify({"success": False, "message": "Message not found."}), 404
        if str(message_row.get("appeal_status", "")).upper() != "PENDING_ADMIN":
            return jsonify({"success": False, "message": "No pending appeal for this message."}), 400

        approved = decision == "approve"
        MessageStore.resolve_appeal(group_id, message_id, approved, username, admin_note)
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
        return jsonify({
            "success": True,
            "appeal_status": "APPROVED" if approved else "REJECTED",
            "final_status": "PASS" if approved else "FLAGGED",
        }), 200

    # ══════════════════════════════════════════════════════════════════════
    # IMAGE MESSAGES API
    # ══════════════════════════════════════════════════════════════════════

    @app.route("/api/groups/<group_id>/images", methods=["POST"])
    def api_send_image(group_id):
        """
        Accept a base64-encoded image, summarize it via Gemma-3 vision,
        then moderate the summary against group rules.

        Request body (JSON):
            username   (str)  — sender
            image_data (str)  — base64-encoded image bytes
            mime_type  (str)  — e.g. "image/png", "image/jpeg" (default: image/png)

        Response:
            success, status ("PASS"/"FLAGGED"), reason, summary
        """
        data = request.get_json()
        username   = data.get("username", "").strip()
        image_data = data.get("image_data", "").strip()
        mime_type  = data.get("mime_type", "image/png").strip()

        if not all([username, image_data]):
            return jsonify({"success": False, "message": "Username and image_data required."}), 400

        _bind_request_context(user=username, group_id=group_id)
        group = GroupStore.get_group_details(group_id)
        if not group:
            return jsonify({"success": False, "message": "Group not found."}), 404

        image_plugin = engine.get_plugin("image_moderation")
        image_backend = _plugin_backend_name(image_plugin)
        if not image_plugin:
            return _service_unavailable_response("Image")

        rules = group.get("rules", "")
        moderation_sensitivity = group.get("moderation_sensitivity", "Moderate")
        recent = MessageStore.get_visible_messages(group_id)
        recent_context = [f"{m['username']}: {m['message']}" for m in recent[-6:]]

        try:
            result = engine.process("image_moderation", {
                "image_data": image_data,
                "mime_type":  mime_type,
                "rules":      rules,
                "recent_messages": recent_context,
                "moderation_sensitivity": moderation_sensitivity,
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

        # Decode base64 and save image to disk so it persists across restarts
        # and is visible to all users via /media/image/{filename}.
        ext = _sanitize_media_ext(mime_type, default="png")
        filename = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(MEDIA_IMAGE_DIR, filename)

        try:
            raw_bytes = base64.b64decode(image_data)
            with open(filepath, "wb") as f:
                f.write(raw_bytes)
            log_event(
                logger,
                logging.INFO,
                "image_saved",
                "Image written to media storage",
                category="media",
                **_request_context(),
                details={"file": filename, "bytes": len(raw_bytes), "mime_type": mime_type},
            )
        except Exception as e:
            log_event(
                logger,
                logging.ERROR,
                "image_save_failed",
                "Failed to persist image",
                category="media",
                **_request_context(),
                details={"error": str(e), "file": filename},
            )
            return jsonify({"success": False, "message": "Failed to save image."}), 500

        # URL the frontend uses: stored in CSV so it works for all users + after page reload
        media_url    = f"/media/image/{filename}"
        message_text = "[IMAGE]"
        summary_text = result["summary"] if result["summary"] else ""

        if result["allowed"]:
            msg_id = MessageStore.save_message(
                group_id, username, message_text, "PASS",
                reason="", summary=summary_text, media_url=media_url, group_rules=rules
            )
            log_event(
                logger,
                logging.INFO,
                "image_message_passed",
                "Image message accepted",
                category="moderation",
                **_request_context(),
                message_id=msg_id,
                details={"backend": image_backend, "summary_preview": _payload_preview(summary_text), "media_url": media_url},
            )
            return safe_json({
                "success":    True,
                "status":     "PASS",
                "message_id": msg_id,
                "media_url":  media_url,
                "summary":    summary_text
            })
        else:
            msg_id = MessageStore.save_message(
                group_id, username, message_text, "FLAGGED",
                reason=result["reason"], summary=summary_text, media_url=media_url, group_rules=rules
            )
            log_event(
                logger,
                logging.WARNING,
                "image_message_flagged",
                "Image message flagged",
                category="moderation",
                **_request_context(),
                message_id=msg_id,
                details={"backend": image_backend, "reason": result["reason"], "summary_preview": _payload_preview(summary_text)},
            )
            return safe_json({
                "success": False,
                "status":  "FLAGGED",
                "message_id": msg_id,
                "reason":  result["reason"],
                "summary": summary_text
            })


    # ══════════════════════════════════════════════════════════════════════
    # AUDIO MESSAGES API
    # ══════════════════════════════════════════════════════════════════════

    @app.route("/api/groups/<group_id>/audio", methods=["POST"])
    def api_send_audio(group_id):
        """
        Accept a base64-encoded audio file, transcribe it via the configured
        backend, then moderate the transcript against group rules.

        Request body (JSON):
            username   (str) — sender
            audio_data (str) — base64-encoded audio bytes
            mime_type  (str) — e.g. "audio/wav", "audio/mpeg" (default: audio/wav)

        Response:
            success, status ("PASS"/"FLAGGED"), reason, transcript, media_url
        """
        data       = request.get_json()
        username   = data.get("username",   "").strip()
        audio_data = data.get("audio_data", "").strip()
        mime_type  = data.get("mime_type",  "audio/wav").strip()

        if not all([username, audio_data]):
            return jsonify({"success": False, "message": "Username and audio_data required."}), 400

        _bind_request_context(user=username, group_id=group_id)
        group = GroupStore.get_group_details(group_id)
        if not group:
            return jsonify({"success": False, "message": "Group not found."}), 404

        audio_plugin = engine.get_plugin("audio_moderation")
        audio_backend = _plugin_backend_name(audio_plugin)
        if not audio_plugin:
            return _service_unavailable_response("Audio")

        rules = group.get("rules", "")
        moderation_sensitivity = group.get("moderation_sensitivity", "Moderate")
        recent = MessageStore.get_visible_messages(group_id)
        recent_context = [f"{m['username']}: {m['message']}" for m in recent[-6:]]

        try:
            result = engine.process("audio_moderation", {
                "audio_data": audio_data,
                "mime_type":  mime_type,
                "rules":      rules,
                "recent_messages": recent_context,
                "moderation_sensitivity": moderation_sensitivity,
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

        # Save audio file to disk so it persists and is playable from any client
        ext = _normalize_audio_extension(mime_type)
        filename  = f"{uuid.uuid4()}.{ext}"
        filepath  = os.path.join(MEDIA_AUDIO_DIR, filename)
        media_url = f"/media/audio/{filename}"

        try:
            raw_bytes = base64.b64decode(audio_data)
            with open(filepath, "wb") as f:
                f.write(raw_bytes)
            log_event(
                logger,
                logging.INFO,
                "audio_saved",
                "Audio written to media storage",
                category="media",
                **_request_context(),
                details={"file": filename, "bytes": len(raw_bytes), "mime_type": mime_type},
            )
        except Exception as e:
            log_event(
                logger,
                logging.ERROR,
                "audio_save_failed",
                "Failed to persist audio",
                category="media",
                **_request_context(),
                details={"error": str(e), "file": filename},
            )
            return jsonify({"success": False, "message": "Failed to save audio."}), 500

        summary_text = result.get("summary", "")
        transcript   = result.get("transcript", "")
        message_text = "[AUDIO]"

        if result["allowed"]:
            msg_id = MessageStore.save_message(
                group_id, username, message_text, "PASS",
                reason="", summary=summary_text, media_url=media_url, group_rules=rules
            )
            log_event(
                logger,
                logging.INFO,
                "audio_message_passed",
                "Audio message accepted",
                category="moderation",
                **_request_context(),
                message_id=msg_id,
                details={
                    "backend": audio_backend,
                    "summary_preview": _payload_preview(summary_text),
                    "transcript_preview": _payload_preview(transcript),
                },
            )
            return safe_json({
                "success":    True,
                "status":     "PASS",
                "message_id": msg_id,
                "media_url":  media_url,
                "summary":    summary_text,
                "transcript": transcript
            })
        else:
            msg_id = MessageStore.save_message(
                group_id, username, message_text, "FLAGGED",
                reason=result["reason"], summary=summary_text, media_url=media_url, group_rules=rules
            )
            log_event(
                logger,
                logging.WARNING,
                "audio_message_flagged",
                "Audio message flagged",
                category="moderation",
                **_request_context(),
                message_id=msg_id,
                details={
                    "backend": audio_backend,
                    "reason": result["reason"],
                    "summary_preview": _payload_preview(summary_text),
                    "transcript_preview": _payload_preview(transcript),
                },
            )
            return safe_json({
                "success":    False,
                "status":     "FLAGGED",
                "message_id": msg_id,
                "reason":     result["reason"],
                "summary":    summary_text,
                "transcript": transcript
            })


    # ══════════════════════════════════════════════════════════════════════
    # MODERATION REPORT API
    # ══════════════════════════════════════════════════════════════════════

    @app.route("/api/groups/<group_id>/report", methods=["GET"])
    def api_moderation_report(group_id):
        """
        Returns a full moderation analytics report for the group.
        Intended for admin panel view.
        """
        _bind_request_context(group_id=group_id)
        details = GroupStore.get_group_details(group_id)
        if not details:
            return jsonify({"success": False, "message": "Group not found."}), 404

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
    def api_group_summary(group_id):
        _bind_request_context(group_id=group_id)
        details = GroupStore.get_group_details(group_id)
        if not details:
            return jsonify({"success": False, "message": "Group not found."}), 404

        try:
            limit = max(5, min(int(request.args.get("limit", "25")), 60))
        except ValueError:
            limit = 25

        timeline = MessageStore.build_summary_payload(group_id, limit=limit)
        fallback_items = _fallback_summary_items(timeline)

        if not timeline:
            return jsonify({
                "success": True,
                "summary": {
                    "headline": "No recent activity",
                    "bullets": fallback_items,
                    "limit": limit,
                }
            }), 200

        transcript = "\n".join([
            f"{item['timestamp']} | {item['username']} | {item['type']}: {item['content']}"
            for item in timeline
        ])
        ai_text = run_text_task(
            "You summarize group chats for users who need a quick catch-up.",
            (
                "Summarize the recent conversation into 3 to 5 concise bullet points. "
                "Focus on decisions, updates, open questions, and current direction. "
                "Do not mention every message. Keep it factual.\n\n"
                f"Conversation:\n{transcript}"
            ),
            fallback_text="\n".join(f"- {item}" for item in fallback_items)
        )
        bullets = _extract_bullets(ai_text) or fallback_items

        return jsonify({
            "success": True,
            "summary": {
                "headline": f"Catch-up from the last {len(timeline)} messages",
                "bullets": bullets,
                "limit": limit,
            }
        }), 200

    @app.route("/api/rules/suggest", methods=["POST"])
    def api_suggest_rules():
        data = request.get_json() or {}
        rules = (data.get("rules", "") or "").strip()
        group_name = (data.get("group_name", "") or "").strip()

        fallback = _fallback_rule_suggestions(rules)
        if not rules:
            return jsonify({
                "success": True,
                "suggestions": fallback["suggestions"],
                "revised_rules": fallback["revised_rules"],
            }), 200

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
            return jsonify({
                "success": True,
                "suggestions": fallback["suggestions"],
                "revised_rules": fallback["revised_rules"],
            }), 200

        suggestions_part, revised_part = ai_text.split("REVISED_RULES:", 1)
        suggestions = _extract_bullets(suggestions_part, min_items=2, max_items=4) or fallback["suggestions"]
        revised_rules = revised_part.strip() or fallback["revised_rules"]

        return jsonify({
            "success": True,
            "suggestions": suggestions,
            "revised_rules": revised_rules,
        }), 200

    @app.route("/api/rules/extract", methods=["POST"])
    def api_extract_rules():
        """Extract text from an uploaded .txt or .pdf file for use as group rules."""
        if "file" not in request.files:
            return jsonify({"success": False, "message": "No file provided."}), 400

        MAX_EXTRACT_BYTES = 5 * 1024 * 1024
        file = request.files["file"]
        declared = request.content_length or 0
        if declared and declared > MAX_EXTRACT_BYTES:
            return jsonify({"success": False, "message": "File too large. Max 5 MB."}), 413
        filename = (file.filename or "").lower()

        if filename.endswith(".txt"):
            try:
                raw = file.read(MAX_EXTRACT_BYTES + 1)
                if len(raw) > MAX_EXTRACT_BYTES:
                    return jsonify({"success": False, "message": "File too large. Max 5 MB."}), 413
                text = raw.decode("utf-8", errors="replace").strip()
            except Exception as exc:
                return jsonify({"success": False, "message": f"Failed to read text file: {exc}"}), 400
        elif filename.endswith(".pdf"):
            try:
                import io
                import pdfplumber

                pdf_bytes = file.read(MAX_EXTRACT_BYTES + 1)
                if len(pdf_bytes) > MAX_EXTRACT_BYTES:
                    return jsonify({"success": False, "message": "File too large. Max 5 MB."}), 413
                text_parts = []
                with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(page_text.strip())
                text = "\n".join(text_parts).strip()
            except ImportError:
                return jsonify({
                    "success": False,
                    "message": "PDF support requires pdfplumber. Install it with: pip install pdfplumber",
                }), 500
            except Exception as exc:
                return jsonify({"success": False, "message": f"Failed to read PDF: {exc}"}), 400
        else:
            return jsonify({"success": False, "message": "Only .txt and .pdf files are supported."}), 400

        if not text:
            return jsonify({"success": False, "message": "File appears to be empty."}), 400

        max_rules_length = 4000
        if len(text) > max_rules_length:
            text = text[:max_rules_length].rsplit(" ", 1)[0] + "\n[Truncated - original document was too long]"

        return jsonify({"success": True, "extracted_text": text}), 200

    # ══════════════════════════════════════════════════════════════════════
    # SETTINGS API
    # ══════════════════════════════════════════════════════════════════════

    @app.route("/api/settings", methods=["GET"])
    def api_get_settings():
        """Return user-facing application settings without exposing backend internals."""
        safe_config = {
            "moderation_status": "Active",
            "workspace_mode": "Protected",
            "content_types": ["Text", "Image", "Audio"],
            "features": [
                "Real-time moderation",
                "Appeal review flow",
                "Admin analytics dashboard",
            ],
            "app_version": APP_VERSION,
            "plugin_count": len(engine.list_plugins()),
        }
        log_event(
            logger,
            logging.INFO,
            "settings_viewed",
            "User-facing settings loaded",
            category="settings",
            **_request_context(),
            details={"plugin_count": safe_config["plugin_count"]},
        )
        return jsonify({"success": True, "settings": safe_config}), 200

    @app.route("/api/user/profile", methods=["GET"])
    def api_user_profile():
        username = request.args.get("username", "")
        if not username:
            return jsonify({"success": False, "message": "Username required."}), 400
        profile = UserStore.get_profile(username)
        if profile:
            profile.pop("password", None)
            return safe_json({"success": True, "profile": profile})
        return safe_json({"success": False, "message": "User not found."}, status=404)

    @app.route("/api/user/profile", methods=["PUT"])
    def api_update_profile():
        data = request.get_json() or {}
        username = data.get("username", "").strip()
        full_name = data.get("full_name", None)
        bio = data.get("bio", None)
        avatar = data.get("avatar", None)

        if not username:
            return jsonify({"success": False, "message": "Username required."}), 400

        _bind_request_context(user=username)
        success, message = UserStore.update_profile(username, full_name, bio, avatar)
        if success:
            log_event(
                logger, logging.INFO, "profile_updated",
                "User profile updated", category="auth",
                **_request_context(),
            )
        status = 200 if success else 404
        return jsonify({"success": success, "message": message}), status

    logger.info("ConvoEase application initialized successfully")
    return app



