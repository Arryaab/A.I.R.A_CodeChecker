"""
Tests for real fixture archives and large repository test accounting integrity.
Verifies:
1. aira_test_project.zip: 3 discovered, 3 selected, 3 executed, 2 passed, 1 failed -> C2 FAIL, REJECTED
2. aira_security_test_project.zip: 2 passed, C6 FAIL on archive_utils.py (APPLICATION_CODE) -> REJECTED
3. Large/Real repository test accounting:
   - Pytest repo config respected
   - Discovered >= Selected >= Executed invariant holds
   - Security scanner classifies files properly into APPLICATION_CODE, TEST_CODE, FIXTURE, BENCHMARK, TOOLING
"""
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from aegis.api.service import app, RUNS_STORE, is_docker_available
from aegis.uploads.models import StageStatus
from aegis.uploads.detection import get_pytest_repo_config, discover_project_tests
from aegis.verification.security import SecurityScanner, classify_source_path

client = TestClient(app)
API_KEY = "test-secret-key-32-chars-minimum-length"
AUTH_HEADERS = {"X-API-Key": API_KEY}


def test_aira_test_project_calculator_accounting():
    zip_path = Path(r"C:\Users\aryab\Downloads\aira_test_project.zip")
    assert zip_path.exists(), "aira_test_project.zip must exist"

    with open(zip_path, "rb") as f:
        res = client.post(
            "/api/projects/upload",
            files={"archive": ("aira_test_project.zip", f, "application/zip")},
            headers=AUTH_HEADERS,
        )
    assert res.status_code == 201
    project_id = res.json()["project_id"]

    verify_res = client.post(
        f"/api/projects/{project_id}/verify",
        json={"tier": "standard", "run_project_tests": True, "run_security": True},
        headers=AUTH_HEADERS,
    )
    assert verify_res.status_code == 202
    run_id = verify_res.json()["run_id"]

    # Wait for completion (sync since background job runs in thread/process)
    import time
    for _ in range(60):
        run = RUNS_STORE.get(run_id, {})
        if run.get("status") in ("completed", "failed"):
            break
        time.sleep(1)

    assert run.get("status") == "completed"
    report = run.get("report")
    assert report is not None

    c2 = report["criteria"]["C2_visible_tests"]
    assert c2["discovered_count"] == 3
    assert c2["selected_count"] == 3
    assert c2["tests_executed"] == 3
    assert c2["tests_passed"] == 2
    assert c2["tests_failed"] == 1
    assert c2["status"] == StageStatus.FAIL.value

    # Failed test must be test_divide_by_zero
    assert any("test_divide_by_zero" in ft for ft in c2["failed_tests"])

    # Final verdict must be REJECTED
    assert report["decision"]["technical_verdict"] == "REJECTED"
    assert report["decision"]["release_policy"] == "BLOCK"

    client.delete(f"/api/projects/{project_id}", headers=AUTH_HEADERS)


def test_aira_security_test_project_accounting():
    zip_path = Path(r"C:\Users\aryab\Downloads\aira_security_test_project.zip")
    assert zip_path.exists(), "aira_security_test_project.zip must exist"

    with open(zip_path, "rb") as f:
        res = client.post(
            "/api/projects/upload",
            files={"archive": ("aira_security_test_project.zip", f, "application/zip")},
            headers=AUTH_HEADERS,
        )
    assert res.status_code == 201
    project_id = res.json()["project_id"]

    verify_res = client.post(
        f"/api/projects/{project_id}/verify",
        json={"tier": "standard", "run_project_tests": True, "run_security": True},
        headers=AUTH_HEADERS,
    )
    assert verify_res.status_code == 202
    run_id = verify_res.json()["run_id"]

    import time
    for _ in range(60):
        run = RUNS_STORE.get(run_id, {})
        if run.get("status") in ("completed", "failed"):
            break
        time.sleep(1)

    assert run.get("status") == "completed"
    report = run.get("report")
    assert report is not None

    # Project tests pass
    c2 = report["criteria"]["C2_visible_tests"]
    assert c2["tests_passed"] == 2
    assert c2["tests_failed"] == 0

    # C6 security fails due to path traversal in application code archive_utils.py
    c6 = report["criteria"]["C6_security"]
    assert c6["status"] == StageStatus.FAIL.value
    assert len(c6.get("findings", [])) >= 1
    assert any("CWE-22" in str(f) or "path_traversal" in str(f).lower() for f in c6.get("findings", []))

    # Evidence must contain security table with source classification
    sec_table = report["evidence"]["security_table"]
    assert len(sec_table) >= 1
    app_findings = [f for f in sec_table if f["source_classification"] == "APPLICATION_CODE"]
    assert len(app_findings) >= 1

    # Final verdict must be REJECTED
    assert report["decision"]["technical_verdict"] == "REJECTED"
    assert report["decision"]["release_policy"] == "BLOCK"

    client.delete(f"/api/projects/{project_id}", headers=AUTH_HEADERS)


def test_repository_test_discovery_and_classification():
    repo_root = Path(__file__).parent.parent
    config = get_pytest_repo_config(repo_root)

    # testpaths should be ['tests']
    assert "tests" in config["testpaths"]

    # Discover repository tests
    nodeids = discover_project_tests(repo_root)
    # The repository authoritative test suite has 328+ tests
    assert len(nodeids) >= 300
    # Should not include tests/fixtures/projects/
    assert not any("tests/fixtures/projects" in nid for nid in nodeids)

    # Classification test
    assert classify_source_path("aegis/uploads/archive.py") == "APPLICATION_CODE"
    assert classify_source_path("tests/test_api.py") == "TEST_CODE"
    assert classify_source_path("tests/fixtures/projects/failing_test_project/string_utils.py") == "FIXTURE"
    assert classify_source_path("benchmarks/run_benchmark.py") == "BENCHMARK"
    assert classify_source_path("scripts/build.py") == "TOOLING"


