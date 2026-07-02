"""
Task 2: Independently recompute accuracy, precision, recall, F1 for all four conditions
from benchmark_raw_1200.csv. Does NOT trust any previously-reported summary numbers.
Read-only — writes only paper_artifacts/metrics_and_significance.json and
paper_artifacts/metrics_and_significance.md.
"""
import csv
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ARTIFACTS = Path(__file__).resolve().parents[1]
ROWS_CSV = ARTIFACTS / "benchmark_raw_1200.csv"
OUT_JSON = ARTIFACTS / "metrics_and_significance.json"
OUT_MD = ARTIFACTS / "metrics_and_significance.md"

POSITIVE = "FLAGGED"
NEGATIVE = "PASS"


def safe_div(n, d):
    return n / d if d else 0.0


def confusion_matrix_counts(rows):
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
    return c


def compute_metrics(rows):
    c = confusion_matrix_counts(rows)
    tp, fp, fn, tn = c["tp"], c["fp"], c["fn"], c["tn"]
    n = tp + fp + fn + tn
    prec = safe_div(tp, tp + fp)
    rec = safe_div(tp, tp + fn)
    f1 = safe_div(2 * prec * rec, prec + rec)
    return {
        "n": n,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "accuracy": round(safe_div(tp + tn, n), 6),
        "precision_flagged": round(prec, 6),
        "recall_flagged": round(rec, 6),
        "f1_flagged": round(f1, 6),
        "accuracy_pct": round(100 * safe_div(tp + tn, n), 4),
        "precision_flagged_pct": round(100 * prec, 4),
        "recall_flagged_pct": round(100 * rec, 4),
        "f1_flagged_pct": round(100 * f1, 4),
    }


# ────────────────────────────────────────────────────────────────────────────
# Normal CDF approximation (Abramowitz & Stegun 26.2.17)
# ────────────────────────────────────────────────────────────────────────────
def _norm_cdf(x):
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    p = 0.3989422804014327 * math.exp(-x * x / 2.0)
    poly = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937
           + t * (-1.821255978 + t * 1.330274429))))
    cdf = 1.0 - p * poly
    return cdf if x >= 0 else 1.0 - cdf


def _chi2_sf(chi2, df=1):
    if chi2 <= 0:
        return 1.0
    z = math.sqrt(chi2)
    return 2.0 * (1.0 - _norm_cdf(z))


