"""
ConvoEase — Core Processing Engine
Plugin-style architecture for AI model integration.

Design Principles:
  - Each processing task is a "plugin" with a standard interface.
  - Input/output contracts are defined independently per plugin.
  - Switching from API to local model = change config, not code.
  - Adding new capabilities (image, audio, doc) = add a new plugin class.

Usage:
  engine = ProcessingEngine()
  engine.register_plugin(TextModerationPlugin(config.MODEL_CONFIG))
  engine.register_plugin(ImageModerationPlugin(config.MODEL_CONFIG, config.VISION_MODEL_CONFIG))
  result = engine.process("text_moderation", input_data={"message": "...", "rules": "..."})
  result = engine.process("image_moderation", input_data={"image_data": "base64...", "mime_type": "image/png", "rules": "..."})
"""

from abc import ABC, abstractmethod
from openai import OpenAI
from config import setup_logging

logger = setup_logging("processing_engine")


# ═══════════════════════════════════════════════════════════════════════════════
# BASE PLUGIN
# ═══════════════════════════════════════════════════════════════════════════════

class ProcessingPlugin(ABC):
    """
    Base class for all processing plugins.
    
    Every plugin defines:
      - name:              Unique identifier for dispatch
      - get_input_schema:  What input variables/keys this plugin expects
      - get_output_schema: What output variables/keys this plugin returns
      - process():         The actual processing logic
    """
    name = "base"

    def get_input_schema(self):
        """Returns a dict describing expected input keys and their types."""
        return {}

    def get_output_schema(self):
        """Returns a dict describing output keys and their types."""
        return {}

    @abstractmethod
    def process(self, input_data, context=None):
        """
        Process the input and return a result dict.
        
        Args:
            input_data (dict): Must match get_input_schema() keys.
            context (dict, optional): Additional context (e.g. recent messages).
        
        Returns:
            dict: Must match get_output_schema() keys.
        """
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# TEXT MODERATION PLUGIN
# ═══════════════════════════════════════════════════════════════════════════════

