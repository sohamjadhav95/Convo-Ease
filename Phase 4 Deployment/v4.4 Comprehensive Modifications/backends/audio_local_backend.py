import base64
import os
import shutil
import tempfile
from contextlib import contextmanager

import whisper

from .base import AudioBackend


class LocalAudioBackend(AudioBackend):
    def __init__(self, config: dict):
        model_size = config.get("whisper_model_size", "base")
        # Loads from ~/.cache/whisper/ - downloads automatically on first run
        self._model = whisper.load_model(model_size)

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
    def _resolve_ffmpeg_dir() -> str:
        configured = os.getenv("FFMPEG_BINARY", "").strip().strip('"')
        if configured and os.path.isfile(configured):
            return os.path.dirname(os.path.abspath(configured))

        try:
            import imageio_ffmpeg

            ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            if ffmpeg_path and os.path.isfile(ffmpeg_path):
                ffmpeg_dir = os.path.join(tempfile.gettempdir(), "convoease-ffmpeg")
                os.makedirs(ffmpeg_dir, exist_ok=True)
                shim_path = os.path.join(ffmpeg_dir, "ffmpeg.exe")
                if not os.path.isfile(shim_path):
                    shutil.copy2(ffmpeg_path, shim_path)
                return ffmpeg_dir
        except Exception:
            pass

        return ""

    @contextmanager
    def _ffmpeg_path_context(self):
        ffmpeg_dir = self._resolve_ffmpeg_dir()
        original_path = os.environ.get("PATH", "")
        if ffmpeg_dir:
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + original_path
        try:
            yield
        finally:
            if ffmpeg_dir:
                os.environ["PATH"] = original_path

    def transcribe(self, base64_data: str, mime_type: str = "audio/wav") -> str:
        raw_bytes = base64.b64decode(base64_data)

        # Determine file extension from mime type
        ext = self._normalize_format(mime_type)

        # Write to temp file - whisper requires a file path, not bytes
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
            tmp.write(raw_bytes)
            tmp_path = tmp.name

        try:
            with self._ffmpeg_path_context():
                result = self._model.transcribe(tmp_path)
            return (result.get("text") or "").strip()
        finally:
            os.remove(tmp_path)  # always clean up
