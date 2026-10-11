import pandas as pd
import numpy as np
import json
import math

file_path = 'paper_artifacts/benchmark_raw_1200.csv'
df = pd.read_csv(file_path)

out = []
def p(s):
    print(s)
    out.append(s)

def calc_metrics(y_true, y_pred):
    tp = np.sum((y_true == 1) & (y_pred == 1))
    fp = np.sum((y_true == 0) & (y_pred == 1))
    tn = np.sum((y_true == 0) & (y_pred == 0))
    fn = np.sum((y_true == 1) & (y_pred == 0))
    
    acc = (tp + tn) / (tp + fp + tn + fn)
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (prec * rec) / (prec + rec) if (prec + rec) > 0 else 0
    
    num = (tp * tn) - (fp * fn)
    den = np.sqrt(float(tp + fp) * float(tp + fn) * float(tn + fp) * float(tn + fn))
    mcc = num / den if den != 0 else 0
    
    return acc * 100, prec * 100, rec * 100, f1 * 100, mcc, tn, fp, fn, tp

def wilson_ci(correct, n, z=1.95996):
    p_hat = correct / n
    denominator = 1 + z**2/n
    centre = p_hat + z**2 / (2*n)
    spread = z * np.sqrt((p_hat*(1 - p_hat) + z**2 / (4*n)) / n)
    return (centre - spread) / denominator, (centre + spread) / denominator

def binom_test(k, n, p_val=0.5):
    # exact two-sided binomial test
    prob = sum(math.comb(n, i) * (p_val**i) * ((1-p_val)**(n-i)) for i in range(n+1))
    # more accurately, we only sum probabilities <= P(X=k)
    p_k = math.comb(n, k) * (p_val**k) * ((1-p_val)**(n-k))
    p_total = 0
    for i in range(n+1):
        p_i = math.comb(n, i) * (p_val**i) * ((1-p_val)**(n-i))
        if p_i <= p_k * (1 + 1e-7):
            p_total += p_i
    return min(1.0, p_total)

p("## 1.1 Locate and describe the data")
p(f"File path: {file_path}")
p(f"Format: CSV")
p(f"Row count: {len(df)}")
p(f"Column names: {list(df.columns)}")

p("\nDistinct values of the condition column:")
cond_counts = df['condition'].value_counts()
for k, v in cond_counts.items():
    p(f"  {k}: {v}")

p("\nDistinct values of the rule-set column:")
rule_counts = df['rules'].value_counts()
for k, v in rule_counts.items():
    p(f"  {repr(k)}: {v}")

p("\nChecks:")
p(f"Total rows is 1,200: {len(df) == 1200} ({len(df)})")
distinct_messages = df['message'].nunique()
p(f"Distinct messages is 300: {distinct_messages == 300} ({distinct_messages})")
conds_cover = (df.groupby('condition')['message'].nunique() == 300).all() and len(df['condition'].unique()) == 4
p(f"Four conditions, each covering all 300 messages: {conds_cover} (Distinct conditions: {len(df['condition'].unique())}, each covers 300 messages: {df.groupby('condition')['message'].nunique().to_dict()})")
p(f"Fifteen distinct rule sets: {len(df['rules'].unique()) == 15} ({len(df['rules'].unique())})")

msg_df = df[['message', 'label']].drop_duplicates()
label_counts = msg_df['label'].value_counts()
p(f"Label balance is 150 allowable and 150 violating: {label_counts.get('PASS', 0) == 150 and label_counts.get('FLAGGED', 0) == 150} (PASS: {label_counts.get('PASS', 0)}, FLAGGED: {label_counts.get('FLAGGED', 0)})")


p("\n## 1.2 Reproduce the published headline figures")
published_figures = {
    'generic_safety': {'Acc': 68.3, 'Prec': 83.1, 'Rec': 46.0, 'F1': 59.2, 'MCC': 0.410, 'TP': 69, 'FP': 14, 'TN': 136, 'FN': 81},
    'org_moderate': {'Acc': 76.7, 'Prec': 76.7, 'Rec': 76.7, 'F1': 76.7, 'MCC': 0.533, 'TP': 115, 'FP': 35, 'TN': 115, 'FN': 35},
    'org_strict': {'Acc': 77.0, 'Prec': 76.8, 'Rec': 77.3, 'F1': 77.1, 'MCC': 0.540},
    'org_relaxed': {'Acc': 65.7, 'Prec': 89.8, 'Rec': 35.3, 'F1': 50.7, 'MCC': 0.394}
}
conditions_mapping = {'generic_safety': 'generic_safety', 'org_moderate': 'org_moderate', 'org_strict': 'org_strict', 'org_relaxed': 'org_relaxed'}

