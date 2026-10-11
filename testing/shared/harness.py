import base64
import os
from pathlib import Path


def _assign(module, name, value, monkeypatch=None):
    if monkeypatch is not None:
        monkeypatch.setattr(module, name, value, raising=False)
    else:
        setattr(module, name, value)


def configure_test_environment(sandbox_root, monkeypatch=None):
    """Point the app at a throwaway SQLite database inside sandbox_root."""
    import config
    import main as main_module
    from database.Database_processing import DBManager

    sandbox_root = Path(sandbox_root)
    media_dir = sandbox_root / "media"
    logs_dir = sandbox_root / "logs"
    for directory in (media_dir / "image", media_dir / "audio", logs_dir):
        directory.mkdir(parents=True, exist_ok=True)

    database_path = sandbox_root / "convoease-test.db"
    # Set CONVOEASE_TEST_DATABASE_URL to run the suite against Postgres; its
    # tables are wiped before each test.
    database_url = os.getenv("CONVOEASE_TEST_DATABASE_URL") or f"sqlite:///{database_path}"

    _assign(config, "DATABASE_URL", database_url, monkeypatch)
    _assign(config, "LOG_DIR", str(logs_dir), monkeypatch)
    _assign(config, "MEDIA_DIR", str(media_dir), monkeypatch)
    _assign(main_module, "MEDIA_DIR", str(media_dir), monkeypatch)

    if not database_url.startswith("sqlite"):
        from database.Database_processing.db_manager import metadata

        metadata.drop_all(DBManager.initialize(database_url))
    DBManager.initialize(database_url)

    return {
        "sandbox_root": sandbox_root,
        "database_url": database_url,
        "database_path": database_path,
        "media_dir": media_dir,
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
        image_bytes = base64.b64decode(input_data.get("image_data", "") or "")
        is_flagged = b"badimage" in image_bytes or b"unsafe" in image_bytes
        summary = "A calm study desk setup." if not is_flagged else "An insulting meme with unsafe text."
        return {
            "allowed": not is_flagged,
            "reason": "" if not is_flagged else "Test: flagged image content",
            "summary": summary,
        }

    def fake_audio_process(self, input_data, context=None):
        audio_bytes = base64.b64decode(input_data.get("audio_data", "") or "")
        is_flagged = b"badaudio" in audio_bytes or b"unsafe" in audio_bytes
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


# Smallest valid-looking headers, so uploads pass the server's file-type check.
PNG_HEADER = b"\x89PNG\r\n\x1a\n"
WAV_HEADER = b"RIFF\x24\x00\x00\x00WAVEfmt "


def image_payload(marker):
    return base64.b64encode(PNG_HEADER + marker.encode("utf-8")).decode("ascii")


def audio_payload(marker):
    return base64.b64encode(WAV_HEADER + marker.encode("utf-8")).decode("ascii")

