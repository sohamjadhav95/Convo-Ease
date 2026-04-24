"""
ConvoEase — Full Dataset Converter
====================================
Converts ALL available data from every uploaded source into one unified
training CSV. No arbitrary row cap — uses everything.

Inputs (pass as args):
  --train   train_csv.txt          (Jigsaw train — full file from Kaggle)
  --test    test_csv.txt           (Jigsaw test)
  --labels  test_labels.csv        (Jigsaw test labels)
  --hate18  HateSpeech18.zip

Output columns:
  source | message | rules | context | label | reason | instruction | response

Usage:
  python convert_all_datasets.py \
      --train  train_csv.txt \
      --test   test_csv.txt \
      --labels test_labels.csv \
      --hate18 HateSpeech18.zip \
      --out    convoease_full_dataset.csv \
      --seed   42
"""

import argparse
import csv
import os
import random
import zipfile

import pandas as pd

# ─── 15 Realistic Rule Sets ──────────────────────────────────────────────────

RULE_SETS = [
    "No hate speech, slurs, or personal attacks of any kind.",
    "Keep all messages respectful. Insults and name-calling are not allowed.",
    "No discrimination based on race, religion, gender, nationality, or sexuality.",
    "Treat every member with respect. Harassment and bullying are strictly forbidden.",
    "No spam, repeated messages, or unsolicited promotions.",
    "Stay on topic. Only discuss subjects relevant to this group.",
    "No self-promotion or sharing personal links without admin approval.",
    "No explicit, violent, or graphic content.",
    "English only — no messages in other languages.",
    (
        "1. No hate speech or personal attacks.\n"
        "2. No spam or repeated messages.\n"
        "3. Stay on topic — this is a Python programming group.\n"
        "4. English only."
    ),
    (
        "Rules:\n"
        "- No insults, slurs, or harassment.\n"
        "- No self-promotion or external links.\n"
        "- Keep discussions relevant to machine learning.\n"
        "- No political or religious debates."
    ),
    (
        "Community guidelines:\n"
        "1. Zero tolerance for hate speech or discrimination.\n"
        "2. No threats of violence under any circumstances.\n"
        "3. No doxxing or sharing others' personal information.\n"
        "4. No NSFW content."
    ),
    (
        "Business group rules:\n"
        "- Professional language only. Slang and profanity are not allowed.\n"
        "- No off-topic personal conversations.\n"
        "- All product promotions must be approved by admins first."
    ),
    (
        "Group Guidelines:\n"
        "• Respect all members at all times.\n"
        "• No spam, flooding, or off-topic messages.\n"
        "• Constructive criticism only — no personal attacks."
    ),
    (
        "Study group rules:\n"
        "1. No insults or aggressive language.\n"
        "2. Questions must be related to current semester topics.\n"
        "3. Share resources freely but no paid course links without permission."
    ),
]

# ─── Context Templates ───────────────────────────────────────────────────────

CONTEXT_TEMPLATES = [
    "(no prior messages)",
    "(no prior messages)",   # weighted higher — most messages have no context
    "(no prior messages)",
    "User_A: Can anyone help me with this?\nUser_B: Sure, what's the issue?",
    "User_A: Did everyone finish the assignment?\nUser_B: Just submitted mine.",
    "User_A: Welcome to the group!\nUser_B: Thanks for adding me.",
    "User_A: Has anyone tried the new update?\nUser_B: Yes, it works well.",
    "User_A: I need advice on this.\nUser_B: What specifically?\nUser_A: The second part.",
    "User_A: What do you think about this topic?\nUser_B: It is quite complex.",
    "User_A: Good morning everyone!\nUser_B: Morning! Ready for the session?",
]

# ─── Jigsaw Label → Reason Mapping ──────────────────────────────────────────

JIGSAW_REASONS = {
    "severe_toxic":  "Message contains severely toxic language that violates community standards.",
    "obscene":       "Message contains obscene or vulgar language.",
    "threat":        "Message contains a threat of violence or harm.",
    "insult":        "Message contains a direct insult targeting a person or group.",
    "identity_hate": "Message expresses hate toward an identity group (race, religion, gender, etc.).",
    "toxic":         "Message contains toxic language that violates community standards.",
}

HATE18_REASON = "Message contains hate speech or discriminatory content targeting a group."

# ─── Prompt Builder ──────────────────────────────────────────────────────────

PROMPT = """\
You are a strict Group Chat Moderator.

ADMIN RULES:
{rules}

CHAT CONTEXT (Last several messages):
{context}

YOUR TASK:
Validate the following NEW message.
Use the properties of the CHAT CONTEXT to determine if the message is relevant \
(e.g. a "Yes" to a previous question is valid).
However, if the NEW message explicitly violates a rule (e.g. insults, spam), \
you must FLAG it regardless of context.

NEW MESSAGE: "{message}"

OUTPUT FORMAT:
- If compliant: PASS
- If violation: FLAGGED <reason>"""


def make_row(source, message, label, reason, rules, context):
    instruction = PROMPT.format(rules=rules, context=context, message=message)
    response = "PASS" if label == "PASS" else f"FLAGGED: {reason}"
    return {
        "source":      source,
        "message":     message,
        "rules":       rules,
        "context":     context,
        "label":       label,
        "reason":      reason,
        "instruction": instruction,
        "response":    response,
    }


# ─── Source Loaders ──────────────────────────────────────────────────────────

