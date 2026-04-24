import requests, base64, json, mimetypes

invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"
stream = True

API_KEY = "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"  # your key


def encode_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# =========================
# INPUT
# =========================
image_path = r"C:\Users\soham\OneDrive\Pictures\Screenshots\test.png"
prompt = "Explain this image briefly"

base64_image = encode_image(image_path)

mime_type, _ = mimetypes.guess_type(image_path)
mime_type = mime_type or "image/png"


headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "text/event-stream" if stream else "application/json",
    "Content-Type": "application/json"
}

payload = {
    "model": "meta/llama-3.2-90b-vision-instruct",
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{base64_image}"
                    }
                }
            ]
        }
    ],
    "max_tokens": 512,
    "temperature": 1,
    "top_p": 1,
    "stream": stream
}

response = requests.post(invoke_url, headers=headers, json=payload)

print("Status:", response.status_code)

# =========================
# STREAM PARSER (SDK-LIKE)
# =========================
if stream:
    for line in response.iter_lines():
        if not line:
            continue

        decoded = line.decode("utf-8").strip()

        if decoded.startswith("data: "):
            data = decoded[6:]

            if data == "[DONE]":
                break

            try:
                chunk = json.loads(data)

                delta = chunk["choices"][0]["delta"]

                # content
                if "content" in delta and delta["content"]:
                    print(delta["content"], end="", flush=True)

                # reasoning (like SDK)
                if "reasoning_content" in delta:
                    print(delta["reasoning_content"], end="", flush=True)

            except Exception as e:
                print("\nParse error:", e)
else:
    print(response.json())