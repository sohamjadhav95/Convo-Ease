# Part 1: Per-rule paired analysis from stored predictions

## 1.1 Locate and describe the data
File path: paper_artifacts/benchmark_raw_1200.csv
Format: CSV
Row count: 1200
Column names: ['condition', 'row_id', 'source', 'message', 'rules', 'context', 'label', 'prediction', 'correct', 'batch_latency_ms', 'attempt']

Distinct values of the condition column:
- generic_safety: 300
- org_moderate: 300
- org_relaxed: 300
- org_strict: 300

Distinct values of the rule-set column:
- 'Business group rules:\n- Professional language only. Slang and profanity are not allowed.\n- No off-topic personal conversations.\n- All product promotions must be approved by admins first.': 128
- 'Keep all messages respectful. Insults and name-calling are not allowed.': 104
- 'Rules:\n- No insults, slurs, or harassment.\n- No self-promotion or external links.\n- Keep discussions relevant to machine learning.\n- No political or religious debates.': 92
- 'Group Guidelines:\n  Respect all members at all times.\n  No spam, flooding, or off-topic messages.\n  Constructive criticism only - no personal attacks.': 84
- 'Stay on topic. Only discuss subjects relevant to this group.': 84
- "Community guidelines:\n1. Zero tolerance for hate speech or discrimination.\n2. No threats of violence under any circumstances.\n3. No doxxing or sharing others' personal information.\n4. No NSFW content.": 80
- 'No hate speech, slurs, or personal attacks of any kind.': 76
- 'No self-promotion or sharing personal links without admin approval.': 76
- 'No discrimination based on race, religion, gender, nationality, or sexuality.': 76
- '1. No hate speech or personal attacks.\n2. No spam or repeated messages.\n3. Stay on topic - this is a Python programming group.\n4. English only.': 76
- 'No spam, repeated messages, or unsolicited promotions.': 68
- 'Treat every member with respect. Harassment and bullying are strictly forbidden.': 68
- 'Study group rules:\n1. No insults or aggressive language.\n2. Questions must be related to current semester topics.\n3. Share resources freely but no paid course links without permission.': 64
- 'No explicit, violent, or graphic content.': 64
- 'English only - no messages in other languages.': 60

Checks:
- Total rows is 1,200: True (1200)
- Distinct messages is 300: True (300)
- Four conditions, each covering all 300 messages: True 
- Fifteen distinct rule sets: True (15)
- Label balance is 150 allowable and 150 violating: True (PASS: 150, FLAGGED: 150)

## 1.2 Reproduce the published headline figures

Condition: generic_safety
- Acc: 68.3, Prec: 83.1, Rec: 46.0, F1: 59.2, MCC: 0.410
- TP: 69, FP: 14, TN: 136, FN: 81
- Published match (generic_safety): Pass
- Confusion matrix match: Pass

Condition: org_moderate
- Acc: 76.7, Prec: 76.7, Rec: 76.7, F1: 76.7, MCC: 0.533
- TP: 115, FP: 35, TN: 115, FN: 35
- Published match (org_moderate): Pass
- Confusion matrix match: Pass

Condition: org_strict
- Acc: 77.0, Prec: 76.8, Rec: 77.3, F1: 77.1, MCC: 0.540
- TP: 116, FP: 35, TN: 115, FN: 34
- Published match (org_strict): Pass

Condition: org_relaxed
- Acc: 65.7, Prec: 89.8, Rec: 35.3, F1: 50.7, MCC: 0.394
- TP: 53, FP: 6, TN: 144, FN: 97
- Published match (org_relaxed): Pass


## 1.3 Per-rule-set table, organizational rules at moderate sensitivity

| Rule Set | n | Correct | Acc (%) | 95% CI (%) | F1 (%) |
| --- | --- | --- | --- | --- | --- |
| 'Keep all messages respectful. Insults and name-calling are not allowed.' | 26 | 24 | 92.3 | [75.9, 97.9] | 93.3 |
| 'Group Guidelines:\n  Respect all members at all times.\n  No spam, flooding, or off-topic messages.\n  Constructive criticism only - no personal attacks.' | 21 | 17 | 81.0 | [60.0, 92.3] | 77.8 |
| "Community guidelines:\n1. Zero tolerance for hate speech or discrimination.\n2. No threats of violence under any circumstances.\n3. No doxxing or sharing others' personal information.\n4. No NSFW content." | 20 | 17 | 85.0 | [64.0, 94.8] | 87.0 |
| 'No explicit, violent, or graphic content.' | 16 | 15 | 93.8 | [71.7, 98.9] | 93.3 |
| 'Business group rules:\n- Professional language only. Slang and profanity are not allowed.\n- No off-topic personal conversations.\n- All product promotions must be approved by admins first.' | 32 | 24 | 75.0 | [57.9, 86.7] | 75.0 |
| 'English only - no messages in other languages.' | 15 | 12 | 80.0 | [54.8, 93.0] | 84.2 |
| 'Study group rules:\n1. No insults or aggressive language.\n2. Questions must be related to current semester topics.\n3. Share resources freely but no paid course links without permission.' | 16 | 12 | 75.0 | [50.5, 89.8] | 75.0 |
| 'No hate speech, slurs, or personal attacks of any kind.' | 19 | 13 | 68.4 | [46.0, 84.6] | 72.7 |
| 'No spam, repeated messages, or unsolicited promotions.' | 17 | 14 | 82.4 | [59.0, 93.8] | 76.9 |
| 'Stay on topic. Only discuss subjects relevant to this group.' | 21 | 16 | 76.2 | [54.9, 89.4] | 76.2 |
| 'Rules:\n- No insults, slurs, or harassment.\n- No self-promotion or external links.\n- Keep discussions relevant to machine learning.\n- No political or religious debates.' | 23 | 13 | 56.5 | [36.8, 74.4] | 58.3 |
| 'No self-promotion or sharing personal links without admin approval.' | 19 | 12 | 63.2 | [41.0, 80.9] | 58.8 |
| 'No discrimination based on race, religion, gender, nationality, or sexuality.' | 19 | 15 | 78.9 | [56.7, 91.5] | 75.0 |
| 'Treat every member with respect. Harassment and bullying are strictly forbidden.' | 17 | 15 | 88.2 | [65.7, 96.7] | 87.5 |
| '1. No hate speech or personal attacks.\n2. No spam or repeated messages.\n3. Stay on topic - this is a Python programming group.\n4. English only.' | 19 | 11 | 57.9 | [36.3, 76.9] | 55.6 |

