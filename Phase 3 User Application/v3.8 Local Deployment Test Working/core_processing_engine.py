"""
ConvoEase - Core Processing Engine
Plugin-style architecture for AI model integration.

Design principles:
  - Each processing task is a plugin with a standard interface.
  - Task logic is separated from the model backend.
  - The same plugin can run against a local model directory or a hosted API model.
"""

import io
import math
import base64
import logging
from abc import ABC, abstractmethod

from backend_factory import get_audio_backend, get_image_backend, get_text_backend

from config import log_event, setup_logging

logger = setup_logging("processing_engine")

try:
    from langdetect import DetectorFactory, LangDetectException, detect_langs
    DetectorFactory.seed = 0
except ImportError:
    DetectorFactory = None
    LangDetectException = Exception
    detect_langs = None

try:
    from deep_translator import GoogleTranslator
except ImportError:
    GoogleTranslator = None


def _ensure_dir_has_files(path):
    """Return True when a local model directory contains at least one file."""
    import os

    if not path or not os.path.isdir(path):
        return False

    for _, _, files in os.walk(path):
        if files:
            return True
    return False


def _release_backend_instance(backend):
    release = getattr(backend, "release", None)
    if callable(release):
        try:
            release()
        except Exception as exc:
            logger.warning("Backend release failed: %s", exc)


class ProcessingPlugin(ABC):
    """Base class for all processing plugins."""

    name = "base"

    def get_input_schema(self):
        return {}

    def get_output_schema(self):
        return {}

    @abstractmethod
    def process(self, input_data, context=None):
        pass


