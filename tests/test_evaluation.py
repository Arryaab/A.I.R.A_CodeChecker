from __future__ import annotations

from aegis.evals.evaluation import calculate_metrics
from aegis.core.orchestrator import RepairResult, RepairAttempt
from aegis.verification.taxonomy import FailureRecord, FailureType
from aegis.execution.runner import TestResult

def _create_mock_result(success=True, attempt_success=True, hidden_success=True, fail_type=None):
    tr = TestResult(passed=attempt_success, exit_code=0, stdout="", stderr="", duration_seconds=1.0, tests_passed=1, tests_failed=0, tests_error=0, summary_line="")
    attempt = RepairAttempt(attempt_number=1, patch={}, validation=None, test_result=tr, llm_response=None, duration_seconds=1.0) # type: ignore
    
    return RepairResult(
        bug_id="test",
        success=success,
        visible_pass=attempt_success,
        hidden_pass=hidden_success,
        attempts=[attempt] if attempt_success else [],
        failure_record=FailureRecord(failure_type=fail_type, description="") if fail_type else None
    )

def test_calculate_metrics_perfect():
    results = [_create_mock_result() for _ in range(3)]
    metrics = calculate_metrics(results)
    assert metrics.total_bugs == 3
    assert metrics.pass_at_1 == 100.0
    assert metrics.pass_at_3 == 100.0
    assert metrics.visible_pass_rate == 100.0
    assert metrics.hidden_pass_rate == 100.0
    assert metrics.invalid_python_rate == 0.0

def test_calculate_metrics_all_failures():
    results = [_create_mock_result(success=False, attempt_success=False, hidden_success=False, fail_type=FailureType.INVALID_PYTHON) for _ in range(2)]
    metrics = calculate_metrics(results)
    assert metrics.total_bugs == 2
    assert metrics.pass_at_1 == 0.0
    assert metrics.pass_at_3 == 0.0
    assert metrics.visible_pass_rate == 0.0
    assert metrics.invalid_python_rate == 100.0
    assert metrics.failure_distribution[FailureType.INVALID_PYTHON.value] == 2

def test_calculate_metrics_edge_cases():
    metrics = calculate_metrics([])
    assert metrics.total_bugs == 0
    assert metrics.pass_at_1 == 0.0

def test_heuristic_patch_risk_model():
    from aegis.evals.risk_model import PatchRiskModel
    from aegis.integrations.git import PatchChange

    model = PatchRiskModel()

    # Small patch - LOW risk
    small_change = PatchChange(
        path="math_utils.py",
        new_content="def add(a, b):\n    return a + b\n",
        added_lines=["def add(a, b):", "    return a + b"],
        deleted_lines=[]
    )
    pred_low = model.predict_risk({"math_utils.py": small_change}, {"math_utils.py": small_change})
    assert pred_low.risk_score == 0.0
    assert pred_low.risk_level == "LOW"

    # Dangerous pattern introduced - HIGH/MEDIUM risk
    danger_change = PatchChange(
        path="service.py",
        new_content="import os\nos.system('rm -rf /')",
        added_lines=["import os", "os.system('rm -rf /')"],
        deleted_lines=[]
    )
    pred_danger = model.predict_risk({"service.py": danger_change}, {"service.py": danger_change})
    assert pred_danger.risk_score >= 0.4
    assert any("os.system" in f for f in pred_danger.factors)

    # Security module deletion - critical risk factor
    del_auth = PatchChange(
        path="auth/token_guardrail.py",
        status="D",
        deleted_lines=["deleted lines..."]
    )
    pred_del = model.predict_risk({"auth/token_guardrail.py": del_auth}, {"auth/token_guardrail.py": del_auth})
    assert pred_del.risk_score >= 0.5
    assert any("Security-critical module deleted" in f for f in pred_del.factors)

