"""
A.I.R.A. Test Discovery and Execution Integrity Regression Suite.
Addresses all 12 required regression scenarios from Directive Section 14:
1. three discovered / three executed / one failed => REJECTED
2. three discovered / two executed without user selection => ERROR
3. three discovered / two selected explicitly => PARTIAL SUITE
4. zero failed => C2 PASS
5. one failed => C2 FAIL
6. one error => C2 ERROR
7. discovery/execution mismatch => ERROR
8. selected subset clearly shown in evidence
9. qualified impossible after required failure
10. auto-approve impossible after required failure
11. no silent test filtering
12. calculator project reproduces expected 2 pass / 1 fail result
"""

import io
import os
import zipfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from aegis.api.service import app, PROJECTS_STORE, RUNS_STORE, execute_project_verification_job
from aegis.uploads.models import ProjectVerifyRequest, StageStatus
from aegis.uploads.detection import detect_framework, discover_project_tests
from aegis.execution.runner import TestResult, _parse_structured_test_results
from aegis.execution.sandbox import SandboxResult

AUTH_HEADERS = {"X-API-Key": "test-key"}
client = TestClient(app)


def make_in_memory_zip(files: dict[str, str]) -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    buf.seek(0)
    return buf


@pytest.fixture
def clean_stores():
    yield
    PROJECTS_STORE.clear()
    RUNS_STORE.clear()


# ============================================================================
# Scenario 1: Three discovered / three executed / one failed => REJECTED
# ============================================================================
def test_scenario_1_three_discovered_three_executed_one_failed_rejected(tmp_path, clean_stores):
    project_id = "proj_test_s1"
    run_id = "run_test_s1"

    # Setup dummy project dir with 3 tests in test_calculator.py
    test_file = tmp_path / "test_calculator.py"
    test_file.write_text(
        "def test_add(): assert 1 + 1 == 2\n"
        "def test_divide(): assert 10 / 2 == 5\n"
        "def test_divide_by_zero(): assert False\n"
    )

    discovered = discover_project_tests(tmp_path, ["test_calculator.py"])
    assert len(discovered) == 3

    PROJECTS_STORE[project_id] = {
        "project_id": project_id,
        "root_dir": str(tmp_path),
        "framework": "pytest",
        "test_files": ["test_calculator.py"],
        "discovered_tests": discovered,
        "discovered_count": 3,
        "user_test_files": [],
        "project_hash": "hash_s1"
    }
    RUNS_STORE[run_id] = {"status": "queued"}

    mock_tr = TestResult(
        passed=False, exit_code=1,
        stdout=(
            "test_calculator.py::test_add PASSED\n"
            "test_calculator.py::test_divide PASSED\n"
            "test_calculator.py::test_divide_by_zero FAILED\n"
            "=================== short test summary info ===================\n"
            "FAILED test_calculator.py::test_divide_by_zero - AssertionError\n"
            "=================== 1 failed, 2 passed in 0.05s ===============\n"
        ),
        stderr="", duration_seconds=1.2,
        tests_passed=2, tests_failed=1, tests_error=0, tests_skipped=0,
        total_collected=3, total_executed=3,
        test_outcomes={
            "test_calculator.py::test_add": "PASSED",
            "test_calculator.py::test_divide": "PASSED",
            "test_calculator.py::test_divide_by_zero": "FAILED"
        },
        failed_test_details={"test_calculator.py::test_divide_by_zero": "AssertionError"},
        summary_line="1 failed, 2 passed", failure_messages=[]
    )

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-env-mock"), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", return_value=SandboxResult(test_result=mock_tr, used_sandbox=True, command=["pytest"])):

        req = ProjectVerifyRequest(run_project_tests=True, run_security=False)
        execute_project_verification_job(run_id, project_id, req)

    run_data = RUNS_STORE[run_id]
    assert run_data["technical_verdict"] == "REJECTED"
    assert run_data["release_policy"] == "BLOCK"
    c2 = run_data["report"]["criteria"]["C2_visible_tests"]
    assert c2["status"] == StageStatus.FAIL.value
    assert c2["tests_passed"] == 2
    assert c2["tests_failed"] == 1


