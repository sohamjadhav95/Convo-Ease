from groq import Groq

from groq import Groq

def stream_groq_response(api_key: str, system_message: str, user_message: str):
    """Yield streamed response chunks from Groq chat completion API."""
    client = Groq(api_key=api_key)
    completion = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": system_message},
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
