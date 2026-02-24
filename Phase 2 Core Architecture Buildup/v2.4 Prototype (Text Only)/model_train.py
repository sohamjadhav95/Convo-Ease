import pandas as pd
import torch
from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling
)
from peft import LoraConfig, get_peft_model, TaskType
# ADD: DefaultDataCollator import to match its usage below
from transformers import DefaultDataCollator
# ADD: imports for JSON folder loading
from pathlib import Path
import json

# -------------------
# Load Dataset
# -------------------
# CHANGE: Load from a single JSONL file
JSONL_PATH = r"C:\Project\Convo-Ease-main\Convo-Ease-main\v2.3 Prototype (Text Only Full)\full_dataset.jsonl"
records = []
with open(JSONL_PATH, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            if "message" in rec and "label" in rec:
                records.append({"message": rec["message"], "label": str(rec["label"]).strip().upper()})
        except Exception:
            continue

if not records:
    raise ValueError(f"No valid records found in JSONL file: {JSONL_PATH}")

df = pd.DataFrame(records)

# Expecting columns: "message", "label"
# Convert labels into "VALID"/"INVALID" responses
df["text"] = df.apply(lambda row: f"User: {row['message']}\nAssistant: {row['label']}", axis=1)

dataset = Dataset.from_pandas(df[["text"]])

# -------------------
# Load Model & Tokenizer
# -------------------
# Use raw string to avoid backslash-escape issues in Windows paths
model_path = r"C:\Project\Convo-Ease-main\Convo-Ease-main\v2.3 Prototype (Text Only Full)\gemma-2-9b-it"   # change to your model folder
tokenizer = AutoTokenizer.from_pretrained(model_path)

# Ensure padding tokens are set
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
tokenizer.padding_side = "right"  # right padding is typical for decoder-only LMs

MAX_LENGTH = 512  # keep your original sequence length

# -------------------
# Prepare examples with masked labels (train only on assistant response)
# -------------------
def prepare_examples(examples):
    input_ids_list = []
    attention_mask_list = []
    labels_list = []

    for text in examples["text"]:
        # Split into prompt and target using the known format "User: ...\nAssistant: ..."
        if "\nAssistant:" in text:
            parts = text.split("\nAssistant:")
            prompt = parts[0] + "\nAssistant:"  # up to the assistant prefix
            target = parts[1].strip()           # assistant output ("VALID"/"INVALID")
        else:
            # Fallback: if format is unexpected, treat full text as prompt and target empty
            prompt = text
            target = ""

        # Tokenize full sequence (prompt + target)
        full = tokenizer(
            prompt + " " + target,
            truncation=True,
            padding="max_length",
            max_length=MAX_LENGTH,
        )

        # Tokenize prompt separately (to compute the mask boundary)
        prompt_only = tokenizer(
            prompt,
            truncation=True,
            padding=False,
            max_length=MAX_LENGTH,
            add_special_tokens=False
        )

        labels = full["input_ids"].copy()
        prompt_len = len(prompt_only["input_ids"])

        # Mask out the prompt tokens; train only on assistant response tokens
        for i in range(prompt_len):
            labels[i] = -100

        input_ids_list.append(full["input_ids"])
        attention_mask_list.append(full["attention_mask"])
        labels_list.append(labels)

    return {
        "input_ids": input_ids_list,
        "attention_mask": attention_mask_list,
        "labels": labels_list,
    }

# Map dataset to tokenized form with masked labels
tokenized_dataset = dataset.map(prepare_examples, batched=True, remove_columns=["text"])

# Optional: split for evaluation
splits = tokenized_dataset.train_test_split(test_size=0.05, seed=42)
train_dataset = splits["train"]
eval_dataset = splits["test"]

# -------------------
# LoRA Config
# -------------------
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    device_map="auto"
)

# Ensure model pad token id is set
if getattr(model.config, "pad_token_id", None) is None:
    model.config.pad_token_id = tokenizer.pad_token_id

lora_config = LoraConfig(
    task_type=TaskType.CAUSAL_LM,
    r=16,
    lora_alpha=32,
    target_modules=["q_proj","v_proj"],  # typical for transformers
    lora_dropout=0.05,
    bias="none"
)

model = get_peft_model(model, lora_config)

# -------------------
# Training Setup
# -------------------
# Remove DataCollatorForLanguageModeling to avoid overwriting our custom labels
data_collator = DefaultDataCollator()

training_args = TrainingArguments(
    output_dir="./finetuned-gemma-2-9b-it",  # align output dir with model/save name
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    evaluation_strategy="epoch",
    num_train_epochs=3,
    learning_rate=2e-4,
    save_strategy="epoch",
    logging_steps=50,
    fp16=torch.cuda.is_available(),
    push_to_hub=False
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,  # use train split
    eval_dataset=eval_dataset,    # eval split
    tokenizer=tokenizer,
    data_collator=data_collator
)

# -------------------
# Train
# -------------------
trainer.train()

# -------------------
# Save
# -------------------
model.save_pretrained("./finetuned-gemma-2-9b-it-lora")
tokenizer.save_pretrained("./finetuned-gemma-2-9b-it-lora")
