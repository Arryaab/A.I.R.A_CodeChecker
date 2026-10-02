"""
Comprehensive Test Suite for MLVerify Phase 3 Expansion (Directive Section 16)
Validates all 15 integrity and verification invariants:
1. task-group split integrity
2. no train/test task overlap
3. repository lineage leakage
4. temporal feature contract
5. feature denylist
6. provider provenance
7. model-selection reproducibility
8. final-test isolation
9. per-tier timing reconstruction
10. shadow-routing calculation
11. counterfactual/observed distinction
12. no synthetic timing constants
13. no post-verification feature contamination
14. deterministic run keys
15. experiment resume semantics
"""

import hashlib
import json
from pathlib import Path
import pytest
import yaml

from aegis.research.worker_pool import IdempotentScheduler
from aegis.research.verifier.pipeline import (
    AegisResearchVerifier,
    AegisVerificationReport,
    VerificationTierResults,
)
from aegis.research.agent.loop import AgentRunResult
from aegis.research.provenance.tracker import ProvenanceRecord
from mlverify.features.schema import FORBIDDEN_VERIFICATION_FIELDS, PRE_VERIFICATION_FEATURES


# ---------------------------------------------------------------------------
# Invariants 1 & 2: Task-Group Split Integrity & Zero Overlap
# ---------------------------------------------------------------------------

def test_task_group_split_integrity_and_no_overlap():
    split_file = Path("results/mlverify_v2/split_manifest.json")
    assert split_file.exists(), "split_manifest.json missing!"

    data = json.loads(split_file.read_text(encoding="utf-8"))
    splits = data["splits"]
    train_ids = set(splits["train"]["task_ids"])
    dev_ids = set(splits["dev"]["task_ids"])
    test_ids = set(splits["locked_test"]["task_ids"])

    assert len(train_ids) == 18, f"Expected 18 train tasks, got {len(train_ids)}"
    assert len(dev_ids) == 6, f"Expected 6 dev tasks, got {len(dev_ids)}"
    assert len(test_ids) == 6, f"Expected 6 locked test tasks, got {len(test_ids)}"

    # Zero overlap
    assert train_ids.isdisjoint(dev_ids), f"Train/Dev overlap: {train_ids & dev_ids}"
    assert train_ids.isdisjoint(test_ids), f"Train/Test overlap: {train_ids & test_ids}"
    assert dev_ids.isdisjoint(test_ids), f"Dev/Test overlap: {dev_ids & test_ids}"

    # Complete union of 30 tasks
    all_tasks = train_ids | dev_ids | test_ids
    assert len(all_tasks) == 30, f"Expected exactly 30 unique tasks, got {len(all_tasks)}"


# ---------------------------------------------------------------------------
# Invariant 3: Repository Lineage Leakage
# ---------------------------------------------------------------------------

def test_repository_lineage_leakage_between_splits():
    task_manifest_file = Path("results/mlverify_v2/task_manifest.json")
    split_file = Path("results/mlverify_v2/split_manifest.json")
    assert task_manifest_file.exists() and split_file.exists()

    task_data = json.loads(task_manifest_file.read_text(encoding="utf-8"))
    split_data = json.loads(split_file.read_text(encoding="utf-8"))

    task_repo_map = {t["task_id"]: t["repository"] for t in task_data["tasks"]}

    train_repos = {task_repo_map[tid] for tid in split_data["splits"]["train"]["task_ids"]}
    test_repos = {task_repo_map[tid] for tid in split_data["splits"]["locked_test"]["task_ids"]}

    # Verify no unexpected cross-split repository leakage
    leakage = train_repos.intersection(test_repos)
    assert not leakage, f"Repository lineage leakage between Train and Locked Test: {leakage}"


# ---------------------------------------------------------------------------
# Invariants 4 & 5: Temporal Feature Contract & Denylist Guard
# ---------------------------------------------------------------------------

