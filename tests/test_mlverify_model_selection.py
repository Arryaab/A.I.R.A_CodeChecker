"""
Test Suite: MLVerify Model Selection Protocol (P0 & P1)
Verifies that model selection strictly adheres to the registered selection criterion
and cannot contradict empirical metrics or calibration gates.
"""

import json
import pytest


@pytest.fixture(scope="module")
def model_selection_spec():
    with open("mlverify/models/model_selection.json", "r", encoding="utf-8") as f:
        return json.load(f)


def test_model_selection_matches_registered_criterion(model_selection_spec):
    """
    REQUIRED FAILURE CONDITION:
    Model selection cannot contradict the registered criterion.
    The selected model must pass all gates and achieve the highest primary metric.
    """
    candidates = model_selection_spec["candidate_evaluations"]
    selected = model_selection_spec["selection_result"]["selected_model"]

    # Filter candidates passing both calibration gate and stability gate
    eligible = [
        c for c in candidates
        if c["calibration_gate_passed"] and c["stability_gate_passed"]
    ]
    assert len(eligible) > 0, "No candidate models passed registered gates!"

    # Find candidate with highest PR-AUC among eligible
    best_candidate = max(eligible, key=lambda c: c["pr_auc"])

    assert selected == best_candidate["model"], (
        f"Contradiction in model selection! Registered rule requires selecting "
        f"'{best_candidate['model']}' (PR-AUC: {best_candidate['pr_auc']}), but '{selected}' was selected."
    )


def test_poorly_calibrated_model_cannot_be_selected(model_selection_spec):
    """Verify that a model with high calibration error (ECE > 0.08) is rejected."""
    candidates = {c["model"]: c for c in model_selection_spec["candidate_evaluations"]}

    # Regularized L1 has high PR-AUC (0.9348) but ECE 0.1275 > 0.08
    assert not candidates["regularized_l1"]["calibration_gate_passed"]
    assert model_selection_spec["selection_result"]["selected_model"] != "regularized_l1"


def test_selection_explanation_is_complete(model_selection_spec):
    """Verify that selection rationale contains all required components."""
    rationale = model_selection_spec["selection_result"]["rationale"]
    assert "PR-AUC" in rationale
    assert "calibration" in rationale.lower()
    assert "stability" in rationale.lower()
