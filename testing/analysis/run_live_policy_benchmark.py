import argparse
import csv
import json
import os
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from openai import OpenAI


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PREDICTIONS_CSV = PROJECT_ROOT / "Fine_Tune" / "Results" / "PI3" / "predictions.csv"
OUTPUT_DIR = PROJECT_ROOT / "testing" / "generated_review_metrics"
ROWS_CSV = OUTPUT_DIR / "live_policy_benchmark_rows.csv"
SUMMARY_JSON = OUTPUT_DIR / "live_policy_benchmark_summary.json"
POSITIVE = "FLAGGED"
NEGATIVE = "PASS"

CONDITIONS = {
    "org_strict": {
        "mode": "organization",
        "sensitivity": "Strict",
        "instruction": (
            "Flag borderline content, mild disrespect, and messages that are even slightly "
            "off-topic. When uncertain, lean toward FLAGGED."
        ),
    },
    "org_moderate": {
        "mode": "organization",
        "sensitivity": "Moderate",
        "instruction": (
            "Enforce the rules consistently without over-flagging. Flag clear violations "
            "and clear off-topic messages, but do not punish minor ambiguity."
        ),
    },
    "org_relaxed": {
        "mode": "organization",
        "sensitivity": "Relaxed",
        "instruction": (
            "Only flag clear and meaningful rule violations. Allow harmless digressions, "
            "mild tone issues, and ambiguous content unless the violation is obvious."
        ),
    },
    "generic_safety": {
        "mode": "generic",
        "sensitivity": "Moderate",
        "instruction": (
            "Flag clear generic safety violations: threats or violence, harassment or hate, "
            "sexual content, self-harm encouragement, illegal activity, dangerous instructions, "
            "doxxing or credential exposure, and obvious scams or spam. Otherwise PASS."
        ),
    },
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=os.getenv("CONVOEASE_TEXT_MODEL_ID", "openai/gpt-oss-120b"))
    parser.add_argument("--base-url", default=os.getenv("NVIDIA_API_URL", "https://integrate.api.nvidia.com/v1"))
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--conditions", nargs="+", choices=sorted(CONDITIONS), default=list(CONDITIONS))
    return parser.parse_args()


def api_key():
    key = (
        os.getenv("NVIDIA_API_KEY")
        or os.getenv("NVIDIA_NIM_API_KEY")
        or os.getenv("CONVOEASE_API_KEY")
    )
    if key:
        return key.strip()

    sys.path.insert(0, str(PROJECT_ROOT))
    import config

    key = str(config.TEXT_MODEL_CONFIG.get("api_key", "")).strip()
    if not key:
        raise RuntimeError("Set NVIDIA_API_KEY before running the live benchmark.")
    return key


def read_rows(limit=0):
    with PREDICTIONS_CSV.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for index, row in enumerate(rows):
        row["row_id"] = str(index)
    return rows[:limit] if limit else rows


def build_prompt(condition_name, batch):
    condition = CONDITIONS[condition_name]
    if condition["mode"] == "organization":
        boundary = (
            "For each item, ADMIN RULES are the primary decision boundary. Use chat context "
            "only to resolve references or short ambiguous replies. Do not narrow broad admin "
            "rules to the latest micro-topic. Evaluate disguised wording and non-English text "
            "by meaning and intent."
        )
        payload = [
            {
                "id": row["row_id"],
                "message": row["message"],
                "admin_rules": row["rules"],
                "chat_context": row.get("context") or "(no prior messages)",
            }
            for row in batch
        ]
    else:
        boundary = (
            "Ignore organization-specific rules. Apply only the generic safety taxonomy in "
            "the sensitivity instruction, using chat context only when needed for meaning."
        )
        payload = [
            {
                "id": row["row_id"],
                "message": row["message"],
                "chat_context": row.get("context") or "(no prior messages)",
            }
            for row in batch
        ]

    return f"""Classify every item as PASS or FLAGGED.

POLICY MODE: {condition["mode"]}
SENSITIVITY: {condition["sensitivity"]}
SENSITIVITY INSTRUCTION: {condition["instruction"]}
DECISION BOUNDARY: {boundary}

Return ONLY a JSON array with one object per input, preserving IDs:
[{{"id":"0","decision":"PASS"}},{{"id":"1","decision":"FLAGGED"}}]

INPUT ITEMS:
{json.dumps(payload, ensure_ascii=True)}
"""


def extract_predictions(content, expected_ids):
    text = str(content or "").strip()
    match = re.search(r"\[[\s\S]*\]", text)
    if not match:
        raise ValueError(f"No JSON array in response: {text[:200]!r}")
    parsed = json.loads(match.group(0))
    found = {}
    for item in parsed:
        row_id = str(item.get("id", "")).strip()
        decision = str(item.get("decision", "")).strip().upper()
        if row_id in expected_ids and decision in {POSITIVE, NEGATIVE}:
            found[row_id] = decision
    missing = expected_ids - set(found)
    if missing:
        raise ValueError(f"Missing predictions for IDs: {sorted(missing)}")
    return found


