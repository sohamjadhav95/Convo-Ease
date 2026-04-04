from openai import OpenAI

from .base import TextBackend


class APITextBackend(TextBackend):
    def __init__(self, config: dict):
        self._client = OpenAI(
            base_url=config["base_url"],
            api_key=config["api_key"],
        )
        self._model_id = config["api_model_id"]

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
        )
        return (response.choices[0].message.content or "").strip()

