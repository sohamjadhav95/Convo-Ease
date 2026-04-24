"""
Gemma 4 Image Test — mirrors the working text script exactly
"""

import torch
from transformers import AutoProcessor, AutoModelForCausalLM
from PIL import Image
import os

MODEL_PATH = r"D:\SOHAM\Convo-Ease\v3.8 Local Deployment Test\Models\Text\gemma-4-E2B-it"

MODERATION_PROMPT = (
    "Describe this image in detail for content moderation. "
    "Include all visible people and actions, any objects, "
    "any text visible, and identify any harmful, offensive, "
    "or inappropriate content."
)

print("Loading model...")
processor = AutoProcessor.from_pretrained(MODEL_PATH)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_PATH,
    torch_dtype=torch.float16,   # same as working text script
    device_map="cuda",           # same as working text script
)
model.eval()
print("Model ready! Type 'exit' to quit.\n")

while True:
    path = input("Image path: ").strip().strip('"').strip("'")
    if not path:
        continue
    if path.lower() in ("exit", "quit"):
        break
    if not os.path.isfile(path):
        print(f"  File not found: {path}\n")
        continue

    image = Image.open(path).convert("RGB")

    messages = [{
        "role": "user",
        "content": [
            {"type": "image", "image": image},
            {"type": "text",  "text": MODERATION_PROMPT},
        ]
    }]

    prompt = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = processor(
        text=prompt,
        images=image,
        return_tensors="pt",
    ).to("cuda", dtype=torch.float16)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=256,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            pad_token_id=processor.tokenizer.eos_token_id,
        )

    new_tokens = outputs[0][inputs["input_ids"].shape[-1]:]
    response = processor.decode(new_tokens, skip_special_tokens=True).strip()
    print(f"\nGemma: {response}\n")