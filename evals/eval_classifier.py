"""
Eval Harness — Risk Classifier
-------------------------------
Scores the classifier's predictions against the ground-truth tags baked
into data/synthetic_reports.py. This is what separates "I prompted an LLM
and it looked right" from "I measured whether it's actually right."

Usage:
    export ANTHROPIC_API_KEY=sk-...
    python evals/eval_classifier.py

Outputs per-category precision/recall and an overall accuracy score,
plus a list of specific misclassifications for manual review.
"""

import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data.synthetic_reports import to_dicts
from agents.risk_classifier import classify_all


def normalize_tag(tag):
    """Ground truth uses None for 'clean' statements; classifier returns 'none'."""
    return tag if tag is not None else "none"


def run_eval(verbose: bool = True) -> dict:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise EnvironmentError("ANTHROPIC_API_KEY not set. See .env.example.")

    statements = to_dicts()
    results = classify_all(statements)

    total = 0
    correct = 0
    errors = 0
    per_category = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    misclassifications = []

    for r in results:
        if r.error:
            errors += 1
            continue

        total += 1
        truth = normalize_tag(r.ground_truth_tag)
        pred = r.category

        if truth == pred:
            correct += 1
            per_category[truth]["tp"] += 1
        else:
            per_category[pred]["fp"] += 1
            per_category[truth]["fn"] += 1
            misclassifications.append({
                "text": r.text,
                "predicted": pred,
                "expected": truth,
                "confidence": r.confidence,
            })

    accuracy = correct / total if total else 0.0

    report = {
        "total_statements": len(statements),
        "successfully_classified": total,
        "classifier_errors": errors,
        "accuracy": round(accuracy, 3),
        "per_category": {},
        "misclassifications": misclassifications,
    }

    for cat, counts in per_category.items():
        tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        report["per_category"][cat] = {
            "precision": round(precision, 3) if precision is not None else None,
            "recall": round(recall, 3) if recall is not None else None,
            "support": tp + fn,
        }

    if verbose:
        print(f"\n{'='*50}\nEVAL RESULTS\n{'='*50}")
        print(f"Accuracy: {accuracy:.1%} ({correct}/{total} correct, {errors} errors)\n")
        print(f"{'Category':22s} {'Precision':>10s} {'Recall':>8s} {'Support':>8s}")
        for cat, m in report["per_category"].items():
            p = f"{m['precision']:.2f}" if m['precision'] is not None else "n/a"
            r = f"{m['recall']:.2f}" if m['recall'] is not None else "n/a"
            print(f"{cat:22s} {p:>10s} {r:>8s} {m['support']:>8d}")
        if misclassifications:
            print(f"\n{len(misclassifications)} misclassification(s):")
            for m in misclassifications:
                print(f"  ❌ expected={m['expected']:22s} got={m['predicted']:22s} — {m['text'][:60]}")

    out_path = os.path.join(os.path.dirname(__file__), "eval_report.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)

    return report


if __name__ == "__main__":
    run_eval()
