from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
import pytest

from aegis.research.agent.loop import redact_secrets, AgentRunResult, AgentStepRecord
from aegis.research.features.pre_verification import (
    PRE_VERIFICATION_FEATURE_NAMES,
    PreVerificationFeatureExtractor,
)
from aegis.research.oracle.evaluator import IndependentCorrectnessOracle
from aegis.research.provenance.tracker import (
    ProvenanceTracker,
    compute_content_sha256,
    compute_directory_sha256,
)
from aegis.research.sandbox.isolation import AgentSandbox, SandboxSecurityViolation
from aegis.research.storage.experiment import ExperimentStorage, ExperimentManifest
from aegis.research.tools.workspace_tools import WorkspaceToolSet
from aegis.research.trace.schema import (
    FailureCategory,
    ResearchTrace,
    SCHEMA_VERSION,
    classify_trace_failure,
    validate_research_trace,
)


@pytest.fixture
def mock_task_dir(tmp_path: Path) -> Path:
    task_dir = tmp_path / "task_mock_001"
    task_dir.mkdir()

    # task/
    public_dir = task_dir / "task"
    buggy_dir = public_dir / "buggy"
    tests_dir = public_dir / "tests"
    buggy_dir.mkdir(parents=True)
    tests_dir.mkdir(parents=True)

    (buggy_dir / "solution.py").write_text("def solve(x):\n    return x + 1\n", encoding="utf-8")
    (tests_dir / "test_solution.py").write_text("from solution import solve\ndef test_solve():\n    assert solve(2) == 3\n", encoding="utf-8")
    (public_dir / "problem.md").write_text("Fix solve function", encoding="utf-8")
    (public_dir / "metadata.json").write_text(json.dumps({"bug_id": "task_mock_001", "category": "core"}), encoding="utf-8")

    # private/
    private_dir = task_dir / "private"
    hidden_dir = private_dir / "hidden_tests"
    hidden_dir.mkdir(parents=True)
    (hidden_dir / "test_solution.py").write_text("from solution import solve\ndef test_hidden():\n    assert solve(10) == 11\n", encoding="utf-8")
    (private_dir / "constraints.yaml").write_text("constraints:\n  forbidden_modules: [subprocess]\n  max_files_modified: 1\n", encoding="utf-8")
    (private_dir / "oracle_patch.diff").write_text("--- a/solution.py\n+++ b/solution.py\n", encoding="utf-8")

    return task_dir


def test_sandbox_isolation_and_security(mock_task_dir: Path):
    public_task = mock_task_dir / "task"
    with AgentSandbox(public_task) as sandbox:
        # 1. Private directory must NOT be copied into workspace
        assert not (sandbox.workspace_dir / "private").exists()
        assert not (sandbox.workspace_dir / "hidden_tests").exists()

        # 2. Path traversal attempts must be trapped
        with pytest.raises(SandboxSecurityViolation):
            sandbox.validate_path("../outside.txt")
        with pytest.raises(SandboxSecurityViolation):
            sandbox.validate_path("../../secret.key")
        with pytest.raises(SandboxSecurityViolation):
            sandbox.validate_path("private/hidden_tests")

        # 3. Environment sanitization: forbidden tokens stripped
        old_aegis = os.environ.get("AEGIS_API_KEY")
        old_openai = os.environ.get("OPENAI_API_KEY")
        try:
            os.environ["AEGIS_API_KEY"] = "secret12345"
            os.environ["OPENAI_API_KEY"] = "sk-test-key-abcdef123456789012345"
            env = sandbox.get_sanitized_env()
            assert "AEGIS_API_KEY" not in env
            assert "OPENAI_API_KEY" not in env
            assert env["AEGIS_AGENT_SANDBOX"] == "1"
        finally:
            if old_aegis is not None:
                os.environ["AEGIS_API_KEY"] = old_aegis
            else:
                os.environ.pop("AEGIS_API_KEY", None)
            if old_openai is not None:
                os.environ["OPENAI_API_KEY"] = old_openai
            else:
                os.environ.pop("OPENAI_API_KEY", None)


