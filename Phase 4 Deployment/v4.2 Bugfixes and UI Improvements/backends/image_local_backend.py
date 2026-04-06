import base64
import io
import os
import threading

import torch
from PIL import Image
from transformers import AutoModelForCausalLM, AutoProcessor

from .base import ImageBackend

MODERATION_PROMPT = (
    "Describe this image in detail for content moderation. "
    "Include all visible people and actions, any objects, "
    "any text visible, and identify any harmful, offensive, "
    "or inappropriate content."
)


class LocalImageBackend(ImageBackend):
    def __init__(self, config: dict):
        self._model_path = os.path.abspath(config["local_model_path"])
        if not os.path.isfile(os.path.join(self._model_path, "config.json")):
            raise FileNotFoundError(
                f"Image model not found at '{self._model_path}'. "
                "Gemma model must be present in Models/Text/ for local image mode."
            )
        self._processor = None
        self._model = None
        self._dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        self._input_device = "cuda" if torch.cuda.is_available() else "cpu"
        self._load_lock = threading.Lock()

    @staticmethod
    def _is_cuda_memory_error(exc: Exception) -> bool:
        text = str(exc).lower()
        return "out of memory" in text or "cuda error" in text

    def _load_model(self, target_device):
        if target_device == "cuda":
            self._dtype = torch.float16
            self._input_device = "cuda"
            model = AutoModelForCausalLM.from_pretrained(
                self._model_path,
                torch_dtype=torch.float16,
                device_map="cuda",
                local_files_only=True,
            )
        else:
            self._dtype = torch.float32
            self._input_device = "cpu"
            model = AutoModelForCausalLM.from_pretrained(
                self._model_path,
                torch_dtype=torch.float32,
                local_files_only=True,
            )
            model.to("cpu")
        model.eval()
        return model

    def _build_inputs(self, prompt, image):
        inputs = self._processor(
            text=prompt,
            images=image,
            return_tensors="pt",
        )
        inputs = inputs.to(self._input_device)
        if "pixel_values" in inputs:
            inputs["pixel_values"] = inputs["pixel_values"].to(dtype=self._dtype)
        return inputs

    def release(self):
        if self._model is None and self._processor is None:
            return
        self._model = None
        self._processor = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _ensure_loaded(self):
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            self._processor = AutoProcessor.from_pretrained(
                self._model_path,
                local_files_only=True,
            )
            if torch.cuda.is_available():
                try:
                    # Prefer the validated single-GPU path, then fall back to CPU
                    # when the text backend already occupies most of the 4 GB VRAM budget.
                    self._model = self._load_model("cuda")
                except RuntimeError as exc:
                    if not self._is_cuda_memory_error(exc):
                        raise
                    torch.cuda.empty_cache()
                    self._model = self._load_model("cpu")
            else:
                self._model = self._load_model("cpu")

    def describe(self, base64_data: str, mime_type: str) -> str:
        self._ensure_loaded()

        image_bytes = base64.b64decode(base64_data)
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        messages = [{
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text",  "text": MODERATION_PROMPT},
            ]
        }]

        prompt = self._processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._build_inputs(prompt, image)

        try:
            with torch.no_grad():
                outputs = self._model.generate(
                    **inputs,
                    max_new_tokens=256,
                    do_sample=True,
                    temperature=0.7,
                    top_p=0.9,
                    pad_token_id=self._processor.tokenizer.eos_token_id,
                )
        except RuntimeError as exc:
            if not torch.cuda.is_available() or not self._is_cuda_memory_error(exc):
                raise
            torch.cuda.empty_cache()
            with self._load_lock:
                self._model = self._load_model("cpu")
            inputs = self._build_inputs(prompt, image)
            with torch.no_grad():
                outputs = self._model.generate(
                    **inputs,
                    max_new_tokens=256,
                    do_sample=True,
                    temperature=0.7,
                    top_p=0.9,
                    pad_token_id=self._processor.tokenizer.eos_token_id,
                )

        new_tokens = outputs[0][inputs["input_ids"].shape[-1]:]
        return self._processor.decode(new_tokens, skip_special_tokens=True).strip()
