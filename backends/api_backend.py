from openai import OpenAI

from .base import TextBackend


def make_client(config: dict) -> OpenAI:
    """OpenAI-compatible client for whichever provider the config points at."""
    from config import AI_PROVIDER_PRESETS

    provider = config.get("provider", "custom")
    label = config.get("provider_label", provider)
    api_key = str(config.get("api_key", "")).strip()
    if not api_key:
        env_names = AI_PROVIDER_PRESETS.get(provider, {}).get("key_envs") or ("CONVOEASE_API_KEY",)
        raise ValueError(f"{label} API key is missing. Set {' or '.join(env_names)}.")
    base_url = str(config.get("base_url", "")).strip()
    if not base_url:
        raise ValueError(f"{label} base URL is missing. Set CONVOEASE_API_URL.")
    return OpenAI(
        base_url=base_url,
        api_key=api_key,
        timeout=float(config.get("api_timeout_seconds", 60)),
        max_retries=2,  # retries 429 / 5xx with backoff
    )


def message_text(response) -> str:
    """Plain text from a chat completion, tolerating list-style content."""
    if not getattr(response, "choices", None):
        return ""
    content = response.choices[0].message.content
    if isinstance(content, list):
        content = "\n".join(
            str(part.get("text", "")) for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return (content or "").strip()


def completion_options(config: dict) -> dict:
    options = {}
    effort = config.get("reasoning_effort")
    if effort:
        options["reasoning_effort"] = effort
    return options


class APITextBackend(TextBackend):
    def __init__(self, config: dict):
        self._client = make_client(config)
        self._model_id = config["api_model_id"]
        self._options = completion_options(config)

    def generate(
        self,
        system_prompt,
        user_prompt,
        max_new_tokens=256,
        temperature=0.2,
    ) -> str:
        response = self._client.chat.completions.create(
            model=self._model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_new_tokens,
            temperature=temperature,
            **self._options,
        )
        return message_text(response)
