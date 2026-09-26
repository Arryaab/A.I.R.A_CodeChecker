"""Test runner for Aegis-Lite.

Runs pytest against a target project directory and returns structured
results including pass/fail status, exit code, captured output, timing,
and extracted failure information.

This module is the foundation of the entire repair loop. Every later
stage — LLM interaction, patching, retry, evaluation — depends on
this module producing clean, structured test results.

Design note: We use subprocess to invoke pytest rather than pytest's
Python API. This matters because in later stages, tests will run
inside Docker containers. Subprocess is the right abstraction level
since it generalizes to "run a command somewhere and capture output."
"""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path


# Pytest exit codes (from pytest documentation).
# We define these as constants so the rest of the codebase can reference
# them by name instead of remembering magic numbers.
PYTEST_EXIT_OK = 0              # All tests passed
PYTEST_EXIT_TESTS_FAILED = 1    # Some tests failed
PYTEST_EXIT_INTERRUPTED = 2     # Test run was interrupted
PYTEST_EXIT_INTERNAL_ERROR = 3  # Internal pytest error
PYTEST_EXIT_USAGE_ERROR = 4     # Command-line usage error
PYTEST_EXIT_NO_TESTS = 5       # No tests were collected


@dataclass
class TestResult:
    """Structured result from a single pytest run."""
    __test__ = False

    passed: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    tests_passed: int
    tests_failed: int
    tests_error: int
    summary_line: str
    failure_messages: list[str] = field(default_factory=list)


def run_tests(
    project_dir: str | Path,
    timeout: int = 60,
    test_files: list[str] | None = None
) -> TestResult:
    """Run pytest on a project directory and return structured results.
    If test_files is specified, runs ONLY those specific test files.
    """
    import sys
    # Resolve to an absolute path so error messages are unambiguous.
    project_path = Path(project_dir).resolve()

    if not project_path.is_dir():
        raise FileNotFoundError(f"Project directory not found: {project_path}")

    # Build the pytest command.
    cmd = [
        sys.executable, "-m", "pytest",
        "-v",
        "--tb=short",
        "--color=no",
        "-p", "no:cacheprovider",
    ]
    if test_files:
        cmd.extend(test_files)

    # time.monotonic() is used instead of time.time() because it
    # cannot go backwards due to system clock adjustments (NTP, DST, etc.).
    start = time.monotonic()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,  # Capture both stdout and stderr.
            text=True,            # Decode output as UTF-8 strings.
            timeout=timeout,
            cwd=str(project_path),  # Run pytest FROM the project directory.
        )
    except subprocess.TimeoutExpired as exc:
        # Re-raise as a standard TimeoutError with a clear message.
        raise TimeoutError(
            f"Test run exceeded {timeout}s timeout in {project_path}"
        ) from exc

    elapsed = time.monotonic() - start

    # Parse structured information from pytest's text output.
    tests_passed, tests_failed, tests_error = _parse_counts(result.stdout)
    summary_line = _extract_summary_line(result.stdout)
    failure_messages = _extract_failures(result.stdout)

    return TestResult(
        passed=(result.returncode == PYTEST_EXIT_OK),
        exit_code=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_seconds=round(elapsed, 3),
        tests_passed=tests_passed,
        tests_failed=tests_failed,
        tests_error=tests_error,
        summary_line=summary_line,
        failure_messages=failure_messages,
    )


# ---------------------------------------------------------------------------
# Output parsing helpers
# ---------------------------------------------------------------------------
# These functions extract structured data from pytest's text output.
# We parse text rather than using a pytest plugin because:
#   1. It keeps our dependency list minimal (just pytest itself).
#   2. It works identically when pytest runs inside Docker later.
#   3. The text format is stable across pytest versions.
# ---------------------------------------------------------------------------


def _parse_counts(stdout: str) -> tuple[int, int, int]:
    """Extract pass/fail/error counts from pytest's summary line.

    Pytest prints a summary like:
        "2 passed, 1 failed in 0.05s"
    or:
        "1 passed in 0.02s"

    We use simple regex to pull out the numbers. If a category
    isn't mentioned (e.g., no errors), its count is 0.
    """
    passed = failed = error = 0

    match = re.search(r"(\d+) passed", stdout)
    if match:
        passed = int(match.group(1))

    match = re.search(r"(\d+) failed", stdout)
    if match:
        failed = int(match.group(1))

    match = re.search(r"(\d+) error", stdout)
    if match:
        error = int(match.group(1))

    return passed, failed, error


def _extract_summary_line(stdout: str) -> str:
    """Extract the final summary line from pytest output.

    This is the line that looks like:
        ========= 1 failed, 1 passed in 0.05s =========

    We strip the decoration (= signs) to get the clean text.
    """
    lines = stdout.strip().splitlines()

    # Walk backwards from the end to find the summary line.
    # It's always one of the last few lines and contains "passed",
    # "failed", or "error" along with a time measurement.
    for line in reversed(lines):
        stripped = line.strip()
        if stripped and ("passed" in stripped or "failed" in stripped
                         or "error" in stripped):
            # Remove leading/trailing '=' and whitespace.
            cleaned = stripped.strip("= ")
            if cleaned:
                return cleaned

    return ""


def _extract_failures(stdout: str) -> list[str]:
    """Extract individual failure blocks from pytest output.

    With --tb=short, pytest output looks like:

        ================================ FAILURES ================================
        _________________________ test_subtract __________________________
        test_mathlib.py:8: in test_subtract
            assert subtract(10, 3) == 7
        E       AssertionError: assert 8 == 7
        E        +  where 8 = subtract(10, 3)
        ======================== short test summary info =========================
        FAILED test_mathlib.py::test_subtract - ...
        ===================== 1 failed, 1 passed in 0.03s ======================

    We extract each block between the '____' separators within the
    FAILURES section. Each block becomes one entry in the returned list.
    These blocks are what we will eventually send to the LLM for diagnosis.
    """
    failures: list[str] = []
    in_failures_section = False
    current_block: list[str] = []

    for line in stdout.splitlines():
        # Detect the start of the FAILURES section.
        if "FAILURES" in line and line.strip().startswith("="):
            in_failures_section = True
            continue

        if not in_failures_section:
            continue

        # Detect the end of the FAILURES section:
        # any line starting with "=" that isn't the FAILURES header.
        if line.strip().startswith("=") and "FAILURES" not in line:
            # Save the last block if we have one.
            if current_block:
                failures.append("\n".join(current_block).strip())
            break

        # Detect a new failure block separator (underscores line).
        if line.strip().startswith("_") and line.strip().endswith("_"):
            # Save the previous block (if any) and start a new one.
            if current_block:
                failures.append("\n".join(current_block).strip())
            current_block = []
            continue

        # Accumulate lines into the current failure block.
        current_block.append(line)

    return failures
