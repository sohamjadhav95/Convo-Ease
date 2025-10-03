from groq import Groq

# Streaming core logic  

DEFAULT_SYSTEM_PROMPT = "You are a messages validator system. Only messages align to the below rules mark them as valid else mark as Invalid. *ONLY RESPOND WITH VALID OR INVALID WORD*"

def groq_response(api_key: str, rules: str, user_message: str):
    """Yield streamed response chunks from Groq chat completion API. Uses rules as system prompt."""
    system_prompt = DEFAULT_SYSTEM_PROMPT
    client = Groq(api_key=api_key)
    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt + rules},
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

def validate_message(api_key: str, rules: str, user_message: str):
    response_chunks = []
    for chunk in groq_response(api_key, rules, user_message):
        response_chunks.append(chunk)
    full_response = "".join(response_chunks).strip().upper()
    if full_response == "VALID":
        return user_message
    else:
        return "Invalid Message"