# ============================================================================
# Scenario 2: Three discovered / two executed without user selection => ERROR
# ============================================================================
def test_scenario_2_three_discovered_two_executed_without_selection_error(tmp_path, clean_stores):
    project_id = "proj_test_s2"
    run_id = "run_test_s2"

    test_file = tmp_path / "test_calc.py"
    test_file.write_text("def test_1(): pass\ndef test_2(): pass\ndef test_3(): pass\n")
    discovered = ["test_calc.py::test_1", "test_calc.py::test_2", "test_calc.py::test_3"]

    PROJECTS_STORE[project_id] = {
        "project_id": project_id,
        "root_dir": str(tmp_path),
        "framework": "pytest",
        "test_files": ["test_calc.py"],
        "discovered_tests": discovered,
        "discovered_count": 3,
        "user_test_files": [],
        "project_hash": "hash_s2"
    }
    RUNS_STORE[run_id] = {"status": "queued"}

    # Mock runner only executes 2 tests (e.g. pytest truncated or dropped 1 test)
    mock_tr = TestResult(
        passed=True, exit_code=0,
        stdout="test_calc.py::test_1 PASSED\ntest_calc.py::test_2 PASSED\n=== 2 passed in 0.02s ===",
        stderr="", duration_seconds=0.5,
        tests_passed=2, tests_failed=0, tests_error=0, tests_skipped=0,
        total_collected=2, total_executed=2,
        test_outcomes={"test_calc.py::test_1": "PASSED", "test_calc.py::test_2": "PASSED"},
        summary_line="2 passed", failure_messages=[]
    )

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-env-mock"), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", return_value=SandboxResult(test_result=mock_tr, used_sandbox=True)):

        req = ProjectVerifyRequest(run_project_tests=True, run_security=False)
        execute_project_verification_job(run_id, project_id, req)

    run_data = RUNS_STORE[run_id]
    assert run_data["technical_verdict"] == "INDETERMINATE"
    assert run_data["release_policy"] == "REVIEW"
    c2 = run_data["report"]["criteria"]["C2_visible_tests"]
    assert c2["status"] == StageStatus.ERROR.value
    assert "DISCOVERY_EXECUTION_MISMATCH" in c2["detail"]


# ============================================================================
# Scenario 3: Three discovered / two selected explicitly => PARTIAL SUITE
# ============================================================================
def test_scenario_3_three_discovered_two_selected_explicitly_partial_suite(tmp_path, clean_stores):
    project_id = "proj_test_s3"
    run_id = "run_test_s3"

    discovered = ["test_a.py::t1", "test_a.py::t2", "test_a.py::t3"]
    PROJECTS_STORE[project_id] = {
        "project_id": project_id,
        "root_dir": str(tmp_path),
        "framework": "pytest",
        "test_files": ["test_a.py"],
        "discovered_tests": discovered,
        "discovered_count": 3,
        "user_test_files": [],
        "project_hash": "hash_s3"
    }
    RUNS_STORE[run_id] = {"status": "queued"}

    mock_tr = TestResult(
        passed=True, exit_code=0,
        stdout="test_a.py::t1 PASSED\ntest_a.py::t2 PASSED\n=== 2 passed in 0.02s ===",
        stderr="", duration_seconds=0.5,
        tests_passed=2, tests_failed=0, tests_error=0, tests_skipped=0,
        total_collected=2, total_executed=2,
        test_outcomes={"test_a.py::t1": "PASSED", "test_a.py::t2": "PASSED"},
        summary_line="2 passed", failure_messages=[]
    )

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-env-mock"), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", return_value=SandboxResult(test_result=mock_tr, used_sandbox=True)):

        # Explicitly request 2-test subset
        req = ProjectVerifyRequest(
            run_project_tests=True,
            selected_tests=["test_a.py::t1", "test_a.py::t2"],
            run_security=False
        )
        execute_project_verification_job(run_id, project_id, req)

    evidence = RUNS_STORE[run_id]["report"]["evidence"]
    disc = evidence["project_test_discovery"]
    assert disc["discovered"] == 3
    assert disc["selected"] == 2
    assert disc["excluded"] == 1
    assert "test_a.py::t3" in disc["excluded_tests"]
    assert any("partial test suite" in lim.lower() for lim in evidence["limitations"])