class TextModerationPlugin(ProcessingPlugin):
    """
    Validates messages against group rules using either an API model or a local model.
    """

    name = "text_moderation"

    def __init__(self, model_config):
        self.config = model_config
        self.backend = model_config.get("backend", "api")
        self._backend = get_text_backend(model_config)

    def get_input_schema(self):
        return {
            "message": "str - The new message to validate",
            "rules": "str - The group's moderation rules",
            "recent_messages": "list[str] - Recent messages for context",
            "moderation_sensitivity": "str - Strict / Moderate / Relaxed",
            "language_hint": "str - Optional known language code or label",
        }

    def get_output_schema(self):
        return {
            "allowed": "bool - Whether the message is allowed",
            "reason": "str - Explanation if flagged"
        }

    def process(self, input_data, context=None):
        message = input_data.get("message", "")
        rules = input_data.get("rules", "")
        recent_messages = input_data.get("recent_messages", [])
        moderation_sensitivity = self._normalize_sensitivity(
            input_data.get("moderation_sensitivity", "Moderate")
        )
        language_hint = input_data.get("language_hint", "")

        if not rules:
            return {"allowed": True, "reason": "No rules set."}

        language_meta = self._prepare_language_context(message, recent_messages, rules, language_hint)

        try:
            system_prompt = "You are a strict Group Chat Moderator."
            user_prompt = self._build_prompt(
                message, rules, recent_messages, moderation_sensitivity, language_meta
            )
            content = self.generate_text(system_prompt, user_prompt, max_new_tokens=48)
            result = self._parse_response(content)
        except Exception as exc:
            logger.error("Moderation error: %s", exc)
            result = {
                "allowed": False,
                "reason": "Moderation temporarily unavailable.",
                "system_error": True,
            }

        result.update({
            "detected_language": language_meta["detected_language"],
            "language_confidence": language_meta["language_confidence"],
            "translated_message": language_meta["translated_message"],
        })
        return result

    def _build_prompt(self, message, rules, recent_messages, moderation_sensitivity, language_meta):
        context_str = "\n".join(recent_messages) if recent_messages else "(no prior messages)"
        context_mode = "required" if self._message_needs_context(message) else "reference_only"
        translated_message = language_meta.get("translated_message", "")
        translated_context = "\n".join(language_meta.get("translated_recent_messages", [])) or "(no translation available)"
        translated_rules = language_meta.get("translated_rules", "") or rules
        language_label = language_meta.get("language_label", "unknown")
        sensitivity_instructions = self._sensitivity_instructions(moderation_sensitivity)
        return f"""You are a strict Group Chat Moderator.

ADMIN RULES:
{rules}

ENGLISH RULES REFERENCE:
{translated_rules}

MODERATION SENSITIVITY:
{moderation_sensitivity}
{sensitivity_instructions}

CHAT CONTEXT USE MODE:
{context_mode}

MODERATION PRINCIPLES:
1. The ADMIN RULES are the primary decision boundary.
2. CHAT CONTEXT is only for understanding references, short replies, follow-up questions, or pronouns.
3. Do not narrow a broad rule to the latest micro-topic in the chat.
4. If a message fits the ADMIN RULES on its own, it should PASS even if it changes the subtopic.
5. Only use context to rescue ambiguous messages like "what happened?", "yes", "same here", "when?", or similar short replies.
6. Do not FLAG a message just because it is different from the last few messages, unless it clearly violates or falls outside the ADMIN RULES.

CHAT CONTEXT:
{context_str}

ENGLISH CONTEXT REFERENCE:
{translated_context}

TASK:
Validate the NEW message against the rules and context.
The user's language appears to be: {language_label}.
Use the original wording as the source of truth. The English translation is only a compatibility aid for the model.
Reply in one of these formats only:
PASS
FLAGGED <reason>

NEW MESSAGE: "{message}"
ENGLISH MESSAGE REFERENCE: "{translated_message or message}"
"""

    @staticmethod
    def _message_needs_context(message):
        text = (message or "").strip().lower()
        if not text:
            return True

        tokens = text.split()
        if len(tokens) <= 4:
            return True

        short_reference_phrases = {
            "ok", "okay", "yes", "no", "maybe", "why", "when", "where",
            "what happened", "same here", "me too", "tell me more",
            "can you explain", "how so", "what about that"
        }
        if text in short_reference_phrases:
            return True

        pronoun_markers = {"it", "that", "this", "they", "them", "he", "she", "those", "these"}
        if len(tokens) <= 8 and any(token in pronoun_markers for token in tokens):
            return True

        if text.endswith("?") and len(tokens) <= 6:
            return True

        return False

    def generate_text(self, system_prompt, user_prompt, max_new_tokens=256, temperature=0.2):
        """Run a general-purpose text generation task on the configured backend."""
        return self._backend.generate(
            system_prompt, user_prompt, max_new_tokens, temperature
        )

    @staticmethod
    def _parse_response(content):
        if content.startswith("PASS"):
            return {"allowed": True, "reason": ""}
        if content.startswith("FLAGGED"):
            reason = content.replace("FLAGGED", "", 1).strip().lstrip(":- ")
            return {"allowed": False, "reason": reason or "Flagged by moderation model."}

        lower = content.lower()
        if any(keyword in lower for keyword in ["flagged", "violation", "not allowed"]):
            return {"allowed": False, "reason": "Flagged by moderation model."}
        return {"allowed": True, "reason": ""}

    @staticmethod
    def _normalize_sensitivity(value):
        normalized = str(value or "Moderate").strip().lower()
        mapping = {
            "strict": "Strict",
            "moderate": "Moderate",
            "relaxed": "Relaxed",
        }
        return mapping.get(normalized, "Moderate")

    @staticmethod
    def _sensitivity_instructions(level):
        if level == "Strict":
            return (
                "Strict mode: flag borderline content, mild disrespect, and messages that are even slightly off-topic. "
                "When uncertain between PASS and FLAGGED, lean toward FLAGGED."
            )
        if level == "Relaxed":
            return (
                "Relaxed mode: only flag clear and meaningful rule violations. "
                "Allow harmless digressions, mild tone issues, and ambiguous content unless the violation is obvious."
            )
        return (
            "Moderate mode: enforce the rules consistently without over-flagging. "
            "Flag clear violations and clear off-topic messages, but do not punish minor ambiguity."
        )

    def _prepare_language_context(self, message, recent_messages, rules, language_hint=""):
        detected_language, confidence = self._detect_language(message, language_hint)
        translated_message = self._translate_if_needed(message, detected_language)
        translated_recent = [
            self._translate_if_needed(item, detected_language) if item else item
            for item in (recent_messages or [])
        ]
        translated_rules = self._translate_if_needed(rules, detected_language)
        return {
            "detected_language": detected_language,
            "language_confidence": f"{confidence:.2f}" if confidence else "",
            "language_label": self._language_label(detected_language),
            "translated_message": translated_message,
            "translated_recent_messages": translated_recent,
            "translated_rules": translated_rules,
        }

    def _detect_language(self, text, language_hint=""):
        if language_hint:
            hint = str(language_hint).strip().lower()
            return hint, 1.0

        content = str(text or "").strip()
        if not content or detect_langs is None:
            return "unknown", 0.0

        try:
            candidates = detect_langs(content)
            if not candidates:
                return "unknown", 0.0
            top = candidates[0]
            return top.lang, float(top.prob)
        except LangDetectException:
            return "unknown", 0.0

    def _translate_if_needed(self, text, detected_language):
        content = str(text or "").strip()
        if not content:
            return ""
        if detected_language in {"", "unknown", "en"}:
            return content
        if GoogleTranslator is None:
            return content
        try:
            return GoogleTranslator(source="auto", target="en").translate(content) or content
        except Exception as exc:
            logger.warning("Translation fallback failed for language %s: %s", detected_language, exc)
            return content

    @staticmethod
    def _language_label(code):
        mapping = {
            "en": "English",
            "hi": "Hindi",
            "mr": "Marathi",
            "ta": "Tamil",
            "te": "Telugu",
            "bn": "Bengali",
            "gu": "Gujarati",
            "kn": "Kannada",
            "ml": "Malayalam",
            "pa": "Punjabi",
            "ur": "Urdu",
        }
        return mapping.get(code, code or "unknown")


