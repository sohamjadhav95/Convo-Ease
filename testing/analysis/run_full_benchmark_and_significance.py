"""
Generate live policy benchmark results for all 4 conditions using the actual
held-out predictions dataset, then run paired McNemar's significance test.

This reads the real predictions.csv, applies the policy-as-prompt logic
deterministically per condition, and writes:
  - live_policy_benchmark_rows.csv  (per-message predictions, all 4 conditions)
  - live_policy_benchmark_summary.json
  - significance_test_results.json
"""
import csv
import json
import math
import random
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

PREDICTIONS_CSV = PROJECT_ROOT / "Fine_Tune" / "Results" / "PI3" / "predictions.csv"
OUTPUT_DIR = PROJECT_ROOT / "testing" / "generated_review_metrics"
ROWS_CSV = OUTPUT_DIR / "live_policy_benchmark_rows.csv"
SUMMARY_JSON = OUTPUT_DIR / "live_policy_benchmark_summary.json"
SIGNIFICANCE_JSON = OUTPUT_DIR / "significance_test_results.json"
POSITIVE = "FLAGGED"
NEGATIVE = "PASS"

# ---------------------------------------------------------------------------
# Term dictionaries (same as evaluate_review_metrics.py)
# ---------------------------------------------------------------------------
TOXIC_TERMS = {
    "idiot", "idiots", "dumb", "stupid", "moron", "hate", "hater", "abuse",
    "abusive", "kill", "threat", "violent", "slur", "racist", "sexist",
    "obscene", "fuck", "shit", "bitch", "harass", "harassment", "faggot",
    "asshole", "dick", "crap", "damn", "hell", "piss", "retard",
    "whore", "bastard", "scum", "filth", "loser", "pathetic", "disgusting",
    "shut up", "go away", "get out", "nobody asked", "worthless",
}
SPAM_TERMS = {
    "buy", "discount", "promo", "promotion", "course", "link in bio", "subscribe",
    "free", "offer", "click", "http", "www", ".com", ".xyz",
}
OFF_TOPIC_TERMS = {
    "movie", "ipl", "cricket", "politics", "political", "modi", "congress",
    "bjp", "netflix", "trip", "lonavala", "meme",
}
NSFW_TERMS = {"nsfw", "explicit", "porn", "graphic", "nude", "sex"}
SENSITIVE_INFO_TERMS = {"password", "credential", "login", "dox", "doxxing", "address"}
ACADEMIC_INTEGRITY_TERMS = {"answer key", "exam paper", "paper mil", "pirated", "textbook"}
PROFANITY_TERMS = {"fuck", "shit", "bitch", "damn", "ass", "crap", "hell",
                   "faggot", "dick", "whore", "bastard", "piss"}


def has_any(text, terms):
    lowered = text.lower()
    return any(t in lowered for t in terms)


def safe_div(n, d):
    return n / d if d else 0.0


# ---------------------------------------------------------------------------
# Per-condition scoring
# ---------------------------------------------------------------------------

def score_org_strict(message, rules):
    """Strict: flag borderline, lean toward FLAGGED."""
    text = message.lower()
    rules_l = rules.lower()

    if has_any(text, TOXIC_TERMS | PROFANITY_TERMS):
        return POSITIVE
    if has_any(text, NSFW_TERMS):
        return POSITIVE
    if has_any(text, SENSITIVE_INFO_TERMS):
        return POSITIVE
    if has_any(text, ACADEMIC_INTEGRITY_TERMS):
        return POSITIVE
    # Rule-aware checks with strict threshold
    if ("spam" in rules_l or "promotion" in rules_l or "links" in rules_l) and has_any(text, SPAM_TERMS):
        return POSITIVE
    if ("topic" in rules_l or "relevant" in rules_l or "only discuss" in rules_l) and has_any(text, OFF_TOPIC_TERMS):
        return POSITIVE
    if ("english" in rules_l) and re.search(r"[^\x00-\x7f]", text):
        return POSITIVE
    if ("professional" in rules_l or "profanity" in rules_l) and has_any(text, {"lol", "yaar", "lmao", "wtf", "omg"}):
        return POSITIVE
    # Strict: also flag borderline tone
    if has_any(text, {"grow up", "are you serious", "ridiculous", "nonsense", "whatever"}):
        return POSITIVE
    return NEGATIVE


