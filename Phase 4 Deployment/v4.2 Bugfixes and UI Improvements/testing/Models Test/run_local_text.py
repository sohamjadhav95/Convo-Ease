import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
import os

MODEL_PATH = r"D:\SOHAM\Convo-Ease\v3.8 Local Deployment Test\Models\Text\gemma-4-E2B-it"

print("Loading model...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_PATH,
    torch_dtype=torch.float16,   # fp16 to fit in RTX 3050 VRAM
    device_map="cuda",
)
model.eval()
print("Model ready! Type 'exit' to quit.\n")

history = []

while True:
    user_input = input("You: ").strip()
    if not user_input:
        continue
    if user_input.lower() in ("exit", "quit"):
        break

    history.append({"role": "user", "content": user_input})

    # Apply chat template
    prompt = tokenizer.apply_chat_template(
        history,
        tokenize=False,
        add_generation_prompt=True,
    )

    inputs = tokenizer(prompt, return_tensors="pt").to("cuda")

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=512,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            pad_token_id=tokenizer.eos_token_id,
        )

    # Decode only the newly generated tokens
    new_tokens = outputs[0][inputs["input_ids"].shape[-1]:]
    response = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

    history.append({"role": "assistant", "content": response})
    print(f"\nGemma: {response}\n")