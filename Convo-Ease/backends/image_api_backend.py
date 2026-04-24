import requests

from .base import ImageBackend

IMAGE_SUMMARY_PROMPT = (
    "Describe the image in plain text only. "
    "Use 1 or 2 short sentences maximum. "
    "Do not use markdown, bullets, labels, headings, or emoji. "
    "Focus only on the main visible content."
)


def _normalize_summary(text: str) -> str:
    content = str(text or "").strip()
    if not content:
        return ""

    replacements = {
        "\r": " ",
        "\n": " ",
        "**": "",
        "__": "",
        "`": "",
        "*": "",
        "#": "",
        ">": "",
    }
    for old, new in replacements.items():
        content = content.replace(old, new)

    content = " ".join(content.split()).strip(" -:;,.")
    if not content:
        return ""

    sentences = []
    current = ""
    for char in content:
        current += char
        if char in ".!?":
            sentences.append(current.strip())
            current = ""
            if len(sentences) == 2:
                break
    if current.strip() and len(sentences) < 2:
        sentences.append(current.strip())

    summary = " ".join(sentence.strip() for sentence in sentences if sentence.strip()).strip()
    return summary[:220].rstrip(" ,;:-")


class APIImageBackend(ImageBackend):
    def __init__(self, config: dict):
        self._api_key = str(config.get("api_key", "")).strip()
        if not self._api_key:
            raise ValueError(
                "NVIDIA API key is missing. Set NVIDIA_API_KEY, NVIDIA_NIM_API_KEY, or CONVOEASE_API_KEY."
            )
        self._base_url = str(config["base_url"]).rstrip("/")
        self._model_id = config["api_model_id"]
        self._timeout = int(config.get("api_timeout_seconds", 90))

    def describe(self, base64_data: str, mime_type: str) -> str:
        response = requests.post(
            f"{self._base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json={
                "model": self._model_id,
                "messages": [{
                    "role": "user",
                        "content": [
                        {"type": "text", "text": IMAGE_SUMMARY_PROMPT},
                        {"type": "image_url", "image_url": {
                            "url": f"data:{mime_type};base64,{base64_data}"
                        }},
                    ],
                }],
                "max_tokens": 120,
                "temperature": 0.2,
                "top_p": 1,
                "stream": False,
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()

        choices = payload.get("choices") or []
        if not choices:
            return ""

        message = choices[0].get("message") or {}
        content = message.get("content", "")
        if isinstance(content, str):
            return _normalize_summary(content)

        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text", "")).strip())
            return _normalize_summary("\n".join(part for part in parts if part))

        return _normalize_summary(str(content or ""))
