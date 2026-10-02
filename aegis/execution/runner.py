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
    tests_skipped: int = 0
    tests_xfailed: int = 0
    tests_xpassed: int = 0
    total_collected: int = 0
    total_executed: int = 0
    test_outcomes: dict[str, str] = field(default_factory=dict)
    failed_test_details: dict[str, str] = field(default_factory=dict)
    executed_nodeids: list[str] = field(default_factory=list)
    passed_nodeids: list[str] = field(default_factory=list)
    failed_nodeids: list[str] = field(default_factory=list)
    error_nodeids: list[str] = field(default_factory=list)
    skipped_nodeids: list[str] = field(default_factory=list)
    collection_error_count: int = 0
    collection_error_nodeids: list[str] = field(default_factory=list)
    collection_errors_details: dict[str, str] = field(default_factory=dict)
    raw_junit_testcase_count: int = 0
    unique_junit_testcase_count: int = 0

    def __post_init__(self):
        if self.total_executed == 0 and (self.tests_passed or self.tests_failed or self.tests_error):
            self.total_executed = self.tests_passed + self.tests_failed + self.tests_error + self.tests_xpassed + self.tests_xfailed


def parse_junit_xml(xml_content: str) -> dict:
    """Authoritative parser for pytest JUnit XML output.
    Separates four distinct states:
    1. collected_tests (from valid testcases)
    2. collection_errors (from collection failure testcases)
    3. executed_tests (passed + failed + runtime error + skipped)
    4. execution_results (outcomes and details per node)

    Never counts collection errors as executed tests.
    Guarantees: passed + failures + errors == total_executed.
    Skipped tests are NOT counted as executed (executed + skipped == total_collected).
    """
    import xml.etree.ElementTree as ET
    from pathlib import Path

    outcomes: dict[str, str] = {}
    failed_details: dict[str, str] = {}
    failure_messages: list[str] = []
    executed_nodeids: list[str] = []
    passed_nodeids: list[str] = []
    failed_nodeids: list[str] = []
    error_nodeids: list[str] = []
    skipped_nodeids: list[str] = []
    collection_error_nodeids: list[str] = []
    collection_errors_details: dict[str, str] = {}
    collection_error_messages: list[str] = []

    try:
        root = ET.fromstring(xml_content)
    except Exception as e:
        logger.warning(f"Failed to parse JUnit XML: {e}")
        return {
            "tests_passed": 0, "tests_failed": 0, "tests_error": 0, "tests_skipped": 0,
            "tests_xfailed": 0, "tests_xpassed": 0, "total_collected": 0, "total_executed": 0,
            "collection_error_count": 0, "collection_error_nodeids": [], "collection_errors_details": {},
            "raw_junit_testcase_count": 0, "unique_junit_testcase_count": 0,
            "test_outcomes": {}, "failed_test_details": {}, "failure_messages": [],
            "executed_nodeids": [], "passed_nodeids": [], "failed_nodeids": [],
            "error_nodeids": [], "skipped_nodeids": []
        }

    suites = list(root.iter("testsuite"))
    if not suites and root.tag == "testsuite":
        suites = [root]

    all_testcase_elements = list(root.iter("testcase"))
    raw_junit_testcase_count = len(all_testcase_elements)
    all_parsed_nodeids: list[str] = []

    for tc in all_testcase_elements:
        name = tc.attrib.get("name", "")
        file_attr = tc.attrib.get("file")
        classname = tc.attrib.get("classname", "")

        fail_child = tc.find("failure")
        err_child = tc.find("error")
        skip_child = tc.find("skipped")

        # Check for pytest collection failure
        is_collection_error = False
        is_collection_skipped = False

        if err_child is not None:
            err_msg = (err_child.attrib.get("message") or "").strip().lower()
            err_text = (err_child.text or "").strip().lower()
            if "collection failure" in err_msg or "collection failure" in err_text:
                is_collection_error = True
            elif "error collecting" in err_msg or "error collecting" in err_text:
                is_collection_error = True
            elif "failed to collect" in err_msg or "failed to collect" in err_text:
                is_collection_error = True
            elif classname == "":
                # In pytest JUnit XML, real executed tests ALWAYS have a non-empty
                # classname (module.path or module.path.ClassName). A testcase with
                # classname="" and an <error> child is ALWAYS a collection failure —
                # the test was never instantiated, so pytest has no class to report.
                is_collection_error = True

        if skip_child is not None:
            skip_msg = (skip_child.attrib.get("message") or "").strip().lower()
            skip_text = (skip_child.text or "").strip().lower()
            if "collection skipped" in skip_msg or "collection skipped" in skip_text:
                is_collection_skipped = True

        # Derive node ID
        if file_attr:
            norm_file = file_attr.replace("\\", "/")
            if norm_file.startswith("/workspace/"):
                norm_file = norm_file[len("/workspace/"):]
            elif norm_file.startswith("./"):
                norm_file = norm_file[2:]

            stem = Path(norm_file).stem
            if classname and stem in classname and not classname.endswith(stem):
                class_part = classname.split(".")[-1]
                node_id = f"{norm_file}::{class_part}::{name}"
            elif name and name != stem:
                node_id = f"{norm_file}::{name}"
            else:
                node_id = norm_file
        elif classname:
            parts = classname.split(".")
            if len(parts) > 1 and parts[-1] and parts[-1][0].isupper():
                file_part = "/".join(parts[:-1]) + ".py"
                node_id = f"{file_part}::{parts[-1]}::{name}"
            else:
                file_part = "/".join(parts) + ".py"
                node_id = f"{file_part}::{name}"
        else:
            norm_name = name.replace(".", "/").replace("\\", "/")
            if not norm_name.endswith(".py"):
                norm_name += ".py"
            node_id = norm_name

        all_parsed_nodeids.append(node_id)

        if is_collection_error or is_collection_skipped:
            child = err_child if err_child is not None else skip_child
            msg = child.attrib.get("message") or (child.text or "").strip() or ("Collection skipped" if is_collection_skipped else "Collection failure")
            collection_error_nodeids.append(node_id)
            collection_errors_details[node_id] = msg[:300]
            collection_error_messages.append(f"{node_id}: {msg[:200]}")
            # DO NOT count in executed_nodeids!
            continue

        # Classify the testcase outcome
        if fail_child is not None:
            msg = fail_child.attrib.get("message") or (fail_child.text or "").strip() or "Test failed"
            outcomes[node_id] = "FAILED"
            failed_details[node_id] = msg[:200]
            failure_messages.append(f"{node_id}: {msg[:200]}")
            failed_nodeids.append(node_id)
            executed_nodeids.append(node_id)
        elif err_child is not None:
            msg = err_child.attrib.get("message") or (err_child.text or "").strip() or "Test execution error"
            outcomes[node_id] = "ERROR"
            failed_details[node_id] = msg[:200]
            failure_messages.append(f"{node_id}: {msg[:200]}")
            error_nodeids.append(node_id)
            executed_nodeids.append(node_id)
        elif skip_child is not None:
            # Skipped tests are NOT executed — they are selected but intentionally not run.
            outcomes[node_id] = "SKIPPED"
            skipped_nodeids.append(node_id)
        else:
            outcomes[node_id] = "PASSED"
            passed_nodeids.append(node_id)
            executed_nodeids.append(node_id)

    failures = len(failed_nodeids)
    errors = len(error_nodeids)
    skipped = len(skipped_nodeids)
    passed = len(passed_nodeids)
    total_executed = len(executed_nodeids)  # = passed + failed + errors (NOT skipped)
    collection_errors = len(collection_error_nodeids)
    total_collected = total_executed + skipped  # collected = executed + skipped

    return {
        "tests_passed": passed,
        "tests_failed": failures,
        "tests_error": errors,
        "tests_skipped": skipped,
        "tests_xfailed": 0,
        "tests_xpassed": 0,
        "total_collected": total_collected,
        "total_executed": total_executed,
        "raw_junit_testcase_count": raw_junit_testcase_count,
        "unique_junit_testcase_count": len(set(all_parsed_nodeids)),
        "collection_error_count": collection_errors,
        "collection_error_nodeids": collection_error_nodeids,
        "collection_errors_details": collection_errors_details,
        "collection_error_messages": collection_error_messages,
        "test_outcomes": outcomes,
        "failed_test_details": failed_details,
        "failure_messages": failure_messages,
        "executed_nodeids": executed_nodeids,
        "passed_nodeids": passed_nodeids,
        "failed_nodeids": failed_nodeids,
        "error_nodeids": error_nodeids,
        "skipped_nodeids": skipped_nodeids,
    }


