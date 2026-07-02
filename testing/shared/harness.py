import base64
from pathlib import Path


def _assign(module, name, value, monkeypatch=None):
    if monkeypatch is not None:
        monkeypatch.setattr(module, name, value, raising=False)
    else:
        setattr(module, name, value)


def configure_test_environment(sandbox_root, monkeypatch=None):
    import config
    import main as main_module
    from database.Database_processing import db_manager, group_store, message_store, user_store

    sandbox_root = Path(sandbox_root)
    db_dir = sandbox_root / "database" / "Databases"
    media_dir = sandbox_root / "database" / "media"
    image_dir = media_dir / "image"
    audio_dir = media_dir / "audio"
    video_dir = media_dir / "video"
    logs_dir = sandbox_root / "logs"

    for directory in (db_dir, image_dir, audio_dir, video_dir, logs_dir):
        directory.mkdir(parents=True, exist_ok=True)

    users_file = db_dir / "users.csv"
    groups_file = db_dir / "groups.csv"
    members_file = db_dir / "group_members.csv"
    chats_file = db_dir / "group_chats.csv"

    config_updates = {
        "DATABASE_DIR": str(db_dir),
        "LOG_DIR": str(logs_dir),
        "MEDIA_DIR": str(media_dir),
        "MEDIA_IMAGE_DIR": str(image_dir),
        "MEDIA_AUDIO_DIR": str(audio_dir),
        "MEDIA_VIDEO_DIR": str(video_dir),
        "USERS_FILE": str(users_file),
        "GROUPS_FILE": str(groups_file),
        "MEMBERS_FILE": str(members_file),
        "CHATS_FILE": str(chats_file),
    }
    for name, value in config_updates.items():
        _assign(config, name, value, monkeypatch)

    for name, value in {
        "DATABASE_DIR": str(db_dir),
        "USERS_FILE": str(users_file),
        "GROUPS_FILE": str(groups_file),
        "MEMBERS_FILE": str(members_file),
        "CHATS_FILE": str(chats_file),
    }.items():
        _assign(db_manager, name, value, monkeypatch)

    db_manager.SCHEMAS["users"]["path"] = str(users_file)
    db_manager.SCHEMAS["groups"]["path"] = str(groups_file)
    db_manager.SCHEMAS["members"]["path"] = str(members_file)
    db_manager.SCHEMAS["chats"]["path"] = str(chats_file)

    _assign(user_store, "USERS_FILE", str(users_file), monkeypatch)
    _assign(group_store, "GROUPS_FILE", str(groups_file), monkeypatch)
    _assign(group_store, "MEMBERS_FILE", str(members_file), monkeypatch)
    _assign(message_store, "CHATS_FILE", str(chats_file), monkeypatch)

    _assign(main_module, "MEDIA_DIR", str(media_dir), monkeypatch)
    _assign(main_module, "MEDIA_IMAGE_DIR", str(image_dir), monkeypatch)
    _assign(main_module, "MEDIA_AUDIO_DIR", str(audio_dir), monkeypatch)
    _assign(main_module, "MEDIA_VIDEO_DIR", str(video_dir), monkeypatch)

    db_manager.DBManager.initialize()

    return {
        "sandbox_root": sandbox_root,
        "database_dir": db_dir,
        "media_dir": media_dir,
        "image_dir": image_dir,
        "audio_dir": audio_dir,
        "video_dir": video_dir,
        "logs_dir": logs_dir,
    }


