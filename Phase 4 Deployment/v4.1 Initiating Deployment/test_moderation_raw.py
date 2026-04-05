import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core_processing_engine import TextModerationPlugin
from config import TEXT_MODEL_CONFIG

plugin = TextModerationPlugin(TEXT_MODEL_CONFIG)
print("BASE URL:", TEXT_MODEL_CONFIG["base_url"])
print("API KEY length:", len(TEXT_MODEL_CONFIG["api_key"]) if TEXT_MODEL_CONFIG["api_key"] else 0)

message = "Go to hell"
rules = "Only academic topics no off-topic discussions"

language_meta = {
    "detected_language": "en",
    "language_confidence": "1.0",
    "translated_message": "Go to hell",
    "translated_recent_messages": [],
    "translated_rules": rules,
    "language_label": "English"
}

user_prompt = plugin._build_prompt(message, rules, [], "Strict", language_meta)
system_prompt = "You are a strict Group Chat Moderator."

backend = plugin._backend
response = backend._client.chat.completions.create(
    model=backend._model_id,
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ],
    max_tokens=48,
    temperature=0.2,
)
print("RAW RESPONSE OBJECT:", response)
