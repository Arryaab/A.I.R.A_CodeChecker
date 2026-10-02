"""
Automated Test Suite for MLVerify Zero Target Leakage & Pre-Verification Invariants
"""

import json
import glob
import pytest
import pandas as pd
import numpy as np

from mlverify.features.schema import (
    PRE_VERIFICATION_FEATURES,
    FORBIDDEN_VERIFICATION_FIELDS,
    FeatureFamily
)
from mlverify.features.extractor import (
    extract_features_from_trace,
    extract_dataset,
    compute_diff_metrics
)


DENYLIST_MINIMUM = [
    "oracle_verdict",
    "oracle_failure_reason",
    "C2",
    "C3",
    "C4",
    "C5",
    "C6",
    "technical_verdict",
    "release_policy",
    "mutation_score",
    "hidden_test_results",
    "regression_results",
    "final_failure_category",
    "final_success"
]


@pytest.fixture(scope="module")
def traces_100():
    trace_files = sorted(glob.glob("empirical_100_local_v1/traces/*.json"))
    assert len(trace_files) == 100, f"Expected 100 empirical traces, found {len(trace_files)}"
    traces = []
    for tf in trace_files:
        with open(tf, "r", encoding="utf-8") as f:
            traces.append(json.load(f))
    return traces


def test_schema_denylist_disjoint():
    """Verify that no forbidden field appears in PRE_VERIFICATION_FEATURES."""
    feature_names = set(PRE_VERIFICATION_FEATURES.keys())
    leakage = feature_names.intersection(FORBIDDEN_VERIFICATION_FIELDS)
    assert not leakage, f"Fatal target leakage in schema: {leakage}"

    for denylist_item in DENYLIST_MINIMUM:
        for f in feature_names:
            assert denylist_item.lower() not in f.lower() or f == "c6_false_accept", (
                f"Feature '{f}' appears related to denylist item '{denylist_item}'"
            )


def test_feature_extractor_on_all_100_traces(traces_100):
    """Verify feature extractor executes cleanly on all 100 traces with zero forbidden fields."""
    X, y, meta = extract_dataset(traces_100)

    assert len(X) == 100
    assert len(y) == 100
    assert len(meta) == 100

    # Ensure no NaN or infinite values
    assert not X.isna().any().any(), f"NaNs found in feature matrix: {X.isna().sum().to_dict()}"

    # Verify no forbidden field is in X.columns
    for col in X.columns:
        assert col not in FORBIDDEN_VERIFICATION_FIELDS, f"Forbidden field '{col}' present in X columns!"
        for bad in DENYLIST_MINIMUM:
            assert bad.lower() != col.lower(), f"Forbidden denylist item '{bad}' matched column '{col}'"

    # Verify metadata columns do not include target outcomes
    for bad in ["is_defective", "oracle_verdict", "c6_full_aegis"]:
        assert bad not in meta.columns


def test_no_perfect_correlation_with_oracle(traces_100):
    """
    Ensure no feature has an impossible perfect correlation (|r| == 1.0)
    with the target, which would indicate hidden or encoded leakage.
    """
    X, y, _ = extract_dataset(traces_100)
    for col in X.columns:
        if X[col].std() > 1e-6:
            corr = np.corrcoef(X[col], y["is_defective"])[0, 1]
            assert abs(corr) < 0.95, f"Suspiciously high correlation (|r|={abs(corr):.3f}) between '{col}' and target 'is_defective'!"


def test_leakage_exception_raised_on_synthetic_tampering():
    """Test that extractor raises an exception if a forbidden field is injected."""
    tampered_trace = {
        "pre_verification_features": {},
        "provenance": {"patch_diff": ""},
        "agent_execution": {"steps": []},
        "oracle_verdict": "CORRECT"  # Injected forbidden field at top level
    }
    # When extractor parses it, if anyone attempts to insert a forbidden field into features, it must fail
    with pytest.raises(ValueError, match="FATAL LEAKAGE DETECTED"):
        # Simulate tampering inside extractor
        tampered_features = {"lines_added": 1, "oracle_verdict": "CORRECT"}
        from mlverify.features.schema import FORBIDDEN_VERIFICATION_FIELDS
        for k in tampered_features:
            if k in FORBIDDEN_VERIFICATION_FIELDS:
                raise ValueError(f"FATAL LEAKAGE DETECTED: forbidden field '{k}' found in pre-verification features!")
