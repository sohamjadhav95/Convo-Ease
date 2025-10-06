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

# -------------------
# Load Dataset
# -------------------
df = pd.read_csv("multi_rule_forum_dataset.csv")

# Expecting columns: "message", "label"
# Convert labels into "VALID"/"INVALID" responses
df["text"] = df.apply(lambda row: f"User: {row['message']}\nAssistant: {row['label']}", axis=1)

dataset = Dataset.from_pandas(df[["text"]])

# -------------------
# Load Model & Tokenizer
# -------------------
model_path = "D:/Convo-Ease/gpt-oss-20b"   # change to your model folder
tokenizer = AutoTokenizer.from_pretrained(model_path)

if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

def tokenize_function(examples):
    return tokenizer(
        examples["text"],
        truncation=True,
        padding="max_length",
        max_length=512
    )

tokenized_dataset = dataset.map(tokenize_function, batched=True, remove_columns=["text"])

# -------------------
# LoRA Config
# -------------------
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    device_map="auto"
)

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
data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

training_args = TrainingArguments(
    output_dir="./finetuned-gpt-oss-20b",
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    evaluation_strategy="no",
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
    train_dataset=tokenized_dataset,
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
model.save_pretrained("./finetuned-gpt-oss-20b-lora")
tokenizer.save_pretrained("./finetuned-gpt-oss-20b-lora")