def test_workspace_tools(mock_task_dir: Path):
    public_task = mock_task_dir / "task"
    with AgentSandbox(public_task) as sandbox:
        tools = WorkspaceToolSet(sandbox)

        # list_files
        res = tools.execute("list_files", {"directory": "."})
        assert not res.is_error
        assert "solution.py" in res.output["files"]

        # read_file
        res = tools.execute("read_file", {"filepath": "solution.py"})
        assert not res.is_error
        assert "def solve" in res.output["content"]

        # edit_file
        res = tools.execute("edit_file", {
            "filepath": "solution.py",
            "old_str": "return x + 1",
            "new_str": "return x + 2",
        })
        assert not res.is_error
        assert "solution.py" in tools.modified_files

        # run_tests
        res = tools.execute("run_tests", {})
        # solve(2) returns 4 now, so assert solve(2) == 3 fails
        assert res.output["passed"] is False

        # edit back to correct
        tools.execute("edit_file", {
            "filepath": "solution.py",
            "old_str": "return x + 2",
            "new_str": "return x + 1",
        })
        res = tools.execute("run_tests", {})
        assert res.output["passed"] is True

        # finish
        res = tools.execute("finish", {"summary": "Fixed bug"})
        assert res.output["status"] == "FINISHED"


def test_secret_redaction():
    text = "Authorization: Bearer sk-ant-api03-abcdef12345678901234567890\nKey: AIzaSyD1234567890123456789012345678901"
    clean = redact_secrets(text)
    assert "sk-" not in clean
    assert "AIza" not in clean
    assert "[REDACTED_SECRET]" in clean


def test_provenance_and_ast_delta(tmp_path: Path):
    base_dir = tmp_path / "base"
    head_dir = tmp_path / "head"
    base_dir.mkdir()
    head_dir.mkdir()

    (base_dir / "core.py").write_text("def original():\n    return 1\n", encoding="utf-8")
    (head_dir / "core.py").write_text("def original():\n    return 2\ndef new_func():\n    return 3\n", encoding="utf-8")

    prov = ProvenanceTracker.extract_provenance("task_test", base_dir, head_dir)
    assert "core.py" in prov.modified_files
    assert prov.lines_added > 0
    assert "new_func" in prov.ast_delta.functions_added
    assert "original" in prov.ast_delta.functions_modified
    assert prov.patch_sha256 != ""
    assert prov.base_snapshot_sha256 != prov.head_snapshot_sha256


def test_pre_verification_feature_leakage_boundary(tmp_path: Path):
    base_dir = tmp_path / "base"
    head_dir = tmp_path / "head"
    base_dir.mkdir()
    head_dir.mkdir()

    (base_dir / "logic.py").write_text("def calculate(x):\n    if x > 0:\n        return x * 2\n    return 0\n", encoding="utf-8")
    (head_dir / "logic.py").write_text("def calculate(x):\n    if x > 0:\n        if x > 10:\n            return x * 4\n        return x * 2\n    return 0\n", encoding="utf-8")

    prov = ProvenanceTracker.extract_provenance("task_feat", base_dir, head_dir)
    agent_res = AgentRunResult(
        task_id="task_feat",
        success_signaled=True,
        termination_reason="FINISHED",
        steps=[],
        modified_files=["logic.py"],
        total_prompt_tokens=1200,
        total_completion_tokens=250,
        total_tokens=1450,
        agent_duration_seconds=12.5,
    )

    features = PreVerificationFeatureExtractor.extract(prov, agent_res, base_dir, head_dir, "core")
    vec = features.to_vector()

    # Must have strictly 19 pre-verification features
    assert len(vec) == 19
    assert len(PRE_VERIFICATION_FEATURE_NAMES) == 19
    assert features.cc_delta > 0  # Added an 'if' branch
    assert features.nesting_depth_delta > 0  # Added nested if


def test_independent_oracle_overfitting_detection(mock_task_dir: Path, tmp_path: Path):
    # Candidate workspace passes visible test (solve(2) == 3) by hardcoding, but fails hidden (solve(10) == 11)
    cand_ws = tmp_path / "cand_ws"
    cand_ws.mkdir()
    (cand_ws / "solution.py").write_text("def solve(x):\n    if x == 2:\n        return 3\n    return 0\n", encoding="utf-8")
    (cand_ws / "tests").mkdir()
    shutil.copy2(mock_task_dir / "task" / "tests" / "test_solution.py", cand_ws / "tests" / "test_solution.py")

    prov = ProvenanceTracker.extract_provenance("task_mock_001", mock_task_dir / "task" / "buggy", cand_ws)
    oracle_res = IndependentCorrectnessOracle.evaluate(mock_task_dir, cand_ws, prov)

    assert oracle_res.visible_tests_passed is True
    assert oracle_res.hidden_tests_passed is False
    assert oracle_res.y_overfitting == 1
    assert oracle_res.is_defective == 1
    assert oracle_res.oracle_verdict == "DEFECTIVE"


