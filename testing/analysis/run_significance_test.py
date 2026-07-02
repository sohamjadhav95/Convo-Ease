"""
Paired significance test on the headline delta:
  org_moderate (policy-as-prompt) vs generic_safety (generic taxonomy)

Uses McNemar's test on per-message correctness vectors.
Also computes bootstrap 95% CI on the accuracy delta.

Reads: live_policy_benchmark_rows.csv
Writes: significance_test_results.json
"""
import csv
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

OUTPUT_DIR = PROJECT_ROOT / "testing" / "generated_review_metrics"
ROWS_CSV = OUTPUT_DIR / "live_policy_benchmark_rows.csv"
RESULTS_JSON = OUTPUT_DIR / "significance_test_results.json"


def load_rows():
    with ROWS_CSV.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def correctness_vector(rows, condition):
    """Return {row_id: bool} for a single condition."""
    return {
        r["row_id"]: (r["correct"] == "True")
        for r in rows
        if r["condition"] == condition
    }


def mcnemar_test(a_correct, b_correct, shared_ids):
    """
    McNemar's test on paired binary outcomes.
    a_correct, b_correct: dict {row_id: bool}
    Returns chi2, p_value, contingency table counts.
    """
    # Contingency: (a_right & b_right), (a_right & b_wrong),
    #              (a_wrong & b_right), (a_wrong & b_wrong)
    both_right = sum(1 for k in shared_ids if a_correct[k] and b_correct[k])
    a_only     = sum(1 for k in shared_ids if a_correct[k] and not b_correct[k])
    b_only     = sum(1 for k in shared_ids if not a_correct[k] and b_correct[k])
    both_wrong = sum(1 for k in shared_ids if not a_correct[k] and not b_correct[k])

    n_discordant = a_only + b_only
    if n_discordant == 0:
        return 0.0, 1.0, {"both_right": both_right, "a_only": a_only,
                           "b_only": b_only, "both_wrong": both_wrong}

    # McNemar chi-squared with continuity correction
    chi2 = (abs(a_only - b_only) - 1) ** 2 / n_discordant

    # p-value from chi-squared distribution with 1 df
    # Using survival function approximation
    import math
    # Simple chi2 p-value (1 df) via complementary error function
    p_value = _chi2_sf(chi2, df=1)

    return chi2, p_value, {
        "both_right": both_right,
        "a_only": a_only,
        "b_only": b_only,
        "both_wrong": both_wrong,
    }


def _chi2_sf(x, df=1):
    """Survival function for chi-squared distribution (1 df) without scipy."""
    import math
    if x <= 0:
        return 1.0
    # For df=1, chi2 SF = 2 * (1 - Phi(sqrt(x)))
    z = math.sqrt(x)
    return 2.0 * (1.0 - _normal_cdf(z))


def _normal_cdf(x):
    """Standard normal CDF approximation (Abramowitz & Stegun)."""
    import math
    if x < 0:
        return 1.0 - _normal_cdf(-x)
    t = 1.0 / (1.0 + 0.2316419 * x)
    d = 0.3989422804014327  # 1/sqrt(2*pi)
    p = d * math.exp(-x * x / 2.0)
    poly = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 +
           t * (-1.821255978 + t * 1.330274429))))
    return 1.0 - p * poly


def bootstrap_ci(a_correct, b_correct, shared_ids, n_boot=10000, alpha=0.05):
    """Bootstrap 95% CI on accuracy delta (a - b)."""
    import random
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
    mean_delta = sum(deltas) / len(deltas)
    return {
        "mean_delta": round(mean_delta, 4),
        "ci_lower": round(lo, 4),
        "ci_upper": round(hi, 4),
        "n_bootstrap": n_boot,
        "alpha": alpha,
    }


def per_sensitivity_comparison(rows):
    """Compare org_strict vs org_moderate and org_relaxed vs org_moderate."""
    results = {}
    org_mod = correctness_vector(rows, "org_moderate")
    for condition in ("org_strict", "org_relaxed"):
        other = correctness_vector(rows, condition)
        shared = set(org_mod) & set(other)
        if not shared:
            results[f"{condition}_vs_org_moderate"] = {"error": "no shared rows"}
            continue
        chi2, p, table = mcnemar_test(other, org_mod, shared)
        acc_other = sum(1 for k in shared if other[k]) / len(shared)
        acc_mod   = sum(1 for k in shared if org_mod[k]) / len(shared)
        ci = bootstrap_ci(other, org_mod, shared)
        results[f"{condition}_vs_org_moderate"] = {
            f"accuracy_{condition}": round(acc_other, 4),
            "accuracy_org_moderate": round(acc_mod, 4),
            "accuracy_delta_pp": round(100 * (acc_other - acc_mod), 2),
            "mcnemar_chi2": round(chi2, 4),
            "mcnemar_p_value": round(p, 6),
            "significant_at_005": p < 0.05,
            "contingency": table,
            "bootstrap_95ci": ci,
        }
    return results


def main():
    rows = load_rows()
    conditions = sorted(set(r["condition"] for r in rows))
    print(f"Loaded {len(rows)} rows across conditions: {conditions}")

    # --- Headline: org_moderate vs generic_safety ---
    org_mod = correctness_vector(rows, "org_moderate")
    generic = correctness_vector(rows, "generic_safety")
    shared = set(org_mod) & set(generic)
    print(f"Paired samples (org_moderate vs generic_safety): {len(shared)}")

    if not shared:
        print("ERROR: No shared row_ids between org_moderate and generic_safety.")
        return

    chi2, p, table = mcnemar_test(org_mod, generic, shared)
    acc_org = sum(1 for k in shared if org_mod[k]) / len(shared)
    acc_gen = sum(1 for k in shared if generic[k]) / len(shared)
    ci = bootstrap_ci(org_mod, generic, shared)

    headline = {
        "comparison": "org_moderate vs generic_safety",
        "n_paired_samples": len(shared),
        "accuracy_org_moderate": round(acc_org, 4),
        "accuracy_generic_safety": round(acc_gen, 4),
        "accuracy_delta_pp": round(100 * (acc_org - acc_gen), 2),
        "mcnemar_chi2": round(chi2, 4),
        "mcnemar_p_value": round(p, 6),
        "significant_at_005": p < 0.05,
        "significant_at_001": p < 0.01,
        "contingency_table": table,
        "bootstrap_95ci_on_delta": ci,
    }

    # --- Sensitivity: org_strict/org_relaxed vs org_moderate ---
    sensitivity = per_sensitivity_comparison(rows)

    result = {
        "headline_paired_test": headline,
        "sensitivity_paired_tests": sensitivity,
        "method": "McNemar's test with continuity correction + bootstrap 95% CI (n=10000)",
    }

    RESULTS_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
