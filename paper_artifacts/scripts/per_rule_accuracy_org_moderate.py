"""
Task 3: Per-rule-set accuracy under org_moderate condition only,
recomputed from benchmark_raw_1200.csv.
Does NOT use or reference per_rule_accuracy.csv (fine-tuned run numbers).
Output: paper_artifacts/per_rule_accuracy_org_moderate.csv
"""
import csv
from collections import Counter, defaultdict
from pathlib import Path

ARTIFACTS = Path(__file__).resolve().parents[1]
ROWS_CSV = ARTIFACTS / "benchmark_raw_1200.csv"
OLD_PER_RULE = (
    Path(__file__).resolve().parents[2]
    / "testing" / "generated_review_metrics" / "per_rule_accuracy.csv"
)
OUT_CSV = ARTIFACTS / "per_rule_accuracy_org_moderate.csv"

POSITIVE = "FLAGGED"
NEGATIVE = "PASS"


def safe_div(n, d):
    return n / d if d else 0.0


def compute_metrics(rows):
    c = Counter()
    for r in rows:
        t = r["label"].strip().upper()
        p = r["prediction"].strip().upper()
        if t == POSITIVE and p == POSITIVE:
            c["tp"] += 1
        elif t == NEGATIVE and p == POSITIVE:
            c["fp"] += 1
        elif t == POSITIVE and p == NEGATIVE:
            c["fn"] += 1
        else:
            c["tn"] += 1
    tp, fp, fn, tn = c["tp"], c["fp"], c["fn"], c["tn"]
    n = tp + fp + fn + tn
    prec = safe_div(tp, tp + fp)
    rec = safe_div(tp, tp + fn)
    f1 = safe_div(2 * prec * rec, prec + rec)
    return {
        "n": n, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "accuracy": round(safe_div(tp + tn, n), 4),
        "precision_flagged": round(prec, 4),
        "recall_flagged": round(rec, 4),
        "f1_flagged": round(f1, 4),
    }


def main():
    # Load and filter to org_moderate only
    with ROWS_CSV.open(newline="", encoding="utf-8") as f:
        all_rows = list(csv.DictReader(f))

    org_mod_rows = [r for r in all_rows if r["condition"] == "org_moderate"]
    print(f"org_moderate rows: {len(org_mod_rows)}")

    # Group by rule set text
    rule_groups = defaultdict(list)
    for r in org_mod_rows:
        rule_groups[r["rules"]].append(r)

    # Sort by descending n (largest rule sets first)
    sorted_rules = sorted(rule_groups.items(), key=lambda x: -len(x[1]))
    print(f"Distinct rule sets: {len(sorted_rules)}")

    # Assign rule IDs by frequency rank
    results = []
    for rank, (rule_text, rows) in enumerate(sorted_rules, start=1):
        m = compute_metrics(rows)
        # Abbreviated rule text (first 120 chars, newlines replaced)
        rule_preview = rule_text.replace("\n", " | ").replace("\r", "")[:120]
        results.append({
            "rule_id": f"rule_{rank:02d}",
            "n": m["n"],
            "tp": m["tp"],
            "fp": m["fp"],
            "fn": m["fn"],
            "tn": m["tn"],
            "accuracy": m["accuracy"],
            "precision_flagged": m["precision_flagged"],
            "recall_flagged": m["recall_flagged"],
            "f1_flagged": m["f1_flagged"],
            "rule_preview": rule_preview,
        })

    # Write CSV
    fieldnames = ["rule_id", "n", "tp", "fp", "fn", "tn",
                  "accuracy", "precision_flagged", "recall_flagged",
                  "f1_flagged", "rule_preview"]
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(results)

    print(f"Written: {OUT_CSV}")
    print()
    print(f"NOTE: Old per_rule_accuracy.csv (fine-tuned run) is at:")
    print(f"  {OLD_PER_RULE}")
    print("  It was NOT consulted or merged here.")
    print()
    print(f"{'Rule':>8} {'N':>5} {'Acc':>6} {'Prec':>6} {'Recall':>7} {'F1':>6}  Preview")
    print("-" * 90)
    for r in results:
        print(f"{r['rule_id']:>8} {r['n']:>5} {r['accuracy']:>6.4f} "
              f"{r['precision_flagged']:>6.4f} {r['recall_flagged']:>7.4f} "
              f"{r['f1_flagged']:>6.4f}  {r['rule_preview'][:50]}")


if __name__ == "__main__":
    main()
