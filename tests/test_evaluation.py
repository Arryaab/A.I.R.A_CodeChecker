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

def test_audit_report_schema_1_0():
    from aegis.cli import Path
    import json
    report_file = Path(__file__).resolve().parent.parent / "aegis-report.json"
    if report_file.exists():
        data = json.loads(report_file.read_text(encoding="utf-8"))
        assert data.get("schema_version") == "1.0"
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
        assert data["decision"]["technical_verdict"] in ("QUALIFIED", "FAILED")
        assert data["decision"]["release_policy"] in ("AUTO_APPROVE", "REVIEW", "BLOCK")