# ============================================================================
# Scenario 4: Zero failed => C2 PASS
# ============================================================================
def test_scenario_4_zero_failed_c2_pass(tmp_path, clean_stores):
    project_id = "proj_test_s4"
    run_id = "run_test_s4"

    discovered = ["test_a.py::t1", "test_a.py::t2"]
    PROJECTS_STORE[project_id] = {
        "project_id": project_id,
        "root_dir": str(tmp_path),
        "framework": "pytest",
        "test_files": ["test_a.py"],
        "discovered_tests": discovered,
        "discovered_count": 2,
        "user_test_files": [],
        "project_hash": "hash_s4"
    }
    RUNS_STORE[run_id] = {"status": "queued"}

    mock_tr = TestResult(
        passed=True, exit_code=0,
        stdout="test_a.py::t1 PASSED\ntest_a.py::t2 PASSED\n=== 2 passed ===",
        stderr="", duration_seconds=0.4,
        tests_passed=2, tests_failed=0, tests_error=0, tests_skipped=0,
        total_collected=2, total_executed=2,
        test_outcomes={"test_a.py::t1": "PASSED", "test_a.py::t2": "PASSED"},
        summary_line="2 passed", failure_messages=[]
    )

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-env-mock"), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", return_value=SandboxResult(test_result=mock_tr, used_sandbox=True)):

        req = ProjectVerifyRequest(run_project_tests=True, run_security=False)
        execute_project_verification_job(run_id, project_id, req)

    c2 = RUNS_STORE[run_id]["report"]["criteria"]["C2_visible_tests"]
    assert c2["status"] == StageStatus.PASS.value
    assert c2["tests_failed"] == 0


# ============================================================================
# Scenario 5: One failed => C2 FAIL
# ============================================================================
def test_scenario_5_one_failed_c2_fail(tmp_path, clean_stores):
    project_id = "proj_test_s5"
    run_id = "run_test_s5"

    discovered = ["test_a.py::t1"]
    PROJECTS_STORE[project_id] = {
        "project_id": project_id,
        "root_dir": str(tmp_path),
        "framework": "pytest",
        "test_files": ["test_a.py"],
        "discovered_tests": discovered,
        "discovered_count": 1,
        "user_test_files": [],
        "project_hash": "hash_s5"
    }
    RUNS_STORE[run_id] = {"status": "queued"}

    mock_tr = TestResult(
        passed=False, exit_code=1,
        stdout="test_a.py::t1 FAILED\n=== 1 failed ===",
        stderr="", duration_seconds=0.3,
        tests_passed=0, tests_failed=1, tests_error=0, tests_skipped=0,
        total_collected=1, total_executed=1,
        test_outcomes={"test_a.py::t1": "FAILED"},
        failed_test_details={"test_a.py::t1": "AssertionError: failed"},
        summary_line="1 failed", failure_messages=[]
    )

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-env-mock"), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", return_value=SandboxResult(test_result=mock_tr, used_sandbox=True)):

        req = ProjectVerifyRequest(run_project_tests=True, run_security=False)
        execute_project_verification_job(run_id, project_id, req)

    c2 = RUNS_STORE[run_id]["report"]["criteria"]["C2_visible_tests"]
    assert c2["status"] == StageStatus.FAIL.value


# ============================================================================
# Scenario 6: One error => C2 ERROR
# ============================================================================
def test_scenario_6_one_error_c2_error(tmp_path, clean_stores):
    project_id = "proj_test_s6"
    run_id = "run_test_s6"

    discovered = ["test_a.py::t1"]
    PROJECTS_STORE[project_id] = {
        "project_id": project_id,
        "root_dir": str(tmp_path),
        "framework": "pytest",
        "test_files": ["test_a.py"],
        "discovered_tests": discovered,
        "discovered_count": 1,
        "user_test_files": [],
        "project_hash": "hash_s6"
    }
    RUNS_STORE[run_id] = {"status": "queued"}

    mock_tr = TestResult(
        passed=False, exit_code=2,
        stdout="test_a.py::t1 ERROR\n=== 1 error in 0.01s ===",
        stderr="", duration_seconds=0.2,
        tests_passed=0, tests_failed=0, tests_error=1, tests_skipped=0,
        total_collected=1, total_executed=1,
        test_outcomes={"test_a.py::t1": "ERROR"},
        failed_test_details={"test_a.py::t1": "FixtureError"},
        summary_line="1 error", failure_messages=[]
    )

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-env-mock"), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", return_value=SandboxResult(test_result=mock_tr, used_sandbox=True)):

        req = ProjectVerifyRequest(run_project_tests=True, run_security=False)
        execute_project_verification_job(run_id, project_id, req)

    c2 = RUNS_STORE[run_id]["report"]["criteria"]["C2_visible_tests"]
    assert c2["status"] == StageStatus.ERROR.value
    assert RUNS_STORE[run_id]["technical_verdict"] == "INDETERMINATE"
    assert RUNS_STORE[run_id]["release_policy"] == "REVIEW"


