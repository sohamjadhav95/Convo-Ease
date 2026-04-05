import os
import sys
import json

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core_processing_engine import TextModerationPlugin
from config import TEXT_MODEL_CONFIG

plugin = TextModerationPlugin(TEXT_MODEL_CONFIG)

message = "Go to hell"
rules = "Only academic topics no off-topic discussions, No abusive language or personal attacks, No sharing of pirated study material or answer keys, No promotional messages or spam links"

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

content = plugin.generate_text(system_prompt, user_prompt, max_new_tokens=48)
parsed = plugin._parse_response(content)

with open('test_output.json', 'w') as f:
    json.dump({
        "raw_content": content,
        "parsed": parsed
    }, f, indent=2)