for cond_name, cond_val in conditions_mapping.items():
    sub = df[df['condition'] == cond_val]
    y_true = (sub['label'] == 'FLAGGED').astype(int).values
    y_pred = (sub['prediction'] == 'FLAGGED').astype(int).values
    
    acc, prec, rec, f1, mcc, tn, fp, fn, tp = calc_metrics(y_true, y_pred)
    
    p(f"\nCondition: {cond_name}")
    p(f"  Acc: {acc:.1f}, Prec: {prec:.1f}, Rec: {rec:.1f}, F1: {f1:.1f}, MCC: {mcc:.3f}")
    p(f"  TP: {tp}, FP: {fp}, TN: {tn}, FN: {fn}")
    
    pub = published_figures[cond_name]
    pass_acc = abs(acc - pub['Acc']) < 0.1
    pass_prec = abs(prec - pub['Prec']) < 0.1
    pass_rec = abs(rec - pub['Rec']) < 0.1
    pass_f1 = abs(f1 - pub['F1']) < 0.1
    pass_mcc = abs(mcc - pub['MCC']) < 0.002
    
    status = "Pass" if all([pass_acc, pass_prec, pass_rec, pass_f1, pass_mcc]) else "Fail"
    p(f"  Published match ({cond_name}): {status}")
    if not pass_acc: p(f"    Discrepancy Acc: computed {acc:.1f}, published {pub['Acc']}")
    if not pass_prec: p(f"    Discrepancy Prec: computed {prec:.1f}, published {pub['Prec']}")
    if not pass_rec: p(f"    Discrepancy Rec: computed {rec:.1f}, published {pub['Rec']}")
    if not pass_f1: p(f"    Discrepancy F1: computed {f1:.1f}, published {pub['F1']}")
    if not pass_mcc: p(f"    Discrepancy MCC: computed {mcc:.3f}, published {pub['MCC']}")
    if 'TP' in pub:
        pass_cm = (tp == pub['TP'] and fp == pub['FP'] and tn == pub['TN'] and fn == pub['FN'])
        p(f"  Confusion matrix match: {'Pass' if pass_cm else 'Fail'}")
        if not pass_cm:
            p(f"    Discrepancy CM: computed TP={tp} FP={fp} TN={tn} FN={fn}, published TP={pub['TP']} FP={pub['FP']} TN={pub['TN']} FN={pub['FN']}")

p("\n## 1.3 Per-rule-set table, organizational rules at moderate sensitivity")
sub = df[df['condition'] == 'org_moderate']
rulesets = sub['rules'].unique()
p("Rule Set | n | Correct | Acc (%) | 95% CI (%) | F1 (%)")
for r in rulesets:
    r_sub = sub[sub['rules'] == r]
    n = len(r_sub)
    correct = r_sub['correct'].sum()
    acc = correct / n * 100
    ci_low, ci_high = wilson_ci(correct, n)
    
    y_true = (r_sub['label'] == 'FLAGGED').astype(int).values
    y_pred = (r_sub['prediction'] == 'FLAGGED').astype(int).values
    _, _, _, f1, _, _, _, _, _ = calc_metrics(y_true, y_pred)
    
    r_name = repr(r)
    p(f"{r_name} | {n} | {correct} | {acc:.1f} | [{ci_low*100:.1f}, {ci_high*100:.1f}] | {f1:.1f}")

p("\n## 1.4 Homogeneity test across rule sets")
contingency = []
for r in rulesets:
    r_sub = sub[sub['rules'] == r]
    correct = r_sub['correct'].sum()
    incorrect = len(r_sub) - correct
    contingency.append([correct, incorrect])

contingency = np.array(contingency)
row_sums = contingency.sum(axis=1)
col_sums = contingency.sum(axis=0)
total = contingency.sum()
expected = np.outer(row_sums, col_sums) / total

import scipy.stats as stats
chi2, p_val, dof, _ = stats.chi2_contingency(contingency, correction=False)
p(f"Pearson chi-square test: chi2={chi2:.3f}, df={dof}, p={p_val:.3e}")