def load_jigsaw(train_path, test_path, labels_path, rng):
    rows = []

    # ── Train ──
    if train_path and os.path.exists(train_path):
        print(f"  Reading {train_path} ...")
        try:
            df = pd.read_csv(train_path, engine="python", on_bad_lines="skip")
            label_cols = ["severe_toxic", "obscene", "threat", "insult", "identity_hate", "toxic"]
            for _, row in df.iterrows():
                msg = str(row.get("comment_text", "")).strip()
                if not msg or len(msg) < 5:
                    continue
                # Pick the most specific positive label
                flagged = [c for c in label_cols[:5] if row.get(c, 0) == 1]
                if flagged:
                    label, reason = "FLAGGED", JIGSAW_REASONS[flagged[0]]
                elif row.get("toxic", 0) == 1:
                    label, reason = "FLAGGED", JIGSAW_REASONS["toxic"]
                else:
                    label, reason = "PASS", ""
                rows.append(make_row(
                    "jigsaw_train", msg, label, reason,
                    rng.choice(RULE_SETS), rng.choice(CONTEXT_TEMPLATES)
                ))
            print(f"    → {len(rows):,} rows from train")
        except Exception as e:
            print(f"    ✗ Could not read train file: {e}")

    # ── Test + Labels ──
    if test_path and labels_path and os.path.exists(test_path) and os.path.exists(labels_path):
        print(f"  Reading {test_path} + {labels_path} ...")
        prev = len(rows)
        try:
            test_df   = pd.read_csv(test_path, engine="python", on_bad_lines="skip")
            labels_df = pd.read_csv(labels_path)
            df = test_df.merge(labels_df, on="id", how="inner")
            label_cols = ["toxic", "severe_toxic", "obscene", "threat", "insult", "identity_hate"]
            for _, row in df.iterrows():
                # Skip unscored rows (all -1)
                if all(row.get(c, -1) == -1 for c in label_cols):
                    continue
                msg = str(row.get("comment_text", "")).strip()
                if not msg or len(msg) < 5:
                    continue
                flagged = [c for c in ["severe_toxic", "obscene", "threat", "insult", "identity_hate"]
                           if row.get(c, 0) == 1]
                if flagged:
                    label, reason = "FLAGGED", JIGSAW_REASONS[flagged[0]]
                elif row.get("toxic", 0) == 1:
                    label, reason = "FLAGGED", JIGSAW_REASONS["toxic"]
                else:
                    label, reason = "PASS", ""
                rows.append(make_row(
                    "jigsaw_test", msg, label, reason,
                    rng.choice(RULE_SETS), rng.choice(CONTEXT_TEMPLATES)
                ))
            print(f"    → {len(rows) - prev:,} rows from test")
        except Exception as e:
            print(f"    ✗ Could not read test files: {e}")

    return rows


def load_hate18(zip_path, rng):
    rows = []
    if not zip_path or not os.path.exists(zip_path):
        print("  HateSpeech18 zip not found, skipping.")
        return rows

    print(f"  Reading {zip_path} ...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        with zf.open("data/annotations_metadata.csv") as f:
            meta = pd.read_csv(f)

        for _, row in meta.iterrows():
            file_id  = str(row["file_id"]).strip()
            hs_label = str(row["label"]).strip().lower()
            txt_path = f"data/all_files/{file_id}.txt"
            try:
                with zf.open(txt_path) as tf:
                    msg = tf.read().decode("utf-8", errors="replace").strip()
            except KeyError:
                continue
            if not msg or len(msg) < 5:
                continue

            label  = "FLAGGED" if hs_label == "hate" else "PASS"
            reason = HATE18_REASON if label == "FLAGGED" else ""

            rows.append(make_row(
                "hate18", msg, label, reason,
                rng.choice(RULE_SETS), rng.choice(CONTEXT_TEMPLATES)
            ))

    print(f"    → {len(rows):,} rows from HateSpeech18")
    return rows


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train",  default=None)
    ap.add_argument("--test",   default=None)
    ap.add_argument("--labels", default=None)
    ap.add_argument("--hate18", default=None)
    ap.add_argument("--out",    default="convoease_full_dataset.csv")
    ap.add_argument("--seed",   type=int, default=42)
    args = ap.parse_args()

    rng = random.Random(args.seed)

    print("\n── Loading all sources ──")
    all_rows = []
    all_rows += load_jigsaw(args.train, args.test, args.labels, rng)
    all_rows += load_hate18(args.hate18, rng)

    if not all_rows:
        print("No data loaded. Check your file paths.")
        return

    rng.shuffle(all_rows)

    # ── Stats ──
    total    = len(all_rows)
    flagged  = sum(1 for r in all_rows if r["label"] == "FLAGGED")
    passed   = total - flagged
    src_cnt  = {}
    for r in all_rows:
        src_cnt[r["source"]] = src_cnt.get(r["source"], 0) + 1

    print(f"\n── Dataset Summary ──────────────────────")
    print(f"  Total rows : {total:,}")
    print(f"  PASS       : {passed:,}  ({passed/total*100:.1f}%)")
    print(f"  FLAGGED    : {flagged:,}  ({flagged/total*100:.1f}%)")
    print(f"  By source  :")
    for src, cnt in sorted(src_cnt.items()):
        print(f"    {src:<20} {cnt:,}")

    # ── Write ──
    fields = ["source", "message", "rules", "context", "label", "reason",
              "instruction", "response"]
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)

    size_mb = os.path.getsize(args.out) / 1024 / 1024
    print(f"\n  Saved → {args.out}  ({size_mb:.2f} MB)")

    # ── 3 random samples ──
    print("\n── 3 Random Samples ─────────────────────")
    for i, r in enumerate(rng.sample(all_rows, min(3, total)), 1):
        print(f"\n  [{i}] source={r['source']}  label={r['label']}")
        print(f"      message  : {r['message'][:100].replace(chr(10),' ')}")
        print(f"      rules    : {r['rules'][:70].replace(chr(10),' ')}")
        print(f"      response : {r['response'][:80]}")


if __name__ == "__main__":
    main()