# ============================================================================
# Scenario 7: Discovery/execution mismatch => ERROR
# ============================================================================
def test_scenario_7_discovery_execution_mismatch_error(tmp_path, clean_stores):
    project_id = "proj_test_s7"
    run_id = "run_test_s7"

    discovered = ["test_a.py::t1", "test_a.py::t2", "test_a.py::t3", "test_a.py::t4"]
    PROJECTS_STORE[project_id] = {
        "project_id": project_id,
        "root_dir": str(tmp_path),
        "framework": "pytest",
        "test_files": ["test_a.py"],
        "discovered_tests": discovered,
        "discovered_count": 4,
        "user_test_files": [],
        "project_hash": "hash_s7"
    }
    RUNS_STORE[run_id] = {"status": "queued"}

    mock_tr = TestResult(
        passed=True, exit_code=0,
        stdout="=== 2 passed ===", stderr="", duration_seconds=0.2,
        tests_passed=2, tests_failed=0, tests_error=0, tests_skipped=0,
        total_collected=2, total_executed=2,
        summary_line="2 passed", failure_messages=[]
    )

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-env-mock"), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", return_value=SandboxResult(test_result=mock_tr, used_sandbox=True)):

        req = ProjectVerifyRequest(run_project_tests=True, run_security=False)
        execute_project_verification_job(run_id, project_id, req)

    c2 = RUNS_STORE[run_id]["report"]["criteria"]["C2_visible_tests"]
    assert c2["status"] == StageStatus.ERROR.value
    assert "DISCOVERY_EXECUTION_MISMATCH" in c2["detail"]


# ============================================================================
# Scenario 8: Selected subset clearly shown in evidence
# ============================================================================
def test_scenario_8_selected_subset_shown_in_evidence(tmp_path, clean_stores):
    project_id = "proj_test_s8"
    run_id = "run_test_s8"

    discovered = ["test_1.py::a", "test_2.py::b", "test_3.py::c"]
    PROJECTS_STORE[project_id] = {
        "project_id": project_id,
        "root_dir": str(tmp_path),
        "framework": "pytest",
        "test_files": ["test_1.py", "test_2.py", "test_3.py"],
        "discovered_tests": discovered,
        "discovered_count": 3,
        "user_test_files": [],
        "project_hash": "hash_s8"
    }
    RUNS_STORE[run_id] = {"status": "queued"}

    mock_tr = TestResult(
        passed=True, exit_code=0,
        stdout="test_1.py::a PASSED\n=== 1 passed ===", stderr="", duration_seconds=0.2,
        tests_passed=1, tests_failed=0, tests_error=0, tests_skipped=0,
        total_collected=1, total_executed=1,
        test_outcomes={"test_1.py::a": "PASSED"},
        summary_line="1 passed", failure_messages=[]
    )

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-env-mock"), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", return_value=SandboxResult(test_result=mock_tr, used_sandbox=True)):

        req = ProjectVerifyRequest(run_project_tests=True, selected_tests=["test_1.py::a"], run_security=False)
        execute_project_verification_job(run_id, project_id, req)

    evidence = RUNS_STORE[run_id]["report"]["evidence"]
    disc = evidence["project_test_discovery"]
    assert disc["selected"] == 1
    assert disc["selected_tests"] == ["test_1.py::a"]
    assert disc["excluded"] == 2
    assert "test_2.py::b" in disc["excluded_tests"]
    assert "test_3.py::c" in disc["excluded_tests"]


# ============================================================================
# Scenario 9: QUALIFIED impossible after required failure
# ============================================================================
def test_scenario_9_qualified_impossible_after_required_failure(tmp_path, clean_stores):
    project_id = "proj_test_s9"
    run_id = "run_test_s9"

    discovered = ["test_x.py::fail_test"]
    PROJECTS_STORE[project_id] = {
        "project_id": project_id,
        "root_dir": str(tmp_path),
        "framework": "pytest",
        "test_files": ["test_x.py"],
        "discovered_tests": discovered,
        "discovered_count": 1,
        "user_test_files": [],
        "project_hash": "hash_s9"
    }
    RUNS_STORE[run_id] = {"status": "queued"}

    mock_tr = TestResult(
        passed=False, exit_code=1,
        stdout="test_x.py::fail_test FAILED\n=== 1 failed ===", stderr="", duration_seconds=0.2,
        tests_passed=0, tests_failed=1, tests_error=0, tests_skipped=0,
        total_collected=1, total_executed=1,
        test_outcomes={"test_x.py::fail_test": "FAILED"},
        summary_line="1 failed", failure_messages=[]
    )

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-env-mock"), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", return_value=SandboxResult(test_result=mock_tr, used_sandbox=True)):

        req = ProjectVerifyRequest(run_project_tests=True, run_security=False)
        execute_project_verification_job(run_id, project_id, req)

    verdict = RUNS_STORE[run_id]["technical_verdict"]
    assert verdict == "REJECTED"
    assert "QUALIFIED" not in verdict


