"""
Read-only verification script.
Recomputes all four-condition metrics from benchmark_raw_1200.csv
and checks them against live_policy_benchmark_summary.json.
Writes NO files other than printing to stdout.
"""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ARTIFACTS_DIR = Path(__file__).resolve().parents[1]
ROWS_CSV = ARTIFACTS_DIR / "benchmark_raw_1200.csv"
SUMMARY_JSON = (
    Path(__file__).resolve().parents[2]
    / "testing" / "generated_review_metrics" / "live_policy_benchmark_summary.json"
)

POSITIVE = "FLAGGED"
NEGATIVE = "PASS"


def safe_div(n, d):
    return n / d if d else 0.0


def recompute(rows):
    counts = Counter()
    for r in rows:
        truth = r["label"].strip().upper()
        pred = r["prediction"].strip().upper()
        if truth == POSITIVE and pred == POSITIVE:
            counts["tp"] += 1
        elif truth == NEGATIVE and pred == POSITIVE:
            counts["fp"] += 1
        elif truth == POSITIVE and pred == NEGATIVE:
            counts["fn"] += 1
        else:
            counts["tn"] += 1
    tp, fp, fn, tn = counts["tp"], counts["fp"], counts["fn"], counts["tn"]
    n = len(rows)
    prec = safe_div(tp, tp + fp)
    rec = safe_div(tp, tp + fn)
    return {
        "n": n, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "accuracy": round(safe_div(tp + tn, n), 4),
        "precision_flagged": round(prec, 4),
        "recall_flagged": round(rec, 4),
        "f1_flagged": round(safe_div(2 * prec * rec, prec + rec), 4),
    }


def main():
    with ROWS_CSV.open(newline="", encoding="utf-8") as fh:
        all_rows = list(csv.DictReader(fh))
    with SUMMARY_JSON.open(encoding="utf-8") as fh:
        summary = json.load(fh)

    grouped = defaultdict(list)
    for r in all_rows:
        grouped[r["condition"]].append(r)

    print(f"Total rows in benchmark_raw_1200.csv: {len(all_rows)}")
    print()
    print("Recomputed metrics vs. live_policy_benchmark_summary.json:")
    print()

    all_match = True
    for cond in sorted(grouped):
        recomp = recompute(grouped[cond])
        stored = summary["conditions"][cond]["metrics"]
        match = (
            recomp["tp"] == stored["tp"] and
            recomp["fp"] == stored["fp"] and
            recomp["fn"] == stored["fn"] and
            recomp["tn"] == stored["tn"] and
            recomp["accuracy"] == stored["accuracy"]
        )
        status = "OK" if match else "MISMATCH"
        if not match:
            all_match = False
        print(f"[{status}] {cond}")
        print(f"  Recomputed : acc={recomp['accuracy']:.4f} prec={recomp['precision_flagged']:.4f} "
              f"rec={recomp['recall_flagged']:.4f} f1={recomp['f1_flagged']:.4f} "
              f"tp={recomp['tp']} fp={recomp['fp']} fn={recomp['fn']} tn={recomp['tn']}")
        print(f"  JSON stored: acc={stored['accuracy']:.4f} prec={stored['precision_flagged']:.4f} "
              f"rec={stored['recall_flagged']:.4f} f1={stored['f1_flagged']:.4f} "
              f"tp={stored['tp']} fp={stored['fp']} fn={stored['fn']} tn={stored['tn']}")
        print()

    if all_match:
        print("RESULT: All four conditions match the stored summary JSON exactly.")
    else:
        print("RESULT: MISMATCH DETECTED — see above.")


if __name__ == "__main__":
    main()
