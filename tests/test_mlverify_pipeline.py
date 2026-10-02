"""
Unit Test Suite for MLVerify Multi-Head Architecture & Shadow Mode Simulator
"""

import os
import json
import pytest
import pandas as pd
import numpy as np

from mlverify.models.pipeline import MLVerifyMultiHeadPredictor
from mlverify.routing.simulator import ShadowRoutingSimulator
from mlverify.features.schema import PRE_VERIFICATION_FEATURES


@pytest.fixture(scope="module")
def dataset_df():
    df = pd.read_csv("mlverify/dataset/dataset_full.csv")
    assert len(df) == 100
    return df


def test_multi_head_architecture_partitions_supported_and_unsupported(dataset_df):
    """Verify that unsupported heads return NOT_TRAINED with None probability."""
    feature_cols = list(PRE_VERIFICATION_FEATURES.keys())
    predictor = MLVerifyMultiHeadPredictor(random_state=42)
    predictor.fit(dataset_df[feature_cols], dataset_df)

    sample_features = dataset_df.iloc[0][feature_cols].to_dict()
    risks = predictor.predict_risks(sample_features)

    # Predictive head
    assert risks["defect_risk"]["head_type"] == "pre_verification_prediction"
    assert risks["defect_risk"]["status"] == "ACTIVE_RESEARCH"
    assert isinstance(risks["defect_risk"]["probability"], float)
    assert 0.0 <= risks["defect_risk"]["probability"] <= 1.0

    # Diagnostic classifier
    assert risks["agent_failure_risk"]["head_type"] == "post_agent_diagnostic"
    assert risks["agent_failure_risk"]["status"] == "DIAGNOSTIC_ONLY"
    assert isinstance(risks["agent_failure_risk"]["diagnostic_score"], float)

    # Research prototypes
    assert risks["test_overfitting_risk"]["status"] == "DESCRIPTIVE_ONLY"
    assert risks["false_accept_risk"]["status"] == "INSUFFICIENT_DATA"
    assert risks["security_risk"]["status"] == "DESCRIPTIVE_ONLY"

    # Unsupported heads MUST NEVER fabricate probabilities
    assert risks["regression_risk"]["status"] == "NOT_TRAINED"
    assert risks["regression_risk"]["probability"] is None
    assert risks["regression_risk"]["reason"] == "INSUFFICIENT_DATA"

    assert risks["performance_risk"]["status"] == "NOT_TRAINED"
    assert risks["performance_risk"]["probability"] is None
    assert risks["performance_risk"]["reason"] == "INSUFFICIENT_DATA"


def test_model_serialization_and_reproducibility(dataset_df, tmp_path):
    """Verify MLVerify model saves, loads, and produces identical risk predictions."""
    feature_cols = list(PRE_VERIFICATION_FEATURES.keys())
    model = MLVerifyMultiHeadPredictor(random_state=42)
    model.fit(dataset_df[feature_cols], dataset_df)

    save_path = tmp_path / "test_model.pkl"
    model.save(str(save_path))
    assert save_path.exists()

    loaded = MLVerifyMultiHeadPredictor.load(str(save_path))
    sample = dataset_df.iloc[10][feature_cols].to_dict()

    r1 = model.predict_risks(sample)
    r2 = loaded.predict_risks(sample)

    assert r1["defect_risk"]["probability"] == r2["defect_risk"]["probability"]
    assert r1["agent_failure_risk"]["diagnostic_score"] == r2["agent_failure_risk"]["diagnostic_score"]


def test_shadow_routing_simulator_flags_unsafe_escape_increase():
    """Verify simulator detects and flags safety degradation in naive routing."""
    sim = ShadowRoutingSimulator(
        dataset_path="mlverify/dataset/dataset_full.csv",
        traces_dir="empirical_100_local_v1/traces"
    )

    # Fake naive probabilities that route everything to FAST
    fake_probs = np.full(100, 0.1)
    res = sim.simulate_policy(
        name="ALL_FAST",
        description="All fast test",
        threshold_provenance="POST_HOC_EXPLORATORY",
        routing_fn=lambda p, r: "FAST",
        oof_probs=fake_probs
    )

    assert res["safety_counterfactual"]["bad_patch_escapes"] == 11
    assert "UNSAFE_ESCAPE_INCREASE" in res["safety_counterfactual"]["safety_verdict"]
