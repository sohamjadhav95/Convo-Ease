from pathlib import Path
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

DEFAULT_SYSTEM_PROMPT = (
    "You are a message validator system. "
    "Only messages that align with the below rules should be marked as VALID; "
    "else, mark them as INVALID. "
    "Respond ONLY with the single word 'VALID' or 'INVALID'."
)

MODEL_DIR = Path(r"D:\convo-ease\Base_Models\gemma-2-9b-it")

tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_DIR,
    device_map="auto",
    dtype=torch.float16
)

def local_model_response(rules: str, user_message: str):
    # ✅ Gemma does NOT support "system" role — include it in user message itself
    messages = [
        {
            "role": "user",
            "content": (
                f"{DEFAULT_SYSTEM_PROMPT}\n\n"
                f"Rules:\n{rules}\n\n"
                f"User Message:\n{user_message}\n\n"
                "Reply with only VALID or INVALID."
            )
        }
    ]

    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    output_ids = model.generate(
        **inputs,
        max_new_tokens=10,
        pad_token_id=tokenizer.eos_token_id
    )

    generated_text = tokenizer.decode(output_ids[0][inputs['input_ids'].shape[-1]:], skip_special_tokens=True)
    return generated_text.strip().upper()

def validate_message(rules: str, user_message: str):
    response = local_model_response(rules, user_message)
    if "VALID" in response and "INVALID" not in response:
        return "VALID", user_message
    else:
        return "INVALID", user_message

if __name__ == "__main__":
    rules = """General information is allowed regarding class and college.
               Personal messages are not allowed.
               Only educational and learning-related messages are allowed.
               Be respectful and kind.
               Advertisements and promotions are strictly prohibited."""

    test_messages = [
        "Can you explain what quantum computing is?",
        "Hey, meet me at 5 pm at the coffee shop!",
        "Join our paid course on programming at cheap rates!",
        "What is the syllabus for computer science class this semester?"
    ]

    results = []
    print(f"{'Message':<70} | {'Validation'}")
    print("-"*90)

    for msg in test_messages:
        status, message = validate_message(rules, msg)
        results.append(status)
        print(f"{message[:65]:<70} | {status}")

    print("\nValidation Summary:")
    print(f"Total Messages: {len(test_messages)}")
    print(f"VALID: {results.count('VALID')}")
    print(f"INVALID: {results.count('INVALID')}")