class TextModerationPlugin(ProcessingPlugin):
    """
    Validates messages against group rules using an AI model.
    
    Supports two modes via model_config:
      - "api":   Calls a remote API (OpenRouter, OpenAI, etc.)
      - "local": Loads a local model (future implementation)
    
    Input:  {"message": str, "rules": str, "recent_messages": list[str]}
    Output: {"allowed": bool, "reason": str}
    """
    name = "text_moderation"

    def __init__(self, model_config):
        """
        Args:
            model_config (dict): Contains mode, api_key, base_url, model,
                                 or model_path and model_type for local mode.
        """
        self.config = model_config
        self._client = None
        self._local_model = None
        self._initialize()

    def _initialize(self):
        """Initialize the appropriate model backend."""
        if self.config["mode"] == "api":
            self._client = OpenAI(
                base_url=self.config["base_url"],
                api_key=self.config["api_key"]
            )
            logger.info(f"TextModeration initialized in API mode: {self.config['model']}")
        elif self.config["mode"] == "local":
            # ── Future: load local model here ──
            logger.info(f"TextModeration initialized in LOCAL mode: {self.config.get('model_path', 'N/A')}")
            raise NotImplementedError(
                "Local model support is planned for a future release. "
                "Set CONVOEASE_MODEL_MODE=api to use API mode."
            )

    def get_input_schema(self):
        return {
            "message": "str — The new message to validate",
            "rules": "str — The group's moderation rules",
            "recent_messages": "list[str] — Last N messages for context (optional)"
        }

    def get_output_schema(self):
        return {
            "allowed": "bool — Whether the message is allowed",
            "reason": "str — Explanation (empty if allowed)"
        }

    def process(self, input_data, context=None):
        """
        Validate a message against rules.
        
        Args:
            input_data (dict): Keys: message, rules, recent_messages (list of "user: msg" strings)
            context (dict, optional): Not used currently.
        
        Returns:
            dict: {"allowed": bool, "reason": str}
        """
        message = input_data.get("message", "")
        rules = input_data.get("rules", "")
        recent_messages = input_data.get("recent_messages", [])

        if not rules:
            return {"allowed": True, "reason": "No rules set."}

        if self.config["mode"] == "api":
            return self._process_api(message, rules, recent_messages)
        else:
            return self._process_local(message, rules, recent_messages)

    def _process_api(self, message, rules, recent_messages):
        """Send message to API for moderation."""
        context_str = "\n".join(recent_messages) if recent_messages else "(no prior messages)"

        system_prompt = f"""You are a strict Group Chat Moderator.

ADMIN RULES:
{rules}

CHAT CONTEXT (Last several messages):
{context_str}

YOUR TASK:
Validate the following NEW message.
Use the properties of the CHAT CONTEXT to determine if the message is relevant (e.g. a "Yes" to a previous question is valid).
However, if the NEW message explicitly violates a rule (e.g. insults, spam), you must FLAG it regardless of context.

NEW MESSAGE: "{message}"

OUTPUT FORMAT:
- If compliant: PASS
- If violation: FLAGGED <reason>"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Analyze the NEW MESSAGE."}
        ]

        try:
            response = self._client.chat.completions.create(
                model=self.config["model"],
                messages=messages
            )
            content = response.choices[0].message.content.strip()
            logger.info(f"Moderation API response for '{message[:50]}': {content[:100]}")
            return self._parse_response(content)

        except Exception as e:
            logger.error(f"Moderation API error: {str(e)}")
            return {"allowed": False, "reason": f"Moderation Error: {str(e)}"}

    def _process_local(self, message, rules, recent_messages):
        """Process using local model (future implementation)."""
        raise NotImplementedError("Local model processing not yet implemented.")

    @staticmethod
    def _parse_response(content):
        """Parse AI response into structured output."""
        if content.startswith("PASS"):
            return {"allowed": True, "reason": ""}
        elif content.startswith("FLAGGED"):
            reason = content.replace("FLAGGED", "", 1).strip().lstrip(":- ")
            return {"allowed": False, "reason": reason}
        else:
            lower = content.lower()
            if any(kw in lower for kw in ["violate", "not allowed", "flagged"]):
                return {"allowed": False, "reason": "Message flagged by content filter."}
            return {"allowed": True, "reason": ""}


# ═══════════════════════════════════════════════════════════════════════════════
# IMAGE MODERATION PLUGIN
# ═══════════════════════════════════════════════════════════════════════════════

class ImageModerationPlugin(ProcessingPlugin):
    """
    Moderates images using a two-step pipeline:
      Step 1 — Summarize: Sends the base64 image to a vision model (Gemma-3)
               which returns a concise text description of the image content.
      Step 2 — Moderate: Passes that text summary through the same text-
               moderation logic (TextModerationPlugin) against group rules.

    This reuses 100% of the text moderation system — only the summarization
    step is unique to images.

    Input:  {"image_data": str (base64), "mime_type": str, "rules": str}
    Output: {"allowed": bool, "reason": str, "summary": str}
    """
    name = "image_moderation"

    def __init__(self, text_model_config, vision_model_config):
        """
        Args:
            text_model_config (dict):   Config for the text moderation (TextModerationPlugin).
            vision_model_config (dict): Config for the vision model (Gemma-3).
                                        Keys: api_key, base_url, model.
        """
        self.vision_config = vision_model_config
        self.text_config = text_model_config

        # Vision API client (for summarization step)
        self._vision_client = OpenAI(
            base_url=vision_model_config["base_url"],
            api_key=vision_model_config["api_key"]
        )

        # Text moderator (reused for the moderation step)
        self._text_moderator = TextModerationPlugin(text_model_config)

        logger.info(
            f"ImageModeration initialized | vision={vision_model_config['model']} "
            f"| text={text_model_config.get('model', 'N/A')}"
        )

    def get_input_schema(self):
        return {
            "image_data": "str — Base64-encoded image bytes",
            "mime_type":  "str — MIME type e.g. 'image/png', 'image/jpeg'",
            "rules":      "str — The group's moderation rules",
        }

    def get_output_schema(self):
        return {
            "allowed": "bool — Whether the image is allowed",
            "reason":  "str  — Explanation if flagged (empty if allowed)",
            "summary": "str  — AI-generated description of the image content",
        }

    def process(self, input_data, context=None):
        """
        Run the 2-step image moderation pipeline.

        Args:
            input_data (dict): Keys: image_data (base64 str), mime_type, rules
            context (dict, optional): Not used currently.

        Returns:
            dict: {"allowed": bool, "reason": str, "summary": str}
        """
        image_data = input_data.get("image_data", "")
        mime_type  = input_data.get("mime_type", "image/png")
        rules      = input_data.get("rules", "")

        if not image_data:
            return {"allowed": False, "reason": "No image data provided.", "summary": ""}

        # ── Step 1: Summarize the image ──────────────────────────────────────
        summary = self._summarize_image(image_data, mime_type)
        if summary is None:
            return {
                "allowed": False,
                "reason": "Image could not be analyzed. Upload blocked for safety.",
                "summary": ""
            }
        logger.info(f"Image summary: {summary[:120]}")

        # ── Step 2: Moderate the summary against group rules ─────────────────
        if not rules:
            return {"allowed": True, "reason": "", "summary": summary}

        moderation = self._text_moderator._process_api(
            message=summary,
            rules=rules,
            recent_messages=[]
        )
        return {
            "allowed": moderation["allowed"],
            "reason":  moderation["reason"],
            "summary": summary,
        }

    def _summarize_image(self, base64_data, mime_type):
        """
        Step 1 — Call Gemma-3 vision model to describe the image.
        Uses the exact API pattern from test_api_gen.py.

        Returns:
            str: Text summary of image content, or None on failure.
        """
        try:
            completion = self._vision_client.chat.completions.create(
                model=self.vision_config["model"],
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "Describe this image in 1-3 concise sentences. "
                                    "Focus on: what is shown, any text visible, "
                                    "any people/actions/objects, and the general tone or theme. "
                                    "Be objective and factual."
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
            summary = completion.choices[0].message.content.strip()
            return summary

        except Exception as e:
            logger.error(f"Image summarization failed: {str(e)}")
            return None


# ═══════════════════════════════════════════════════════════════════════════════
# FUTURE PLUGIN TEMPLATES (uncomment and implement when needed)
# ═══════════════════════════════════════════════════════════════════════════════

# class AudioProcessingPlugin(ProcessingPlugin):
#     """Process audio — transcription, moderation."""
#     name = "audio_processing"
#
#     def get_input_schema(self):
#         return {"audio_data": "bytes", "task": "str — 'transcribe' | 'moderate'"}
#
#     def get_output_schema(self):
#         return {"text": "str", "status": "str"}
#
#     def process(self, input_data, context=None):
#         pass

# class DocumentProcessingPlugin(ProcessingPlugin):
#     """Process documents — summarization, extraction."""
#     name = "document_processing"
#
#     def get_input_schema(self):
#         return {"document_data": "bytes", "task": "str — 'summarize' | 'extract'"}
#
#     def get_output_schema(self):
#         return {"result": "str", "metadata": "dict"}
#
#     def process(self, input_data, context=None):
#         pass


# ═══════════════════════════════════════════════════════════════════════════════
# PROCESSING ENGINE (Registry + Dispatcher)
# ═══════════════════════════════════════════════════════════════════════════════

class ProcessingEngine:
    """
    Central registry for all processing plugins.
    Register plugins, then dispatch processing requests by name.
    """

    def __init__(self):
        self._plugins = {}

    def register_plugin(self, plugin):
        """Register a processing plugin."""
        if not isinstance(plugin, ProcessingPlugin):
            raise TypeError(f"Expected ProcessingPlugin, got {type(plugin).__name__}")
        self._plugins[plugin.name] = plugin
        logger.info(f"Plugin registered: {plugin.name}")

    def get_plugin(self, plugin_name):
        """Get a plugin by name."""
        return self._plugins.get(plugin_name)

    def list_plugins(self):
        """List all registered plugin names."""
        return list(self._plugins.keys())

    def process(self, plugin_name, input_data, context=None):
        """
        Dispatch a processing request to the named plugin.
        
        Args:
            plugin_name (str): Name of the registered plugin.
            input_data (dict): Input matching the plugin's input schema.
            context (dict, optional): Additional context.
        
        Returns:
            dict: Output matching the plugin's output schema.
        
        Raises:
            KeyError: If plugin_name is not registered.
        """
        plugin = self._plugins.get(plugin_name)
        if not plugin:
            available = ", ".join(self._plugins.keys()) or "none"
            raise KeyError(f"Plugin '{plugin_name}' not found. Available: {available}")
        
        logger.info(f"Processing with plugin: {plugin_name}")
        return plugin.process(input_data, context)