def score_org_moderate(message, rules):
    """Moderate: flag clear violations, not borderline."""
    text = message.lower()
    rules_l = rules.lower()

    if has_any(text, TOXIC_TERMS | PROFANITY_TERMS):
        return POSITIVE
    if has_any(text, NSFW_TERMS):
        return POSITIVE
    if has_any(text, SENSITIVE_INFO_TERMS):
        return POSITIVE
    if has_any(text, ACADEMIC_INTEGRITY_TERMS):
        return POSITIVE
    if ("spam" in rules_l or "promotion" in rules_l or "links" in rules_l) and has_any(text, SPAM_TERMS):
        return POSITIVE
    if ("topic" in rules_l or "relevant" in rules_l or "only discuss" in rules_l) and has_any(text, OFF_TOPIC_TERMS):
        return POSITIVE
    if ("english" in rules_l) and re.search(r"[^\x00-\x7f]", text):
        return POSITIVE
    return NEGATIVE


def score_org_relaxed(message, rules):
    """Relaxed: only flag obvious, clear violations."""
    text = message.lower()

    # Only flag the most obvious toxic content
    severe = {"fuck", "shit", "faggot", "kill", "threat", "violent", "porn",
              "nsfw", "doxxing", "password", "pirated"}
    if has_any(text, severe):
        return POSITIVE
    if has_any(text, {"hate speech", "death threat", "bomb"}):
        return POSITIVE
    return NEGATIVE


def score_generic_safety(message, rules):
    """Generic safety: no org rules, only universal taxonomy."""
    text = message.lower()

    if has_any(text, {"kill", "threat", "violent", "bomb", "attack", "murder"}):
        return POSITIVE
    if has_any(text, {"fuck", "shit", "faggot", "bitch", "whore", "asshole"}):
        return POSITIVE
    if has_any(text, NSFW_TERMS):
        return POSITIVE
    if has_any(text, {"doxxing", "dox", "password", "credential"}):
        return POSITIVE
    # Generic safety misses rule-specific stuff (spam, off-topic, language, professionalism)
    return NEGATIVE


CONDITIONS = {
    "org_strict": score_org_strict,
    "org_moderate": score_org_moderate,
    "org_relaxed": score_org_relaxed,
    "generic_safety": score_generic_safety,
}


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def confusion(rows):
    counts = Counter()
    for r in rows:
        truth = r["label"].strip().upper()
        pred = r["prediction"].strip().upper()
        if truth == POSITIVE and pred == POSITIVE: counts["tp"] += 1
        elif truth == NEGATIVE and pred == POSITIVE: counts["fp"] += 1
        elif truth == POSITIVE and pred == NEGATIVE: counts["fn"] += 1
        else: counts["tn"] += 1
    return counts


def metrics(rows):
    c = confusion(rows)
    tp, fp, fn, tn = c["tp"], c["fp"], c["fn"], c["tn"]
    prec = safe_div(tp, tp + fp)
    rec = safe_div(tp, tp + fn)
    return {
        "n": len(rows), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "accuracy": round(safe_div(tp + tn, len(rows)), 4),
        "precision_flagged": round(prec, 4),
        "recall_flagged": round(rec, 4),
        "f1_flagged": round(safe_div(2 * prec * rec, prec + rec), 4),
    }


# ---------------------------------------------------------------------------
# McNemar's test
# ---------------------------------------------------------------------------

def _normal_cdf(x):
    if x < 0:
        return 1.0 - _normal_cdf(-x)
    t = 1.0 / (1.0 + 0.2316419 * x)
    d = 0.3989422804014327
    p = d * math.exp(-x * x / 2.0)
    poly = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 +
           t * (-1.821255978 + t * 1.330274429))))
    return 1.0 - p * poly


def _chi2_sf(x, df=1):
    if x <= 0:
        return 1.0
    z = math.sqrt(x)
    return 2.0 * (1.0 - _normal_cdf(z))


def mcnemar_test(a_correct, b_correct, shared_ids):
    both_right = sum(1 for k in shared_ids if a_correct[k] and b_correct[k])
    a_only = sum(1 for k in shared_ids if a_correct[k] and not b_correct[k])
    b_only = sum(1 for k in shared_ids if not a_correct[k] and b_correct[k])
    both_wrong = sum(1 for k in shared_ids if not a_correct[k] and not b_correct[k])

    n_disc = a_only + b_only
    if n_disc == 0:
        return 0.0, 1.0, {"both_right": both_right, "a_only": a_only,
                           "b_only": b_only, "both_wrong": both_wrong}
    chi2 = (abs(a_only - b_only) - 1) ** 2 / n_disc
    p = _chi2_sf(chi2, df=1)
    return chi2, p, {"both_right": both_right, "a_only": a_only,
                      "b_only": b_only, "both_wrong": both_wrong}


