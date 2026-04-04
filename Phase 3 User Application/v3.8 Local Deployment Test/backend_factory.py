from backends.api_backend import APITextBackend
from backends.local_backend import LocalTextBackend


def get_text_backend(config: dict):
    mode = config.get("backend", "api")
    if mode == "api":
        return APITextBackend(config)
    if mode == "local":
        return LocalTextBackend(config)
    raise ValueError(f"Unknown backend mode: '{mode}'. Must be 'api' or 'local'.")