# ============================================================================
# Scenario 10: AUTO_APPROVE impossible after required failure
# ============================================================================
def test_scenario_10_auto_approve_impossible_after_required_failure(tmp_path, clean_stores):
    project_id = "proj_test_s10"
    run_id = "run_test_s10"

    discovered = ["test_x.py::fail_test"]
    PROJECTS_STORE[project_id] = {
        "project_id": project_id,
        "root_dir": str(tmp_path),
        "framework": "pytest",
        "test_files": ["test_x.py"],
        "discovered_tests": discovered,
        "discovered_count": 1,
        "user_test_files": [],
        "project_hash": "hash_s10"
    }
    RUNS_STORE[run_id] = {"status": "queued"}

    mock_tr = TestResult(
        passed=False, exit_code=1,
        stdout="test_x.py::fail_test FAILED\n=== 1 failed ===", stderr="", duration_seconds=0.2,
        tests_passed=0, tests_failed=1, tests_error=0, tests_skipped=0,
        total_collected=1, total_executed=1,
        test_outcomes={"test_x.py::fail_test": "FAILED"},
        summary_line="1 failed", failure_messages=[]
    )

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-env-mock"), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", return_value=SandboxResult(test_result=mock_tr, used_sandbox=True)):

        req = ProjectVerifyRequest(run_project_tests=True, run_security=False)
        execute_project_verification_job(run_id, project_id, req)

    policy = RUNS_STORE[run_id]["release_policy"]
    assert policy == "BLOCK"
    assert policy != "AUTO_APPROVE"


# ============================================================================
# Scenario 11: No silent test filtering
# ============================================================================
def test_scenario_11_no_silent_test_filtering(tmp_path):
    # Verify that discover_project_tests finds every test in multiple files
    f1 = tmp_path / "test_one.py"
    f1.write_text("def test_alpha(): pass\ndef test_beta(): pass\n")
    f2 = tmp_path / "test_two.py"
    f2.write_text("class TestClass:\n    def test_gamma(self): pass\n    def test_delta(self): pass\n")

    discovered = discover_project_tests(tmp_path)
    assert len(discovered) == 4
    assert any("test_alpha" in t for t in discovered)
    assert any("test_beta" in t for t in discovered)
    assert any("test_gamma" in t for t in discovered)
    assert any("test_delta" in t for t in discovered)


# ============================================================================
# Scenario 12: Calculator project reproduces expected 2 pass / 1 fail result
# ============================================================================
def test_scenario_12_calculator_project_reproduces_2_pass_1_fail():
    calc_zip = Path(r"C:\Users\aryab\Downloads\aira_test_project.zip")
    if not calc_zip.exists():
        pytest.skip("aira_test_project.zip not available in Downloads")

    with open(calc_zip, "rb") as f:
        content = f.read()

    res = client.post(
        "/api/projects/upload",
        files={"archive": ("aira_test_project.zip", io.BytesIO(content), "application/zip")},
        headers=AUTH_HEADERS,
    )
    assert res.status_code == 201
    pdata = res.json()
    project_id = pdata["project_id"]

    assert pdata["discovered_count"] == 3
    assert len(pdata["discovered_tests"]) == 3
    assert any("test_divide_by_zero" in t for t in pdata["discovered_tests"])

    client.delete(f"/api/projects/{project_id}", headers=AUTH_HEADERS)


