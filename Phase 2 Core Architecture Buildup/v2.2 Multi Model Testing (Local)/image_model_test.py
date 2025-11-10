from pathlib import Path
from transformers import AutoProcessor, Blip2ForConditionalGeneration
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers import BlipProcessor, BlipForConditionalGeneration
import torch
from PIL import Image

# =======================================
# CONFIG
# =======================================
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# BLIP-2 for image captioning
IMG_MODEL_DIR = r"D:\convo-ease\Base_Models\blip-image-captioning-large"  # or local path if downloaded

# Gemma text validator model
TEXT_MODEL_DIR = Path(r"D:\convo-ease\Base_Models\gemma-2-9b-it")

# =======================================
# Load Models
# =======================================
print("Loading image summarization model...")
image_processor = BlipProcessor.from_pretrained(IMG_MODEL_DIR)
image_model = BlipForConditionalGeneration.from_pretrained(
    IMG_MODEL_DIR,
    torch_dtype=torch.float16 if DEVICE == "cuda" else torch.float32
).to(DEVICE)

print("Loading text validation model...")
tokenizer = AutoTokenizer.from_pretrained(TEXT_MODEL_DIR)
text_model = AutoModelForCausalLM.from_pretrained(
    TEXT_MODEL_DIR,
    device_map="auto",
    dtype=torch.float16
)

# =======================================
# Generate Image Summary
# =======================================
def summarize_image(image_path: str) -> str:
    """Generate a short summary (1–2 sentences) for an image."""
    image = Image.open(image_path).convert("RGB")
    inputs = image_processor(images=image, return_tensors="pt").to(DEVICE, torch.float16)

    summary_ids = image_model.generate(**inputs, max_new_tokens=50)
    summary = image_processor.tokenizer.decode(summary_ids[0], skip_special_tokens=True)
    print(summary)
    return summary.strip()

# =======================================
# Text Validation (Gemma)
# =======================================
DEFAULT_SYSTEM_PROMPT = (
    "You are an image content validator system. "
    "Only image summaries that align with the below rules should be marked as VALID; "
    "else, mark them as INVALID. Respond ONLY with the single word 'VALID' or 'INVALID'."
)

def local_model_response(rules: str, user_message: str):
    # Gemma doesn’t support 'system' role, so include it inside the user message
    messages = [
        {
            "role": "user",
            "content": (
                f"{DEFAULT_SYSTEM_PROMPT}\n\n"
                f"Rules:\n{rules}\n\n"
                f"Image Summary:\n{user_message}\n\n"
                "Reply with only VALID or INVALID."
            )
        }
    ]

    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to(text_model.device)

    output_ids = text_model.generate(
        **inputs,
        max_new_tokens=10,
        pad_token_id=tokenizer.eos_token_id
    )

    generated_text = tokenizer.decode(output_ids[0][inputs['input_ids'].shape[-1]:], skip_special_tokens=True)
    return generated_text.strip().upper()

def validate_summary(rules: str, summary: str):
    response = local_model_response(rules, summary)
    if "VALID" in response and "INVALID" not in response:
        return "VALID", summary
    else:
        return "INVALID", summary

# =======================================
# MAIN TEST
# =======================================
if __name__ == "__main__":
    rules = """Images related to education, science, learning, or classroom environments are allowed.
               Personal, violent, or promotional content is not allowed.
               Ensure the image aligns with respectful and kind representation."""

    image_paths = [
        r"C:\Users\soham_ai_engineer_01\Pictures\{2D44D3BC-F169-4F62-97D4-B2883C0D3D13}.png",
        r"C:\Users\soham_ai_engineer_01\Pictures\{BF60D246-C3A2-4888-A45A-9700F072C8A2}.png"
    ]

    print(f"{'Image':<50} | {'Summary':<50} | {'Validation'}")
    print("-" * 130)

    for img in image_paths:
        summary = summarize_image(img)
        status, _ = validate_summary(rules, summary)
        print(f"{Path(img).name:<50} | {summary[:47]:<50} | {status}")