def test_temporal_feature_contract_and_denylist():
    contract_file = Path("results/mlverify_v2/feature_contract.json")
    assert contract_file.exists(), "feature_contract.json missing!"

    contract = json.loads(contract_file.read_text(encoding="utf-8"))
    assert contract["status"] == "PASSED_UNDER_DECLARED_FEATURE_CONTRACT"
    assert contract["prediction_boundary"]["symbol"] == "t_prediction"

    denylist = set(contract["forbidden_denylist"]["fields"])
    declared_features = set()
    for fam in contract["feature_families"].values():
        declared_features.update(fam["features"])

    # Hard guard: zero intersection between declared features and denylist
    intersection = declared_features.intersection(denylist)
    assert not intersection, f"Forbidden leakage in declared features: {intersection}"
    assert declared_features.isdisjoint(FORBIDDEN_VERIFICATION_FIELDS)


# ---------------------------------------------------------------------------
# Invariant 6: Provider Provenance Requirement
# ---------------------------------------------------------------------------

def test_provider_provenance_schema_compliance():
    required_provenance_keys = {
        "model",
        "provider",
        "seed",
        "temperature",
        "timestamp",
        "provenance",
        "pre_verification_features",
        "execution_origin",
        "client_request_id",
        "run_key"
    }
    # Validate against schema definition
    from aegis.research.trace.schema import REQUIRED_TOP_LEVEL_KEYS
    assert "provenance" in REQUIRED_TOP_LEVEL_KEYS
    assert "pre_verification_features" in REQUIRED_TOP_LEVEL_KEYS


# ---------------------------------------------------------------------------
# Invariant 7: Model Selection Reproducibility
# ---------------------------------------------------------------------------

def test_model_selection_hierarchy_reproducibility():
    from mlverify.models.selection import evaluate_model_selection_hierarchy

    candidates = {
        "candidate_A": {"pr_auc": 0.82, "ece": 0.04, "fold_std": 0.02, "complexity": 1},
        "candidate_B": {"pr_auc": 0.90, "ece": 0.05, "fold_std": 0.03, "complexity": 2},
        "candidate_C": {"pr_auc": 0.95, "ece": 0.12, "fold_std": 0.02, "complexity": 2},  # Fails ECE gate
    }
    # Candidate B should win because Candidate C violates secondary ECE <= 0.08 gate
    winner = evaluate_model_selection_hierarchy(candidates)
    assert winner == "candidate_B"

    # Deterministic: rerunning yields identical winner
    assert evaluate_model_selection_hierarchy(candidates) == "candidate_B"


# ---------------------------------------------------------------------------
# Invariant 8: Final Locked Test Isolation
# ---------------------------------------------------------------------------

def test_final_locked_test_isolation():
    split_file = Path("results/mlverify_v2/split_manifest.json")
    split_data = json.loads(split_file.read_text(encoding="utf-8"))

    locked_test = split_data["splits"]["locked_test"]
    assert locked_test["status"] == "LOCKED_UNTIL_FINAL_EVALUATION"
    assert len(locked_test["task_ids"]) == 6

    # Verify no locked test task is in train or dev
    for tid in locked_test["task_ids"]:
        assert tid not in split_data["splits"]["train"]["task_ids"]
        assert tid not in split_data["splits"]["dev"]["task_ids"]


# ---------------------------------------------------------------------------
# Invariant 9: Per-Tier Timing Reconstruction (|total - sum(Ci)| <= 0.10s)
# ---------------------------------------------------------------------------