def _binom_exact_p(b, c):
    """Exact p-value for McNemar via binomial(b+c, 0.5) — two-tailed."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    # Sum P(X <= k) for two-tail
    log_p = -n * math.log(2)
    p = 0.0
    log_binom = 0.0
    for i in range(k + 1):
        if i == 0:
            log_binom = 0.0
        else:
            log_binom += math.log(n - i + 1) - math.log(i)
        p += math.exp(log_binom + log_p)
    return min(2 * p, 1.0)


def mcnemar(a_correct, b_correct, shared_ids):
    """
    a_correct, b_correct: dict {row_id: bool}
    Returns dict with full test results.
    """
    both_right = sum(1 for k in shared_ids if a_correct[k] and b_correct[k])
    a_only = sum(1 for k in shared_ids if a_correct[k] and not b_correct[k])
    b_only = sum(1 for k in shared_ids if not a_correct[k] and b_correct[k])
    both_wrong = sum(1 for k in shared_ids if not a_correct[k] and not b_correct[k])

    b, c = a_only, b_only
    n_disc = b + c

    # Exact binomial if min(b,c) < 25
    use_exact = min(b, c) < 25
    if n_disc == 0:
        chi2_cc = 0.0
        p_cc = 1.0
        p_exact = 1.0
    else:
        # McNemar with continuity correction
        chi2_cc = (abs(b - c) - 1) ** 2 / n_disc if n_disc > 0 else 0.0
        p_cc = _chi2_sf(chi2_cc)
        p_exact = _binom_exact_p(b, c)

    return {
        "contingency_table": {
            "both_right": both_right,
            "a_only_right": a_only,
            "b_only_right": b_only,
            "both_wrong": both_wrong,
        },
        "n_discordant": n_disc,
        "chi2_continuity_corrected": round(chi2_cc, 6),
        "p_value_cc": round(p_cc, 8),
        "p_value_exact_binomial": round(p_exact, 8),
        "test_used": "exact_binomial" if use_exact else "chi2_continuity_corrected",
        "significant_at_005": (p_exact if use_exact else p_cc) < 0.05,
        "significant_at_001": (p_exact if use_exact else p_cc) < 0.01,
    }


def wilson_ci(p, n, z=1.96):
    """Wilson score confidence interval for a proportion."""
    if n == 0:
        return 0.0, 0.0
    center = (p + z * z / (2 * n)) / (1 + z * z / n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, center - margin), min(1.0, center + margin)


def bootstrap_accuracy_diff(a_correct, b_correct, shared_ids,
                             n_boot=10_000, alpha=0.05, seed=42):
    """Bootstrap CI for accuracy_a - accuracy_b."""
    rng = random.Random(seed)
    ids = list(shared_ids)
    n = len(ids)
    deltas = []
    for _ in range(n_boot):
        sample = rng.choices(ids, k=n)
        acc_a = sum(1 for k in sample if a_correct[k]) / n
        acc_b = sum(1 for k in sample if b_correct[k]) / n
        deltas.append(acc_a - acc_b)
    deltas.sort()
    lo = deltas[int(n_boot * alpha / 2)]
    hi = deltas[int(n_boot * (1 - alpha / 2))]
    return {
        "method": "bootstrap (n=10000, seed=42)",
        "alpha": alpha,
        "mean_delta": round(sum(deltas) / n_boot, 6),
        "mean_delta_pp": round(100 * sum(deltas) / n_boot, 4),
        "ci_lower": round(lo, 6),
        "ci_upper": round(hi, 6),
        "ci_lower_pp": round(100 * lo, 4),
        "ci_upper_pp": round(100 * hi, 4),
    }


def main():
    # ── Load ────────────────────────────────────────────────────────────────
    with ROWS_CSV.open(newline="", encoding="utf-8") as f:
        all_rows = list(csv.DictReader(f))

    grouped = defaultdict(list)
    for r in all_rows:
        grouped[r["condition"]].append(r)

    print(f"Loaded {len(all_rows)} rows from {ROWS_CSV.name}")

    # ── Per-condition metrics ───────────────────────────────────────────────
    condition_metrics = {}
    for cond in ["generic_safety", "org_relaxed", "org_moderate", "org_strict"]:
        condition_metrics[cond] = compute_metrics(grouped[cond])

    # ── Correctness vectors for McNemar ─────────────────────────────────────
    def cvec(condition):
        return {r["row_id"]: (r["correct"].strip().lower() in ("true", "1")) for r in grouped[condition]}

    org_mod_c = cvec("org_moderate")
    generic_c = cvec("generic_safety")
    org_strict_c = cvec("org_strict")
    org_relaxed_c = cvec("org_relaxed")

    # ── Three paired comparisons ────────────────────────────────────────────
    comparisons = {}

    for (name_a, a_c), (name_b, b_c) in [
        (("org_moderate", org_mod_c), ("generic_safety", generic_c)),
        (("org_strict", org_strict_c), ("org_moderate", org_mod_c)),
        (("org_relaxed", org_relaxed_c), ("org_moderate", org_mod_c)),
    ]:
        shared = set(a_c) & set(b_c)
        key = f"{name_a}_vs_{name_b}"
        mn = mcnemar(a_c, b_c, shared)
        acc_a = sum(1 for k in shared if a_c[k]) / len(shared)
        acc_b = sum(1 for k in shared if b_c[k]) / len(shared)
        delta = acc_a - acc_b
        ci = bootstrap_accuracy_diff(a_c, b_c, shared)
        comparisons[key] = {
            "condition_a": name_a,
            "condition_b": name_b,
            "n_paired": len(shared),
            "accuracy_a": round(acc_a, 6),
            "accuracy_b": round(acc_b, 6),
            "delta_pp": round(100 * delta, 4),
            **mn,
            "accuracy_diff_ci": ci,
        }

    # ── Assemble output ─────────────────────────────────────────────────────
    result = {
        "source_csv": str(ROWS_CSV),
        "total_rows": len(all_rows),
        "note": "All metrics recomputed fresh from benchmark_raw_1200.csv. No prior summary numbers were consulted.",
        "condition_metrics": condition_metrics,
        "paired_significance_tests": comparisons,
    }

    OUT_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Written: {OUT_JSON}")

    # ── Markdown table ───────────────────────────────────────────────────────
    md_lines = [
        "# Benchmark Metrics and Significance Tests",
        "",
        "> All numbers recomputed from `benchmark_raw_1200.csv`. "
        "No previously-reported values consulted.",
        "",
        "## Per-Condition Metrics (N=300 each)",
        "",
        "| Condition | Acc % | Prec % | Recall % | F1 % | TP | FP | FN | TN |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for cond in ["generic_safety", "org_relaxed", "org_moderate", "org_strict"]:
        m = condition_metrics[cond]
        md_lines.append(
            f"| {cond} | {m['accuracy_pct']:.2f} | {m['precision_flagged_pct']:.2f} | "
            f"{m['recall_flagged_pct']:.2f} | {m['f1_flagged_pct']:.2f} | "
            f"{m['tp']} | {m['fp']} | {m['fn']} | {m['tn']} |"
        )

    md_lines += [
        "",
        "## Paired McNemar Significance Tests",
        "",
        "Wilson CI is not applicable to paired accuracy-difference tests; "
        "bootstrap CI (n=10,000, seed=42) is used for the accuracy delta.",
        "",
    ]

    for key, comp in comparisons.items():
        use_exact = comp["test_used"] == "exact_binomial"
        p_val = comp["p_value_exact_binomial"] if use_exact else comp["p_value_cc"]
        test_label = "exact binomial" if use_exact else "chi2 (continuity-corrected)"
        md_lines += [
            f"### {comp['condition_a']} vs {comp['condition_b']}",
            "",
            f"- N paired: {comp['n_paired']}",
            f"- Accuracy A ({comp['condition_a']}): {comp['accuracy_a']*100:.2f}%",
            f"- Accuracy B ({comp['condition_b']}): {comp['accuracy_b']*100:.2f}%",
            f"- Delta (A − B): {comp['delta_pp']:+.2f} pp",
            "",
            "**Discordant-pairs contingency table:**",
            "",
            "| | B correct | B wrong |",
            "|---|---|---|",
            f"| A correct | {comp['contingency_table']['both_right']} | {comp['contingency_table']['a_only_right']} |",
            f"| A wrong   | {comp['contingency_table']['b_only_right']} | {comp['contingency_table']['both_wrong']} |",
            "",
            f"- Chi² (continuity-corrected): {comp['chi2_continuity_corrected']:.4f}",
            f"- p (continuity-corrected): {comp['p_value_cc']:.6f}",
            f"- p (exact binomial): {comp['p_value_exact_binomial']:.6f}",
            f"- Test reported: {test_label}  (exact binomial used when min(b,c) < 25)",
            f"- Significant at 0.05: {'YES' if comp['significant_at_005'] else 'NO'}",
            f"- Significant at 0.01: {'YES' if comp['significant_at_001'] else 'NO'}",
            "",
            "**Bootstrap 95% CI for accuracy delta (A − B):**",
            "",
            f"- [{comp['accuracy_diff_ci']['ci_lower_pp']:+.2f}, {comp['accuracy_diff_ci']['ci_upper_pp']:+.2f}] pp",
            f"  (method: {comp['accuracy_diff_ci']['method']})",
            "",
        ]

    OUT_MD.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"Written: {OUT_MD}")

    # ── Console summary ──────────────────────────────────────────────────────
    print()
    print(f"{'Condition':<20} {'Acc%':>7} {'Prec%':>7} {'Rec%':>7} {'F1%':>7}")
    print("-" * 55)
    for cond in ["generic_safety", "org_relaxed", "org_moderate", "org_strict"]:
        m = condition_metrics[cond]
        print(f"{cond:<20} {m['accuracy_pct']:>7.2f} {m['precision_flagged_pct']:>7.2f} "
              f"{m['recall_flagged_pct']:>7.2f} {m['f1_flagged_pct']:>7.2f}")

    print()
    for key, comp in comparisons.items():
        use_exact = comp["test_used"] == "exact_binomial"
        p_val = comp["p_value_exact_binomial"] if use_exact else comp["p_value_cc"]
        ci = comp["accuracy_diff_ci"]
        print(f"{comp['condition_a']} vs {comp['condition_b']}: "
              f"delta={comp['delta_pp']:+.2f}pp, "
              f"p={p_val:.6f} ({comp['test_used']}), "
              f"95%CI=[{ci['ci_lower_pp']:+.2f}, {ci['ci_upper_pp']:+.2f}]pp, "
              f"sig@0.05={'YES' if comp['significant_at_005'] else 'NO'}")


if __name__ == "__main__":
    main()