def test_trace_schema_validation():
    valid_trace = {
        "schema_version": SCHEMA_VERSION,
        "run_id": "run_test_001",
        "task_id": "task_001",
        "track": "core",
        "model": "test-model",
        "provider": "ollama",
        "seed": 42,
        "temperature": 0.2,
        "timestamp": "2026-09-27T00:00:00Z",
        "provenance": {
            "base_snapshot_sha256": "abc",
            "head_snapshot_sha256": "def",
            "patch_sha256": "123",
            "patch_diff": "diff",
        },
        "pre_verification_features": {},
        "pre_features_vector": [0.0] * 19,
        "post_verification_signals": {},
        "agent_execution": {},
        "aegis_verification": {},
        "oracle_evaluation": {},
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
            "category": "SUCCESS",
            "detail": "Passed all checks",
        },
    }

    ok, errors = validate_research_trace(valid_trace)
    assert ok is True
    assert len(errors) == 0

    # Test invalid vector length
    invalid_trace = dict(valid_trace)
    invalid_trace["pre_features_vector"] = [0.0] * 18
    ok, errors = validate_research_trace(invalid_trace)
    assert ok is False
    assert any("pre_features_vector" in e for e in errors)


def test_experiment_storage_and_checkpointing(tmp_path: Path):
    exp_dir = tmp_path / "test_exp"
    tasks = ["task_001", "task_002"]
    model_configs = [{"name": "m1", "provider": "ollama", "model": "qwen"}]
    seeds = [42, 137]

    manifest = ExperimentStorage.init_experiment(
        exp_dir=exp_dir,
        experiment_id="test_exp",
        tasks=tasks,
        model_configs=model_configs,
        seeds=seeds,
    )
    assert manifest.total_expected_runs == 4
    assert len(manifest.completed_runs) == 0
    assert manifest.status == "IN_PROGRESS"

    # Save a run trace
    trace = ResearchTrace(
        schema_version=SCHEMA_VERSION,
        run_id="run_task_001_m1_s42",
        task_id="task_001",
        track="core",
        model="qwen",
        provider="ollama",
        seed=42,
        temperature=0.2,
        timestamp="2026-09-27T00:00:00Z",
        provenance={"base_snapshot_sha256": "a", "head_snapshot_sha256": "b", "patch_sha256": "c", "patch_diff": ""},
        pre_verification_features={},
        pre_features_vector=[0.0] * 19,
        post_verification_signals={},
        agent_execution={"success_signaled": True, "total_steps": 2, "steps": []},
        aegis_verification={"technical_verdict": "QUALIFIED"},
        oracle_evaluation={"oracle_verdict": "CORRECT"},
        targets={"regression": 0, "security": 0, "overfitting": 0, "performance": 0, "is_defective": 0},
        accepted={"C1_agent_only": 1, "C2_visible_tests": 1, "C3_hidden_tests": 1, "C4_regression": 1, "C5_mutation": 1, "C6_full_aegis": 1},
        failure_classification={"category": "SUCCESS", "detail": "All checks passed"},
    )
    saved = ExperimentStorage.save_run_trace(trace, exp_dir)
    assert saved.exists()

    completed = ExperimentStorage.get_completed_run_ids(exp_dir)
    assert "run_task_001_m1_s42" in completed

    reloaded_manifest = ExperimentStorage.load_manifest(exp_dir)
    assert "run_task_001_m1_s42" in reloaded_manifest.completed_runs


def test_failure_taxonomy_classification():
    c, d = classify_trace_failure("subprocess timeout", False, True, False, True, "FAILED")
    assert c == FailureCategory.TIMEOUT

    c, d = classify_trace_failure(None, False, True, False, True, "FAILED")
    assert c == FailureCategory.AGENT_FAILURE

    c, d = classify_trace_failure(None, True, False, False, True, "FAILED")
    assert c == FailureCategory.INVALID_PATCH

    c, d = classify_trace_failure(None, True, True, True, True, "FAILED")
    assert c == FailureCategory.ORACLE_FAILURE

    c, d = classify_trace_failure(None, True, True, True, False, "QUALIFIED")
    assert c == FailureCategory.SUCCESS
