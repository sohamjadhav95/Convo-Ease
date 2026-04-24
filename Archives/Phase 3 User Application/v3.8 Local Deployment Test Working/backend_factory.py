import os

from backends.api_backend import APITextBackend
from backends.audio_api_backend import APIAudioBackend
from backends.image_api_backend import APIImageBackend


def _has_model_config(path: str) -> bool:
    return os.path.isfile(os.path.join(path, "config.json"))


def resolve_text_backend_config(config: dict) -> dict:
    resolved = dict(config)
    if resolved.get("backend", "api") != "local":
        return resolved

    model_path = os.path.abspath(str(resolved.get("local_model_path", "")).strip())
    if not model_path:
        raise FileNotFoundError(
            "Local text backend selected but no local_model_path was configured."
        )

    if _has_model_config(model_path):
        resolved["local_model_path"] = model_path
        return resolved

    if not os.path.isdir(model_path):
        raise FileNotFoundError(
            f"Local text model path does not exist: '{model_path}'."
        )

    candidates = sorted(
        entry.path
        for entry in os.scandir(model_path)
        if entry.is_dir() and _has_model_config(entry.path)
    )

    if len(candidates) == 1:
        resolved["local_model_path"] = candidates[0]
        return resolved

    if not candidates:
        raise FileNotFoundError(
            f"No local text model was found under '{model_path}'. "
            "Point CONVOEASE_TEXT_MODEL_PATH to a model directory that contains config.json."
        )

    candidate_names = ", ".join(os.path.basename(path) for path in candidates)
    raise FileNotFoundError(
        f"Multiple local text models were found under '{model_path}': {candidate_names}. "
        "Point CONVOEASE_TEXT_MODEL_PATH to the exact model directory you want to load."
    )


def _create_local_text_backend(config: dict):
    from backends.local_backend import LocalTextBackend

    return LocalTextBackend(config)


def _resolve_media_backend_config(config: dict, backend_name: str) -> dict:
    resolved = dict(config)
    if resolved.get("backend", "api") != "local":
        return resolved

    model_path = os.path.abspath(str(resolved.get("local_model_path", "")).strip())
    if not model_path:
        raise FileNotFoundError(
            f"Local {backend_name} backend selected but no local_model_path was configured."
        )

    if _has_model_config(model_path):
        resolved["local_model_path"] = model_path
        return resolved

    if not os.path.isdir(model_path):
        raise FileNotFoundError(
            f"Local {backend_name} model path does not exist: '{model_path}'."
        )

    candidates = sorted(
        entry.path
        for entry in os.scandir(model_path)
        if entry.is_dir() and _has_model_config(entry.path)
    )

    if len(candidates) == 1:
        resolved["local_model_path"] = candidates[0]
        return resolved

    env_var = f"CONVOEASE_{backend_name.upper()}_MODEL_PATH"
    if not candidates:
        raise FileNotFoundError(
            f"No local {backend_name} model was found under '{model_path}'. "
            f"Point {env_var} to a model directory that contains config.json."
        )

    candidate_names = ", ".join(os.path.basename(path) for path in candidates)
    raise FileNotFoundError(
        f"Multiple local {backend_name} models were found under '{model_path}': {candidate_names}. "
        f"Point {env_var} to the exact model directory you want to load."
    )


def _create_local_image_backend(config: dict):
    from backends.image_local_backend import LocalImageBackend

    return LocalImageBackend(config)


def _create_local_audio_backend(config: dict):
    from backends.audio_local_backend import LocalAudioBackend

    return LocalAudioBackend(config)


def get_text_backend(config: dict):
    mode = config.get("backend", "api")
    if mode == "api":
        return APITextBackend(config)
    if mode == "local":
        return _create_local_text_backend(resolve_text_backend_config(config))
    raise ValueError(f"Unknown backend mode: '{mode}'. Must be 'api' or 'local'.")


def get_image_backend(config: dict):
    mode = config.get("backend", "api")
    if mode == "api":
        return APIImageBackend(config)
    if mode == "local":
        return _create_local_image_backend(_resolve_media_backend_config(config, "image"))
    raise ValueError(
        f"Unknown image backend mode: '{mode}'. Must be 'api' or 'local'."
    )


def get_audio_backend(config: dict):
    mode = config.get("backend", "api")
    if mode == "api":
        return APIAudioBackend(config)
    if mode == "local":
        # whisper manages its own model cache - no local path resolution needed
        return _create_local_audio_backend(config)
    raise ValueError(
        f"Unknown audio backend mode: '{mode}'. Must be 'api' or 'local'."
    )
