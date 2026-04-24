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
  result = engine.process("text_moderation", input_data={"message": "...", "rules": "..."})
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
            # Example:
            #   from transformers import AutoModelForCausalLM, AutoTokenizer
            #   self._local_model = AutoModelForCausalLM.from_pretrained(self.config["model_path"])
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
            logger.info(f"Moderation API response for '{message[:50]}...': {content[:100]}")
            return self._parse_response(content)

        except Exception as e:
            logger.error(f"Moderation API error: {str(e)}")
            return {"allowed": False, "reason": f"Moderation Error: {str(e)}"}

    def _process_local(self, message, rules, recent_messages):
        """Process using local model (future implementation)."""
        # ── Placeholder for local model inference ──
        # When implementing:
        #   1. Build the same prompt as _process_api
        #   2. Feed it to self._local_model
        #   3. Parse the response with _parse_response
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
# FUTURE PLUGIN TEMPLATES (uncomment and implement when needed)
# ═══════════════════════════════════════════════════════════════════════════════

# class ImageProcessingPlugin(ProcessingPlugin):
#     """Process images — moderation, generation, analysis."""
#     name = "image_processing"
#
#     def get_input_schema(self):
#         return {"image_data": "bytes", "task": "str — 'moderate' | 'generate' | 'analyze'"}
#
#     def get_output_schema(self):
#         return {"result": "dict", "status": "str"}
#
#     def process(self, input_data, context=None):
#         pass

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
