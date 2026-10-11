import logging
import uuid

import pytest

import backend_factory
import config


def test_get_text_backend_resolves_single_local_model_directory(tmp_path, monkeypatch):
    model_root = tmp_path / "Models" / "Text"
    model_dir = model_root / "gemma-4"
    model_dir.mkdir(parents=True)
    (model_dir / "config.json").write_text("{}", encoding="utf-8")

    captured = {}

    class FakeLocalBackend:
        def __init__(self, backend_config):
            captured.update(backend_config)

    monkeypatch.setattr(backend_factory, "_create_local_text_backend", lambda backend_config: FakeLocalBackend(backend_config))

    backend_factory.get_text_backend({
        "backend": "local",
        "local_model_path": str(model_root),
    })

    assert captured["local_model_path"] == str(model_dir.resolve())


def test_setup_logging_adds_debug_file_when_debug_level_enabled(tmp_path, monkeypatch):
    logger_name = f"test-debug-{uuid.uuid4().hex}"
    monkeypatch.setattr(config, "LOG_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(config, "LOG_LEVEL", logging.DEBUG, raising=False)

    logger = config.setup_logging(logger_name)
    handler_paths = {
        getattr(handler, "baseFilename", None)
        for handler in logger.handlers
        if getattr(handler, "baseFilename", None)
    }

    assert str((tmp_path / "debug.log").resolve()) in handler_paths


def test_text_message_returns_503_when_moderation_plugin_is_unavailable(user, create_group, join_group, monkeypatch):
    import main

    group_id = create_group(rules="Be respectful. No insults.")
    join_group(group_id, username="member1")

    original_get_plugin = main.ProcessingEngine.get_plugin

    def fake_get_plugin(self, plugin_name):
        if plugin_name == "text_moderation":
            return None
        return original_get_plugin(self, plugin_name)

    monkeypatch.setattr(main.ProcessingEngine, "get_plugin", fake_get_plugin)

    member = user("member1")
    response = member.post(f"/api/groups/{group_id}/messages", json={"message": "This should not auto-pass"})
    visible_response = member.get(f"/api/groups/{group_id}/messages")

    assert response.status_code == 503
    assert response.get_json()["status"] == "UNAVAILABLE"
    assert visible_response.get_json()["messages"] == []


def test_parse_response_handles_markdown_verdicts():
    from core_processing_engine import TextModerationPlugin

    assert TextModerationPlugin._parse_response("**PASS**")["allowed"] is True
    flagged = TextModerationPlugin._parse_response("**FLAGGED**: off-topic promotion")
    assert flagged == {"allowed": False, "reason": "off-topic promotion"}
    assert TextModerationPlugin._parse_response("FLAGGED Insult toward a member")["reason"] == "Insult toward a member"


def test_provider_presets_resolve_keys_and_models(monkeypatch):
    import importlib

    monkeypatch.setenv("CONVOEASE_AI_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("CONVOEASE_IMAGE_MODEL_ID", "custom-vision")
    reloaded = importlib.reload(config)
    try:
        assert reloaded.TEXT_MODEL_CONFIG["api_key"] == "test-key"
        assert reloaded.TEXT_MODEL_CONFIG["base_url"].startswith("https://generativelanguage.googleapis.com")
        assert reloaded.IMAGE_MODEL_CONFIG["api_model_id"] == "custom-vision"
        assert reloaded.AUDIO_MODEL_CONFIG["backend"] == "api"
        assert reloaded.AUDIO_MODEL_CONFIG["audio_mode"] == "chat"
    finally:
        monkeypatch.undo()
        importlib.reload(config)