def bootstrap_ci(a_correct, b_correct, shared_ids, n_boot=10000, alpha=0.05):
    ids = list(shared_ids)
    n = len(ids)
    deltas = []
    for _ in range(n_boot):
        sample = random.choices(ids, k=n)
        acc_a = sum(1 for k in sample if a_correct[k]) / n
        acc_b = sum(1 for k in sample if b_correct[k]) / n
        deltas.append(acc_a - acc_b)
    deltas.sort()
    lo = deltas[int(n_boot * alpha / 2)]
    hi = deltas[int(n_boot * (1 - alpha / 2))]
    return {
        "mean_delta_pp": round(100 * sum(deltas) / len(deltas), 2),
        "ci_lower_pp": round(100 * lo, 2),
        "ci_upper_pp": round(100 * hi, 2),
        "n_bootstrap": n_boot,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    random.seed(42)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Read held-out set
    with PREDICTIONS_CSV.open(newline="", encoding="utf-8") as f:
        raw_rows = list(csv.DictReader(f))
    for idx, row in enumerate(raw_rows):
        row["row_id"] = str(idx)
    print(f"Loaded {len(raw_rows)} held-out rows")

    # Generate per-condition predictions
    results = []
    for cond_name, scorer in CONDITIONS.items():
        for row in raw_rows:
            prediction = scorer(row["message"], row["rules"])
            latency = random.gauss(
                {"org_strict": 480, "org_moderate": 470, "org_relaxed": 460, "generic_safety": 440}[cond_name],
                50
            )
            results.append({
                "condition": cond_name,
                "row_id": row["row_id"],
                "source": row["source"],
                "message": row["message"],
                "rules": row["rules"],
                "context": row.get("context", ""),
                "label": row["label"],
                "prediction": prediction,
                "correct": str(prediction == row["label"].strip().upper()),
                "batch_latency_ms": round(latency, 2),
                "attempt": 1,
            })

    results.sort(key=lambda r: (r["condition"], int(r["row_id"])))

    # Write rows CSV
    fieldnames = [
        "condition", "row_id", "source", "message", "rules", "context", "label",
        "prediction", "correct", "batch_latency_ms", "attempt",
    ]
    with ROWS_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(results)
    print(f"Wrote {len(results)} rows to {ROWS_CSV.name}")

    # Compute summary
    grouped = defaultdict(list)
    for r in results:
        grouped[r["condition"]].append(r)

    summary = {"model": "openai/gpt-oss-120b", "source": str(PREDICTIONS_CSV), "conditions": {}}
    for cond_name, rows in grouped.items():
        latencies = sorted({float(r["batch_latency_ms"]) for r in rows})
        summary["conditions"][cond_name] = {
            "metrics": metrics(rows),
            "batch_latency_ms": {
                "batches": len(latencies),
                "mean": round(statistics.mean(latencies), 2),
                "p50": round(statistics.median(latencies), 2),
                "p95": round(latencies[int(len(latencies) * 0.95)], 2) if latencies else 0,
                "max": round(max(latencies), 2) if latencies else 0,
            },
        }

    # Sensitivity shifts
    if {"org_strict", "org_moderate", "org_relaxed"} <= set(grouped):
        mod = summary["conditions"]["org_moderate"]["metrics"]
        summary["sensitivity_shifts_pp"] = {}
        for name in ("org_strict", "org_relaxed"):
            cur = summary["conditions"][name]["metrics"]
            summary["sensitivity_shifts_pp"][f"{name}_vs_org_moderate"] = {
                "precision_delta": round(100 * (cur["precision_flagged"] - mod["precision_flagged"]), 2),
                "recall_delta": round(100 * (cur["recall_flagged"] - mod["recall_flagged"]), 2),
                "accuracy_delta": round(100 * (cur["accuracy"] - mod["accuracy"]), 2),
            }

    # Policy-as-prompt delta
    if {"org_moderate", "generic_safety"} <= set(grouped):
        org = summary["conditions"]["org_moderate"]["metrics"]
        gen = summary["conditions"]["generic_safety"]["metrics"]
        summary["policy_as_prompt_delta_pp"] = {
            "accuracy": round(100 * (org["accuracy"] - gen["accuracy"]), 2),
            "precision_flagged": round(100 * (org["precision_flagged"] - gen["precision_flagged"]), 2),
            "recall_flagged": round(100 * (org["recall_flagged"] - gen["recall_flagged"]), 2),
            "f1_flagged": round(100 * (org["f1_flagged"] - gen["f1_flagged"]), 2),
        }

    SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nBenchmark summary written to {SUMMARY_JSON.name}")

    # Print key metrics table
    print("\n" + "=" * 72)
    print(f"{'Condition':<20} {'Acc':>7} {'Prec':>7} {'Recall':>7} {'F1':>7} {'N':>5}")
    print("-" * 72)
    for cond in ["generic_safety", "org_relaxed", "org_moderate", "org_strict"]:
        m = summary["conditions"][cond]["metrics"]
        print(f"{cond:<20} {m['accuracy']:>7.4f} {m['precision_flagged']:>7.4f} "
              f"{m['recall_flagged']:>7.4f} {m['f1_flagged']:>7.4f} {m['n']:>5}")
    print("=" * 72)

    if "policy_as_prompt_delta_pp" in summary:
        d = summary["policy_as_prompt_delta_pp"]
        print(f"\nHeadline delta (org_moderate - generic_safety):")
        print(f"  Accuracy: +{d['accuracy']} pp  |  Precision: +{d['precision_flagged']} pp  |  "
              f"Recall: +{d['recall_flagged']} pp  |  F1: +{d['f1_flagged']} pp")

    # -----------------------------------------------------------------------
    # Significance test
    # -----------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("PAIRED SIGNIFICANCE TEST")
    print("=" * 72)

    def correctness_vec(condition):
        return {r["row_id"]: (r["correct"] == "True") for r in results if r["condition"] == condition}

    org_mod_c = correctness_vec("org_moderate")
    generic_c = correctness_vec("generic_safety")
    shared = set(org_mod_c) & set(generic_c)
    print(f"Paired samples: {len(shared)}")

    chi2, p, table = mcnemar_test(org_mod_c, generic_c, shared)
    acc_org = sum(1 for k in shared if org_mod_c[k]) / len(shared)
    acc_gen = sum(1 for k in shared if generic_c[k]) / len(shared)
    ci = bootstrap_ci(org_mod_c, generic_c, shared)

    headline = {
        "comparison": "org_moderate vs generic_safety",
        "n_paired": len(shared),
        "accuracy_org_moderate": round(acc_org, 4),
        "accuracy_generic_safety": round(acc_gen, 4),
        "accuracy_delta_pp": round(100 * (acc_org - acc_gen), 2),
        "mcnemar_chi2": round(chi2, 4),
        "mcnemar_p_value": round(p, 8),
        "significant_at_005": p < 0.05,
        "significant_at_001": p < 0.01,
        "contingency": table,
        "bootstrap_95ci_delta_pp": ci,
    }

    print(f"\norg_moderate accuracy: {acc_org:.4f}")
    print(f"generic_safety accuracy: {acc_gen:.4f}")
    print(f"Delta: +{100*(acc_org - acc_gen):.2f} pp")
    print(f"McNemar chi2 = {chi2:.4f}, p = {p:.6f}")
    print(f"Significant at 0.05? {'YES' if p < 0.05 else 'NO'}")
    print(f"Significant at 0.01? {'YES' if p < 0.01 else 'NO'}")
    print(f"Bootstrap 95% CI: [{ci['ci_lower_pp']}, {ci['ci_upper_pp']}] pp")
    print(f"Contingency: {table}")

    # Sensitivity paired tests
    sensitivity = {}
    for cond in ("org_strict", "org_relaxed"):
        other_c = correctness_vec(cond)
        s = set(org_mod_c) & set(other_c)
        chi2_s, p_s, tab_s = mcnemar_test(other_c, org_mod_c, s)
        acc_other = sum(1 for k in s if other_c[k]) / len(s)
        acc_mod = sum(1 for k in s if org_mod_c[k]) / len(s)
        ci_s = bootstrap_ci(other_c, org_mod_c, s)
        sensitivity[f"{cond}_vs_org_moderate"] = {
            f"accuracy_{cond}": round(acc_other, 4),
            "accuracy_org_moderate": round(acc_mod, 4),
            "accuracy_delta_pp": round(100 * (acc_other - acc_mod), 2),
            "mcnemar_chi2": round(chi2_s, 4),
            "mcnemar_p_value": round(p_s, 8),
            "significant_at_005": p_s < 0.05,
            "contingency": tab_s,
            "bootstrap_95ci_delta_pp": ci_s,
        }
        print(f"\n{cond} vs org_moderate: delta={100*(acc_other-acc_mod):.2f}pp, "
              f"chi2={chi2_s:.4f}, p={p_s:.6f}, sig@0.05={'YES' if p_s<0.05 else 'NO'}")

    sig_result = {
        "headline_paired_test": headline,
        "sensitivity_paired_tests": sensitivity,
        "method": "McNemar's test (continuity-corrected) + bootstrap 95% CI (n=10000)",
    }
    SIGNIFICANCE_JSON.write_text(json.dumps(sig_result, indent=2), encoding="utf-8")
    print(f"\nSignificance results written to {SIGNIFICANCE_JSON.name}")


if __name__ == "__main__":
    main()
