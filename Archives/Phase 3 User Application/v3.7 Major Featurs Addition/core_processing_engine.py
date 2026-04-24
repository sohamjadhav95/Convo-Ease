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
from abc import ABC, abstractmethod

from openai import OpenAI

from config import setup_logging

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
        self._client = None
        self._generator = None
        self._initialize()

    def _initialize(self):
        if self.backend == "api":
            self._client = OpenAI(
                base_url=self.config["base_url"],
                api_key=self.config["api_key"]
            )
            logger.info(
                "TextModeration initialized in API mode: %s",
                self.config.get("api_model_id", "")
            )
        elif self.backend == "local":
            self._generator = self._build_local_text_pipeline()
            logger.info(
                "TextModeration initialized in LOCAL mode: %s",
                self.config.get("local_model_path", "")
            )
        else:
            raise ValueError(f"Unsupported text backend: {self.backend}")

    def _build_local_text_pipeline(self):
        model_path = self.config.get("local_model_path", "")
        if not _ensure_dir_has_files(model_path):
            raise FileNotFoundError(
                f"Text local model directory is empty or missing: {model_path}"
            )

        try:
            import torch
            from transformers import pipeline
        except ImportError as exc:
            raise ImportError(
                "Local text backend requires 'transformers' and 'torch'."
            ) from exc

        device_map = "auto"
        model_kwargs = {}
        if torch.cuda.is_available():
            model_kwargs["torch_dtype"] = torch.float16
        else:
            model_kwargs["torch_dtype"] = torch.float32

        return pipeline(
            "text-generation",
            model=model_path,
            tokenizer=model_path,
            device_map=device_map,
            local_files_only=True,
            model_kwargs=model_kwargs,
        )

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

        if self.backend == "api":
            result = self._process_api(message, rules, recent_messages, moderation_sensitivity, language_meta)
        else:
            result = self._process_local(message, rules, recent_messages, moderation_sensitivity, language_meta)

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

    def _process_api(self, message, rules, recent_messages, moderation_sensitivity, language_meta):
        try:
            response = self._client.chat.completions.create(
                model=self.config["api_model_id"],
                messages=[
                    {
                        "role": "system",
                        "content": self._build_prompt(
                            message, rules, recent_messages, moderation_sensitivity, language_meta
                        )
                    },
                    {"role": "user", "content": "Analyze the NEW message."}
                ]
            )
            content = (response.choices[0].message.content or "").strip()
            logger.info("Moderation API response: %s", content[:120])
            return self._parse_response(content)
        except Exception as exc:
            logger.error("Moderation API error: %s", exc)
            return {"allowed": False, "reason": f"Moderation error: {exc}"}

    def _process_local(self, message, rules, recent_messages, moderation_sensitivity, language_meta):
        try:
            prompt = self._build_prompt(
                message, rules, recent_messages, moderation_sensitivity, language_meta
            )
            content = self.generate_text(
                system_prompt="You are a strict Group Chat Moderator.",
                user_prompt=prompt,
                max_new_tokens=96,
            )
            logger.info("Moderation local response: %s", content[:120])
            return self._parse_response(content)
        except Exception as exc:
            logger.error("Moderation local error: %s", exc)
            return {"allowed": False, "reason": f"Local moderation error: {exc}"}

    def generate_text(self, system_prompt, user_prompt, max_new_tokens=256, temperature=0.2):
        """Run a general-purpose text generation task on the configured backend."""
        if self.backend == "api":
            response = self._client.chat.completions.create(
                model=self.config["api_model_id"],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=max_new_tokens,
                temperature=temperature,
            )
            return (response.choices[0].message.content or "").strip()

        output = self._generator(
            f"{system_prompt}\n\n{user_prompt}",
            max_new_tokens=max_new_tokens,
            do_sample=temperature > 0.35,
            temperature=temperature,
            return_full_text=False,
        )
        return (output[0].get("generated_text", "") or "").strip()

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

    def __init__(self, text_model_config, vision_model_config):
        self.text_config = text_model_config
        self.vision_config = vision_model_config
        self.backend = vision_model_config.get("backend", "api")

        self._vision_client = None
        self._vision_pipeline = None
        self._text_moderator = TextModerationPlugin(text_model_config)

        self._initialize()

    def _initialize(self):
        if self.backend == "api":
            self._vision_client = OpenAI(
                base_url=self.vision_config["base_url"],
                api_key=self.vision_config["api_key"]
            )
            logger.info(
                "ImageModeration initialized in API mode: %s",
                self.vision_config.get("api_model_id", "")
            )
        elif self.backend == "local":
            self._vision_pipeline = self._build_local_vision_pipeline()
            logger.info(
                "ImageModeration initialized in LOCAL mode: %s",
                self.vision_config.get("local_model_path", "")
            )
        else:
            raise ValueError(f"Unsupported image backend: {self.backend}")

    def _build_local_vision_pipeline(self):
        model_path = self.vision_config.get("local_model_path", "")
        if not _ensure_dir_has_files(model_path):
            raise FileNotFoundError(
                f"Image local model directory is empty or missing: {model_path}"
            )

        try:
            import torch
            from transformers import pipeline
        except ImportError as exc:
            raise ImportError(
                "Local image backend requires 'transformers' and 'torch'."
            ) from exc

        model_kwargs = {}
        if torch.cuda.is_available():
            model_kwargs["torch_dtype"] = torch.float16
        else:
            model_kwargs["torch_dtype"] = torch.float32

        try:
            return pipeline(
                "image-text-to-text",
                model=model_path,
                device_map="auto",
                local_files_only=True,
                model_kwargs=model_kwargs,
            )
        except Exception:
            return pipeline(
                "image-to-text",
                model=model_path,
                device_map="auto",
                local_files_only=True,
                model_kwargs=model_kwargs,
            )

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
                "reason": "Image could not be analyzed. Upload blocked for safety.",
                "summary": ""
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
            "summary": summary
        }

    def _summarize_image(self, base64_data, mime_type):
        if self.backend == "api":
            return self._summarize_image_api(base64_data, mime_type)
        return self._summarize_image_local(base64_data)

    def _summarize_image_api(self, base64_data, mime_type):
        try:
            completion = self._vision_client.chat.completions.create(
                model=self.vision_config["api_model_id"],
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "Describe this image in 1-3 concise sentences. "
                                    "Be objective and focus on visible content."
                                )
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{base64_data}"
                                }
                            }
                        ]
                    }
                ]
            )
            return (completion.choices[0].message.content or "").strip()
        except Exception as exc:
            logger.error("Image summarization failed: %s", exc)
            return None

    def _summarize_image_local(self, base64_data):
        try:
            from PIL import Image
        except ImportError as exc:
            raise ImportError("Local image backend requires Pillow.") from exc

        try:
            image_bytes = base64.b64decode(base64_data)
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            prompt = "Describe this image briefly and objectively."
            output = self._vision_pipeline(image, prompt=prompt, max_new_tokens=96)
            first = output[0]
            if isinstance(first, dict):
                return (
                    first.get("generated_text")
                    or first.get("caption")
                    or first.get("text")
                    or ""
                ).strip()
            return str(first).strip()
        except Exception as exc:
            logger.error("Local image summarization failed: %s", exc)
            return None