def run_batch(client, model, condition_name, batch, max_retries):
    expected_ids = {row["row_id"] for row in batch}
    prompt = build_prompt(condition_name, batch)
    last_error = None
    for attempt in range(1, max_retries + 1):
        started = time.perf_counter()
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a precise moderation classifier."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                top_p=1,
                max_tokens=max(512, len(batch) * 80),
            )
            latency_ms = (time.perf_counter() - started) * 1000
            predictions = extract_predictions(response.choices[0].message.content, expected_ids)
            return condition_name, batch, predictions, latency_ms, attempt
        except Exception as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(2 ** (attempt - 1))
    raise RuntimeError(
        f"{condition_name} batch {batch[0]['row_id']}-{batch[-1]['row_id']} failed: {last_error}"
    )


def confusion(rows):
    counts = Counter()
    for row in rows:
        truth = row["label"].strip().upper()
        pred = row["prediction"].strip().upper()
        if truth == POSITIVE and pred == POSITIVE:
            counts["tp"] += 1
        elif truth == NEGATIVE and pred == POSITIVE:
            counts["fp"] += 1
        elif truth == POSITIVE and pred == NEGATIVE:
            counts["fn"] += 1
        else:
            counts["tn"] += 1
    return counts


def safe_div(numerator, denominator):
    return numerator / denominator if denominator else 0.0


def metrics(rows):
    counts = confusion(rows)
    tp, fp, fn, tn = counts["tp"], counts["fp"], counts["fn"], counts["tn"]
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    return {
        "n": len(rows),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "accuracy": round(safe_div(tp + tn, len(rows)), 4),
        "precision_flagged": round(precision, 4),
        "recall_flagged": round(recall, 4),
        "f1_flagged": round(safe_div(2 * precision * recall, precision + recall), 4),
    }


def percentile(values, fraction):
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def write_outputs(results, model):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "condition", "row_id", "source", "message", "rules", "context", "label",
        "prediction", "correct", "batch_latency_ms", "attempt",
    ]
    with ROWS_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    grouped = defaultdict(list)
    for row in results:
        grouped[row["condition"]].append(row)

    summary = {"model": model, "source": str(PREDICTIONS_CSV), "conditions": {}}
    for condition_name, rows in grouped.items():
        latencies = sorted({float(row["batch_latency_ms"]) for row in rows})
        summary["conditions"][condition_name] = {
            "policy": CONDITIONS[condition_name],
            "metrics": metrics(rows),
            "batch_latency_ms": {
                "batches": len(latencies),
                "mean": round(statistics.mean(latencies), 2),
                "p50": round(percentile(latencies, 0.50), 2),
                "p95": round(percentile(latencies, 0.95), 2),
                "max": round(max(latencies), 2),
            },
        }

    if {"org_strict", "org_moderate", "org_relaxed"} <= set(grouped):
        moderate = summary["conditions"]["org_moderate"]["metrics"]
        summary["sensitivity_shifts_percentage_points"] = {}
        for name in ("org_strict", "org_relaxed"):
            current = summary["conditions"][name]["metrics"]
            summary["sensitivity_shifts_percentage_points"][f"{name}_vs_org_moderate"] = {
                "precision_flagged": round(
                    100 * (current["precision_flagged"] - moderate["precision_flagged"]), 2
                ),
                "recall_flagged": round(
                    100 * (current["recall_flagged"] - moderate["recall_flagged"]), 2
                ),
            }

    if {"org_moderate", "generic_safety"} <= set(grouped):
        org = summary["conditions"]["org_moderate"]["metrics"]
        generic = summary["conditions"]["generic_safety"]["metrics"]
        summary["policy_as_prompt_delta_percentage_points"] = {
            "accuracy": round(100 * (org["accuracy"] - generic["accuracy"]), 2),
            "precision_flagged": round(
                100 * (org["precision_flagged"] - generic["precision_flagged"]), 2
            ),
            "recall_flagged": round(
                100 * (org["recall_flagged"] - generic["recall_flagged"]), 2
            ),
        }

    SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main():
    args = parse_args()
    rows = read_rows(args.limit)
    client = OpenAI(base_url=args.base_url, api_key=api_key(), timeout=args.timeout)
    tasks = []
    for condition_name in args.conditions:
        for start in range(0, len(rows), args.batch_size):
            tasks.append((condition_name, rows[start:start + args.batch_size]))

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(
                run_batch, client, args.model, condition_name, batch, args.max_retries
            )
            for condition_name, batch in tasks
        ]
        for completed, future in enumerate(as_completed(futures), start=1):
            condition_name, batch, predictions, latency_ms, attempt = future.result()
            for row in batch:
                prediction = predictions[row["row_id"]]
                results.append({
                    "condition": condition_name,
                    "row_id": row["row_id"],
                    "source": row["source"],
                    "message": row["message"],
                    "rules": row["rules"],
                    "context": row.get("context", ""),
                    "label": row["label"],
                    "prediction": prediction,
                    "correct": prediction == row["label"].strip().upper(),
                    "batch_latency_ms": round(latency_ms, 2),
                    "attempt": attempt,
                })
            print(f"[{completed}/{len(tasks)}] {condition_name} rows {batch[0]['row_id']}-{batch[-1]['row_id']} {latency_ms:.0f} ms")

    results.sort(key=lambda row: (row["condition"], int(row["row_id"])))
    print(json.dumps(write_outputs(results, args.model), indent=2))


if __name__ == "__main__":
    main()
