"""
Test Suite: MLVerify Threshold Provenance & Validation Design (P0 & P1)
Verifies that post-hoc exploratory thresholds cannot be labeled pre-registered.
"""

import json
import pytest


@pytest.fixture(scope="module")
def routing_sim():
    with open("mlverify/routing/routing_simulation.json", "r", encoding="utf-8") as f:
        return json.load(f)


def test_post_hoc_thresholds_cannot_be_labeled_preregistered(routing_sim):
    """
    REQUIRED FAILURE CONDITION:
    Post-hoc thresholds determined after inspecting 100-run distribution
    CANNOT be labeled PRE_REGISTERED.
    They must be explicitly labeled POST_HOC_EXPLORATORY.
    """
    dynamic_policies = [
        p for p in routing_sim["policies"]
        if p["policy_name"] in ("NAIVE_SPEED_FIRST_ROUTING", "CONSERVATIVE_SAFETY_CONSTRAINED_ROUTING")
    ]
    assert len(dynamic_policies) == 2

    for policy in dynamic_policies:
        prov = policy["threshold_provenance"]
        assert prov == "POST_HOC_EXPLORATORY", (
            f"Policy '{policy['policy_name']}' incorrectly has threshold_provenance '{prov}'. "
            "Thresholds optimized on the evaluation dataset cannot be labeled PRE_REGISTERED!"
        )
        assert "PRE_REGISTERED" not in prov


def test_static_baseline_has_distinct_provenance(routing_sim):
    """Verify that static Aegis baseline is cleanly differentiated from exploratory routing."""
    baseline = next(p for p in routing_sim["policies"] if p["policy_name"] == "AEGIS_BASELINE_STATIC_DEEP")
    assert "PRE_REGISTERED" in baseline["threshold_provenance"]


def test_future_production_routing_requires_nested_grouped_design():
    """Verify documentation and schemas mandate nested validation for future threshold tuning."""
    with open("mlverify/routing/routing_simulation.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    note = data.get("threshold_methodology_note", "")
    assert "nested grouped cross-validation" in note.lower()