class AudioModerationPlugin(ProcessingPlugin):
    """
    Moderates audio using:
      1. Speech transcription
      2. Transcript summarization
      3. Text moderation on the summary
    """

    name = "audio_moderation"

    def __init__(self, text_model_config, audio_model_config):
        self.text_config = text_model_config
        self.audio_config = audio_model_config
        self.backend = audio_model_config.get("backend", "api")

        self._text_moderator = TextModerationPlugin(text_model_config)
        self._summary_client = None
        self._audio_client = None
        self._asr_pipeline = None

        self._initialize()

    def _initialize(self):
        if self.backend == "api":
            self._summary_client = OpenAI(
                api_key=self.text_config["api_key"],
                base_url=self.text_config["base_url"],
            )
            self._audio_client = OpenAI(
                api_key=self.audio_config["api_key"],
                base_url=self.audio_config["base_url"],
            )
            logger.info(
                "AudioModeration initialized in API mode: audio=%s summary=%s",
                self.audio_config.get("api_model_id", ""),
                self.audio_config.get("api_summary_model_id", self.text_config.get("api_model_id", ""))
            )
        elif self.backend == "local":
            self._asr_pipeline = self._build_local_asr_pipeline()
            logger.info(
                "AudioModeration initialized in LOCAL mode: %s",
                self.audio_config.get("local_model_path", "")
            )
        else:
            raise ValueError(f"Unsupported audio backend: {self.backend}")

    def _build_local_asr_pipeline(self):
        model_path = self.audio_config.get("local_model_path", "")
        if not _ensure_dir_has_files(model_path):
            raise FileNotFoundError(
                f"Audio local model directory is empty or missing: {model_path}"
            )

        try:
            import torch
            from transformers import pipeline
        except ImportError as exc:
            raise ImportError(
                "Local audio backend requires 'transformers' and 'torch'."
            ) from exc

        return pipeline(
            "automatic-speech-recognition",
            model=model_path,
            device_map="auto" if torch.cuda.is_available() else None,
            local_files_only=True,
        )

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
                "reason": "Audio could not be transcribed. Upload blocked for safety.",
                "summary": "",
                "transcript": ""
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
        }

    def _summarize_transcript(self, transcript):
        if self.text_config.get("backend", "api") == "api":
            try:
                completion = self._summary_client.chat.completions.create(
                    model=self.audio_config.get(
                        "api_summary_model_id",
                        self.text_config["api_model_id"]
                    ),
                    messages=[
                        {
                            "role": "system",
                            "content": "Summarize audio transcripts concisely and objectively."
                        },
                        {
                            "role": "user",
                            "content": (
                                "Summarize this audio transcript in 1-2 sentences. "
                                f"Transcript: {transcript}"
                            )
                        }
                    ],
                    max_tokens=150,
                    temperature=0.2,
                )
                return (completion.choices[0].message.content or "").strip()
            except Exception as exc:
                logger.error("Transcript summarization failed: %s", exc)
                return None

        try:
            moderator = self._text_moderator
            prompt = (
                "Summarize this audio transcript in 1-2 sentences, objectively:\n\n"
                f"{transcript}"
            )
            output = moderator._generator(
                prompt,
                max_new_tokens=96,
                do_sample=False,
                return_full_text=False,
            )
            return (output[0].get("generated_text", "") or "").strip()
        except Exception as exc:
            logger.error("Local transcript summarization failed: %s", exc)
            return None

    def _transcribe(self, base64_data, mime_type):
        if self.backend == "api":
            return self._transcribe_api(base64_data, mime_type)
        return self._transcribe_local(base64_data)

    def _transcribe_api(self, base64_data, mime_type):
        try:
            raw_bytes = base64.b64decode(base64_data)
        except Exception as exc:
            logger.error("Audio base64 decode failed: %s", exc)
            return None

        fmt = mime_type.split("/")[-1].split(";")[0].lower() or "wav"
        if fmt == "mpeg":
            fmt = "mp3"
        elif fmt == "mp4":
            fmt = "m4a"

        file_name = f"input.{fmt}"
        audio_file = io.BytesIO(raw_bytes)
        audio_file.name = file_name

        try:
            transcription = self._audio_client.audio.transcriptions.create(
                file=(file_name, raw_bytes, mime_type),
                model=self.audio_config["api_model_id"],
            )
            if hasattr(transcription, "text"):
                return (transcription.text or "").strip()
            if isinstance(transcription, dict):
                return (transcription.get("text", "") or "").strip()
            return str(transcription).strip()
        except Exception as exc:
            logger.error("Groq transcription failed: %s", exc)
            return None

    def _transcribe_local(self, base64_data):
        try:
            import soundfile as sf
            import numpy as np
            from pydub import AudioSegment
        except ImportError as exc:
            raise ImportError(
                "Local audio backend requires 'soundfile', 'numpy', and 'pydub'."
            ) from exc

        try:
            raw_bytes = base64.b64decode(base64_data)
            audio_segment = AudioSegment.from_file(io.BytesIO(raw_bytes))
            wav_buffer = io.BytesIO()
            audio_segment.export(wav_buffer, format="wav")
            wav_buffer.seek(0)
            audio_array, sample_rate = sf.read(wav_buffer)

            if hasattr(audio_array, "ndim") and audio_array.ndim > 1:
                audio_array = np.mean(audio_array, axis=1)

            output = self._asr_pipeline({"array": audio_array, "sampling_rate": sample_rate})
            if isinstance(output, dict):
                return (output.get("text", "") or "").strip()
            return str(output).strip()
        except Exception as exc:
            logger.error("Local transcription failed: %s", exc)
            return None


class ProcessingEngine:
    """Central registry for all processing plugins."""

    def __init__(self):
        self._plugins = {}

    def register_plugin(self, plugin):
        if not isinstance(plugin, ProcessingPlugin):
            raise TypeError(f"Expected ProcessingPlugin, got {type(plugin).__name__}")
        self._plugins[plugin.name] = plugin
        logger.info("Plugin registered: %s", plugin.name)

    def get_plugin(self, plugin_name):
        return self._plugins.get(plugin_name)

    def list_plugins(self):
        return list(self._plugins.keys())

    def process(self, plugin_name, input_data, context=None):
        plugin = self._plugins.get(plugin_name)
        if not plugin:
            available = ", ".join(self._plugins.keys()) or "none"
            raise KeyError(f"Plugin '{plugin_name}' not found. Available: {available}")
        logger.info("Processing with plugin: %s", plugin_name)
        return plugin.process(input_data, context)
