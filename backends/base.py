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


class ImageBackend(ABC):
    @abstractmethod
    def describe(self, base64_data: str, mime_type: str) -> str:
        """Return a plain-text description of the image."""


class AudioBackend(ABC):
    @abstractmethod
    def transcribe(self, base64_data: str, mime_type: str = "audio/wav") -> str:
        """Return the full speech transcript as plain text."""
