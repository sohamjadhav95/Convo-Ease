"""
ConvoEase — Main Application
Flask app factory with REST API endpoints.
All orchestration logic, route definitions, and app configuration lives here.
"""

import os
import sys
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import FRONTEND_DIR, SECRET_KEY, MODEL_CONFIG, setup_logging
from database.Database_processing import DBManager, UserStore, GroupStore, MessageStore
from core_processing_engine import ProcessingEngine, TextModerationPlugin

logger = setup_logging("main")


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

    # ── Static / Frontend Routes ─────────────────────────────────────────

    @app.route("/")
    def serve_index():
        return send_from_directory(FRONTEND_DIR, "index.html")

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
            # Don't send password hash to frontend
            user_data.pop("password", None)
            return jsonify({"success": True, "user": user_data}), 200
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
        return jsonify({"success": True, "groups": groups}), 200

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
            # Don't expose group password
            details.pop("password", None)
            return jsonify({"success": True, "group": details}), 200
        return jsonify({"success": False, "message": "Group not found."}), 404

    @app.route("/api/groups/<group_id>/rules", methods=["PUT"])
    def api_update_rules(group_id):
        data = request.get_json()
        new_rules = data.get("rules", "")
        requesting_user = data.get("username", "")

        # Verify admin
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
        return jsonify({"success": True, "members": members}), 200

    # ══════════════════════════════════════════════════════════════════════
    # MESSAGES API
    # ══════════════════════════════════════════════════════════════════════

    @app.route("/api/groups/<group_id>/messages", methods=["GET"])
    def api_get_messages(group_id):
        messages = MessageStore.get_visible_messages(group_id)
        return jsonify({"success": True, "messages": messages}), 200

    @app.route("/api/groups/<group_id>/messages/flagged", methods=["GET"])
    def api_get_flagged(group_id):
        flagged = MessageStore.get_flagged_messages(group_id)
        return jsonify({"success": True, "flagged": flagged}), 200

    @app.route("/api/groups/<group_id>/messages", methods=["POST"])
    def api_send_message(group_id):
        data = request.get_json()
        username = data.get("username", "").strip()
        message = data.get("message", "").strip()

        if not all([username, message]):
            return jsonify({"success": False, "message": "Username and message required."}), 400

        # Get group rules for moderation
        group = GroupStore.get_group_details(group_id)
        if not group:
            return jsonify({"success": False, "message": "Group not found."}), 404

        rules = group.get("rules", "")

        # Build context (last 6 messages)
        recent = MessageStore.get_visible_messages(group_id)
        recent_context = [f"{m['username']}: {m['message']}" for m in recent[-6:]]

        # Run moderation through the engine
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
            MessageStore.save_message(group_id, username, message, "PASS")
            return jsonify({"success": True, "status": "PASS"}), 200
        else:
            MessageStore.save_message(group_id, username, message, "FLAGGED", moderation_result["reason"])
            return jsonify({
                "success": False,
                "status": "FLAGGED",
                "reason": moderation_result["reason"]
            }), 200  # 200 because the request was valid, just flagged

    # ══════════════════════════════════════════════════════════════════════
    # SETTINGS API
    # ══════════════════════════════════════════════════════════════════════

    @app.route("/api/settings", methods=["GET"])
    def api_get_settings():
        """Return current engine configuration (safe view)."""
        safe_config = {
            "mode": MODEL_CONFIG["mode"],
            "model": MODEL_CONFIG.get("model", ""),
            "base_url": MODEL_CONFIG.get("base_url", ""),
            "model_path": MODEL_CONFIG.get("model_path", ""),
            "model_type": MODEL_CONFIG.get("model_type", ""),
            "plugins": engine.list_plugins()
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
            return jsonify({"success": True, "profile": profile}), 200
        return jsonify({"success": False, "message": "User not found."}), 404

    logger.info("ConvoEase application initialized successfully")
    return app
