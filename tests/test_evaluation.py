from __future__ import annotations

from aegis.evaluation import calculate_metrics
from aegis.repair import RepairResult, RepairAttempt
from aegis.taxonomy import FailureRecord, FailureType
from aegis.runner import TestResult

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