class ImageModerationPlugin(ProcessingPlugin):
    """
    Moderates images using:
      1. Image summary generation
      2. Text moderation on the summary
    """

    name = "image_moderation"

    def __init__(self, text_model_config, vision_model_config, text_moderator=None):
        self.text_config = text_model_config
        self.vision_config = vision_model_config
        self.backend = vision_model_config.get("backend", "api")
        self._vision_backend = get_image_backend(vision_model_config)
        self._text_moderator = text_moderator or TextModerationPlugin(text_model_config)

    def get_input_schema(self):
        return {
            "image_data": "str - Base64-encoded image bytes",
            "mime_type": "str - MIME type like image/png",
            "rules": "str - Group moderation rules",
            "recent_messages": "list[str] - Recent chat context for ambiguous cases",
            "moderation_sensitivity": "str - Strict / Moderate / Relaxed",
        }

    def get_output_schema(self):
        return {
            "allowed": "bool - Whether the image is allowed",
            "reason": "str - Explanation if flagged",
            "summary": "str - Generated description of the image"
        }

    def process(self, input_data, context=None):
        image_data = input_data.get("image_data", "")
        mime_type = input_data.get("mime_type", "image/png")
        rules = input_data.get("rules", "")
        recent_messages = input_data.get("recent_messages", [])
        moderation_sensitivity = input_data.get("moderation_sensitivity", "Moderate")

        if not image_data:
            return {"allowed": False, "reason": "No image data provided.", "summary": ""}

        summary = self._summarize_image(image_data, mime_type)
        if summary is None:
            return {
                "allowed": False,
                "reason": "Image moderation is temporarily unavailable.",
                "summary": "",
                "system_error": True,
            }

        if not rules:
            return {"allowed": True, "reason": "", "summary": summary}

        moderation = self._text_moderator.process(
            {
                "message": summary,
                "rules": rules,
                "recent_messages": recent_messages,
                "moderation_sensitivity": moderation_sensitivity,
            }
        )
        return {
            "allowed": moderation["allowed"],
            "reason": moderation["reason"],
            "summary": summary,
            "system_error": moderation.get("system_error", False),
        }

    def _summarize_image(self, base64_data, mime_type):
        try:
            # On 4 GB GPUs the local text and image Gemma runtimes cannot stay
            # resident together. Release the text backend before loading the
            # multimodal model, then release the image backend after use so text
            # moderation can reload for the summary decision.
            _release_backend_instance(getattr(self._text_moderator, "_backend", None))
            return self._vision_backend.describe(base64_data, mime_type)
        except Exception as exc:
            logger.error("Image summarization failed: %s", exc)
            return None
        finally:
            _release_backend_instance(self._vision_backend)


