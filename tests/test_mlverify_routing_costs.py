"""
Test Suite: MLVerify Routing Cost Accounting & Separation Invariants (P0 & P1)
Verifies that routing cost cannot be reported when tier-specific cost evidence is unavailable,
and verifies strict separation of safety counterfactuals from cost counterfactuals.
"""

import json
import pytest


@pytest.fixture(scope="module")
def routing_sim():
    with open("mlverify/routing/routing_simulation.json", "r", encoding="utf-8") as f:
        return json.load(f)


def test_workload_reduction_not_estimable_when_tier_timings_unavailable(routing_sim):
    """
    REQUIRED FAILURE CONDITION:
    Routing cost / workload reduction cannot be reported as an empirical percentage
    when tier-specific cost evidence (C2, C3, C4, C5, C6 durations) is unavailable.
    It MUST be reported as WORKLOAD_REDUCTION_NOT_ESTIMABLE.
    """
    for policy in routing_sim["policies"]:
        cost = policy["cost_counterfactual"]
        assert cost["workload_reduction"] == "WORKLOAD_REDUCTION_NOT_ESTIMABLE", (
            f"Policy '{policy['policy_name']}' reported workload_reduction as {cost['workload_reduction']}. "
            "Fabricating tier durations is prohibited; it must be WORKLOAD_REDUCTION_NOT_ESTIMABLE."
        )
        assert "not independently isolate" in cost["reason"].lower()


def test_strict_separation_of_safety_and_cost_counterfactuals(routing_sim):
    """
    Verify that safety counterfactual (escapes, escape rate, false rejects)
    is structurally separated from cost counterfactual in every policy.
    """
    for policy in routing_sim["policies"]:
        assert "safety_counterfactual" in policy
        assert "cost_counterfactual" in policy

        safety = policy["safety_counterfactual"]
        assert "bad_patch_escapes" in safety
        assert "bad_patch_escape_rate" in safety
        assert "false_rejections" in safety

        # Ensure no timing or cost estimates leak into safety block
        assert "duration_seconds" not in safety
        assert "workload_reduction" not in safety


def test_safety_counterfactual_flags_escape_increase(routing_sim):
    """Verify that both exploratory dynamic routing policies flag unsafe escape increases."""
    for policy in routing_sim["policies"]:
        if "EXPLORATORY" in policy["threshold_provenance"]:
            safety = policy["safety_counterfactual"]
            assert safety["bad_patch_escapes"] == 8
            assert safety["escape_delta"] == 4
            assert "UNSAFE_ESCAPE_INCREASE" in safety["safety_verdict"]
