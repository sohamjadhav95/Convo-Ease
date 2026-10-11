import base64

from .api_backend import completion_options, make_client, message_text
from .base import AudioBackend

TRANSCRIBE_PROMPT = (
    "Transcribe the speech in this audio exactly as spoken, in its original language. "
    "Return only the transcript text, with no labels, timestamps or commentary. "
    "If there is no intelligible speech, return exactly: [no speech]"
)
NO_SPEECH = "[no speech]"


class APIAudioBackend(AudioBackend):
    """Speech-to-text through a hosted API.

    audio_mode "transcription": OpenAI-style /audio/transcriptions (Groq, OpenAI).
    audio_mode "chat": audio sent inside a chat request (Gemini).
    """

    def __init__(self, config: dict):
        self._mode = config.get("audio_mode", "transcription")
        if self._mode == "none":
            raise ValueError(
                f"{config.get('provider_label', 'This provider')} has no speech API. "
                "Set CONVOEASE_AUDIO_PROVIDER to gemini or groq, or use local Whisper."
            )
        self._client = make_client(config)
        self._model_id = config["api_model_id"]
        self._options = completion_options(config)

    @staticmethod
    def _normalize_format(mime_type: str) -> str:
        fmt = mime_type.split("/")[-1].split(";")[0].lower().strip() or "wav"
        aliases = {
            "mpeg": "mp3",
            "mp4": "m4a",
            "x-m4a": "m4a",
            "x-wav": "wav",
            "wave": "wav",
        }
        return aliases.get(fmt, fmt)

    @staticmethod
    def _mime_type_for_format(fmt: str) -> str:
        mapping = {
            "mp3": "audio/mpeg",
            "m4a": "audio/m4a",
            "wav": "audio/wav",
            "ogg": "audio/ogg",
            "opus": "audio/opus",
            "flac": "audio/flac",
            "webm": "audio/webm",
        }
        return mapping.get(fmt, f"audio/{fmt}")

    def transcribe(self, base64_data: str, mime_type: str = "audio/wav") -> str:
        fmt = self._normalize_format(mime_type)
        if self._mode == "chat":
            return self._transcribe_with_chat(base64_data, fmt)

        transcription = self._client.audio.transcriptions.create(
            file=(f"input.{fmt}", base64.b64decode(base64_data), self._mime_type_for_format(fmt)),
            model=self._model_id,
        )
        if hasattr(transcription, "text"):
            return (transcription.text or "").strip()
        if isinstance(transcription, dict):
            return (transcription.get("text", "") or "").strip()
        return str(transcription).strip()

    def _transcribe_with_chat(self, base64_data: str, fmt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model_id,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": TRANSCRIBE_PROMPT},
                    {"type": "input_audio", "input_audio": {"data": base64_data, "format": fmt}},
                ],
            }],
            max_tokens=2048,
            temperature=0,
            **self._options,
        )
        text = message_text(response)
        return "" if text.strip().lower() == NO_SPEECH else text
