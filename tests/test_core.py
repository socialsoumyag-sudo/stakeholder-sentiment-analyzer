"""
Unit tests for deterministic logic — no API calls required.
Run with: python -m pytest tests/ -v
(or: python tests/test_core.py  to run without pytest)

These test the parts of the system that don't depend on the LLM's
non-determinism: data integrity, payload construction, JSON validation,
and eval scoring math. The LLM-calling agents themselves are tested
via evals/eval_classifier.py (which requires an API key) rather than
here, since asserting exact LLM outputs in unit tests is brittle.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data.synthetic_reports import to_dicts, REPORTS
from agents.synthesis_agent import _build_input_payload
from agents.risk_classifier import RISK_CATEGORIES


def test_synthetic_data_has_all_required_fields():
    for s in to_dicts():
        for field in ("stakeholder", "role", "week", "topic", "text"):
            assert field in s and s[field], f"Missing/empty '{field}' in statement: {s}"
    print("✅ test_synthetic_data_has_all_required_fields")


def test_synthetic_data_covers_all_risk_categories():
    tags_present = {s.ground_truth_tag for s in REPORTS if s.ground_truth_tag}
    expected = set(RISK_CATEGORIES) - {"none"}
    missing = expected - tags_present
    assert not missing, f"Eval set is missing coverage for categories: {missing}"
    print("✅ test_synthetic_data_covers_all_risk_categories")


def test_synthetic_data_includes_clean_statements():
    """A good eval set must include statements with NO risk pattern,
    otherwise the classifier is never tested for false positives."""
    clean = [s for s in REPORTS if s.ground_truth_tag is None]
    assert len(clean) >= 2, "Eval set should include at least 2 clean/neutral statements"
    print("✅ test_synthetic_data_includes_clean_statements")


def test_build_input_payload_skips_errors():
    classified = [
        {"week": "Week 1", "stakeholder": "A", "role": "Lead", "topic": "X",
         "text": "All good", "category": "none", "confidence": 0.9},
        {"week": "Week 1", "stakeholder": "B", "role": "Lead", "topic": "Y",
         "text": "Broken call", "category": "ERROR", "confidence": 0.0},
    ]
    payload = _build_input_payload(classified)
    assert "All good" in payload
    assert "Broken call" not in payload, "Payload builder must skip ERROR-tagged statements"
    print("✅ test_build_input_payload_skips_errors")


def test_build_input_payload_includes_confidence_and_tag():
    classified = [
        {"week": "Week 2", "stakeholder": "A", "role": "Lead", "topic": "X",
         "text": "Should be fine", "category": "hedging", "confidence": 0.85},
    ]
    payload = _build_input_payload(classified)
    assert "hedging" in payload
    assert "0.85" in payload
    print("✅ test_build_input_payload_includes_confidence_and_tag")


def test_risk_categories_are_well_formed():
    assert "none" in RISK_CATEGORIES, "Must have a 'none'/clean category to avoid false-positive bias"
    assert len(RISK_CATEGORIES) == len(set(RISK_CATEGORIES)), "No duplicate categories"
    print("✅ test_risk_categories_are_well_formed")


def _run_all():
    tests = [
        test_synthetic_data_has_all_required_fields,
        test_synthetic_data_covers_all_risk_categories,
        test_synthetic_data_includes_clean_statements,
        test_build_input_payload_skips_errors,
        test_build_input_payload_includes_confidence_and_tag,
        test_risk_categories_are_well_formed,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed += 1
            print(f"❌ {t.__name__} FAILED: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} tests passed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    _run_all()
