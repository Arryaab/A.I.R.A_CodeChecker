from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from aegis.runner import TestResult
from aegis.validator import ValidationResult


class FailureType(str, Enum):
    WRONG_DIAGNOSIS = "wrong_diagnosis"
    INCOMPLETE_REPAIR = "incomplete_repair"
    REGRESSION = "regression"
    INVALID_PYTHON = "invalid_python"
    TEST_OVERFITTING = "test_overfitting"
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


@dataclass
class FailureRecord:
    failure_type: FailureType
    description: str
    details: dict = field(default_factory=dict)


def classify_failure(
    *,
    visible_result: TestResult | None = None,
    hidden_result: TestResult | None = None,
    validation: ValidationResult | None = None,
    original_result: TestResult | None = None,
    error: Exception | None = None,
) -> FailureRecord:
    """Classify a repair failure into a taxonomy category."""
    if error is not None:
        if isinstance(error, TimeoutError):
            return FailureRecord(
                failure_type=FailureType.TIMEOUT,
                description="Process timed out",
                details={"error": str(error)}
            )

    if validation is not None and not validation.valid:
        return FailureRecord(
            failure_type=FailureType.INVALID_PYTHON,
            description="Generated patch contains invalid Python syntax or fails validation",
            details={"errors": validation.errors}
        )

    if visible_result is not None:
        # Check for infrastructure failure
        if 2 <= visible_result.exit_code <= 5:
            return FailureRecord(
                failure_type=FailureType.INFRASTRUCTURE_FAILURE,
                description="Pytest infrastructure or usage error",
                details={"exit_code": visible_result.exit_code, "stderr": visible_result.stderr}
            )

        if visible_result.passed and hidden_result is not None and not hidden_result.passed:
            return FailureRecord(
                failure_type=FailureType.TEST_OVERFITTING,
                description="Fix passes visible tests but fails hidden tests",
                details={"hidden_errors": hidden_result.failure_messages}
            )

        if not visible_result.passed and original_result is not None:
            # Check for regression (broke passing tests)
            new_failures = set(visible_result.failure_messages) - set(original_result.failure_messages)
            if new_failures:
                return FailureRecord(
                    failure_type=FailureType.REGRESSION,
                    description="Fix caused previously passing tests to fail",
                    details={"new_failures": list(new_failures)}
                )

            # Check if diagnosis is wrong vs incomplete repair
            if set(visible_result.failure_messages) == set(original_result.failure_messages):
                return FailureRecord(
                    failure_type=FailureType.WRONG_DIAGNOSIS,
                    description="Tests still fail with exactly the same errors",
                    details={"failures": visible_result.failure_messages}
                )
            else:
                return FailureRecord(
                    failure_type=FailureType.INCOMPLETE_REPAIR,
                    description="Tests still fail but errors have changed",
                    details={"failures": visible_result.failure_messages}
                )

    return FailureRecord(
        failure_type=FailureType.UNKNOWN,
        description="Could not determine failure cause",
        details={}
    )
