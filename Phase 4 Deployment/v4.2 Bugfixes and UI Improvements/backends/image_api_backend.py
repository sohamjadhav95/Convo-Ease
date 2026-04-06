from openai import OpenAI

from .base import ImageBackend


class APIImageBackend(ImageBackend):
    def __init__(self, config: dict):
        self._client = OpenAI(
            base_url=config["base_url"],
            api_key=config["api_key"],
        )
        self._model_id = config["api_model_id"]

    def describe(self, base64_data: str, mime_type: str) -> str:
        completion = self._client.chat.completions.create(
            model=self._model_id,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": (
                        "Describe this image in 1-3 concise sentences. "
                        "Be objective and focus on visible content."
                    )},
                    {"type": "image_url", "image_url": {
                        "url": f"data:{mime_type};base64,{base64_data}"
                    }}
                ]
            }]
        )
        return (completion.choices[0].message.content or "").strip()
