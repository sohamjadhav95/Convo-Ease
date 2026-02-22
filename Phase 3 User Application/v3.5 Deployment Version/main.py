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
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import FRONTEND_DIR, SECRET_KEY, MODEL_CONFIG, VISION_MODEL_CONFIG, MEDIA_DIR, MEDIA_IMAGE_DIR, MEDIA_AUDIO_DIR, setup_logging
from database.Database_processing import DBManager, UserStore, GroupStore, MessageStore
from core_processing_engine import ProcessingEngine, TextModerationPlugin, ImageModerationPlugin, AudioModerationPlugin

logger = setup_logging("main")

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

def create_app():
    """Application factory — creates and configures the Flask app."""
    app = Flask(
        __name__,
        static_folder=FRONTEND_DIR,
        static_url_path=""
    )
    app.secret_key = SECRET_KEY
    CORS(app)

    # ── Initialize Database ──────────────────────────────────────────────
    DBManager.initialize()

    # ── Initialize Processing Engine ─────────────────────────────────────
    engine = ProcessingEngine()
    try:
        text_plugin = TextModerationPlugin(MODEL_CONFIG)
        engine.register_plugin(text_plugin)
    except NotImplementedError as e:
        logger.warning(f"TextModerationPlugin not available: {e}")

    try:
        image_plugin = ImageModerationPlugin(MODEL_CONFIG, VISION_MODEL_CONFIG)
        engine.register_plugin(image_plugin)
    except Exception as e:
        logger.warning(f"ImageModerationPlugin not available: {e}")

    try:
        audio_plugin = AudioModerationPlugin(MODEL_CONFIG)
        engine.register_plugin(audio_plugin)
    except Exception as e:
        logger.warning(f"AudioModerationPlugin not available: {e}")

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

        success, message = UserStore.register(username, password, full_name, bio)
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
        groups = GroupStore.get_user_groups(username)
        return safe_json({"success": True, "groups": groups})

    @app.route("/api/groups", methods=["POST"])
    def api_create_group():
        data = request.get_json()
        name = data.get("group_name", "").strip()
        password = data.get("password", "").strip()
        admin = data.get("admin_username", "").strip()
        rules = data.get("rules", "Be respectful.").strip()

        if not all([name, admin]):
            return jsonify({"success": False, "message": "Group name and admin required."}), 400

        success, group_id = GroupStore.create_group(name, password, admin, rules)
        return jsonify({"success": success, "group_id": group_id}), 200

    @app.route("/api/groups/join", methods=["POST"])
    def api_join_group():
        data = request.get_json()
        group_id = data.get("group_id", "").strip()
        password = data.get("password", "").strip()
        username = data.get("username", "").strip()

        if not all([group_id, username]):
            return jsonify({"success": False, "message": "Group ID and username required."}), 400

        success, message = GroupStore.join_group(group_id, password, username)
        status = 200 if success else 400
        return jsonify({"success": success, "message": message}), status

    @app.route("/api/groups/<group_id>", methods=["GET"])
    def api_group_details(group_id):
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

        details = GroupStore.get_group_details(group_id)
        if not details:
            return jsonify({"success": False, "message": "Group not found."}), 404
        if details.get("admin_username") != requesting_user:
            return jsonify({"success": False, "message": "Only admin can update rules."}), 403

        GroupStore.update_group_rules(group_id, new_rules)
        return jsonify({"success": True, "message": "Rules updated."}), 200

    @app.route("/api/groups/<group_id>/members", methods=["GET"])
    def api_group_members(group_id):
        members = GroupStore.get_group_members(group_id)
        return safe_json({"success": True, "members": members})

    # ══════════════════════════════════════════════════════════════════════
    # MESSAGES API
    # ══════════════════════════════════════════════════════════════════════

    @app.route("/api/groups/<group_id>/messages", methods=["GET"])
    def api_get_messages(group_id):
        messages = MessageStore.get_visible_messages(group_id)
        return safe_json({"success": True, "messages": messages})

    @app.route("/api/groups/<group_id>/messages/flagged", methods=["GET"])
    def api_get_flagged(group_id):
        flagged = MessageStore.get_flagged_messages(group_id)
        return safe_json({"success": True, "flagged": flagged})

    @app.route("/api/groups/<group_id>/messages", methods=["POST"])
    def api_send_message(group_id):
        data = request.get_json()
        username = data.get("username", "").strip()
        message = data.get("message", "").strip()

        if not all([username, message]):
            return jsonify({"success": False, "message": "Username and message required."}), 400

        group = GroupStore.get_group_details(group_id)
        if not group:
            return jsonify({"success": False, "message": "Group not found."}), 404

        rules = group.get("rules", "")
        recent = MessageStore.get_visible_messages(group_id)
        recent_context = [f"{m['username']}: {m['message']}" for m in recent[-6:]]

        moderation_result = {"allowed": True, "reason": ""}
        if engine.get_plugin("text_moderation") and rules:
            try:
                moderation_result = engine.process("text_moderation", {
                    "message": message,
                    "rules": rules,
                    "recent_messages": recent_context
                })
            except Exception as e:
                logger.error(f"Moderation failed: {e}")
                moderation_result = {"allowed": False, "reason": f"Moderation error: {str(e)}"}

        if moderation_result["allowed"]:
            msg_id = MessageStore.save_message(group_id, username, message, "PASS", group_rules=rules)
            return jsonify({"success": True, "status": "PASS", "message_id": msg_id}), 200
        else:
            MessageStore.save_message(group_id, username, message, "FLAGGED", moderation_result["reason"], group_rules=rules)
            return jsonify({
                "success": False,
                "status": "FLAGGED",
                "reason": moderation_result["reason"]
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

        group = GroupStore.get_group_details(group_id)
        if not group:
            return jsonify({"success": False, "message": "Group not found."}), 404

        image_plugin = engine.get_plugin("image_moderation")
        if not image_plugin:
            return jsonify({"success": False, "message": "Image moderation not available."}), 503

        rules = group.get("rules", "")

        try:
            result = engine.process("image_moderation", {
                "image_data": image_data,
                "mime_type":  mime_type,
                "rules":      rules,
            })
        except Exception as e:
            logger.error(f"Image moderation error: {e}")
            return jsonify({"success": False, "message": f"Processing error: {str(e)}"}), 500

        # Decode base64 and save image to disk so it persists across restarts
        # and is visible to all users via /media/image/{filename}.
        ext = (mime_type.split("/")[-1] or "png").split("+")[0]   # e.g. "jpeg", "png", "webp"

        # We need the message_id before saving so the filename matches
        import uuid as _uuid
        preliminary_id = str(_uuid.uuid4())
        filename = f"{preliminary_id}.{ext}"
        filepath = os.path.join(MEDIA_IMAGE_DIR, filename)

        try:
            raw_bytes = base64.b64decode(image_data)
            with open(filepath, "wb") as f:
                f.write(raw_bytes)
            logger.info(f"Image saved: {filepath} ({len(raw_bytes)} bytes)")
        except Exception as e:
            logger.error(f"Failed to save image to disk: {e}")
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
            return safe_json({
                "success": False,
                "status":  "FLAGGED",
                "reason":  result["reason"],
                "summary": summary_text
            })


    # ══════════════════════════════════════════════════════════════════════
    # AUDIO MESSAGES API
    # ══════════════════════════════════════════════════════════════════════

    @app.route("/api/groups/<group_id>/audio", methods=["POST"])
    def api_send_audio(group_id):
        """
        Accept a base64-encoded audio file, transcribe via Google Speech
        Recognition, then moderate the transcript against group rules.

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

        group = GroupStore.get_group_details(group_id)
        if not group:
            return jsonify({"success": False, "message": "Group not found."}), 404

        audio_plugin = engine.get_plugin("audio_moderation")
        if not audio_plugin:
            return jsonify({"success": False, "message": "Audio moderation not available."}), 503

        rules = group.get("rules", "")

        try:
            result = engine.process("audio_moderation", {
                "audio_data": audio_data,
                "mime_type":  mime_type,
                "rules":      rules,
            })
        except Exception as e:
            logger.error(f"Audio moderation error: {e}")
            return jsonify({"success": False, "message": f"Processing error: {str(e)}"}), 500

        # Save audio file to disk so it persists and is playable from any client
        ext = mime_type.split("/")[-1].split(";")[0]  # e.g. "wav", "mpeg", "ogg"
        if ext == "mpeg": ext = "mp3"
        import uuid as _uuid
        filename  = f"{str(_uuid.uuid4())}.{ext}"
        filepath  = os.path.join(MEDIA_AUDIO_DIR, filename)
        media_url = f"/media/audio/{filename}"

        try:
            raw_bytes = base64.b64decode(audio_data)
            with open(filepath, "wb") as f:
                f.write(raw_bytes)
            logger.info(f"Audio saved: {filepath} ({len(raw_bytes)} bytes)")
        except Exception as e:
            logger.error(f"Failed to save audio to disk: {e}")
            return jsonify({"success": False, "message": "Failed to save audio."}), 500

        summary_text = result.get("summary", "")
        transcript   = result.get("transcript", "")
        message_text = "[AUDIO]"

        if result["allowed"]:
            msg_id = MessageStore.save_message(
                group_id, username, message_text, "PASS",
                reason="", summary=summary_text, media_url=media_url, group_rules=rules
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
            MessageStore.save_message(
                group_id, username, message_text, "FLAGGED",
                reason=result["reason"], summary=summary_text, media_url=media_url, group_rules=rules
            )
            return safe_json({
                "success":    False,
                "status":     "FLAGGED",
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
        details = GroupStore.get_group_details(group_id)
        if not details:
            return jsonify({"success": False, "message": "Group not found."}), 404

        report = MessageStore.get_moderation_report(group_id)
        return safe_json({"success": True, "report": report})

    # ══════════════════════════════════════════════════════════════════════
    # SETTINGS API
    # ══════════════════════════════════════════════════════════════════════

    @app.route("/api/settings", methods=["GET"])
    def api_get_settings():
        """Return current engine configuration (safe view)."""
        safe_config = {
            "mode":       MODEL_CONFIG["mode"],
            "model":      MODEL_CONFIG.get("model", ""),
            "base_url":   MODEL_CONFIG.get("base_url", ""),
            "model_path": MODEL_CONFIG.get("model_path", ""),
            "model_type": MODEL_CONFIG.get("model_type", ""),
            "vision_model": VISION_MODEL_CONFIG.get("model", ""),
            "plugins":    engine.list_plugins()
        }
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

    logger.info("ConvoEase application initialized successfully")
    return app