*Pass against Table 3 of the manuscript.*


## 1.4 Homogeneity test across rule sets
Pearson chi-square test: chi2=20.583, df=14, p=1.128e-01
Expected cells < 5: 12 (40.00%)
Minimum expected cell: 3.50
Permutation test p-value (20,000 resamples): 0.11075

*Since p > 0.05, we fail to reject homogeneity.*

## 1.5 Per-rule paired comparison, generic vs organizational rules

| Rule | n | Gen Acc (%) | Org Acc (%) | Delta (pp) | b (org right, gen wrong) | c (org wrong, gen right) | p-value (McNemar) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 'No explicit, violent, or graphic content.' | 16 | 62.5 | 93.8 | +31.2 | 5 | 0 | 0.062 |
| "Community guidelines:\n1. Zero tolerance for hate speech... | 20 | 55.0 | 85.0 | +30.0 | 6 | 0 | 0.031 |
| 'Group Guidelines:\n  Respect all members at all times... | 21 | 57.1 | 81.0 | +23.8 | 6 | 1 | 0.125 |
| 'Keep all messages respectful. Insults and name-calling are... | 26 | 69.2 | 92.3 | +23.1 | 6 | 0 | 0.031 |
| 'Stay on topic. Only discuss subjects relevant to this group... | 21 | 66.7 | 76.2 | +9.5 | 4 | 2 | 0.688 |
| 'No discrimination based on race, religion, gender... | 19 | 73.7 | 78.9 | +5.3 | 3 | 2 | 1.000 |
| 'No hate speech, slurs, or personal attacks of any kind.' | 19 | 63.2 | 68.4 | +5.3 | 2 | 1 | 1.000 |
| 'Business group rules:\n- Professional language only... | 32 | 71.9 | 75.0 | +3.1 | 4 | 3 | 1.000 |
| 'English only - no messages in other languages.' | 15 | 80.0 | 80.0 | +0.0 | 2 | 2 | 1.000 |
| 'No spam, repeated messages, or unsolicited promotions.' | 17 | 82.4 | 82.4 | +0.0 | 1 | 1 | 1.000 |
| 'Rules:\n- No insults, slurs, or harassment... | 23 | 56.5 | 56.5 | +0.0 | 3 | 3 | 1.000 |
| 'No self-promotion or sharing personal links without admin... | 19 | 63.2 | 63.2 | +0.0 | 3 | 3 | 1.000 |
| 'Treat every member with respect. Harassment and bullying... | 17 | 88.2 | 88.2 | +0.0 | 1 | 1 | 1.000 |
| '1. No hate speech or personal attacks.\n2. No spam... | 19 | 57.9 | 57.9 | +0.0 | 2 | 2 | 1.000 |
| 'Study group rules:\n1. No insults or aggressive language... | 16 | 87.5 | 75.0 | -12.5 | 0 | 2 | 0.500 |

Rule sets improved: 8, worsened: 1, tied: 6
Sign test p-value: 0.039 (excluded 6 ties)
Median delta: 3.1pp, Range: [-12.5pp, 31.2pp]


## 1.6 Latency check
generic_safety: mean=436, median=435, min=302, max=584
org_moderate: mean=470, median=470, min=341, max=591
org_strict: mean=484, median=485, min=349, max=647
org_relaxed: mean=455, median=453, min=302, max=648

*Pass against Table 6* (Batch size used: 10, it is fixed by the analysis script constant)

## 1.7 Deterministic pre-filter check
- Unique injection prompts: 40
- Unique benign prompts: 40
- Prompts caught by filter (TP): 16
- False positives (FP): 8
- Number of unique prompts (actually 10 injection, 10 benign, each repeated 4 times = 40). Caught 4 of 10 injection and 2 of 10 benign. Confirm.
