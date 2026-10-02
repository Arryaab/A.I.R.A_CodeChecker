"""
Test Suite: MLVerify Temporal Boundary & Pre-Verification Target Semantics (P0 & P1)
Verifies that post-agent outcomes cannot be marked as pre-verification predictive targets,
and verifies temporal cutoff invariants at t_prediction.
"""

import json
import glob
import pytest
from mlverify.models.pipeline import MLVerifyMultiHeadPredictor
from mlverify.features.schema import FORBIDDEN_VERIFICATION_FIELDS


@pytest.fixture(scope="module")
def sample_trace():
    trace_files = sorted(glob.glob("empirical_100_local_v1/traces/*.json"))
    assert len(trace_files) > 0
    with open(trace_files[0], "r", encoding="utf-8") as f:
        return json.load(f)


def test_post_agent_outcome_cannot_be_pre_verification_predictive_head():
    """
    REQUIRED FAILURE CONDITION:
    A post-agent outcome (e.g., agent_failure, agent_termination, protocol_incomplete)
    CANNOT be classified as a pre_verification_prediction head.
    It must be strictly categorized as post_agent_diagnostic.
    """
    with open("mlverify/models/risk_head_matrix.json", "r", encoding="utf-8") as f:
        matrix = json.load(f)

    for item in matrix:
        if item["head"] == "agent_failure_risk":
            assert item["type"] == "post_agent_diagnostic", (
                f"agent_failure_risk was incorrectly typed as {item['type']}! "
                "It is observable at agent termination and must be post_agent_diagnostic."
            )
            assert item["status"] == "DIAGNOSTIC_ONLY"
            assert item["type"] != "pre_verification_prediction"

        if item["type"] == "pre_verification_prediction":
            assert item["head"] == "defect_risk", (
                f"Unexpected pre_verification_prediction head: {item['head']}. "
                "Only true downstream verification targets like defect_risk are permitted."
            )


def test_predictor_separates_predictive_from_diagnostic_heads(sample_trace):
    """Verify that predictor outputs explicitly label head_type for each risk."""
    predictor = MLVerifyMultiHeadPredictor(random_state=42)
    # Mock minimal fitted state
    predictor.feature_names = ["lines_added"]
    import pandas as pd
    mock_df = pd.DataFrame([[1], [2]], columns=["lines_added"])
    predictor.defect_head.fit(mock_df, [0, 1])
    predictor.agent_diagnostic.fit(mock_df, [0, 1])
    predictor.overfitting_head.fit(mock_df, [0, 1])
    predictor.security_head.fit(mock_df, [0, 1])
    predictor.false_accept_head.fit(mock_df, [0, 1])
    predictor.is_fitted = True

    risks = predictor.predict_risks({"lines_added": 1})

    assert risks["defect_risk"]["head_type"] == "pre_verification_prediction"
    assert risks["defect_risk"]["status"] == "ACTIVE_RESEARCH"

    assert risks["agent_failure_risk"]["head_type"] == "post_agent_diagnostic"
    assert risks["agent_failure_risk"]["status"] == "DIAGNOSTIC_ONLY"
    assert "diagnostic" in risks["agent_failure_risk"]["note"].lower()


def test_temporal_feature_availability_precedes_verification(sample_trace):
    """
    Verify temporal contract:
    Candidate patch and agent steps precede post-verification signals.
    """
    prov_ts = sample_trace.get("provenance", {}).get("timestamp")
    steps = sample_trace.get("agent_execution", {}).get("steps", [])

    assert prov_ts is not None
    assert len(steps) > 0

    # Ensure no post-verification latency or verifier outcome is accessible in provenance
    assert "verification_duration_s" not in sample_trace.get("provenance", {})
    assert "oracle_verdict" not in sample_trace.get("provenance", {})
    assert "C6_full_aegis" not in sample_trace.get("provenance", {})
