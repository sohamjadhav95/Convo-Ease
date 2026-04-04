import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from .base import TextBackend


class LocalTextBackend(TextBackend):
    def __init__(self, config: dict):
        model_path = config["local_model_path"]
        dtype = torch.float16 if torch.cuda.is_available() else torch.float32

        self._tokenizer = AutoTokenizer.from_pretrained(
            model_path, local_files_only=True
        )
        self._model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=dtype,
            device_map="auto",
            local_files_only=True,
        )
        self._model.eval()

    def generate(
        self,
        system_prompt,
        user_prompt,
        max_new_tokens=256,
        temperature=0.2,
    ) -> str:
        user_content = (
            f"{system_prompt}\n\n{user_prompt}" if system_prompt else user_prompt
        )
        messages = [{"role": "user", "content": user_content}]

        prompt = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        device = next(self._model.parameters()).device
        inputs = self._tokenizer(prompt, return_tensors="pt").to(device)

        with torch.no_grad():
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