def test_per_tier_timing_reconstruction_integrity(tmp_path):
    # Create mock dummy task to run AegisResearchVerifier
    task_dir = tmp_path / "mock_task"
    (task_dir / "task" / "buggy").mkdir(parents=True)
    (task_dir / "task" / "tests").mkdir(parents=True)
    (task_dir / "private" / "hidden_tests").mkdir(parents=True)

    sol_file = task_dir / "task" / "buggy" / "solution.py"
    sol_file.write_text("def add(a, b): return a + b\n")

    test_file = task_dir / "task" / "tests" / "test_solution.py"
    test_file.write_text("from solution import add\ndef test_add(): assert add(1, 2) == 3\n")

    h_test_file = task_dir / "private" / "hidden_tests" / "test_solution.py"
    h_test_file.write_text("from solution import add\ndef test_hidden(): assert add(2, 3) == 5\n")

    # Run verifier
    agent_res = AgentRunResult(
        task_id="mock_task",
        success_signaled=True,
        termination_reason="FINISH",
        steps=[],
        modified_files=["solution.py"],
        total_prompt_tokens=100,
        total_completion_tokens=50,
        total_tokens=150,
        agent_duration_seconds=1.0,
    )
    from aegis.research.provenance.tracker import AstSymbolDelta
    prov = ProvenanceRecord(
        task_id="mock_task",
        base_snapshot_sha256="abc",
        head_snapshot_sha256="abc",
        patch_sha256="def",
        patch_diff="",
        modified_files=["solution.py"],
        added_files=[],
        deleted_files=[],
        lines_added=1,
        lines_deleted=1,
        net_churn=0,
        ast_delta=AstSymbolDelta(),
        timestamp="2026-09-27T00:00:00Z"
    )

    report = AegisResearchVerifier.verify(
        task_dir=task_dir,
        candidate_dir=task_dir / "task" / "buggy",
        agent_result=agent_res,
        provenance=prov,
    )

    # Check per-tier durations exist
    assert "C1" in report.tier_durations
    assert "C2" in report.tier_durations
    assert "C3" in report.tier_durations
    assert "C4" in report.tier_durations
    assert "C5" in report.tier_durations
    assert "C6" in report.tier_durations

    # Timing reconstruction invariant: |total - sum(Ci)| <= 0.10s
    total_tiers = sum(report.tier_durations.values())
    assert abs(report.verification_duration_seconds - total_tiers) <= 0.10
    assert report.verification_duration_seconds > 0.0


# ---------------------------------------------------------------------------
# Invariants 10 & 11: Shadow-Routing Calculation & Counterfactual Separation
# ---------------------------------------------------------------------------

def test_shadow_routing_counterfactual_separation():
    from mlverify.routing.simulator import simulate_routing_policy

    # Mock sample traces
    sample_records = [
        {
            "run_id": "r1",
            "is_defective": 0,
            "actual_release_policy": "AUTO_APPROVE",
            "defect_risk_prob": 0.10,
            "C1_duration_s": 0.02,
            "C2_duration_s": 0.10,
            "C3_duration_s": 0.15,
            "C4_duration_s": 0.12,
            "C5_duration_s": 0.20,
            "C6_duration_s": 0.05,
            "total_verification_duration_s": 0.64
        },
        {
            "run_id": "r2",
            "is_defective": 1,
            "actual_release_policy": "BLOCK",
            "defect_risk_prob": 0.85,
            "C1_duration_s": 0.02,
            "C2_duration_s": 0.10,
            "C3_duration_s": 0.15,
            "C4_duration_s": 0.12,
            "C5_duration_s": 0.20,
            "C6_duration_s": 0.05,
            "total_verification_duration_s": 0.64
        }
    ]

    res = simulate_routing_policy(sample_records, fast_threshold=0.30, deep_threshold=0.70)
    assert "shadow_mode" in res
    assert res["shadow_mode"] is True
    assert "counterfactual_cost" in res
    assert "observed_cost" in res
    assert res["mode"] == "SHADOW_MODE_ONLY"


# ---------------------------------------------------------------------------
# Invariant 12: No Synthetic Timing Multipliers
# ---------------------------------------------------------------------------

def test_no_synthetic_timing_multipliers_in_verifier():
    # Verify no arbitrary static multipliers (like 0.35, 1.8, 2.5) are present in verifier pipeline
    src = Path("aegis/research/verifier/pipeline.py").read_text(encoding="utf-8")
    assert "0.35 *" not in src
    assert "* 1.8" not in src
    assert "* 2.5" not in src
    assert "SYNTHETIC" not in src


