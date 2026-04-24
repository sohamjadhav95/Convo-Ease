import io
import os
import shutil

import speech_recognition as sr


def _normalize_format(path):
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if ext == "mpeg":
        return "mp3"
    if ext == "x-wav":
        return "wav"
    if ext == "wave":
        return "wav"
    if ext == "aif":
        return "aiff"
    return ext or None


print("SpeechRecognition manual tester ready.")
print("Uses recognize_google(), so an internet connection is required.\n")

recognizer = sr.Recognizer()
direct_formats = {"wav", "flac", "aiff", "aifc"}

while True:
    path = input("Audio path (wav/mp3/ogg/m4a, or 'exit'): ").strip()
    if path.lower() in ("exit", "quit"):
        break
    if not os.path.isfile(path):
        print(f"  File not found: {path}\n")
        continue

    try:
        fmt = _normalize_format(path)
        audio_source = path

        if fmt not in direct_formats:
            if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
                print(
                    "\nFailed to process audio:\n"
                    "  MP3/M4A/OGG input requires ffmpeg and ffprobe on PATH.\n"
                    "  Install them, or test with a WAV/FLAC file instead.\n"
                )
                continue

            from pydub import AudioSegment

            audio_segment = AudioSegment.from_file(path, format=fmt)
            wav_buffer = io.BytesIO()
            audio_segment.export(wav_buffer, format="wav")
            wav_buffer.seek(0)
            audio_source = wav_buffer

        with sr.AudioFile(audio_source) as source:
            audio_data = recognizer.record(source)

        transcript = (recognizer.recognize_google(audio_data) or "").strip()
        print(f"\nTranscript:\n  {transcript or '(no speech detected)'}\n")
    except sr.UnknownValueError:
        print("\nTranscript:\n  (no speech detected)\n")
    except sr.RequestError as exc:
        print(f"\nSpeech recognition service error:\n  {exc}\n")
    except Exception as exc:
        print(f"\nFailed to process audio:\n  {exc}\n")
