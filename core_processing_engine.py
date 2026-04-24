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

        if not rules:
            return {"allowed": True, "reason": "No rules set."}

        injection_reason = self._detect_prompt_injection(message)
        if injection_reason:
            return {"allowed": False, "reason": injection_reason}

        is_spam, spam_reason = self._detect_spam_content(message)
        if is_spam:
            return {"allowed": False, "reason": spam_reason}

        try:
            system_prompt = "You are a strict Group Chat Moderator."
            user_prompt = self._build_prompt(
                message, rules, recent_messages, moderation_sensitivity
            )
            content = self.generate_text(system_prompt, user_prompt, max_new_tokens=512)
            result = self._parse_response(content)
        except Exception as exc:
            logger.error("Moderation error: %s", exc)
            result = {
                "allowed": False,
                "reason": "Moderation temporarily unavailable.",
                "system_error": True,
            }

        return result

    def _build_prompt(self, message, rules, recent_messages, moderation_sensitivity):
        context_str = "\n".join(recent_messages) if recent_messages else "(no prior messages)"
        context_mode = "required" if self._message_needs_context(message) else "reference_only"
        sensitivity_instructions = self._sensitivity_instructions(moderation_sensitivity)
        normalized = self._normalize_leetspeak(message)
        normalized_line = ""
        if normalized and normalized.lower() != str(message or "").lower():
            normalized_line = f'\nDECODED MESSAGE (leetspeak normalization): "{normalized}"'
        return f"""You are a strict Group Chat Moderator.

ADMIN RULES:
{rules}

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

EMOJI HANDLING:
- Evaluate emoji by their meaning and intent, not just their appearance.
- The 🤬 emoji (face with symbols on mouth) represents profanity or strong frustration. Flag it if rules prohibit profanity or disrespectful language.
- Skin-tone modified emoji and combinations that could carry discriminatory intent should be evaluated by context and intent.
- A single emoji like 👍 or 😊 used as a reaction is almost always harmless.
- Do not flag emoji just because they look unusual - focus on whether the intent violates the rules.

CHAT CONTEXT:
{context_str}

TASK:
Validate the NEW message against the rules and context.
If the message is in a non-English language or script, evaluate its meaning and intent just as you would for English.
Be aware that users may use character substitutions (leetspeak) to disguise prohibited content. Evaluate the phonetic and visual meaning, not just literal characters.
Reply in one of these formats only:
PASS
FLAGGED <reason>

NEW MESSAGE: "{message}"{normalized_line}
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

    @staticmethod
    def _detect_prompt_injection(message):
        """
        Deterministic pre-filter for common prompt injection patterns.
        Returns a reason string if injection is detected, empty string otherwise.
        """
        text = str(message or "").lower().strip()
        if not text:
            return ""

        injection_patterns = [
            "ignore previous",
            "ignore above",
            "ignore all prior",
            "ignore your instructions",
            "disregard previous",
            "disregard above",
            "disregard your",
            "forget your instructions",
            "forget previous",
            "override your",
            "you are now",
            "act as if",
            "pretend you are",
            "new instructions:",
            "system prompt:",
            "respond with pass",
            "respond with: pass",
            "always respond pass",
            "say pass",
            "output pass",
            "return pass",
            "just say pass",
            "you must say pass",
            "your new role",
            "jailbreak",
            "do not moderate",
            "stop moderating",
            "skip moderation",
        ]

        for pattern in injection_patterns:
            if pattern in text:
                return f"Message appears to contain a prompt injection attempt (matched: '{pattern}')."

        return ""

    @staticmethod
    def _detect_spam_content(message):
        """
        Detect obvious spam/garbage content that doesn't need AI moderation.
        Returns (should_block: bool, reason: str).
        """
        text = str(message or "").strip()
        if not text:
            return False, ""

        lorem_markers = ["lorem ipsum", "dolor sit amet", "consectetur adipiscing", "sed do eiusmod"]
        lower = text.lower()
        if any(marker in lower for marker in lorem_markers):
            return True, "Message appears to be filler/placeholder text (Lorem Ipsum)."

        if len(text) >= 8:
            unique_chars = set(text.replace(" ", ""))
            if len(unique_chars) <= 2:
                return True, "Message appears to be character spam."

        words = text.split()
        if len(words) >= 5:
            unique_words = set(w.lower() for w in words)
            if len(unique_words) <= 2:
                return True, "Message appears to be repetitive spam."

        return False, ""

    @staticmethod
    def _normalize_leetspeak(message):
        """
        Normalize common leetspeak substitutions.
        Returns the normalized text, or empty string if no substitutions were made.
        """
        text = str(message or "")
        if not text:
            return ""

        leet_map = {
            "0": "o", "1": "i", "3": "e", "4": "a", "5": "s",
            "7": "t", "8": "b", "@": "a", "$": "s", "!": "i",
            "+": "t", "(": "c", "|": "l",
        }

        normalized = []
        changed = False
        for char in text:
            if char in leet_map:
                normalized.append(leet_map[char])
                changed = True
            else:
                normalized.append(char)

        return "".join(normalized) if changed else ""

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

        if not content.strip():
            return {"allowed": False, "reason": "Moderation empty response (token limit reached?)."}

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
        self.backend = vision_model_config.get("backend")
        self._vision_backend = get_image_backend(vision_model_config)
        self._text_moderator = text_moderator or TextModerationPlugin(text_model_config)

        # Model-swap policy:
        # - API mode on both sides: never swap.
        # - Local mode on at least one side AND CUDA available: swap to let the
        #   text and vision models share a small VRAM budget.
        # - Local mode on CPU-only: do not swap, because reloading from disk
        #   dominates latency there.
        self._should_swap_backends = self._compute_swap_policy()

    def _compute_swap_policy(self):
        text_local = self.text_config.get("backend", "api") == "local"
        vision_local = self.vision_config.get("backend", "api") == "local"
        if not (text_local or vision_local):
            return False
        try:
            import torch
            return bool(torch.cuda.is_available())
        except Exception:
            return False

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
            # Swap only when local backends are sharing a CUDA VRAM budget.
            if self._should_swap_backends:
                _release_backend_instance(getattr(self._text_moderator, "_backend", None))
            return self._vision_backend.describe(base64_data, mime_type)
        except Exception as exc:
            logger.error("Image summarization failed: %s", exc)
            return None
        finally:
            if self._should_swap_backends:
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
        self.backend = audio_model_config.get("backend", "local")
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
                max_new_tokens=256,
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