# ---------------------------------------------------------------------------
# Invariant 13: No Post-Verification Feature Contamination
# ---------------------------------------------------------------------------

def test_no_post_verification_feature_contamination():
    from mlverify.features.schema import FORBIDDEN_VERIFICATION_FIELDS
    from mlverify.features.extractor import extract_features_from_trace

    # Trace containing post-verification signals
    trace = {
        "run_id": "test_run",
        "task_id": "task_051_boundary_int_overflow_clamp",
        "track": "boundary_violation",
        "model": "qwen2.5-coder",
        "provider": "ollama",
        "seed": 42,
        "temperature": 0.2,
        "provenance": {
            "patch_diff": "--- a/sol.py\n+++ b/sol.py\n@@ -1 +1 @@\n-old\n+new\n",
            "modified_files": ["sol.py"],
            "added_files": [],
            "deleted_files": []
        },
        "agent_execution": {
            "total_steps": 3,
            "total_prompt_tokens": 120,
            "total_completion_tokens": 40,
            "agent_duration_seconds": 1.2,
            "steps": [
                {"tool_calls": [{"name": "edit_file"}], "tool_results": [{"status": "ok"}]}
            ]
        },
        "post_verification_signals": {
            "C1_duration_s": 0.05,
            "C2_duration_s": 0.12,
            "C3_duration_s": 0.15,
            "verification_duration_s": 0.32
        },
        "oracle_evaluation": {"is_defective": 0, "oracle_verdict": "CORRECT"},
        "aegis_verification": {"technical_verdict": "QUALIFIED", "release_policy": "AUTO_APPROVE"}
    }

    feats = extract_features_from_trace(trace)
    for col in feats.keys():
        assert col not in FORBIDDEN_VERIFICATION_FIELDS, f"Contaminated feature: {col}"
        assert not col.startswith("C1_") and not col.startswith("C2_")
        assert "oracle" not in col.lower()


# ---------------------------------------------------------------------------
# Invariant 14: Deterministic Run Keys
# ---------------------------------------------------------------------------

def test_deterministic_run_keys():
    scheduler = IdempotentScheduler()
    k1 = scheduler.compute_run_key(
        experiment_id="empirical_mlverify_v2",
        task_id="task_051_boundary_int_overflow_clamp",
        model_id="qwen2.5-coder:latest",
        seed=42,
        temperature=0.2
    )
    k2 = scheduler.compute_run_key(
        experiment_id="empirical_mlverify_v2",
        task_id="task_051_boundary_int_overflow_clamp",
        model_id="qwen2.5-coder:latest",
        seed=42,
        temperature=0.2
    )
    assert k1 == k2, "Run keys must be deterministic!"

    k3 = scheduler.compute_run_key(
        experiment_id="empirical_mlverify_v2",
        task_id="task_051_boundary_int_overflow_clamp",
        model_id="qwen2.5-coder:latest",
        seed=100,  # Different seed
        temperature=0.2
    )
    assert k1 != k3, "Different seed must produce distinct run key!"


def test_experiment_resume_semantics():
    from aegis.research.worker_pool import IdempotencyConflictError
    scheduler = IdempotentScheduler(experiment_id="empirical_mlverify_v2")
    run_key = "run_test_key_123"

    scheduler.register_execution(run_key, "run_001")
    scheduler.mark_completed(run_key, "run_001")

    # Resuming execution without retry flag is blocked to protect completed runs
    with pytest.raises(IdempotencyConflictError):
        scheduler.register_execution(run_key, "run_002", is_retry=False)

    # With retry flag, execution is admitted as attempt 2
    rec2 = scheduler.register_execution(run_key, "run_002", is_retry=True, retry_reason="WORKER_RECOVERY")
    assert rec2["attempt"] == 2
