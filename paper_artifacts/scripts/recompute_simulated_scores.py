"""
Read-only verification script.
Recomputes the simulated (proxy) condition scores from run_full_benchmark_and_significance.py
on the same predictions.csv, to confirm what numbers that script would produce.
Does NOT modify any existing file.
"""
import csv
import re
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PREDICTIONS_CSV = PROJECT_ROOT / "Fine_Tune" / "Results" / "PI3" / "predictions.csv"

POSITIVE = "FLAGGED"
NEGATIVE = "PASS"

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


def score_org_strict(message, rules):
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
    if (("spam" in rules_l or "promotion" in rules_l or "links" in rules_l)
            and has_any(text, SPAM_TERMS)):
        return POSITIVE
    if (("topic" in rules_l or "relevant" in rules_l or "only discuss" in rules_l)
            and has_any(text, OFF_TOPIC_TERMS)):
        return POSITIVE
    if "english" in rules_l and re.search(r"[^\x00-\x7f]", text):
        return POSITIVE
    if (("professional" in rules_l or "profanity" in rules_l)
            and has_any(text, {"lol", "yaar", "lmao", "wtf", "omg"})):
        return POSITIVE
    if has_any(text, {"grow up", "are you serious", "ridiculous", "nonsense", "whatever"}):
        return POSITIVE
    return NEGATIVE


def score_org_moderate(message, rules):
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
    if (("spam" in rules_l or "promotion" in rules_l or "links" in rules_l)
            and has_any(text, SPAM_TERMS)):
        return POSITIVE
    if (("topic" in rules_l or "relevant" in rules_l or "only discuss" in rules_l)
            and has_any(text, OFF_TOPIC_TERMS)):
        return POSITIVE
    if "english" in rules_l and re.search(r"[^\x00-\x7f]", text):
        return POSITIVE
    return NEGATIVE


def score_org_relaxed(message, rules):
    text = message.lower()
    severe = {"fuck", "shit", "faggot", "kill", "threat", "violent", "porn",
              "nsfw", "doxxing", "password", "pirated"}
    if has_any(text, severe):
        return POSITIVE
    if has_any(text, {"hate speech", "death threat", "bomb"}):
        return POSITIVE
    return NEGATIVE


def score_generic_safety(message, rules):
    text = message.lower()
    if has_any(text, {"kill", "threat", "violent", "bomb", "attack", "murder"}):
        return POSITIVE
    if has_any(text, {"fuck", "shit", "faggot", "bitch", "whore", "asshole"}):
        return POSITIVE
    if has_any(text, NSFW_TERMS):
        return POSITIVE
    if has_any(text, {"doxxing", "dox", "password", "credential"}):
        return POSITIVE
    return NEGATIVE


CONDITIONS = {
    "org_strict": score_org_strict,
    "org_moderate": score_org_moderate,
    "org_relaxed": score_org_relaxed,
    "generic_safety": score_generic_safety,
}


def main():
    with PREDICTIONS_CSV.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    print(f"Loaded {len(rows)} rows from {PREDICTIONS_CSV}")
    print()
    print("--- Scores produced by run_full_benchmark_and_significance.py logic ---")
    print(f"{'Condition':<20} {'Acc':>7} {'Prec':>7} {'Recall':>7} {'F1':>7} "
          f"{'TP':>5} {'FP':>5} {'FN':>5} {'TN':>5}")
    print("-" * 75)

    for cond_name, scorer in CONDITIONS.items():
        counts = Counter()
        for row in rows:
            pred = scorer(row["message"], row["rules"])
            truth = row["label"].strip().upper()
            if truth == POSITIVE and pred == POSITIVE:
                counts["tp"] += 1
            elif truth == NEGATIVE and pred == POSITIVE:
                counts["fp"] += 1
            elif truth == POSITIVE and pred == NEGATIVE:
                counts["fn"] += 1
            else:
                counts["tn"] += 1

        n = len(rows)
        tp, fp, fn, tn = counts["tp"], counts["fp"], counts["fn"], counts["tn"]
        acc = safe_div(tp + tn, n)
        prec = safe_div(tp, tp + fp)
        rec = safe_div(tp, tp + fn)
        f1 = safe_div(2 * prec * rec, prec + rec)
        print(f"{cond_name:<20} {acc:>7.4f} {prec:>7.4f} {rec:>7.4f} {f1:>7.4f} "
              f"{tp:>5} {fp:>5} {fn:>5} {tn:>5}")


if __name__ == "__main__":
    main()