def test_pytest_collection_authoritative():
    """Directive 10.1: pytest collection is authoritative, returning exact node IDs."""
    from aegis.execution.sandbox import parse_pytest_collection_output
    sample_output = """
test_calculator.py::test_add
test_calculator.py::test_divide
test_calculator.py::test_divide_by_zero

3 tests collected in 0.02s
"""
    nodes = parse_pytest_collection_output(sample_output)
    assert len(nodes) == 3
    assert nodes == [
        "test_calculator.py::test_add",
        "test_calculator.py::test_divide",
        "test_calculator.py::test_divide_by_zero"
    ]


def test_junit_xml_parser_authoritative():
    """Directive 10.2: JUnit XML result parsing is authoritative and preserves counts & node IDs."""
    from aegis.execution.runner import parse_junit_xml
    sample_xml = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="0" failures="1" skipped="1" tests="4" time="0.123">
    <testcase classname="tests.test_math" file="tests/test_math.py" name="test_add" time="0.001" />
    <testcase classname="tests.test_math" file="tests/test_math.py" name="test_sub" time="0.001" />
    <testcase classname="tests.test_math" file="tests/test_math.py" name="test_div" time="0.001">
      <failure message="ZeroDivisionError">ZeroDivisionError: division by zero</failure>
    </testcase>
    <testcase classname="tests.test_math" file="tests/test_math.py" name="test_skip" time="0.000">
      <skipped type="pytest.skip" message="unsupported">unsupported</skipped>
    </testcase>
  </testsuite>
