from abc import ABC, abstractmethod


class TextBackend(ABC):
    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_new_tokens: int = 256,
        temperature: float = 0.2,
    ) -> str:
        """Return the model's plain-text response."""

