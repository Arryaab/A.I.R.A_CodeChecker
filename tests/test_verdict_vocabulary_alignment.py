"""
Tests for canonical Aegis Core 1.0 verdict vocabulary alignment across schema and dataset admission.
Directives: P0-F, P0-I, P0-K.
"""

import pytest

from aegis.research.dataset.admission import (
    validate_empirical_admission,
    validate_for_admission,
)
from aegis.research.trace.schema import (
    AegisReleasePolicy,
    AegisTechnicalVerdict,
    FailureCategory,
    TraceLifecycleState,
    validate_research_trace,
)


def make_valid_trace(**overrides) -> dict:
    """Helper to generate a base valid research trace with canonical vocabulary."""
    base = {
        "schema_version": "1.0.0",
        "run_id": "emp100_task_001_s42",
        "task_id": "task_001_fastapi_async_scope",
        "track": "track_1_core_frameworks",
        "model": "qwen2.5-coder:latest",
        "provider": "ollama",
        "seed": 42,
        "temperature": 0.2,
        "timestamp": "2026-09-27T12:00:00Z",
        "provenance": {
            "base_snapshot_sha256": "a" * 64,
            "head_snapshot_sha256": "b" * 64,
            "patch_sha256": "c" * 64,
            "patch_diff": "--- a/sol.py\n+++ b/sol.py\n@@ -1 +1 @@\n-old\n+new\n",
        },
        "pre_verification_features": {},
        "pre_features_vector": [0.0] * 19,
        "post_verification_signals": {},
        "agent_execution": {
            "success_signaled": True,
            "termination_reason": "FINISHED",
            "total_steps": 2,
        },
        "aegis_verification": {
            "technical_verdict": AegisTechnicalVerdict.QUALIFIED.value,
            "release_policy": AegisReleasePolicy.AUTO_APPROVE.value,
        },
        "oracle_evaluation": {
            "oracle_verdict": "CORRECT",
            "is_defective": 0,
        },
        "targets": {
            "regression": 0,
            "security": 0,
            "overfitting": 0,
            "performance": 0,
            "is_defective": 0,
        },
        "accepted": {
            "C1_agent_only": 1,
            "C2_visible_tests": 1,
            "C3_hidden_tests": 1,
            "C4_regression": 1,
            "C5_mutation": 1,
            "C6_full_aegis": 1,
        },
        "failure_classification": {
            "category": FailureCategory.SUCCESS.value,
            "detail": "Clean pass",
        },
        "lifecycle_state": TraceLifecycleState.COMPLETED.value,
        "execution_origin": "REAL_PROVIDER",
        "client_request_id": "client_ollama_qwen_1790000000",
        "provider_request_id": None,
        "provider_request_id_available": False,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Canonical Verdicts Accepted
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "tech_verdict",
    [
        "QUALIFIED",
        "QUALIFIED_WITHIN_SCOPE",
        "FAILED",
        "INDETERMINATE",
    ],
)
def test_canonical_technical_verdicts_accepted(tech_verdict):
    trace = make_valid_trace(
        aegis_verification={
            "technical_verdict": tech_verdict,
            "release_policy": "REVIEW",
        }
    )
    is_valid, errors = validate_research_trace(trace)
    assert is_valid is True, f"Schema validation failed: {errors}"

    admitted, reasons = validate_empirical_admission(trace)
    assert admitted is True, f"Admission failed: {reasons}"


@pytest.mark.parametrize(
    "rel_policy",
    [
        "AUTO_APPROVE",
        "REVIEW",
        "BLOCK",
    ],
)
def test_canonical_release_policies_accepted(rel_policy):
    trace = make_valid_trace(
        aegis_verification={
            "technical_verdict": "QUALIFIED",
            "release_policy": rel_policy,
        }
    )
    is_valid, errors = validate_research_trace(trace)
    assert is_valid is True, f"Schema validation failed: {errors}"

    admitted, reasons = validate_empirical_admission(trace)
    assert admitted is True, f"Admission failed: {reasons}"


# ---------------------------------------------------------------------------
# Obsolete and Invalid Verdicts Explicitly Rejected
# ---------------------------------------------------------------------------

