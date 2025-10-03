from pathlib import Path
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

# =======================
# System prompt
# =======================
DEFAULT_SYSTEM_PROMPT = (
    "You are a messages validator system. "
    "Only messages align to the below rules mark them as valid else mark as Invalid. "
    "*ONLY RESPOND WITH VALID OR INVALID WORD*"
)

# =======================
# Path to your local model directory
# =======================
MODEL_DIR = Path(r"D:\Convo-Ease\Gemma-2-Ataraxy-9B")  # <-- Change to your model path

# =======================
# Load tokenizer and model locally
# =======================
tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_DIR,
    device_map="auto",
    dtype=torch.float16
)

# =======================
# Local model inference
# =======================
def local_model_response(rules: str, user_message: str):
    system_prompt = DEFAULT_SYSTEM_PROMPT
    prompt = (
        system_prompt
        + "\nRules: " + rules
        + "\nUser Message: " + user_message
        + "\nOnly reply with VALID or INVALID in uppercase."
    )

    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    output_ids = model.generate(
        **inputs,
        max_new_tokens=128
    )

    return tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()

# =======================
# Validation function
# =======================
def validate_message(rules: str, user_message: str):
    full_response = local_model_response(rules, user_message).upper()
    if full_response == "VALID":
        return "VALID", user_message
    else:
        return "INVALID", user_message

# =======================
# Main test runner
# =======================
if __name__ == "__main__":
    rules = """ General information is also allowed regarding class and college.
                Personal Messages are not allowed.
                Only educational and Learning messages are allowed.
                Be respectful and Kind.
                Advertisement and promotions are strictly prohibited. """

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

    valid_count = results.count("VALID")
    invalid_count = results.count("INVALID")

    print("\nValidation Summary:")
    print(f"Total Messages: {len(test_messages)}")
    print(f"VALID: {valid_count}")
    print(f"INVALID: {invalid_count}")
