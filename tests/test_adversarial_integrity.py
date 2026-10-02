"""
Integration tests for the 4-stage Adversarial Integrity Defense Matrix:
Validates that test tampering, evaluator probing, secret exfiltration,
framework monkeypatching, and git extraction are blocked.
"""

import pytest
from scripts.run_adversarial_harness import (
    evaluate_adversarial_probe,
    ATTACK_MATRIX,
    BENIGN_CONTROLS
)

@pytest.mark.parametrize("category, probe_id, patch", ATTACK_MATRIX)
def test_adversarial_attack_probes_blocked(category, probe_id, patch):
    res = evaluate_adversarial_probe(category, probe_id, patch, is_attack=True)
    assert res.attempted is True
    assert res.detected is True, f"Failed to detect attack: {probe_id}"
    assert res.blocked is True, f"Failed to block attack: {probe_id}"
    assert res.successful is False, f"Exploit succeeded: {probe_id}"

@pytest.mark.parametrize("category, probe_id, patch", BENIGN_CONTROLS)
def test_benign_controls_unblocked(category, probe_id, patch):
    res = evaluate_adversarial_probe(category, probe_id, patch, is_attack=False)
    assert res.blocked is False, f"False positive on benign patch: {probe_id}"
    assert res.successful is True
