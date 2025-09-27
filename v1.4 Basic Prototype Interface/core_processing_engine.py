from groq import Groq

from groq import Groq

# Streaming core logic  

DEFAULT_SYSTEM_PROMPT = "You are a group chat assistant. Follow the rules provided to moderate and respond to messages."

def stream_groq_response(api_key: str, rules: str, user_message: str):
    """Yield streamed response chunks from Groq chat completion API. Uses rules as system prompt."""
    system_prompt = rules.strip() if rules.strip() else DEFAULT_SYSTEM_PROMPT
    client = Groq(api_key=api_key)
    completion = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        temperature=0.5,
        max_tokens=8192, 
        top_p=1,
        stream=True,
        stop=None
    )
    for chunk in completion:
        yield chunk.choices[0].delta.content or ""

# Moderation/validation logic

def validate_message(api_key: str, rules: str, user_message: str):
    """Validate a message against rules using Groq. Returns (is_valid, reason)."""
    system_prompt = (
        "You are a message validator system. Only messages aligning to the below rules are valid. "
        "Respond with JSON: {\"valid\": true/false, \"reason\": string}.\nRules:\n" + (rules.strip() if rules.strip() else DEFAULT_SYSTEM_PROMPT)
    )
    user_prompt = user_message
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.1,
        max_tokens=256,
        top_p=1,
        stream=False,
        stop=None
    )
    import json
    try:
        result = json.loads(response.choices[0].message.content)
        return bool(result.get("valid", True)), result.get("reason", "No reason provided.")
    except Exception:
        return True, "Validation failed, allowing message."

def validate_and_stream_message(api_key: str, rules: str, user_message: str):
    """Validate message, if valid, stream response. Returns (is_valid, reason, stream_generator)."""
    is_valid, reason = validate_message(api_key, rules, user_message)
    if is_valid:
        return True, reason, stream_groq_response(api_key, rules, user_message)
    else:
        return False, reason, None
