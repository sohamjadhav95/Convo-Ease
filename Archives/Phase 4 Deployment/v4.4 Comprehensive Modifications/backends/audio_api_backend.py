import base64

from openai import OpenAI

from .base import AudioBackend


class APIAudioBackend(AudioBackend):
    def __init__(self, config: dict):
        self._client = OpenAI(
            base_url=config["base_url"],
            api_key=config["api_key"],
        )
        self._model_id = config["api_model_id"]

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
        raw_bytes = base64.b64decode(base64_data)
        fmt = self._normalize_format(mime_type)
        file_name = f"input.{fmt}"
        normalized_mime_type = self._mime_type_for_format(fmt)
        transcription = self._client.audio.transcriptions.create(
            file=(file_name, raw_bytes, normalized_mime_type),
            model=self._model_id,
        )
        if hasattr(transcription, "text"):
            return (transcription.text or "").strip()
        if isinstance(transcription, dict):
            return (transcription.get("text", "") or "").strip()
        return str(transcription).strip()
