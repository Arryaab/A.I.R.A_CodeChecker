from __future__ import annotations

import dataclasses
from aegis.verification.taxonomy import classify_failure, FailureType, FailureRecord
from aegis.execution.runner import TestResult
from aegis.verification.validator import ValidationResult


def make_test_result(passed: bool, exit_code: int = 0, messages: list[str] | None = None) -> TestResult:
    return TestResult(
        passed=passed,
        exit_code=exit_code,
        stdout="",
        stderr="",
        duration_seconds=1.0,
        tests_passed=1 if passed else 0,
        tests_failed=0 if passed else 1,
        tests_error=0,
        summary_line="summary",
        failure_messages=messages or []
    )


def test_classify_timeout():
    record = classify_failure(error=TimeoutError("timeout"))
    assert record.failure_type == FailureType.TIMEOUT


def test_classify_invalid_python():
    record = classify_failure(validation=ValidationResult(valid=False, errors=["SyntaxError"]))
    assert record.failure_type == FailureType.INVALID_PYTHON


def test_classify_infrastructure_failure():
    result = make_test_result(False, exit_code=2)
    record = classify_failure(visible_result=result)
    assert record.failure_type == FailureType.INFRASTRUCTURE_FAILURE


def test_classify_test_overfitting():
    visible = make_test_result(True)
    hidden = make_test_result(False, messages=["Hidden test failed"])
    record = classify_failure(visible_result=visible, hidden_result=hidden)
    assert record.failure_type == FailureType.TEST_OVERFITTING


def test_classify_regression():
    original = make_test_result(False, messages=["Bug 1"])
    visible = make_test_result(False, messages=["Bug 1", "Regression bug"])
    record = classify_failure(visible_result=visible, original_result=original)
    assert record.failure_type == FailureType.REGRESSION


def test_classify_wrong_diagnosis():
    original = make_test_result(False, messages=["Bug 1"])
    visible = make_test_result(False, messages=["Bug 1"])
    record = classify_failure(visible_result=visible, original_result=original)
    assert record.failure_type == FailureType.WRONG_DIAGNOSIS


def test_classify_incomplete_repair():
    original = make_test_result(False, messages=["Bug 1", "Bug 2"])
    visible = make_test_result(False, messages=["Bug 1"])
    record = classify_failure(visible_result=visible, original_result=original)
    assert record.failure_type == FailureType.INCOMPLETE_REPAIR


def test_classify_unknown():
    record = classify_failure()
    assert record.failure_type == FailureType.UNKNOWN


def test_failure_record_serialization():
    record = FailureRecord(failure_type=FailureType.TIMEOUT, description="timeout", details={})
    d = dataclasses.asdict(record)
    assert d["failure_type"] == "timeout"
    assert d["description"] == "timeout"
    assert d["details"] == {}
