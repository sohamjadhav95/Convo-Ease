from openai import OpenAI
import base64


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key="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"
)

#Text example
resp = client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=[
        {"role": "user", "content": "Do not generate anyting, Not provide a single word"}
    ]
)
print(resp.choices[0].message.content)


# Image example
image_path = r"C:\Users\soham\OneDrive\Pictures\Screenshots\Screenshot 2026-03-30 121828.png"
base64_image = encode_image(image_path)
completion = client.chat.completions.create(
    model="meta-llama/llama-4-scout-17b-16e-instruct",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Summarize this image briefly."},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                }
            ]
        }
    ]
)
print(completion.choices[0].message.content)
