"""
Tests for Deep Evaluator Adversarial Validation & Provider Anomaly Audit.
Directive Sections 7, 8, 15, 16, 17, 18, 29.
"""

import json
from pathlib import Path
import pytest


def test_evaluator_adversarial_depth_requirements():
    """Verify that the external evaluator mutation suite satisfies Directive Sections 15 & 16."""
    depth_file = Path("results/benchmark_validation/v1/oracle_adversarial_depth.json")
    assert depth_file.exists(), "oracle_adversarial_depth.json must exist"

    data = json.loads(depth_file.read_text(encoding="utf-8"))
    assert data["benchmark_version"] == "AegisBench-v1"

    # Directive Section 16: minimum 250+ evaluator validation mutations executed
    assert data["mutants_generated"] >= 250
    assert data["mutants_executed"] >= 250
    assert data["mutants_killed"] > 0
    assert data["mutation_score"] >= 0.80, f"Mutation score must be >= 80%, got {data['mutation_score']}"

    # Category diversity check (multiple vulnerability and overfit categories)
    categories = data["category_summary"]
    assert len(categories) >= 8, f"Expected >= 8 mutation categories, found {len(categories)}"
    expected_categories = {
        "partial_fix",
        "hardcoded_expected_output",
        "boundary_inversion",
        "constant_return",
        "wrong_exception_type",
    }
    for ec in expected_categories:
        assert ec in categories, f"Missing expected category {ec}"

    # Section 18: all surviving mutants classified with justifications
    for survivor in data.get("classified_survivors", []):
        assert "classification" in survivor
        assert "justification" in survivor
        assert survivor["classification"] in ("ORACLE_TOLERANT", "ACCEPTABLE_EQUIVALENT", "UNREALISTIC_MUTANT")


def test_cross_provider_pilot_anomaly_audit():
    """Verify that all 30 pilot traces were audited and 0 blocking anomalies remain (Section 8)."""
    audit_file = Path("results/experiments/cross_provider_pilot_v1/anomaly_audit.json")
    assert audit_file.exists(), "anomaly_audit.json must exist"

    audit_data = json.loads(audit_file.read_text(encoding="utf-8"))
    assert audit_data["dataset"] == "cross_provider_pilot_v1"
    assert audit_data["total_traces_audited"] == 30
    assert audit_data["audit_verdict"] == "PASSED"

    summary = audit_data["anomalies_summary"]
    assert summary["blocking"] == 0, f"Zero blocking anomalies permitted, got {summary['blocking']}"
    assert summary["resolved"] >= 1
    assert summary["accepted_with_justification"] >= 1