</testsuites>
"""
    parsed = parse_junit_xml(sample_xml)
    assert parsed["tests_passed"] == 2
    assert parsed["tests_failed"] == 1
    assert parsed["tests_error"] == 0
    assert parsed["tests_skipped"] == 1
    assert parsed["total_executed"] == 3  # passed + failed + errors (NOT skipped)
    assert parsed["total_collected"] == 4  # executed + skipped
    # Invariant: passed + failed + errors == total_executed (skipped NOT included)
    assert parsed["tests_passed"] + parsed["tests_failed"] + parsed["tests_error"] == parsed["total_executed"]
    assert parsed["total_executed"] + parsed["tests_skipped"] == parsed["total_collected"]
    assert "tests/test_math.py::test_div" in parsed["failed_nodeids"]
    assert "tests/test_math.py::test_skip" in parsed["skipped_nodeids"]
    assert "tests/test_math.py::test_skip" not in parsed["executed_nodeids"]  # skipped != executed
    assert len(parsed["executed_nodeids"]) == 3


def test_count_invariants_cannot_become_impossible():
    """Directive 10.3: discovered/executed counts cannot become impossible (discovered < executed is blocked)."""
    from aegis.api.service import execute_project_verification_job, PROJECTS_STORE, RUNS_STORE
    from aegis.uploads.models import ProjectVerifyRequest, VerificationMode
    from unittest.mock import patch
    from aegis.execution.runner import TestResult
    from aegis.execution.sandbox import SandboxResult

    project_id = "proj_test_impossible_counts"
    PROJECTS_STORE[project_id] = {
        "project_id": project_id,
        "root_dir": "C:/dummy",
        "framework": "pytest",
        "discovered_tests": ["test_a.py::test_1"],
        "test_files": ["test_a.py"]
    }
    run_id = "run_impossible_counts"
    RUNS_STORE[run_id] = {"status": "queued", "events": []}

    req = ProjectVerifyRequest(mode=VerificationMode.PROJECT, run_project_tests=True, run_security=False)

    # Mock sandbox to report 5 executed when only 1 discovered
    mock_test_result = TestResult(
        passed=True, exit_code=0, stdout="", stderr="", duration_seconds=1.0,
        tests_passed=5, tests_failed=0, tests_error=0, summary_line="5 passed",
        total_executed=5,
        test_outcomes={f"test_{i}": "PASSED" for i in range(5)},
        passed_nodeids=[f"test_{i}" for i in range(5)],
        executed_nodeids=[f"test_{i}" for i in range(5)]
    )
    mock_sandbox_res = SandboxResult(test_result=mock_test_result, used_sandbox=True)

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-sandbox:latest"), \
         patch("aegis.execution.sandbox.collect_tests_sandboxed", return_value=["test_a.py::test_1"]), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", return_value=mock_sandbox_res):
        execute_project_verification_job(run_id, project_id, req)

    run = RUNS_STORE[run_id]
    report = run["report"]
    c2 = report["criteria"]["C2_visible_tests"]
    assert c2["status"] == StageStatus.ERROR.value
    assert "COUNT_INVARIANT_VIOLATION" in c2["detail"]
    assert report["decision"]["technical_verdict"] == "INDETERMINATE"
    assert report["decision"]["technical_verdict"] != "QUALIFIED"


def test_failed_tests_produce_c2_fail():
    """Directive 10.4: failed tests produce C2 FAIL and final verdict REJECTED."""
    from aegis.api.service import execute_project_verification_job, PROJECTS_STORE, RUNS_STORE
    from aegis.uploads.models import ProjectVerifyRequest, VerificationMode
    from unittest.mock import patch
    from aegis.execution.runner import TestResult
    from aegis.execution.sandbox import SandboxResult

    project_id = "proj_test_fail_verdict"
    PROJECTS_STORE[project_id] = {
        "project_id": project_id,
        "root_dir": "C:/dummy",
        "framework": "pytest",
        "discovered_tests": ["test_a.py::test_1", "test_a.py::test_2"],
        "test_files": ["test_a.py"]
    }
    run_id = "run_fail_verdict"
    RUNS_STORE[run_id] = {"status": "queued", "events": []}

    req = ProjectVerifyRequest(mode=VerificationMode.PROJECT, run_project_tests=True, run_security=False)

    mock_test_result = TestResult(
        passed=False, exit_code=1, stdout="", stderr="", duration_seconds=1.0,
        tests_passed=1, tests_failed=1, tests_error=0, summary_line="1 passed, 1 failed",
        total_executed=2,
        test_outcomes={"test_a.py::test_1": "PASSED", "test_a.py::test_2": "FAILED"},
        failed_test_details={"test_a.py::test_2": "AssertionError"},
        passed_nodeids=["test_a.py::test_1"],
        failed_nodeids=["test_a.py::test_2"],
        executed_nodeids=["test_a.py::test_1", "test_a.py::test_2"]
    )
    mock_sandbox_res = SandboxResult(test_result=mock_test_result, used_sandbox=True)

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-sandbox:latest"), \
         patch("aegis.execution.sandbox.collect_tests_sandboxed", return_value=["test_a.py::test_1", "test_a.py::test_2"]), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", return_value=mock_sandbox_res):
        execute_project_verification_job(run_id, project_id, req)

    run = RUNS_STORE[run_id]
    report = run["report"]
    c2 = report["criteria"]["C2_visible_tests"]
    assert c2["status"] == StageStatus.FAIL.value
    assert report["decision"]["technical_verdict"] == "REJECTED"
    assert report["decision"]["release_policy"] == "BLOCK"


def test_partial_execution_without_selection_produces_c2_error():
    """Directive 10.5: silent restriction (selected < discovered without user selection) produces C2 ERROR."""
    from aegis.api.service import execute_project_verification_job, PROJECTS_STORE, RUNS_STORE
    from aegis.uploads.models import ProjectVerifyRequest, VerificationMode
    from unittest.mock import patch
    from aegis.execution.runner import TestResult
    from aegis.execution.sandbox import SandboxResult

    project_id = "proj_test_partial_error"
    PROJECTS_STORE[project_id] = {
        "project_id": project_id,
        "root_dir": "C:/dummy",
        "framework": "pytest",
        "discovered_tests": ["test_a.py::test_1", "test_a.py::test_2"],
        "test_files": ["test_a.py"]
    }
    run_id = "run_partial_error"
    RUNS_STORE[run_id] = {"status": "queued", "events": []}

    req = ProjectVerifyRequest(mode=VerificationMode.PROJECT, run_project_tests=True, run_security=False)

    # 1 test executed when 2 were discovered, without user selection
    mock_test_result = TestResult(
        passed=True, exit_code=0, stdout="", stderr="", duration_seconds=1.0,
        tests_passed=1, tests_failed=0, tests_error=0, summary_line="1 passed",
        total_executed=1,
        test_outcomes={"test_a.py::test_1": "PASSED"},
        passed_nodeids=["test_a.py::test_1"],
        executed_nodeids=["test_a.py::test_1"]
    )
    mock_sandbox_res = SandboxResult(test_result=mock_test_result, used_sandbox=True)

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-sandbox:latest"), \
         patch("aegis.execution.sandbox.collect_tests_sandboxed", return_value=["test_a.py::test_1", "test_a.py::test_2"]), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", return_value=mock_sandbox_res):
        execute_project_verification_job(run_id, project_id, req)

    run = RUNS_STORE[run_id]
    report = run["report"]
    c2 = report["criteria"]["C2_visible_tests"]
    assert c2["status"] == StageStatus.ERROR.value
    assert report["decision"]["technical_verdict"] == "INDETERMINATE"
    assert report["decision"]["technical_verdict"] != "QUALIFIED"


def test_zero_passed_failed_rejected_when_results_produced():
    """Directive 10.6: zero passed/failed cannot be reported when pytest actually executed tests."""
    from aegis.api.service import execute_project_verification_job, PROJECTS_STORE, RUNS_STORE
    from aegis.uploads.models import ProjectVerifyRequest, VerificationMode
    from unittest.mock import patch
    from aegis.execution.runner import TestResult
    from aegis.execution.sandbox import SandboxResult

    project_id = "proj_test_zero_accounting"
    PROJECTS_STORE[project_id] = {
        "project_id": project_id,
        "root_dir": "C:/dummy",
        "framework": "pytest",
        "discovered_tests": ["test_a.py::test_1"],
        "test_files": ["test_a.py"]
    }
    run_id = "run_zero_accounting"
    RUNS_STORE[run_id] = {"status": "queued", "events": []}

    req = ProjectVerifyRequest(mode=VerificationMode.PROJECT, run_project_tests=True, run_security=False)

    # 5 executed but 0 passed and 0 failed
    mock_test_result = TestResult(
        passed=True, exit_code=0, stdout="", stderr="", duration_seconds=1.0,
        tests_passed=0, tests_failed=0, tests_error=0, tests_skipped=0, summary_line="",
        total_executed=5,
        test_outcomes={},
        executed_nodeids=["t1", "t2", "t3", "t4", "t5"]
    )
    mock_sandbox_res = SandboxResult(test_result=mock_test_result, used_sandbox=True)

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-sandbox:latest"), \
         patch("aegis.execution.sandbox.collect_tests_sandboxed", return_value=["test_a.py::test_1"]), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", return_value=mock_sandbox_res):
        execute_project_verification_job(run_id, project_id, req)

    run = RUNS_STORE[run_id]
    report = run["report"]
    c2 = report["criteria"]["C2_visible_tests"]
    assert c2["status"] == StageStatus.ERROR.value
    assert report["decision"]["technical_verdict"] == "INDETERMINATE"


# ==============================================================================
# SECTION 11 REGRESSION SUITE: FOUR-STATE TEST ACCOUNTING INTEGRITY
# ==============================================================================

def test_collection_errors_not_counted_as_executed_tests():
    """Directive 11.1: Prove collection errors != executed tests."""
    from aegis.execution.runner import parse_junit_xml

    xml_with_collection_errors = """<?xml version="1.0" encoding="utf-8"?>
    <testsuites>
      <testsuite name="pytest" errors="2" failures="0" skipped="0" tests="4" time="1.23">
        <testcase classname="" name="tests.fixtures.broken_syntax" time="0.0">
          <error message="collection failure">SyntaxError: invalid syntax in broken_syntax.py</error>
        </testcase>
        <testcase classname="" name="tests.fixtures.missing_dep" time="0.0">
          <error message="collection failure">ModuleNotFoundError: No module named 'nonexistent'</error>
        </testcase>
        <testcase classname="tests.test_good" name="test_one" time="0.1">
        </testcase>
        <testcase classname="tests.test_good" name="test_two" time="0.2">
        </testcase>
      </testsuite>
    </testsuites>
    """
    parsed = parse_junit_xml(xml_with_collection_errors)

    assert parsed["collection_error_count"] == 2
    assert any("broken_syntax" in c for c in parsed["collection_error_nodeids"])
    assert any("missing_dep" in c for c in parsed["collection_error_nodeids"])
    assert parsed["tests_passed"] == 2
    assert parsed["tests_failed"] == 0
    assert parsed["tests_error"] == 0  # Collection errors are NOT test execution errors!
    assert parsed["total_executed"] == 2  # ONLY 2 tests were actually executed!
    assert len(parsed["executed_nodeids"]) == 2
    assert "tests/test_good.py::test_one" in parsed["executed_nodeids"]
    assert "tests/test_good.py::test_two" in parsed["executed_nodeids"]
    # Collection error nodeids must NOT appear in executed_nodeids
    assert not any("broken_syntax" in e for e in parsed["executed_nodeids"])
    assert not any("missing_dep" in e for e in parsed["executed_nodeids"])


def test_junit_collection_failures_classified_separately():
    """Directive 11.2: JUnit collection failures are classified separately from test failures/errors."""
    from aegis.execution.runner import parse_junit_xml

    xml = """<?xml version="1.0" encoding="utf-8"?>
    <testsuites>
      <testsuite name="pytest" errors="1" failures="1" skipped="1" tests="4">
        <testcase classname="" name="tests.test_import_fail">
          <error message="collection failure">ImportError</error>
        </testcase>
        <testcase classname="" name="tests.test_collect_skip">
          <skipped message="collection skipped">Skipped during collection</skipped>
        </testcase>
        <testcase classname="tests.test_run" name="test_real_fail">
          <failure message="AssertionError">assert 1 == 2</failure>
        </testcase>
        <testcase classname="tests.test_run" name="test_real_error">
          <error message="RuntimeError">Crash during execution</error>
        </testcase>
      </testsuite>
    </testsuites>
    """
    parsed = parse_junit_xml(xml)

    assert parsed["collection_error_count"] == 2
    assert any("test_import_fail" in c for c in parsed["collection_error_nodeids"])
    assert any("test_collect_skip" in c for c in parsed["collection_error_nodeids"])

    # Only the 2 real executed testcases count towards execution
    assert parsed["total_executed"] == 2
    assert parsed["tests_failed"] == 1
    assert parsed["tests_error"] == 1
    assert parsed["tests_skipped"] == 0
    assert parsed["total_executed"] == parsed["tests_passed"] + parsed["tests_failed"] + parsed["tests_error"] + parsed["tests_skipped"]


def test_clean_calculator_suite_reports_three_of_three_execution():
    """Directive 11.3: Clean calculator suite reports 3/3 execution (2 pass, 1 fail)."""
    from aegis.api.service import execute_project_verification_job, PROJECTS_STORE, RUNS_STORE
    from aegis.uploads.models import ProjectVerifyRequest, VerificationMode, StageStatus
    from aegis.execution.runner import TestResult
    from aegis.execution.sandbox import SandboxResult, CollectionResult
    from unittest.mock import patch

    project_id = "proj_test_calc_unit"
    PROJECTS_STORE[project_id] = {
        "project_id": project_id,
        "root_dir": "C:/dummy",
        "framework": "pytest",
        "discovered_tests": [
            "test_calculator.py::test_add",
            "test_calculator.py::test_divide",
            "test_calculator.py::test_divide_by_zero"
        ],
        "test_files": ["test_calculator.py"]
    }
    run_id = "run_calc_unit"
    RUNS_STORE[run_id] = {"status": "queued", "events": []}

    req = ProjectVerifyRequest(mode=VerificationMode.PROJECT, run_project_tests=True, run_security=False)

    calc_collection = CollectionResult([
        "test_calculator.py::test_add",
        "test_calculator.py::test_divide",
        "test_calculator.py::test_divide_by_zero"
    ], [])

    calc_test_res = TestResult(
        passed=False, exit_code=1, stdout="1 failed, 2 passed", stderr="", duration_seconds=0.5,
        tests_passed=2, tests_failed=1, tests_error=0, tests_skipped=0, summary_line="1 failed, 2 passed",
        total_executed=3,
        test_outcomes={
            "test_calculator.py::test_add": "PASSED",
            "test_calculator.py::test_divide": "PASSED",
            "test_calculator.py::test_divide_by_zero": "FAILED"
        },
        passed_nodeids=["test_calculator.py::test_add", "test_calculator.py::test_divide"],
        failed_nodeids=["test_calculator.py::test_divide_by_zero"],
        executed_nodeids=[
            "test_calculator.py::test_add",
            "test_calculator.py::test_divide",
            "test_calculator.py::test_divide_by_zero"
        ]
    )
    mock_sandbox_res = SandboxResult(test_result=calc_test_res, used_sandbox=True)

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-sandbox:latest"), \
         patch("aegis.execution.sandbox.collect_tests_sandboxed", return_value=calc_collection), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", return_value=mock_sandbox_res):
        execute_project_verification_job(run_id, project_id, req)

    run = RUNS_STORE[run_id]
    report = run["report"]
    c2 = report["criteria"]["C2_visible_tests"]
    ev = report["evidence"]

    assert c2["collected_count"] == 3
    assert c2["collection_error_count"] == 0
    assert c2["selected_count"] == 3
    assert c2["tests_executed"] == 3
    assert c2["tests_passed"] == 2
    assert c2["tests_failed"] == 1
    assert c2["status"] == StageStatus.FAIL.value
    assert report["decision"]["technical_verdict"] == "REJECTED"
    assert report["decision"]["release_policy"] == "BLOCK"


def test_collection_failure_causes_c2_error_test_collection_error():
    """Directive 11.4: Collection failure causes C2 ERROR with TEST_COLLECTION_ERROR, not mismatch."""
    from aegis.api.service import execute_project_verification_job, PROJECTS_STORE, RUNS_STORE
    from aegis.uploads.models import ProjectVerifyRequest, VerificationMode, StageStatus
    from aegis.execution.runner import TestResult
    from aegis.execution.sandbox import SandboxResult, CollectionResult
    from unittest.mock import patch

    project_id = "proj_test_coll_fail"
    PROJECTS_STORE[project_id] = {
        "project_id": project_id,
        "root_dir": "C:/dummy",
        "framework": "pytest",
        "discovered_tests": ["test_ok.py::test_1"],
        "test_files": ["test_ok.py", "test_broken.py"]
    }
    run_id = "run_coll_fail"
    RUNS_STORE[run_id] = {"status": "queued", "events": []}

    req = ProjectVerifyRequest(mode=VerificationMode.PROJECT, run_project_tests=True, run_security=False)

    broken_collection = CollectionResult(
        ["test_ok.py::test_1"],
        ["tests/fixtures/test_broken.py"]
    )

    test_res = TestResult(
        passed=True, exit_code=0, stdout="", stderr="", duration_seconds=0.5,
        tests_passed=1, tests_failed=0, tests_error=0, tests_skipped=0, summary_line="1 passed",
        total_executed=1,
        test_outcomes={"test_ok.py::test_1": "PASSED"},
        passed_nodeids=["test_ok.py::test_1"],
        executed_nodeids=["test_ok.py::test_1"],
        collection_error_count=1,
        collection_error_nodeids=["tests/fixtures/test_broken.py"]
    )
    mock_sandbox_res = SandboxResult(test_result=test_res, used_sandbox=True)

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-sandbox:latest"), \
         patch("aegis.execution.sandbox.collect_tests_sandboxed", return_value=broken_collection), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", return_value=mock_sandbox_res):
        execute_project_verification_job(run_id, project_id, req)

    run = RUNS_STORE[run_id]
    report = run["report"]
    c2 = report["criteria"]["C2_visible_tests"]

    assert c2["status"] == StageStatus.ERROR.value
    assert "TEST_COLLECTION_ERROR" in c2["detail"]
    assert "DISCOVERY_EXECUTION_MISMATCH" not in c2["detail"]
    assert c2["collection_error_count"] == 1


def test_collection_failure_cannot_produce_qualified():
    """Directive 11.5: Collection failure cannot produce QUALIFIED."""
    from aegis.api.service import execute_project_verification_job, PROJECTS_STORE, RUNS_STORE
    from aegis.uploads.models import ProjectVerifyRequest, VerificationMode
    from aegis.execution.runner import TestResult
    from aegis.execution.sandbox import SandboxResult, CollectionResult
    from unittest.mock import patch

    project_id = "proj_test_no_qualify"
    PROJECTS_STORE[project_id] = {
        "project_id": project_id,
        "root_dir": "C:/dummy",
        "framework": "pytest",
        "discovered_tests": ["test_ok.py::test_1"],
        "test_files": ["test_ok.py"]
    }
    run_id = "run_no_qualify"
    RUNS_STORE[run_id] = {"status": "queued", "events": []}

    req = ProjectVerifyRequest(mode=VerificationMode.PROJECT, run_project_tests=True, run_security=False)

    coll = CollectionResult(["test_ok.py::test_1"], ["broken_file.py"])
    res = TestResult(
        passed=True, exit_code=0, stdout="", stderr="", duration_seconds=0.2,
        tests_passed=1, tests_failed=0, tests_error=0, tests_skipped=0, summary_line="1 passed",
        total_executed=1,
        test_outcomes={"test_ok.py::test_1": "PASSED"},
        passed_nodeids=["test_ok.py::test_1"],
        executed_nodeids=["test_ok.py::test_1"],
        collection_error_count=1,
        collection_error_nodeids=["broken_file.py"]
    )
    mock_sandbox_res = SandboxResult(test_result=res, used_sandbox=True)

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-sandbox:latest"), \
         patch("aegis.execution.sandbox.collect_tests_sandboxed", return_value=coll), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", return_value=mock_sandbox_res):
        execute_project_verification_job(run_id, project_id, req)

    run = RUNS_STORE[run_id]
    report = run["report"]

    assert report["decision"]["technical_verdict"] != "QUALIFIED"
    assert report["decision"]["technical_verdict"] == "INDETERMINATE"
    assert report["decision"]["release_policy"] == "REVIEW"


def test_executed_count_never_exceeds_selected_count():
    """Directive 11.6: Executed count never exceeds selected count without triggering invariant violation."""
    from aegis.api.service import execute_project_verification_job, PROJECTS_STORE, RUNS_STORE
    from aegis.uploads.models import ProjectVerifyRequest, VerificationMode, StageStatus
    from aegis.execution.runner import TestResult
    from aegis.execution.sandbox import SandboxResult, CollectionResult
    from unittest.mock import patch

    project_id = "proj_test_exec_exceed"
    PROJECTS_STORE[project_id] = {
        "project_id": project_id,
        "root_dir": "C:/dummy",
        "framework": "pytest",
        "discovered_tests": ["test_1.py::test_a"],
        "test_files": ["test_1.py"]
    }
    run_id = "run_exec_exceed"
    RUNS_STORE[run_id] = {"status": "queued", "events": []}

    req = ProjectVerifyRequest(mode=VerificationMode.PROJECT, run_project_tests=True, run_security=False)

    coll = CollectionResult(["test_1.py::test_a"], [])
    # 2 executed when only 1 collected/selected
    res = TestResult(
        passed=True, exit_code=0, stdout="", stderr="", duration_seconds=0.2,
        tests_passed=2, tests_failed=0, tests_error=0, tests_skipped=0, summary_line="2 passed",
        total_executed=2,
        test_outcomes={"test_1.py::test_a": "PASSED", "test_1.py::test_b": "PASSED"},
        passed_nodeids=["test_1.py::test_a", "test_1.py::test_b"],
        executed_nodeids=["test_1.py::test_a", "test_1.py::test_b"]
    )
    mock_sandbox_res = SandboxResult(test_result=res, used_sandbox=True)

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-sandbox:latest"), \
         patch("aegis.execution.sandbox.collect_tests_sandboxed", return_value=coll), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", return_value=mock_sandbox_res):
        execute_project_verification_job(run_id, project_id, req)

    run = RUNS_STORE[run_id]
    report = run["report"]
    c2 = report["criteria"]["C2_visible_tests"]

    assert c2["status"] == StageStatus.ERROR.value
    assert "COUNT_INVARIANT_VIOLATION" in c2["detail"]
    assert report["decision"]["technical_verdict"] == "INDETERMINATE"


def test_evidence_arrays_are_mutually_consistent():
    """Directive 11.7: Evidence arrays and counts are mutually consistent and reconcile."""
    from aegis.api.service import execute_project_verification_job, PROJECTS_STORE, RUNS_STORE
    from aegis.uploads.models import ProjectVerifyRequest, VerificationMode
    from aegis.execution.runner import TestResult
    from aegis.execution.sandbox import SandboxResult, CollectionResult
    from unittest.mock import patch

    project_id = "proj_test_evidence_reconcile"
    PROJECTS_STORE[project_id] = {
        "project_id": project_id,
        "root_dir": "C:/dummy",
        "framework": "pytest",
        "discovered_tests": ["t.py::t1", "t.py::t2", "t.py::t3", "t.py::t4"],
        "test_files": ["t.py"]
    }
    run_id = "run_evidence_reconcile"
    RUNS_STORE[run_id] = {"status": "queued", "events": []}

    req = ProjectVerifyRequest(mode=VerificationMode.PROJECT, run_project_tests=True, run_security=False)

    coll = CollectionResult(["t.py::t1", "t.py::t2", "t.py::t3", "t.py::t4"], ["err_mod.py"])
    res = TestResult(
        passed=False, exit_code=1, stdout="", stderr="", duration_seconds=0.5,
        tests_passed=1, tests_failed=1, tests_error=1, tests_skipped=1, summary_line="",
        total_executed=3,
        test_outcomes={"t.py::t1": "PASSED", "t.py::t2": "FAILED", "t.py::t3": "ERROR", "t.py::t4": "SKIPPED"},
        passed_nodeids=["t.py::t1"],
        failed_nodeids=["t.py::t2"],
        error_nodeids=["t.py::t3"],
        skipped_nodeids=["t.py::t4"],
        executed_nodeids=["t.py::t1", "t.py::t2", "t.py::t3"],
        collection_error_count=1,
        collection_error_nodeids=["err_mod.py"]
    )
    mock_sandbox_res = SandboxResult(test_result=res, used_sandbox=True)

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-sandbox:latest"), \
         patch("aegis.execution.sandbox.collect_tests_sandboxed", return_value=coll), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", return_value=mock_sandbox_res):
        execute_project_verification_job(run_id, project_id, req)

    run = RUNS_STORE[run_id]
    ev = run["report"]["evidence"]

    assert ev["collected_count"] == 4
    assert ev["collection_error_count"] == 1
    assert ev["selected_count"] == 4
    assert ev["executed_count"] == 3
    assert ev["passed_count"] == 1
    assert ev["failed_count"] == 1
    assert ev["error_count"] == 1
    assert ev["skipped_count"] == 1

    assert len(ev["collected_nodeids"]) == ev["collected_count"]
    assert len(ev["collection_error_nodeids"]) == ev["collection_error_count"]
    assert len(ev["selected_nodeids"]) == ev["selected_count"]
    assert len(ev["executed_nodeids"]) == ev["executed_count"]
    assert len(ev["failed_nodeids"]) == ev["failed_count"]
    assert len(ev["error_nodeids"]) == ev["error_count"]
    assert len(ev["skipped_nodeids"]) == ev["skipped_count"]

    # Exact mathematical invariants:
    # 1. passed + failed + errors = executed
    assert ev["passed_count"] + ev["failed_count"] + ev["error_count"] == ev["executed_count"]
    # 2. executed + skipped = selected
    assert ev["executed_count"] + ev["skipped_count"] == ev["selected_count"]
    # 3. selected <= discovered
    assert ev["selected_count"] <= ev["collected_count"]
    # 4. collection errors reported separately
    assert ev["collection_error_count"] == 1


def test_suite_with_skipped_tests_semantics():
    """Directive 10.3 / 11: Skipped tests are selected but NOT counted as executed.
    Invariants: executed + skipped = selected, passed + failed + errors = executed.
    """
    from aegis.api.service import execute_project_verification_job, PROJECTS_STORE, RUNS_STORE
    from aegis.uploads.models import ProjectVerifyRequest, VerificationMode, StageStatus
    from aegis.execution.runner import TestResult
    from aegis.execution.sandbox import SandboxResult, CollectionResult
    from unittest.mock import patch

    project_id = "proj_test_skipped_semantics"
    PROJECTS_STORE[project_id] = {
        "project_id": project_id,
        "root_dir": "C:/dummy",
        "framework": "pytest",
        "discovered_tests": ["t.py::test_a", "t.py::test_b", "t.py::test_c"],
        "test_files": ["t.py"]
    }
    run_id = "run_skipped_semantics"
    RUNS_STORE[run_id] = {"status": "queued", "events": []}
    req = ProjectVerifyRequest(mode=VerificationMode.PROJECT, run_project_tests=True, run_security=False)

    coll = CollectionResult(["t.py::test_a", "t.py::test_b", "t.py::test_c"], [])
    # 2 passed, 1 skipped -> executed = 2, skipped = 1, selected = 3
    res = TestResult(
        passed=True, exit_code=0, stdout="", stderr="", duration_seconds=0.2,
        tests_passed=2, tests_failed=0, tests_error=0, tests_skipped=1, summary_line="2 passed, 1 skipped",
        total_executed=2,
        test_outcomes={"t.py::test_a": "PASSED", "t.py::test_b": "PASSED", "t.py::test_c": "SKIPPED"},
        passed_nodeids=["t.py::test_a", "t.py::test_b"],
        failed_nodeids=[],
        error_nodeids=[],
        skipped_nodeids=["t.py::test_c"],
        executed_nodeids=["t.py::test_a", "t.py::test_b"],
        collection_error_count=0,
        collection_error_nodeids=[]
    )
    mock_sandbox_res = SandboxResult(test_result=res, used_sandbox=True)

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-sandbox:latest"), \
         patch("aegis.execution.sandbox.collect_tests_sandboxed", return_value=coll), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", return_value=mock_sandbox_res):
        execute_project_verification_job(run_id, project_id, req)

    run = RUNS_STORE[run_id]
    ev = run["report"]["evidence"]
    c2 = run["report"]["criteria"]["C2_visible_tests"]

    assert ev["collected_count"] == 3
    assert ev["selected_count"] == 3
    assert ev["executed_count"] == 2
    assert ev["passed_count"] == 2
    assert ev["failed_count"] == 0
    assert ev["error_count"] == 0
    assert ev["skipped_count"] == 1
    assert ev["collection_error_count"] == 0

    # Invariants
    assert ev["passed_count"] + ev["failed_count"] + ev["error_count"] == ev["executed_count"]
    assert ev["executed_count"] + ev["skipped_count"] == ev["selected_count"]
    assert ev["selected_count"] <= ev["collected_count"]
    assert c2["status"] == StageStatus.PASS.value


def test_suite_with_execution_error_semantics():
    """Directive 10.4 / 11: Execution errors (runtime crash during test) produce C2=ERROR.
    Invariants: passed + failed + errors = executed.
    """
    from aegis.api.service import execute_project_verification_job, PROJECTS_STORE, RUNS_STORE
    from aegis.uploads.models import ProjectVerifyRequest, VerificationMode, StageStatus
    from aegis.execution.runner import TestResult
    from aegis.execution.sandbox import SandboxResult, CollectionResult
    from unittest.mock import patch

    project_id = "proj_test_exec_error_semantics"
    PROJECTS_STORE[project_id] = {
        "project_id": project_id,
        "root_dir": "C:/dummy",
        "framework": "pytest",
        "discovered_tests": ["t.py::test_a", "t.py::test_b"],
        "test_files": ["t.py"]
    }
    run_id = "run_exec_error_semantics"
    RUNS_STORE[run_id] = {"status": "queued", "events": []}
    req = ProjectVerifyRequest(mode=VerificationMode.PROJECT, run_project_tests=True, run_security=False)

    coll = CollectionResult(["t.py::test_a", "t.py::test_b"], [])
    # 1 passed, 1 runtime error -> executed = 2, passed = 1, errors = 1
    res = TestResult(
        passed=False, exit_code=1, stdout="", stderr="", duration_seconds=0.2,
        tests_passed=1, tests_failed=0, tests_error=1, tests_skipped=0, summary_line="1 passed, 1 error",
        total_executed=2,
        test_outcomes={"t.py::test_a": "PASSED", "t.py::test_b": "ERROR"},
        passed_nodeids=["t.py::test_a"],
        failed_nodeids=[],
        error_nodeids=["t.py::test_b"],
        skipped_nodeids=[],
        executed_nodeids=["t.py::test_a", "t.py::test_b"],
        collection_error_count=0,
        collection_error_nodeids=[]
    )
    mock_sandbox_res = SandboxResult(test_result=res, used_sandbox=True)

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-sandbox:latest"), \
         patch("aegis.execution.sandbox.collect_tests_sandboxed", return_value=coll), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", return_value=mock_sandbox_res):
        execute_project_verification_job(run_id, project_id, req)

    run = RUNS_STORE[run_id]
    ev = run["report"]["evidence"]
    c2 = run["report"]["criteria"]["C2_visible_tests"]

    assert ev["collected_count"] == 2
    assert ev["selected_count"] == 2
    assert ev["executed_count"] == 2
    assert ev["passed_count"] == 1
    assert ev["failed_count"] == 0
    assert ev["error_count"] == 1
    assert ev["skipped_count"] == 0

    assert ev["passed_count"] + ev["failed_count"] + ev["error_count"] == ev["executed_count"]
    assert ev["executed_count"] + ev["skipped_count"] == ev["selected_count"]
    assert c2["status"] == StageStatus.ERROR.value
    assert run["technical_verdict"] != "QUALIFIED"


def test_mixed_suite_all_semantics_together():
    """Directive 11: Mixed suite containing passed, failed, execution error, skipped,
    and collection error simultaneously.
    Verifies all mathematical invariants and correct C2 / verdict assignment.
    """
    from aegis.api.service import execute_project_verification_job, PROJECTS_STORE, RUNS_STORE
    from aegis.uploads.models import ProjectVerifyRequest, VerificationMode, StageStatus
    from aegis.execution.runner import TestResult
    from aegis.execution.sandbox import SandboxResult, CollectionResult
    from unittest.mock import patch

    project_id = "proj_test_mixed_semantics"
    PROJECTS_STORE[project_id] = {
        "project_id": project_id,
        "root_dir": "C:/dummy",
        "framework": "pytest",
        "discovered_tests": ["t.py::t_pass", "t.py::t_fail", "t.py::t_err", "t.py::t_skip"],
        "test_files": ["t.py"]
    }
    run_id = "run_mixed_semantics"
    RUNS_STORE[run_id] = {"status": "queued", "events": []}
    req = ProjectVerifyRequest(mode=VerificationMode.PROJECT, run_project_tests=True, run_security=False)

    # 4 discovered tests, 1 separate collection error file
    coll = CollectionResult(["t.py::t_pass", "t.py::t_fail", "t.py::t_err", "t.py::t_skip"], ["broken_file.py"])
    # 1 pass, 1 fail, 1 error, 1 skip -> executed = 3, skipped = 1, selected = 4
    res = TestResult(
        passed=False, exit_code=1, stdout="", stderr="", duration_seconds=0.4,
        tests_passed=1, tests_failed=1, tests_error=1, tests_skipped=1, summary_line="",
        total_executed=3,
        test_outcomes={
            "t.py::t_pass": "PASSED",
            "t.py::t_fail": "FAILED",
            "t.py::t_err": "ERROR",
            "t.py::t_skip": "SKIPPED"
        },
        passed_nodeids=["t.py::t_pass"],
        failed_nodeids=["t.py::t_fail"],
        error_nodeids=["t.py::t_err"],
        skipped_nodeids=["t.py::t_skip"],
        executed_nodeids=["t.py::t_pass", "t.py::t_fail", "t.py::t_err"],
        collection_error_count=1,
        collection_error_nodeids=["broken_file.py"]
    )
    mock_sandbox_res = SandboxResult(test_result=res, used_sandbox=True)

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-sandbox:latest"), \
         patch("aegis.execution.sandbox.collect_tests_sandboxed", return_value=coll), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", return_value=mock_sandbox_res):
        execute_project_verification_job(run_id, project_id, req)

    run = RUNS_STORE[run_id]
    ev = run["report"]["evidence"]
    c2 = run["report"]["criteria"]["C2_visible_tests"]

    # 1. Exact definitions
    assert ev["collected_count"] == 4
    assert ev["collection_error_count"] == 1
    assert ev["selected_count"] == 4
    assert ev["executed_count"] == 3
    assert ev["passed_count"] == 1
    assert ev["failed_count"] == 1
    assert ev["error_count"] == 1
    assert ev["skipped_count"] == 1

    # 2. Mathematical invariants
    assert ev["selected_count"] <= ev["collected_count"]
    assert ev["executed_count"] + ev["skipped_count"] == ev["selected_count"]
    assert ev["passed_count"] + ev["failed_count"] + ev["error_count"] == ev["executed_count"]
    assert ev["collection_error_count"] >= 0

    # 3. Collection error causes C2=ERROR and prevents QUALIFIED
    assert c2["status"] == StageStatus.ERROR.value
    assert "TEST_COLLECTION_ERROR" in c2["detail"]
    assert run["technical_verdict"] == "REJECTED" or run["technical_verdict"] == "INDETERMINATE"
    assert run["technical_verdict"] != "QUALIFIED"