class AudioModerationPlugin(ProcessingPlugin):
    """
    Moderates audio using:
      1. Speech transcription
      2. Transcript summarization
      3. Text moderation on the summary
    """

    name = "audio_moderation"

    def __init__(self, text_model_config, audio_model_config, text_moderator=None):
        self.text_config = text_model_config
        self.audio_config = audio_model_config
        self.backend = audio_model_config.get("backend", "api")
        self._audio_backend = get_audio_backend(audio_model_config)
        self._text_moderator = text_moderator or TextModerationPlugin(text_model_config)
        self._summary_moderator = self._text_moderator
        summary_model_id = audio_model_config.get("api_summary_model_id")
        if (
            self.text_config.get("backend", "api") == "api"
            and summary_model_id
            and summary_model_id != self.text_config.get("api_model_id")
        ):
            summary_config = dict(text_model_config)
            summary_config["api_model_id"] = summary_model_id
            self._summary_moderator = TextModerationPlugin(summary_config)

    def get_input_schema(self):
        return {
            "audio_data": "str - Base64-encoded audio bytes",
            "mime_type": "str - MIME type like audio/wav",
            "rules": "str - Group moderation rules",
            "recent_messages": "list[str] - Recent chat context for ambiguous cases",
            "moderation_sensitivity": "str - Strict / Moderate / Relaxed",
        }

    def get_output_schema(self):
        return {
            "allowed": "bool - Whether the audio content is allowed",
            "reason": "str - Explanation if flagged",
            "summary": "str - Summary of the audio transcript",
            "transcript": "str - Full transcript"
        }

    def process(self, input_data, context=None):
        audio_data = input_data.get("audio_data", "")
        mime_type = input_data.get("mime_type", "audio/wav")
        rules = input_data.get("rules", "")
        recent_messages = input_data.get("recent_messages", [])
        moderation_sensitivity = input_data.get("moderation_sensitivity", "Moderate")

        if not audio_data:
            return {"allowed": False, "reason": "No audio data provided.", "summary": "", "transcript": ""}

        transcript = self._transcribe(audio_data, mime_type)
        if transcript is None:
            return {
                "allowed": False,
                "reason": "Audio moderation is temporarily unavailable.",
                "summary": "",
                "transcript": "",
                "system_error": True,
            }

        if not transcript.strip():
            return {"allowed": True, "reason": "", "summary": "(no speech detected)", "transcript": ""}

        summary = self._summarize_transcript(transcript)
        if summary is None:
            logger.warning("Transcript summarization failed - falling back to raw transcript.")
            summary = transcript

        if not rules:
            return {"allowed": True, "reason": "", "summary": summary, "transcript": transcript}

        moderation = self._text_moderator.process(
            {
                "message": summary,
                "rules": rules,
                "recent_messages": recent_messages,
                "moderation_sensitivity": moderation_sensitivity,
            }
        )
        return {
            "allowed": moderation["allowed"],
            "reason": moderation["reason"],
            "summary": summary,
            "transcript": transcript,
            "system_error": moderation.get("system_error", False),
        }

    def _summarize_transcript(self, transcript):
        try:
            return self._summary_moderator.generate_text(
                "Summarize audio transcripts concisely and objectively.",
                f"Summarize this audio transcript in 1-2 sentences:\n\n{transcript}",
                max_new_tokens=96,
                temperature=0.2,
            )
        except Exception as exc:
            logger.error("Transcript summarization failed: %s", exc)
            return None

    def _transcribe(self, base64_data, mime_type):
        try:
            return self._audio_backend.transcribe(base64_data, mime_type)
        except Exception as exc:
            logger.error("Audio transcription failed: %s", exc)
            return None


class ProcessingEngine:
    """Central registry for all processing plugins."""

    def __init__(self):
        self._plugins = {}

    @staticmethod
    def _plugin_backend(plugin):
        return getattr(plugin, "backend", getattr(plugin, "config", {}).get("backend", "-"))

    def register_plugin(self, plugin):
        if not isinstance(plugin, ProcessingPlugin):
            raise TypeError(f"Expected ProcessingPlugin, got {type(plugin).__name__}")
        self._plugins[plugin.name] = plugin
        log_event(
            logger,
            logging.INFO,
            "plugin_registered",
            f"Plugin registered: {plugin.name}",
            category="system",
            details={"plugin": plugin.name, "backend": self._plugin_backend(plugin)},
        )

    def get_plugin(self, plugin_name):
        return self._plugins.get(plugin_name)

    def list_plugins(self):
        return list(self._plugins.keys())

    def process(self, plugin_name, input_data, context=None):
        plugin = self._plugins.get(plugin_name)
        if not plugin:
            available = ", ".join(self._plugins.keys()) or "none"
            raise KeyError(f"Plugin '{plugin_name}' not found. Available: {available}")
        log_event(
            logger,
            logging.INFO,
            "plugin_processing",
            f"Processing with plugin: {plugin_name}",
            category="moderation",
            details={"plugin": plugin_name, "backend": self._plugin_backend(plugin)},
        )
        return plugin.process(input_data, context)
