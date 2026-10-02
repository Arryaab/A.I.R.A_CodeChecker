"""
Tests for Empirical Dataset Admission Gate and Trace Finalization.
Requirements from Directive Sections 9, 10, 11, 12, 13, 14, 29.
"""

import copy
import json
from pathlib import Path
import pytest

from aegis.research.trace.schema import (
    TraceLifecycleState,
    SeedSemantics,
    validate_research_trace,
)
from aegis.research.dataset.admission import validate_for_admission


@pytest.fixture
def valid_trace_sample():
    """Load a valid trace from the cross-provider pilot dataset as a baseline."""
    sample_path = Path("results/experiments/cross_provider_pilot_v1/runs/cross_task_001_fas_cloud_model_a_s100.json")
    with open(sample_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def test_dataset_admission_valid(valid_trace_sample):
    """Test that a compliant completed trace is admitted."""
    admitted, reasons = validate_for_admission(valid_trace_sample)
    assert admitted is True
    assert len(reasons) == 0


def test_dataset_admission_rejects_non_completed_lifecycle(valid_trace_sample):
    """Test that traces not in COMPLETED state are rejected."""
    for state in [
        TraceLifecycleState.CREATED.value,
        TraceLifecycleState.RUNNING.value,
        TraceLifecycleState.VERIFICATION.value,
        TraceLifecycleState.ORACLE.value,
        TraceLifecycleState.FINALIZING.value,
        TraceLifecycleState.FAILED.value,
        TraceLifecycleState.INVALID.value,
    ]:
        bad_trace = copy.deepcopy(valid_trace_sample)
        bad_trace["lifecycle_state"] = state
        admitted, reasons = validate_for_admission(bad_trace)
        assert admitted is False
        assert any("lifecycle_state" in r for r in reasons)


def test_dataset_admission_rejects_missing_provenance(valid_trace_sample):
    """Test that traces with missing provenance hashes are rejected."""
    bad_trace = copy.deepcopy(valid_trace_sample)
    bad_trace["provenance"]["patch_sha256"] = ""
    admitted, reasons = validate_for_admission(bad_trace)
    assert admitted is False
    assert any("patch_sha256" in r for r in reasons)


def test_dataset_admission_rejects_missing_or_invalid_oracle(valid_trace_sample):
    """Test that traces with corrupted or missing oracle outcome are rejected."""
    bad_trace = copy.deepcopy(valid_trace_sample)
    bad_trace["oracle_evaluation"]["oracle_verdict"] = "UNKNOWN"
    admitted, reasons = validate_for_admission(bad_trace)
    assert admitted is False
    assert any("oracle_verdict" in r for r in reasons)


def test_dataset_admission_rejects_invalid_task_id(valid_trace_sample):
    """Test that traces with unauthorized task IDs are rejected."""
    bad_trace = copy.deepcopy(valid_trace_sample)
    allowed_tasks = {"task_002_other", "task_003_other"}
    admitted, reasons = validate_for_admission(bad_trace, allowed_task_ids=allowed_tasks)
    assert admitted is False
    assert any("task_id" in r for r in reasons)


def test_dataset_admission_rejects_nan_in_features(valid_trace_sample):
    """Test that traces with non-finite features are rejected."""
    bad_trace = copy.deepcopy(valid_trace_sample)
    bad_trace["pre_features_vector"][5] = float("nan")
    admitted, reasons = validate_for_admission(bad_trace)
    assert admitted is False
    assert any("non-finite" in r for r in reasons)


def test_seed_and_temperature_semantics():
    """Test SeedSemantics enum values and explicit metadata validation."""
    assert SeedSemantics.DETERMINISTIC.value == "DETERMINISTIC"
    assert SeedSemantics.PSEUDO_DETERMINISTIC.value == "PSEUDO_DETERMINISTIC"
    assert SeedSemantics.BEST_EFFORT.value == "BEST_EFFORT"
    assert SeedSemantics.UNSUPPORTED.value == "UNSUPPORTED"
