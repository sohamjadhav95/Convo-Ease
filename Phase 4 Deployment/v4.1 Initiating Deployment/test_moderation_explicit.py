import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core_processing_engine import TextModerationPlugin
from config import TEXT_MODEL_CONFIG

plugin = TextModerationPlugin(TEXT_MODEL_CONFIG)

base_url = TEXT_MODEL_CONFIG["base_url"]
api_key = TEXT_MODEL_CONFIG["api_key"]
model_id = TEXT_MODEL_CONFIG["api_model_id"]

message = "Go to hell"
rules = "Only academic topics no off-topic discussions"

user_prompt = "user prompt"
system_prompt = "system prompt"

try:
    response = plugin._backend._client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=48,
        temperature=0.2,
    )
    res_str = repr(response)
    content = response.choices[0].message.content or ""
except Exception as e:
    res_str = "EXCEPTION: " + str(e)
    content = "EXCEPTION: " + str(e)

with open('test_output.txt', 'w', encoding='utf-8') as f:
    f.write(f"BASE URL: {base_url}\n")
    f.write(f"MODEL: {model_id}\n")
    f.write(f"RAW RES: {res_str}\n")
    f.write(f"CONTENT: '{content}'\n")
