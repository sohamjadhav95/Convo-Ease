import os
import sys
import json

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core_processing_engine import TextModerationPlugin
from config import TEXT_MODEL_CONFIG

plugin = TextModerationPlugin(TEXT_MODEL_CONFIG)

base_url = TEXT_MODEL_CONFIG["base_url"]
api_key = TEXT_MODEL_CONFIG["api_key"]
model_id = TEXT_MODEL_CONFIG["api_model_id"]

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
    model=model_id,
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ],
    max_tokens=512,
    temperature=0.2,
)

content = response.choices[0].message.content or ""
parsed = plugin._parse_response(content)

with open('test_output_512.txt', 'w', encoding='utf-8') as f:
    f.write(f"RAW RES: {repr(response)}\n")
    f.write(f"CONTENT: '{content}'\n")
    f.write(f"PARSED: '{parsed}'\n")
