"""
Tests for MLVerify Phase 3.1 Empirical Evidence Audit and Claim Gate.
Verifies that all reported metrics strictly originate from admitted raw traces,
that unexecuted runs are never claimed, that timing provenance is mathematically verified,
and that reporting engines fail closed on incomplete cohorts.
"""

import hashlib
import json
from pathlib import Path
import pandas as pd
import pytest

from mlverify.features.schema import PRE_VERIFICATION_FEATURES, FORBIDDEN_VERIFICATION_FIELDS

RESULTS_DIR = Path("results/mlverify_v2")
TRACES_DIR = Path("empirical_mlverify_v2/traces")
RAW_DIR = Path("empirical_mlverify_v2/raw")


def test_evidence_inventory_completeness():
    inventory_path = RESULTS_DIR / "evidence_inventory.json"
    assert inventory_path.exists(), "evidence_inventory.json must exist"

    data = json.loads(inventory_path.read_text(encoding="utf-8"))
    summary = data.get("summary", {})

    assert summary.get("total_planned_runs") == 60
    assert summary.get("total_admitted_runs") == 1
    assert summary.get("total_missing_runs") == 59
    assert summary.get("audit_verdict") == "CANARY_ONLY_IDENTIFIED"

    admitted = data.get("admitted_runs", [])
    assert len(admitted) == 1
    canary = admitted[0]
    assert canary["run_id"] == "v2_task_051_boundary_in_qwen_s42"
    assert canary["model"] == "qwen2.5-coder:latest"
    assert canary["provider"] == "ollama"
    assert canary["execution_origin"] == "REAL_PROVIDER"
    assert canary["admission_status"] == "ADMITTED"

    # Verify sha256 matches actual file on disk
    trace_file = Path(canary["file_path"])
    assert trace_file.exists()
    disk_hash = hashlib.sha256(trace_file.read_bytes()).hexdigest()
    assert canary["file_sha256"] == disk_hash


def test_admitted_dataset_strict_trace_source():
    csv_path = RESULTS_DIR / "admitted_runs.csv"
    parquet_path = RESULTS_DIR / "admitted_runs.parquet"
    assert csv_path.exists(), "admitted_runs.csv must exist"
    assert parquet_path.exists(), "admitted_runs.parquet must exist"

    df_csv = pd.read_csv(csv_path)
    df_parquet = pd.read_parquet(parquet_path)

    assert len(df_csv) == 1, "Admitted runs table must contain exactly 1 row (no fabricated rows)"
    assert len(df_parquet) == 1

    row = df_csv.iloc[0]
    assert row["run_id"] == "v2_task_051_boundary_in_qwen_s42"
    assert row["task_id"] == "task_051_boundary_int_overflow_clamp"
    assert row["is_defective"] == 0
    assert row["is_false_accept"] == 0

    # Ensure all 32 declared features are present
    for feat in PRE_VERIFICATION_FEATURES:
        assert feat in df_csv.columns, f"Feature {feat} must be present in admitted table"

    # Ensure forbidden verification fields are not in pre-verification features
    for forbidden in FORBIDDEN_VERIFICATION_FIELDS:
        assert forbidden not in PRE_VERIFICATION_FEATURES, f"{forbidden} leaked into pre-verification feature contract"


def test_recomputed_event_counts_fidelity():
    event_path = RESULTS_DIR / "recomputed_event_counts.json"
    assert event_path.exists(), "recomputed_event_counts.json must exist"

    data = json.loads(event_path.read_text(encoding="utf-8"))
    assert data.get("total_admitted_traces") == 1

    counts = data.get("recomputed_event_counts", {})
    expected_targets = ["is_defective", "is_false_accept", "y_regression", "y_security", "y_overfitting", "y_performance"]

    for target in expected_targets:
        assert target in counts, f"Missing target {target} in recomputed event counts"
        c = counts[target]
        assert c["positive_events"] == 0, f"Target {target} had non-zero positive count in all-negative canary trace"
        assert c["negative_events"] == 1
        assert c["positive_rate"] == 0.0
        assert len(c["clopper_pearson_ci_95"]) == 2
        # Upper bound of Clopper-Pearson with 0/1 is 0.975
        assert c["clopper_pearson_ci_95"][1] == pytest.approx(0.975, rel=1e-2)


def test_timing_integrity_and_provenance():
    timing_path = RESULTS_DIR / "timing_integrity_report.json"
    assert timing_path.exists(), "timing_integrity_report.json must exist"

    data = json.loads(timing_path.read_text(encoding="utf-8"))
    checks = data.get("timing_integrity_checks", {})

    assert checks.get("all_runs_delta_tolerance_passed") is True
    assert checks.get("all_timestamps_strictly_monotonic") is True
    assert checks.get("zero_timestamp_overlap") is True
    assert checks.get("zero_impossible_durations") is True
    assert checks.get("synthetic_timing_multipliers_detected") is False

    timings = data.get("admitted_run_timings", [])
    assert len(timings) == 1
    t0 = timings[0]
    durations = t0["tier_durations"]
    assert durations["C1"] > 0.0
    assert durations["C2"] > 0.0
    assert durations["C3"] > 0.0
    assert durations["C4"] > 0.0
    assert durations["C5"] > 0.0
    assert durations["C6"] == 0.0  # Skipped because mutation test failed
    assert t0["delta_s"] <= 0.10


def test_claim_gate_disposition_is_fail_closed():
    gate_path = RESULTS_DIR / "CLAIM_GATE.md"
    assert gate_path.exists(), "CLAIM_GATE.md must exist"

    content = gate_path.read_text(encoding="utf-8")
    assert "PHASE_3_EMPIRICAL_STATUS: NOT_COMPLETE" in content or "PHASE_3_EMPIRICAL_STATUS: `NOT_COMPLETE`" in content or "Phase 3 Empirical Status**: `NOT_COMPLETE`" in content
    assert "HALT_UNTIL_CAMPAIGN_EXECUTION" in content
    assert "UNSUPPORTED" in content
    assert "CANARY_ONLY" in content
    assert "python scripts/run_empirical_mlverify_v2.py --concurrency 1" in content


def test_compile_script_fail_closed_mode():
    routing_path = RESULTS_DIR / "routing_simulation.json"
    assert routing_path.exists()
    routing_data = json.loads(routing_path.read_text(encoding="utf-8"))
    assert routing_data.get("disposition", {}).get("autonomous_routing") == "BLOCKED_INSUFFICIENT_DATA"
    assert routing_data.get("statistical_power_certified") is False

    model_sel_path = RESULTS_DIR / "model_selection.json"
    assert model_sel_path.exists()
    model_sel_data = json.loads(model_sel_path.read_text(encoding="utf-8"))
    assert model_sel_data.get("selection_status") == "INSUFFICIENT_DATA"
    assert model_sel_data.get("selection_result", {}).get("selected_model") == "NONE_INSUFFICIENT_DATA"

    multi_head_path = RESULTS_DIR / "multi_head_results.json"
    assert multi_head_path.exists()
    heads_data = json.loads(multi_head_path.read_text(encoding="utf-8"))
    assert len(heads_data) == 6
    for h in heads_data:
        assert h["status"] == "INSUFFICIENT_DATA"
        assert h["pr_auc"] == "N/A"
        assert h["generalization_status"] == "NOT_GENERALIZABLE"
