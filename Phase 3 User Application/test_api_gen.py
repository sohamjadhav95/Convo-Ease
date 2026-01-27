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