def test_obsolete_passed_verdict_rejected():
    trace = make_valid_trace(
        aegis_verification={
            "technical_verdict": "PASSED",
            "release_policy": "AUTO_APPROVE",
        }
    )
    is_valid, errors = validate_research_trace(trace)
    assert is_valid is False
    assert any("Obsolete aegis technical_verdict rejected" in e for e in errors)

    admitted, reasons = validate_empirical_admission(trace)
    assert admitted is False
    assert any("Obsolete aegis technical_verdict rejected: 'PASSED'" in r for r in reasons)


def test_obsolete_release_policy_rejected():
    trace = make_valid_trace(
        aegis_verification={
            "technical_verdict": "QUALIFIED",
            "release_policy": "RELEASE",
        }
    )
    is_valid, errors = validate_research_trace(trace)
    assert is_valid is False
    assert any("Obsolete aegis release_policy rejected" in e for e in errors)

    admitted, reasons = validate_empirical_admission(trace)
    assert admitted is False
    assert any("Obsolete aegis release_policy rejected: 'RELEASE'" in r for r in reasons)


def test_obsolete_error_verdict_rejected():
    trace = make_valid_trace(
        aegis_verification={
            "technical_verdict": "ERROR",
            "release_policy": "BLOCK",
        }
    )
    is_valid, errors = validate_research_trace(trace)
    assert is_valid is False
    assert any("Obsolete aegis technical_verdict rejected" in e for e in errors)

    admitted, reasons = validate_empirical_admission(trace)
    assert admitted is False
    assert any("Obsolete aegis technical_verdict rejected: 'ERROR'" in r for r in reasons)


def test_invalid_arbitrary_verdict_rejected():
    trace = make_valid_trace(
        aegis_verification={
            "technical_verdict": "UNKNOWN_CUSTOM_VERDICT",
            "release_policy": "BLOCK",
        }
    )
    is_valid, errors = validate_research_trace(trace)
    assert is_valid is False

    admitted, reasons = validate_empirical_admission(trace)
    assert admitted is False
    assert any("Invalid aegis technical_verdict" in r for r in reasons)


# ---------------------------------------------------------------------------
# Dataset Admission Integrity Rules (P0-K)
# ---------------------------------------------------------------------------

def test_real_provider_with_available_provider_id_admitted():
    """When a provider exposes a request id (e.g. OpenAI), both client and provider IDs are valid."""
    trace = make_valid_trace(
        client_request_id="client_openai_gpt4o_123456",
        provider_request_id="chatcmpl-abc123xyz",
        provider_request_id_available=True,
    )
    admitted, reasons = validate_empirical_admission(trace)
    assert admitted is True, f"Should be admitted: {reasons}"


def test_mock_origin_rejected():
    trace = make_valid_trace(execution_origin="MOCK")
    admitted, reasons = validate_empirical_admission(trace)
    assert admitted is False
    assert any("REAL_PROVIDER" in r for r in reasons)


def test_synthetic_flag_rejected():
    trace = make_valid_trace(is_synthetic=True)
    admitted, reasons = validate_empirical_admission(trace)
    assert admitted is False
    assert any("synthetic" in r.lower() for r in reasons)


def test_missing_client_request_id_rejected():
    trace = make_valid_trace(client_request_id="", provider_request_id=None)
    admitted, reasons = validate_empirical_admission(trace)
    assert admitted is False
    assert any("client_request_id" in r for r in reasons)


def test_protocol_mismatch_rejected():
    trace = make_valid_trace()
    admitted, reasons = validate_empirical_admission(
        trace, expected_protocol_hash="expected_hash_sha256"
    )
    assert admitted is False
    assert any("Protocol hash mismatch" in r for r in reasons)


def test_benchmark_task_mismatch_rejected():
    trace = make_valid_trace(task_id="unregistered_task_999")
    admitted, reasons = validate_empirical_admission(
        trace, allowed_task_ids={"task_001_fastapi_async_scope"}
    )
    assert admitted is False
    assert any("not found in locked benchmark" in r for r in reasons)


def test_incomplete_lifecycle_rejected():
    trace = make_valid_trace(lifecycle_state=TraceLifecycleState.RUNNING.value)
    admitted, reasons = validate_empirical_admission(trace)
    assert admitted is False
    assert any("lifecycle_state" in r for r in reasons)
