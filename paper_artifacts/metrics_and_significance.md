# Benchmark Metrics and Significance Tests

> All numbers recomputed from `benchmark_raw_1200.csv`. No previously-reported values consulted.

## Per-Condition Metrics (N=300 each)

| Condition | Acc % | Prec % | Recall % | F1 % | TP | FP | FN | TN |
|---|---|---|---|---|---|---|---|---|
| generic_safety | 68.33 | 83.13 | 46.00 | 59.23 | 69 | 14 | 81 | 136 |
| org_relaxed | 65.67 | 89.83 | 35.33 | 50.72 | 53 | 6 | 97 | 144 |
| org_moderate | 76.67 | 76.67 | 76.67 | 76.67 | 115 | 35 | 35 | 115 |
| org_strict | 77.00 | 76.82 | 77.33 | 77.08 | 116 | 35 | 34 | 115 |

## Paired McNemar Significance Tests

Wilson CI is not applicable to paired accuracy-difference tests; bootstrap CI (n=10,000, seed=42) is used for the accuracy delta.

### org_moderate vs generic_safety

- N paired: 300
- Accuracy A (org_moderate): 76.67%
- Accuracy B (generic_safety): 68.33%
- Delta (A − B): +8.33 pp

**Discordant-pairs contingency table:**

| | B correct | B wrong |
|---|---|---|
| A correct | 182 | 48 |
| A wrong   | 23 | 47 |

- Chi² (continuity-corrected): 8.1127
- p (continuity-corrected): 0.004396
- p (exact binomial): 0.004065
- Test reported: exact binomial  (exact binomial used when min(b,c) < 25)
- Significant at 0.05: YES
- Significant at 0.01: YES

**Bootstrap 95% CI for accuracy delta (A − B):**

- [+3.00, +14.00] pp
  (method: bootstrap (n=10000, seed=42))

### org_strict vs org_moderate

- N paired: 300
- Accuracy A (org_strict): 77.00%
- Accuracy B (org_moderate): 76.67%
- Delta (A − B): +0.33 pp

**Discordant-pairs contingency table:**

| | B correct | B wrong |
|---|---|---|
| A correct | 230 | 1 |
| A wrong   | 0 | 69 |

- Chi² (continuity-corrected): 0.0000
- p (continuity-corrected): 1.000000
- p (exact binomial): 1.000000
- Test reported: exact binomial  (exact binomial used when min(b,c) < 25)
- Significant at 0.05: NO
- Significant at 0.01: NO

**Bootstrap 95% CI for accuracy delta (A − B):**

- [+0.00, +1.00] pp
  (method: bootstrap (n=10000, seed=42))

### org_relaxed vs org_moderate

- N paired: 300
- Accuracy A (org_relaxed): 65.67%
- Accuracy B (org_moderate): 76.67%
- Delta (A − B): -11.00 pp

**Discordant-pairs contingency table:**

| | B correct | B wrong |
|---|---|---|
| A correct | 168 | 29 |
| A wrong   | 62 | 41 |

- Chi² (continuity-corrected): 11.2527
- p (continuity-corrected): 0.000795
- p (exact binomial): 0.000705
- Test reported: chi2 (continuity-corrected)  (exact binomial used when min(b,c) < 25)
- Significant at 0.05: YES
- Significant at 0.01: YES

**Bootstrap 95% CI for accuracy delta (A − B):**

- [-17.33, -5.00] pp
  (method: bootstrap (n=10000, seed=42))
