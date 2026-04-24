
from openai import OpenAI

'''
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
'''

client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key="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",
)

completion = client.chat.completions.create(
  extra_headers={
    "HTTP-Referer": "<YOUR_SITE_URL>", # Optional. Site URL for rankings on openrouter.ai.
    "X-Title": "<YOUR_SITE_NAME>", # Optional. Site title for rankings on openrouter.ai.
  },
  extra_body={},
  model="google/gemma-3-27b-it:free",
  messages=[
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "What is in this image?"
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "https://live.staticflickr.com/3851/14825276609_098cac593d_b.jpg"
          }
        }
      ]
    }
  ]
)
print(completion.choices[0].message.content)