def run_tests(
    project_dir: str | Path,
    timeout: int = 60,
    test_files: list[str] | None = None
) -> TestResult:
    """Run pytest on a project directory and return authoritative structured results.
    Uses --junitxml for deterministic test accounting.
    """
    import sys
    import tempfile
    project_path = Path(project_dir).resolve()

    if not project_path.is_dir():
        raise FileNotFoundError(f"Project directory not found: {project_path}")

    junit_tmp = Path(tempfile.NamedTemporaryFile(suffix=".xml", delete=False).name)
    cmd = [
        sys.executable, "-m", "pytest",
        "-v",
        "--tb=short",
        "--color=no",
        "-p", "no:cacheprovider",
        f"--junitxml={junit_tmp}",
    ]
    if test_files:
        cmd.extend(test_files)

    start = time.monotonic()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(project_path),
        )
    except subprocess.TimeoutExpired as exc:
        junit_tmp.unlink(missing_ok=True)
        raise TimeoutError(
            f"Test run exceeded {timeout}s timeout in {project_path}"
        ) from exc

    elapsed = time.monotonic() - start

    parsed = None
    if junit_tmp.exists() and junit_tmp.stat().st_size > 0:
        try:
            xml_text = junit_tmp.read_text(encoding="utf-8", errors="ignore")
            parsed = parse_junit_xml(xml_text)
        except Exception:
            parsed = None
        finally:
            junit_tmp.unlink(missing_ok=True)

    if not parsed or (parsed.get("total_executed", 0) == 0 and result.returncode != 0):
        text_parsed = _parse_structured_test_results(result.stdout)
        if not parsed or text_parsed.get("total_executed", 0) > parsed.get("total_executed", 0):
            parsed = text_parsed

    summary_line = _extract_summary_line(result.stdout)
    failure_messages = parsed.get("failure_messages") or _extract_failures(result.stdout)

    return TestResult(
        passed=(result.returncode == PYTEST_EXIT_OK),
        exit_code=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_seconds=round(elapsed, 3),
        tests_passed=parsed["tests_passed"],
        tests_failed=parsed["tests_failed"],
        tests_error=parsed["tests_error"],
        tests_skipped=parsed["tests_skipped"],
        tests_xfailed=parsed.get("tests_xfailed", 0),
        tests_xpassed=parsed.get("tests_xpassed", 0),
        total_collected=parsed.get("total_collected", 0),
        total_executed=parsed["total_executed"],
        test_outcomes=parsed["test_outcomes"],
        failed_test_details=parsed["failed_test_details"],
        summary_line=summary_line,
        failure_messages=failure_messages,
        executed_nodeids=parsed.get("executed_nodeids", []),
        passed_nodeids=parsed.get("passed_nodeids", []),
        failed_nodeids=parsed.get("failed_nodeids", []),
        error_nodeids=parsed.get("error_nodeids", []),
        skipped_nodeids=parsed.get("skipped_nodeids", []),
        collection_error_count=parsed.get("collection_error_count", 0),
        collection_error_nodeids=parsed.get("collection_error_nodeids", []),
        collection_errors_details=parsed.get("collection_errors_details", {}),
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


def _parse_structured_test_results(stdout: str) -> dict:
    """Authoritative parser for pytest and unittest output.
    Reconciles individual test items, summary lines, and failure details.
    """
    outcomes: dict[str, str] = {}
    failed_details: dict[str, str] = {}

    # 1. Parse individual verbose items: e.g. "test_calc.py::test_add PASSED [ 33%]"
    item_pattern = re.compile(r"^(\S+::\S+)\s+(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)", re.MULTILINE)
    for node_id, status in item_pattern.findall(stdout):
        outcomes[node_id] = status

    # 2. Parse short summary failure info: e.g. "FAILED test_calc.py::test_zero - Failed: DID NOT RAISE ..."
    summary_pattern = re.compile(r"^(?:FAILED|ERROR)\s+(\S+::\S+)\s*(?:-\s*(.*))?$", re.MULTILINE)
    for match in summary_pattern.finditer(stdout):
        node_id = match.group(1)
        detail = (match.group(2) or "").strip()
        failed_details[node_id] = detail or "Test failed"

    # 3. Parse summary line metrics
    reg_passed = reg_failed = reg_error = reg_skipped = reg_xfailed = reg_xpassed = 0
    m = re.search(r"(\d+)\s+passed", stdout)
    if m: reg_passed = int(m.group(1))
    m = re.search(r"(\d+)\s+failed", stdout)
    if m: reg_failed = int(m.group(1))
    m = re.search(r"(\d+)\s+error(?:s)?", stdout)
    if m: reg_error = int(m.group(1))
    m = re.search(r"(\d+)\s+skipped", stdout)
    if m: reg_skipped = int(m.group(1))
    m = re.search(r"(\d+)\s+xfailed", stdout)
    if m: reg_xfailed = int(m.group(1))
    m = re.search(r"(\d+)\s+xpassed", stdout)
    if m: reg_xpassed = int(m.group(1))

    # Parse collected count
    reg_collected = 0
    m = re.search(r"collected\s+(\d+)\s+items|(\d+)\s+tests?\s+collected", stdout)
    if m:
        reg_collected = int(m.group(1) or m.group(2))

    # Fallback for unittest: "Ran N tests in Xs"
    m_unittest = re.search(r"Ran\s+(\d+)\s+tests?", stdout)
    if m_unittest:
        reg_collected = max(reg_collected, int(m_unittest.group(1)))
        m_u_fail = re.search(r"FAILED\s*\((?:failures=(\d+))?(?:,?\s*errors=(\d+))?\)", stdout)
        if m_u_fail:
            reg_failed = int(m_u_fail.group(1) or 0)
            reg_error = int(m_u_fail.group(2) or 0)
            reg_passed = max(0, reg_collected - reg_failed - reg_error)
        elif "OK" in stdout:
            reg_passed = reg_collected

    # Reconcile individual items vs summary line
    passed = max(sum(1 for s in outcomes.values() if s == "PASSED"), reg_passed)
    failed = max(sum(1 for s in outcomes.values() if s == "FAILED"), reg_failed)
    error = max(sum(1 for s in outcomes.values() if s == "ERROR"), reg_error)
    skipped = max(sum(1 for s in outcomes.values() if s == "SKIPPED"), reg_skipped)
    xfailed = max(sum(1 for s in outcomes.values() if s == "XFAIL"), reg_xfailed)
    xpassed = max(sum(1 for s in outcomes.values() if s == "XPASS"), reg_xpassed)

    total_executed = passed + failed + error
    total_collected = max(reg_collected, len(outcomes), total_executed + skipped)

    return {
        "tests_passed": passed,
        "tests_failed": failed,
        "tests_error": error,
        "tests_skipped": skipped,
        "tests_xfailed": xfailed,
        "tests_xpassed": xpassed,
        "total_collected": total_collected,
        "total_executed": total_executed,
        "test_outcomes": outcomes,
        "failed_test_details": failed_details,
    }


def _parse_counts(stdout: str) -> tuple[int, int, int]:
    """Extract pass/fail/error counts from pytest's summary line."""
    parsed = _parse_structured_test_results(stdout)
    return parsed["tests_passed"], parsed["tests_failed"], parsed["tests_error"]


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