def test_section11_calculator_project_executes_3_tests_and_fails_divide_by_zero():
    """Directive 11: Real end-to-end verification of calculator project in Docker."""
    from aegis.execution.sandbox import is_docker_available
    if not is_docker_available():
        pytest.skip("Docker daemon not available for live sandbox run")

    calc_zip = Path(r"C:\Users\aryab\Downloads\aira_test_project.zip")
    if not calc_zip.exists():
        pytest.skip("aira_test_project.zip not available in Downloads")

    with open(calc_zip, "rb") as f:
        content = f.read()

    res = client.post(
        "/api/projects/upload",
        files={"archive": ("aira_test_project.zip", io.BytesIO(content), "application/zip")},
        headers=AUTH_HEADERS,
    )
    assert res.status_code == 201
    project_id = res.json()["project_id"]

    verify_res = client.post(f"/api/projects/{project_id}/verify", json={"tier": "standard"}, headers=AUTH_HEADERS)
    assert verify_res.status_code == 202
    run_id = verify_res.json()["run_id"]

    import time
    for _ in range(30):
        time.sleep(1)
        sr = client.get(f"/api/verifications/{run_id}", headers=AUTH_HEADERS).json()
        if sr.get("status") in ("completed", "failed"):
            break

    assert sr.get("status") == "completed"
    report = sr["report"]
    dec = report["decision"]
    c2 = report["criteria"]["C2_visible_tests"]
    ev = report["evidence"]

    assert c2["discovered_count"] == 3
    assert c2["tests_executed"] == 3
    assert c2["tests_passed"] == 2
    assert c2["tests_failed"] == 1
    assert any("test_divide_by_zero" in ft for ft in c2["failed_tests"])
    assert c2["status"] == "FAIL"
    assert dec["technical_verdict"] == "REJECTED"
    assert dec["release_policy"] == "BLOCK"

    client.delete(f"/api/projects/{project_id}", headers=AUTH_HEADERS)


def test_section11_real_docker_execution_uses_full_suite(tmp_path, clean_stores):
    """Directive 11: Default execution uses full suite without path filter."""
    project_id = "proj_full_suite_test"
    run_id = "run_full_suite_test"

    PROJECTS_STORE[project_id] = {
        "project_id": project_id,
        "root_dir": str(tmp_path),
        "framework": "pytest",
        "test_files": ["test_sample.py"],
        "discovered_tests": ["test_sample.py::t1", "test_sample.py::t2"],
        "discovered_count": 2,
        "user_test_files": [],
        "project_hash": "hash_fs"
    }
    RUNS_STORE[run_id] = {"status": "queued"}

    mock_tr = TestResult(
        passed=True, exit_code=0, stdout="2 passed", stderr="", duration_seconds=0.5,
        tests_passed=2, tests_failed=0, tests_error=0, tests_skipped=0,
        total_collected=2, total_executed=2,
        test_outcomes={"test_sample.py::t1": "PASSED", "test_sample.py::t2": "PASSED"},
        summary_line="2 passed", failure_messages=[]
    )

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-env-mock"), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", return_value=SandboxResult(test_result=mock_tr, used_sandbox=True)) as mock_run:

        req = ProjectVerifyRequest(run_project_tests=True, run_security=False)
        execute_project_verification_job(run_id, project_id, req)

        assert mock_run.called
        _, kwargs = mock_run.call_args
        assert kwargs.get("test_files") is None, "Default full suite must pass test_files=None to execute entire workspace without heuristic filtering"


def test_section11_no_test_selection_heuristic_by_default(tmp_path, clean_stores):
    """Directive 11: No test-selection heuristic runs by default for archive uploads."""
    project_id = "proj_no_heuristic"
    run_id = "run_no_heuristic"

    discovered = ["test_a.py::t1", "test_b.py::t2", "test_c.py::t3"]
    PROJECTS_STORE[project_id] = {
        "project_id": project_id,
        "root_dir": str(tmp_path),
        "framework": "pytest",
        "test_files": ["test_a.py", "test_b.py", "test_c.py"],
        "discovered_tests": discovered,
        "discovered_count": 3,
        "user_test_files": [],
        "project_hash": "hash_nh"
    }
    RUNS_STORE[run_id] = {"status": "queued"}

    mock_tr = TestResult(
        passed=True, exit_code=0, stdout="3 passed", stderr="", duration_seconds=0.5,
        tests_passed=3, tests_failed=0, tests_error=0, tests_skipped=0,
        total_collected=3, total_executed=3,
        test_outcomes={"test_a.py::t1": "PASSED", "test_b.py::t2": "PASSED", "test_c.py::t3": "PASSED"},
        summary_line="3 passed", failure_messages=[]
    )

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-env-mock"), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", return_value=SandboxResult(test_result=mock_tr, used_sandbox=True)):

        req = ProjectVerifyRequest(run_project_tests=True, run_security=False)
        execute_project_verification_job(run_id, project_id, req)

    ev = RUNS_STORE[run_id]["report"]["evidence"]
    disc = ev["project_test_discovery"]
    assert disc["discovered"] == 3
    assert disc["selected"] == 3
    assert disc["excluded"] == 0
    assert disc["excluded_tests"] == []
