
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
import base64

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

image_path = r"C:\Users\soham\OneDrive\Pictures\Screenshots\Screenshot 2026-02-21 191109.png"
base64_image = encode_image(image_path)

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
          "text": "Summerise this image in short based on the content shown in image"
        },
        {
          "type": "image_url",
          "image_url": {
            "url": f"data:image/png;base64,{base64_image}"
          }
        }
      ]
    }
  ]
)
print(completion.choices[0].message.content)

