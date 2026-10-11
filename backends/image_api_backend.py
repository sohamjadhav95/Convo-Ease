from .api_backend import completion_options, make_client, message_text
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
        self._client = make_client(config)
        self._model_id = config["api_model_id"]
        self._options = completion_options(config)

    def describe(self, base64_data: str, mime_type: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model_id,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": IMAGE_SUMMARY_PROMPT},
                    {"type": "image_url", "image_url": {
                        "url": f"data:{mime_type};base64,{base64_data}"
                    }},
                ],
            }],
            # Leaves room for models that think before answering.
            max_tokens=400,
            temperature=0.2,
            **self._options,
        )
        return _normalize_summary(message_text(response))
