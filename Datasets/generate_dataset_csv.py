#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSV Dataset Builder for Convo-Ease
Generates UNIQUE dataset entries for moderation classification.

Output:
data_csv/train.csv
data_csv/val.csv
data_csv/test.csv
"""
import argparse
import csv
import json
import math
import random
import re
import string
from hashlib import blake2b
from pathlib import Path
from collections import defaultdict

# ---------------------------------------
# Global random seed
# ---------------------------------------
SEED = 42
random.seed(SEED)

# ---------------------------------------
# RULE DEFINITIONS (same used in JSON generator)
# ---------------------------------------
FORUMS = {
    "science_forum": [
        ("R1", "Science-only discussions and debates."),
        ("R2", "No pseudoscience or conspiracy theories."),
        ("R3", "Maintain a respectful and educational tone."),
        ("R4", "Cite credible sources when making claims."),
        ("R5", "Encourage curiosity and learning.")
    ],
    "startup_forum": [
        ("R1", "Business and entrepreneurship discussions allowed."),
        ("R2", "No excessive spamming of your own startup."),
        ("R3", "No irrelevant memes or off-topic content."),
        ("R4", "Be constructive with feedback."),
        ("R5", "No scams or pyramid schemes.")
    ],
    "college_forum": [
        ("R1", "Only educational and learning-related messages are allowed."),
        ("R2", "Personal meetups or DMs are not allowed."),
        ("R3", "Be respectful and kind."),
        ("R4", "No advertisements or promotions."),
        ("R5", "Stick to class and college topics.")
    ],
    "health_forum": [
        ("R1", "Discuss general health and wellness information only."),
        ("R2", "No medical misinformation or miracle cures."),
        ("R3", "No direct solicitation of products or services."),
        ("R4", "Be empathetic and non-judgmental."),
        ("R5", "Reference reputable health sources when making claims.")
    ]
}

# ---------------------------------------
# VALID Example templates
# ---------------------------------------
VALID_TEMPLATES = {
    "science_forum": [
        "How does CRISPR work and what risks are involved?",
        "Can someone explain the double-slit experiment?",
        "What are limitations of peer review?",
        "How do we calculate p-values?",
    ],
    "startup_forum": [
        "How do you validate an MVP before launching?",
        "What KPIs matter most for SaaS?",
        "How to collect feedback from users?",
    ],
    "college_forum": [
        "What is the syllabus for data structures?",
        "Any tips for OS practical exam?",
        "How to prepare timetable for GATE?",
    ],
    "health_forum": [
        "How to improve sleep quality?",
        "How does exercise impact heart rate?",
        "Difference between type 1 and type 2 diabetes?",
    ]
}

# ---------------------------------------
# INVALID Example triggers (rule violations)
# ---------------------------------------
INVALID_TEMPLATES = {
    "science_forum": [
        ("R2", "Flat earth is real."),
        ("R2", "Telepathy is scientifically proven."),
        ("R3", "Shut up, your take is dumb."),
    ],
    "startup_forum": [
        ("R2", "Join our paid startup membership."),
        ("R5", "Double your money in 2 days."),
    ],
    "college_forum": [
        ("R2", "DM me your number."),
        ("R4", "Buy my course now, limited offer."),
    ],
    "health_forum": [
        ("R2", "Drink magic water to cure cancer."),
        ("R3", "Buy my coaching plan now."),
    ]
}

# ---------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------
def normalize(text: str) -> str:
    """Normalize text to ensure uniqueness"""
    t = text.lower()
    t = re.sub(r"\s+", " ", t)
    t = t.translate(str.maketrans("", "", string.punctuation))
    return t.strip()


def hash_key(forum_type: str, message: str) -> str:
    """Key ensures uniqueness across dataset"""
    norm = f"{forum_type}::{normalize(message)}"
    return blake2b(norm.encode(), digest_size=16).hexdigest()


def generate_valid(forum_type):
    message = random.choice(VALID_TEMPLATES[forum_type])
    return {
        "forum_type": forum_type,
        "message": message,
        "decision": "VALID",
        "reason": "Message follows rules.",
        "violated_rules": "",
        "confidence": round(random.uniform(0.80, 0.97), 2)
    }


def generate_invalid(forum_type):
    rid, msg = random.choice(INVALID_TEMPLATES[forum_type])
    return {
        "forum_type": forum_type,
        "message": msg,
        "decision": "INVALID",
        "reason": f"Violates {rid}.",
        "violated_rules": rid,
        "confidence": round(random.uniform(0.70, 0.95), 2)
    }


def rules_to_text(forum):
    """Convert rule list → string for CSV"""
    return " | ".join([f"{rid}:{txt}" for rid, txt in FORUMS[forum]])


# ---------------------------------------
# MAIN GENERATION LOOP
# ---------------------------------------
def generate_csv(total, outdir: Path):

    outdir.mkdir(parents=True, exist_ok=True)

    # split counts → train / val / test
    n_train = int(total * 0.8)
    n_val = int(total * 0.1)
    n_test = total - n_train - n_val

    buffers = {
        "train": [],
        "val": [],
        "test": []
    }

    # Target balanced dataset per split
    per_split_valid = total // 2 // 3
    per_split_invalid = per_split_valid

    seen = set()
    forums = list(FORUMS.keys())
    generated = 0

    while generated < total:

        split = (
            "train" if len(buffers["train"]) < n_train else
            "val" if len(buffers["val"]) < n_val else
            "test"
        )

        want_valid = (
            sum(1 for x in buffers[split] if x["decision"] == "VALID") <
            sum(1 for x in buffers[split] if x["decision"] == "INVALID")
        )

        forum = random.choice(forums)

        sample = generate_valid(forum) if want_valid else generate_invalid(forum)

        key = hash_key(sample["forum_type"], sample["message"])
        if key in seen:
            continue
        seen.add(key)

        sample["rules"] = rules_to_text(forum)

        buffers[split].append(sample)
        generated += 1

        if generated % 5000 == 0:
            print(f"[INFO] Generated {generated}/{total} unique rows")

    # Write CSV
    for split, rows in buffers.items():
        with open(outdir / f"{split}.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["forum_type", "rules", "message", "decision", "reason", "violated_rules", "confidence"]
            )
            writer.writeheader()
            writer.writerows(rows)

    print("✅ CSV dataset generated successfully:")
    print(f"    train: {len(buffers['train'])}")
    print(f"    val:   {len(buffers['val'])}")
    print(f"    test:  {len(buffers['test'])}")
    print(f"📁 Output: {outdir.resolve()}")


# ---------------------------------------
# CLI
# ---------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--total", type=int, default=100000, help="Number of examples to generate")
    parser.add_argument("--outdir", type=str, default="data_csv", help="Output CSV directory")
    args = parser.parse_args()

    generate_csv(args.total, Path(args.outdir))