expected_below_5 = np.sum(expected < 5)
total_cells = expected.size
p(f"Expected cells < 5: {expected_below_5} ({expected_below_5/total_cells:.2%})")
p(f"Minimum expected cell: {np.min(expected):.2f}")

np.random.seed(0)
n_resamples = 20000
pool = np.concatenate([np.ones(row_sums[i]) if j==0 else np.zeros(row_sums[i]) for i in range(len(row_sums)) for j in range(2)]) 
# Wait, this pool logic is wrong. The pool is all correct and incorrect across all groups.
pool = np.concatenate([np.ones(col_sums[0]), np.zeros(col_sums[1])])

chi2_perms = []
for _ in range(n_resamples):
    np.random.shuffle(pool)
    start = 0
    sim_table = []
    for n in row_sums:
        c = pool[start:start+n].sum()
        sim_table.append([c, n - c])
        start += n
    
    sim_table = np.array(sim_table)
    sim_col_sums = sim_table.sum(axis=0)
    expected_sim = np.outer(row_sums, sim_col_sums) / sim_table.sum()
    with np.errstate(divide='ignore', invalid='ignore'):
        chi2_sim = np.sum((sim_table - expected_sim)**2 / expected_sim)
    chi2_perms.append(chi2_sim)

p_perm = np.sum(np.array(chi2_perms) >= chi2) / n_resamples
p(f"Permutation test p-value (20,000 resamples): {p_perm:.5f}")

p("\n## 1.5 Per-rule paired comparison, generic vs organizational rules")
generic_sub = df[df['condition'] == 'generic_safety']

results_15 = []
improved = 0
worsened = 0
tied = 0

for r in rulesets:
    org_r_sub = sub[sub['rules'] == r].sort_values('message')
    gen_r_sub = generic_sub[generic_sub['message'].isin(org_r_sub['message'])].sort_values('message')
    
    n = len(org_r_sub)
    gen_correct = gen_r_sub['correct'].values
    org_correct = org_r_sub['correct'].values
    
    acc_gen = gen_correct.mean() * 100
    acc_org = org_correct.mean() * 100
    delta = acc_org - acc_gen
    
    b = np.sum((org_correct == True) & (gen_correct == False))
    c = np.sum((org_correct == False) & (gen_correct == True))
    
    if delta > 0: improved += 1
    elif delta < 0: worsened += 1
    else: tied += 1
    
    if b + c == 0:
        p_mcnemar = 1.0
    else:
        p_mcnemar = binom_test(b, b + c, 0.5)
        
    results_15.append({
        'rule': repr(r),
        'n': n,
        'acc_gen': acc_gen,
        'acc_org': acc_org,
        'delta': delta,
        'b': b,
        'c': c,
        'p_mcnemar': p_mcnemar
    })

results_15.sort(key=lambda x: x['delta'], reverse=True)

for res in results_15:
    p(f"Rule: {res['rule'][:60]}... | n: {res['n']} | Gen Acc: {res['acc_gen']:.1f}% | Org Acc: {res['acc_org']:.1f}% | Delta: {res['delta']:+.1f}pp | b={res['b']}, c={res['c']} | p={res['p_mcnemar']:.3f}")

p(f"\nRule sets improved: {improved}, worsened: {worsened}, tied: {tied}")
p_sign = binom_test(improved, improved + worsened, 0.5) if (improved + worsened) > 0 else 1.0
p(f"Sign test p-value: {p_sign:.3f} (excluded {tied} ties)")
deltas = [x['delta'] for x in results_15]
p(f"Median delta: {np.median(deltas):.1f}pp, Range: [{np.min(deltas):.1f}pp, {np.max(deltas):.1f}pp]")

p("\n## 1.6 Latency check")
for cond_name, cond_val in conditions_mapping.items():
    c_sub = df[df['condition'] == cond_val]['batch_latency_ms']
    p(f"{cond_name}: mean={c_sub.mean():.0f}, median={c_sub.median():.0f}, min={c_sub.min():.0f}, max={c_sub.max():.0f}")

p("\n## 1.7 Deterministic pre-filter check")
try:
    with open('paper_artifacts/injection_filter_results.json', 'r') as f:
        pre_filters = json.load(f)
    p(f"\nPre-filter results loaded from paper_artifacts/injection_filter_results.json")
    p(json.dumps(pre_filters, indent=2))
except Exception as e:
    p(f"Could not load pre-filter results: {e}")

with open('output_part1.txt', 'w') as f:
    f.write('\n'.join(out))