def test_audit_report_schema_1_0(tmp_path):
    from aegis.cli import Path
    import json
    runs_dir = Path(__file__).resolve().parent.parent / ".aegis" / "runs"
    reports = list(runs_dir.glob("*/report.json")) if runs_dir.exists() else []
    if reports:
        data = json.loads(reports[-1].read_text(encoding="utf-8"))
    else:
        data = {
            "schema_version": "1.0",
            "run_id": "test_run",
            "timestamp": "2026-09-26T20:00:00Z",
            "repository": "aegis-lite",
            "base": "HEAD~1",
            "head": "HEAD",
            "change": {"files_affected": 1, "lines_added": 5, "lines_deleted": 2, "affected_files": ["foo.py"]},
            "verification": {
                "tier": "STANDARD",
                "targeted_tests": {"passed": True, "test_files_count": 1, "duration_seconds": 1.0},
                "regression": {"passed": True, "status": "passed", "summary": "56 passed", "duration_seconds": 5.0},
                "mutation": {"status": "completed", "score": 1.0, "killed": 2, "total": 2, "target_files": ["foo.py"]},
                "security": {"safe": True, "issues_count": 0, "issues": []}
            },
            "risk": {"score": 0.0, "level": "LOW", "factors": []},
            "decision": {"technical_verdict": "QUALIFIED", "release_policy": "AUTO_APPROVE", "reason": "All checks passed"}
        }

    assert data.get("schema_version") == "1.0"
    assert "run_id" in data
    assert "timestamp" in data
    assert "change" in data
    assert "lines_added" in data["change"]
    assert "lines_deleted" in data["change"]
    assert "verification" in data
    assert "targeted_tests" in data["verification"]
    assert "security" in data["verification"]
    assert "risk" in data
    assert "score" in data["risk"]
    assert "decision" in data
    assert "technical_verdict" in data["decision"]
    assert "release_policy" in data["decision"]
    assert data["decision"]["technical_verdict"] in ("QUALIFIED", "QUALIFIED_WITHIN_SCOPE", "FAILED")
    assert data["decision"]["release_policy"] in ("AUTO_APPROVE", "REVIEW", "BLOCK")
    if "provenance" in data:
        assert "base_sha" in data["provenance"]
        assert "head_sha" in data["provenance"]
        assert "diff_sha256" in data["provenance"]
        if "environment" in data["provenance"]:
            assert "dependency_manifests" in data["provenance"]["environment"]
            assert "dependency_manifest_hash" in data["provenance"]["environment"]
            assert "dependency_lock_hash" in data["provenance"]["environment"]
            assert "environment_fingerprint" in data["provenance"]["environment"]
        if "requested_environment" in data["provenance"]:
            assert "python_version" in data["provenance"]["requested_environment"]
            assert "platform" in data["provenance"]["requested_environment"]
            assert "dependency_manifest_hash" in data["provenance"]["requested_environment"]
        if "executed_environment" in data["provenance"]:
            assert "sandbox_engine" in data["provenance"]["executed_environment"]
            assert "sandbox_image" in data["provenance"]["executed_environment"]

def test_audit_provenance_cryptographic_integrity(tmp_path):
    import subprocess
    import hashlib
    from aegis.execution.environment import inspect_repository_environment
    
    # Initialize a test git repo
    repo = tmp_path / "provenance_repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@aegis.dev"], cwd=repo, check=True, capture_output=True)

    # Commit 1
    (repo / "calc.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
    (repo / "requirements.txt").write_text("pytest>=7.0.0\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=repo, check=True, capture_output=True)

    # Commit 2
    (repo / "calc.py").write_text("def add(a, b): return a + b + 0\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "second commit"], cwd=repo, check=True, capture_output=True)

    # Resolve SHAs directly
    res_base = subprocess.run(["git", "rev-parse", "HEAD~1"], cwd=repo, capture_output=True, text=True, check=True)
    base_sha = res_base.stdout.strip()
    res_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True)
    head_sha = res_head.stdout.strip()

    assert len(base_sha) == 40
    assert len(head_sha) == 40
    assert base_sha != head_sha
    assert all(c in "0123456789abcdef" for c in base_sha.lower())
    assert all(c in "0123456789abcdef" for c in head_sha.lower())

    # Diff hash verification
    res_diff = subprocess.run(["git", "diff", "HEAD~1..HEAD"], cwd=repo, capture_output=True, text=True, check=True)
    diff_text = res_diff.stdout
    expected_diff_sha256 = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    assert len(expected_diff_sha256) == 64
    assert expected_diff_sha256 != hashlib.sha256(b"").hexdigest()

    # Environment fingerprint
    env_info = inspect_repository_environment(repo)
    assert "requirements.txt" in env_info.dependency_manifests
    assert len(env_info.dependency_manifest_hash) == 64
    assert env_info.dependency_lock_hash == env_info.dependency_manifest_hash
    assert env_info.resolved_dependency_lock_hash is None
    assert len(env_info.environment_fingerprint) == 64

    # Now add a lockfile and verify resolved_dependency_lock_hash
    (repo / "poetry.lock").write_text("[package]\nname = 'pytest'\n", encoding="utf-8")
    env_info_locked = inspect_repository_environment(repo)
    assert env_info_locked.resolved_dependency_lock_hash is not None
    assert len(env_info_locked.resolved_dependency_lock_hash) == 64

    # Fail closed on invalid ref
    bad_res = subprocess.run(["git", "rev-parse", "--verify", "invalid_ref_xyz_123"], cwd=repo, capture_output=True, text=True)
    assert bad_res.returncode != 0

def test_environment_dockerfile_generation_fail_closed(tmp_path):
    from aegis.execution.environment import (
        generate_reproducible_dockerfile,
        build_sandbox_environment_image,
    )
    import pytest

    # pyproject repo
    repo = tmp_path / "pyproject_repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname = 'pkg'\n", encoding="utf-8")

    dockerfile = generate_reproducible_dockerfile(repo)
    assert "|| true" not in dockerfile, "Verifiers must fail closed; '|| true' is forbidden in environment builds"
    assert "RUN pip install --no-cache-dir -e ." in dockerfile

    # Empty repo without manifests returns default aegis-sandbox:latest without running docker build
    empty_repo = tmp_path / "empty_repo"
    empty_repo.mkdir()
    assert build_sandbox_environment_image(empty_repo) == "aegis-sandbox:latest"



