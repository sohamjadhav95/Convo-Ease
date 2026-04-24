from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="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"
)

resp = client.chat.completions.create(
    model="openai/gpt-oss-120b:free",
    messages=[
        {"role": "user", "content": "How many r's are in strawberry?"}
    ]
)

print(resp.choices[0].message.content)
