import os
import logging
import threading

from config import log_event, setup_logging
from .base import TextBackend

logger = setup_logging("local_backend")


class LocalTextBackend(TextBackend):
    def __init__(self, config: dict):
        model_path = os.path.abspath(config["local_model_path"])
        if not os.path.isdir(model_path):
            raise FileNotFoundError(
                f"Local text model directory does not exist: '{model_path}'."
            )
        if not os.path.isfile(os.path.join(model_path, "config.json")):
            raise FileNotFoundError(
                f"Local text model not found at '{model_path}'. "
                "Expected a Hugging Face model directory containing config.json."
            )

        self._config = dict(config)
        self._model_path = model_path
        self._load_lock = threading.Lock()
        self._model = None
        self._tokenizer = None
        self._torch = None
        self._dtype = None
        self._dtype_name = ""
        self._input_device = None
        self._load_strategy = "not_loaded"
        self._device_preference = str(self._config.get("local_device_preference", "cuda")).strip().lower()
        self._allow_cpu_offload = str(
            self._config.get("allow_cpu_offload", "true")
        ).strip().lower() == "true"
        log_event(
            logger,
            logging.INFO,
            "local_text_backend_configured",
            "Local text backend configured for lazy loading",
            category="system",
            details={
                "model_path": self._model_path,
                "device_preference": self._device_preference,
                "allow_cpu_offload": self._allow_cpu_offload,
            },
        )

    def _ensure_loaded(self):
        if self._model is not None and self._tokenizer is not None:
            return

        with self._load_lock:
            if self._model is not None and self._tokenizer is not None:
                return

            # Transformers 4.57 uses async weight materialization by default.
            # On this Windows/CUDA setup that path can crash the process during model load,
            # so we force synchronous loading for stability.
            os.environ["HF_DEACTIVATE_ASYNC_LOAD"] = "1"

            try:
                import torch
                from transformers import AutoModelForCausalLM, AutoTokenizer
            except ImportError as exc:
                raise ImportError(
                    "Local text backend requires 'torch', 'transformers', and any "
                    "model-specific optional dependencies such as 'protobuf'."
                ) from exc

            self._torch = torch
            self._dtype = torch.float16 if torch.cuda.is_available() else torch.float32
            self._dtype_name = "float16" if self._dtype == torch.float16 else "float32"

            try:
                self._tokenizer = AutoTokenizer.from_pretrained(
                    self._model_path,
                    local_files_only=True,
                )
                if self._tokenizer.pad_token_id is None and self._tokenizer.eos_token_id is not None:
                    self._tokenizer.pad_token = self._tokenizer.eos_token

                if torch.cuda.is_available() and self._device_preference != "cpu":
                    try:
                        # Match the known-good manual script as closely as possible.
                        self._model = AutoModelForCausalLM.from_pretrained(
                            self._model_path,
                            torch_dtype=torch.float16,
                            device_map="cuda",
                            local_files_only=True,
                        )
                        self._load_strategy = "gpu-forced"
                    except RuntimeError as exc:
                        if not self._is_cuda_memory_error(exc):
                            raise
                        torch.cuda.empty_cache()
                        if not self._allow_cpu_offload:
                            raise RuntimeError(
                                "Local text model does not fit fully on the GPU and CPU offload is disabled."
                            ) from exc
                        self._model = AutoModelForCausalLM.from_pretrained(
                            self._model_path,
                            torch_dtype=torch.float16,
                            device_map="auto",
                            local_files_only=True,
                        )
                        self._load_strategy = "gpu-auto-offload"
                else:
                    self._model = AutoModelForCausalLM.from_pretrained(
                        self._model_path,
                        torch_dtype=self._dtype,
                        local_files_only=True,
                    )
                    self._model.to("cpu")
                    self._load_strategy = "cpu-only" if not torch.cuda.is_available() else "cpu-forced"
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to load the local text model from '{self._model_path}'. "
                    "Ensure the folder contains a complete model export and install "
                    "any required optional dependencies for that model."
                ) from exc

            self._model.eval()
            self._input_device = self._resolve_input_device()
            self._log_backend_ready(self._model_path)

    def _resolve_input_device(self):
        try:
            return self._model.get_input_embeddings().weight.device
        except Exception:
            return next(self._model.parameters()).device

    @staticmethod
    def _is_cuda_memory_error(exc):
        text = str(exc).lower()
        return "out of memory" in text or "cuda error" in text

    def _device_map_summary(self):
        device_map = getattr(self._model, "hf_device_map", None)
        if not device_map:
            return [str(self._input_device)]
        devices = []
        for device in device_map.values():
            label = str(device)
            if label not in devices:
                devices.append(label)
        return devices

    def _log_backend_ready(self, model_path):
        details = {
            "model_path": model_path,
            "load_strategy": self._load_strategy,
            "input_device": str(self._input_device),
            "device_map": self._device_map_summary(),
            "dtype": self._dtype_name,
            "cuda_available": self._torch.cuda.is_available(),
        }
        if self._torch.cuda.is_available():
            details["gpu_name"] = self._torch.cuda.get_device_name(0)
            details["gpu_vram_gb"] = round(
                self._torch.cuda.get_device_properties(0).total_memory / (1024 ** 3), 2
            )
        log_event(
            logger,
            logging.INFO,
            "local_text_backend_ready",
            "Local text backend initialized",
            category="system",
            details=details,
        )

    def release(self):
        if self._model is None and self._tokenizer is None:
            return
        self._model = None
        self._tokenizer = None
        self._input_device = None
        self._load_strategy = "released"
        if self._torch is not None and self._torch.cuda.is_available():
            self._torch.cuda.empty_cache()

    def generate(
        self,
        system_prompt,
        user_prompt,
        max_new_tokens=256,
        temperature=0.2,
    ) -> str:
        self._ensure_loaded()
        user_content = (
            f"{system_prompt}\n\n{user_prompt}" if system_prompt else user_prompt
        )
        messages = [{"role": "user", "content": user_content}]

        prompt = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._tokenizer(prompt, return_tensors="pt").to(self._input_device)

        with self._torch.inference_mode():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=temperature > 0.35,
                temperature=max(temperature, 1e-6),
                pad_token_id=self._tokenizer.eos_token_id,
            )
        new_tokens = outputs[0][inputs["input_ids"].shape[-1]:]
        return self._tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

    def __call__(
        self,
        prompt,
        max_new_tokens=256,
        do_sample=False,
        temperature=0.2,
        return_full_text=False,
    ):
        generated_text = self.generate(
            "",
            prompt,
            max_new_tokens=max_new_tokens,
            temperature=temperature if do_sample else 0.0,
        )
        if return_full_text:
            generated_text = f"{prompt}{generated_text}"
        return [{"generated_text": generated_text}]