def install_test_ai(monkeypatch=None):
    from core_processing_engine import AudioModerationPlugin, ImageModerationPlugin, TextModerationPlugin

    blocked_terms = {"bad", "insult", "hate", "abuse", "spoiler", "unsafe"}

    class FakeTextBackend:
        def generate(self, system_prompt, user_prompt, max_new_tokens=280, temperature=0.2):
            return fake_generate_text(None, system_prompt, user_prompt, max_new_tokens=max_new_tokens, temperature=temperature)

    def fake_text_process(self, input_data, context=None):
        message = str(input_data.get("message", "") or "")
        rules = str(input_data.get("rules", "") or "")
        lowered = message.lower()
        lowered_rules = rules.lower()
        dynamic_terms = set(blocked_terms)

        if "homework" in lowered_rules:
            dynamic_terms.add("homework")
        if "meme" in lowered_rules:
            dynamic_terms.add("meme")

        matched = next((term for term in dynamic_terms if term in lowered), None)
        if not rules.strip():
            return {
                "allowed": True,
                "reason": "No rules set.",
                "detected_language": "en",
                "language_confidence": "0.99",
                "translated_message": message,
            }
        if matched:
            return {
                "allowed": False,
                "reason": f"Test: blocked term '{matched}'",
                "detected_language": "en",
                "language_confidence": "0.99",
                "translated_message": message,
            }
        return {
            "allowed": True,
            "reason": "",
            "detected_language": "en",
            "language_confidence": "0.99",
            "translated_message": message,
        }

    def fake_generate_text(self, system_prompt, user_prompt, max_new_tokens=280, temperature=0.2):
        system_prompt = system_prompt or ""
        user_prompt = user_prompt or ""
        combined = f"{system_prompt}\n{user_prompt}".lower()

        if "re-evaluate moderated chat messages after a user appeal" in system_prompt.lower():
            if "quote" in combined or "context" in combined:
                return "PASS Appeal accepted because the context is legitimate."
            return "FLAGGED Original moderation decision stands."

        if "summarize group chats" in system_prompt.lower():
            return (
                "- The admin opened the group and conversation.\n"
                "- Members shared updates relevant to the chat.\n"
                "- Moderation blocked unsafe content before delivery."
            )

        if "improve moderation rules" in system_prompt.lower():
            return (
                "SUGGESTIONS:\n"
                "- Add a direct ban on insults and harassment.\n"
                "- Clarify that image and audio uploads follow the same rules.\n"
                "REVISED_RULES:\n"
                "Be respectful.\nNo insults or harassment.\nNo spam.\n"
                "Images and audio must follow the same standards."
            )

        return "PASS"

    def fake_image_process(self, input_data, context=None):
        image_data = input_data.get("image_data", "")
        is_flagged = "YmFkaW1hZ2U=" in image_data or "dW5zYWZl" in image_data
        summary = "A calm study desk setup." if not is_flagged else "An insulting meme with unsafe text."
        return {
            "allowed": not is_flagged,
            "reason": "" if not is_flagged else "Test: flagged image content",
            "summary": summary,
        }

    def fake_audio_process(self, input_data, context=None):
        audio_data = input_data.get("audio_data", "")
        is_flagged = "YmFkYXVkaW8=" in audio_data or "dW5zYWZl" in audio_data
        transcript = "Study group reminder for tomorrow." if not is_flagged else "This audio contains a bad insult."
        summary = "Reminder about tomorrow's study session." if not is_flagged else "Unsafe spoken insult."
        return {
            "allowed": not is_flagged,
            "reason": "" if not is_flagged else "Test: flagged audio content",
            "summary": summary,
            "transcript": transcript,
        }

    def fake_text_init(self, model_config):
        self.config = model_config
        self._backend = FakeTextBackend()

    def fake_image_init(self, text_model_config, vision_model_config, text_moderator=None):
        self.text_config = text_model_config
        self.vision_config = vision_model_config
        self.backend = vision_model_config.get("backend", "api")
        self._vision_client = None
        self._vision_pipeline = None
        self._text_moderator = TextModerationPlugin(text_model_config)

    def fake_audio_init(self, text_model_config, audio_model_config, text_moderator=None):
        self.text_config = text_model_config
        self.audio_config = audio_model_config
        self.backend = audio_model_config.get("backend", "api")
        self._text_moderator = TextModerationPlugin(text_model_config)
        self._summary_client = None
        self._audio_client = None
        self._asr_pipeline = None

    _assign(TextModerationPlugin, "__init__", fake_text_init, monkeypatch)
    _assign(ImageModerationPlugin, "__init__", fake_image_init, monkeypatch)
    _assign(AudioModerationPlugin, "__init__", fake_audio_init, monkeypatch)
    _assign(TextModerationPlugin, "process", fake_text_process, monkeypatch)
    _assign(TextModerationPlugin, "generate_text", fake_generate_text, monkeypatch)
    _assign(ImageModerationPlugin, "process", fake_image_process, monkeypatch)
    _assign(AudioModerationPlugin, "process", fake_audio_process, monkeypatch)


def encode_payload(text):
    return base64.b64encode(text.encode("utf-8")).decode("utf-8")

