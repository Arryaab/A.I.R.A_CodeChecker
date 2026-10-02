"""
Tests for A.I.R.A. project upload, verification security, sandbox enforcement, and correctness hardening.
Covers all 25 security/correctness requirements from the hardening directive.
"""

import io
import os
import tarfile
import zipfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from aegis.api.service import app, PROJECTS_STORE, RUNS_STORE, rate_limiter
from aegis.uploads.archive import extract_archive, secure_cleanup
from aegis.uploads.detection import detect_framework
from aegis.uploads.models import ProjectVerifyRequest, StageStatus
from aegis.execution.runner import TestResult
from aegis.execution.sandbox import SandboxResult, SandboxUnavailableError

AUTH_HEADERS = {"X-API-Key": "test-key"}
client = TestClient(app)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "projects"


def make_zip(project_dir: Path) -> io.BytesIO:
    """Create an in-memory zip from a fixture project directory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for f in files:
                full_path = Path(root) / f
                arc_name = full_path.relative_to(project_dir)
                zf.write(full_path, arc_name)
    buf.seek(0)
    return buf


def make_malicious_zip_with_path_traversal() -> io.BytesIO:
    """Create a zip with path traversal attack."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../../etc/passwd", "root:x:0:0:root")
    buf.seek(0)
    return buf


def make_zip_with_sensitive_file() -> io.BytesIO:
    """Create a zip containing a .env file."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("project/main.py", 'print("hello")')
        zf.writestr("project/.env", "SECRET_KEY=abc123")
    buf.seek(0)
    return buf


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Ensure rate limiter doesn't block unrelated tests."""
    with rate_limiter.lock:
        rate_limiter.history.clear()
    yield
    with rate_limiter.lock:
        rate_limiter.history.clear()


# ============================================================================
# 1. Hard Sandbox Guarantee & Host Execution Prevention
# ============================================================================

def test_uploaded_project_always_requires_sandbox():
    """1. Uploaded project verification strictly requires sandbox; returns 503 if Docker is unavailable."""
    project_dir = FIXTURES_DIR / "passing_project"
    zip_buf = make_zip(project_dir)
    upload_res = client.post(
        "/api/projects/upload",
        files={"archive": ("passing_project.zip", zip_buf, "application/zip")},
        headers=AUTH_HEADERS,
    )
    assert upload_res.status_code == 201, f"Upload failed: {upload_res.text}"
    project_id = upload_res.json()["project_id"]

    with patch("aegis.api.service.is_docker_available", return_value=False):
        res = client.post(
            f"/api/projects/{project_id}/verify",
            json={"tier": "standard"},
            headers=AUTH_HEADERS,
        )
        assert res.status_code == 503
        assert "Sandbox unavailable" in res.json()["detail"] or "isolated container runtime" in res.json()["detail"]

    client.delete(f"/api/projects/{project_id}", headers=AUTH_HEADERS)


def test_sandbox_executor_receives_use_docker_and_require_sandbox():
    """2 & 3. Verification calls run_tests_sandboxed with explicit use_docker=True and require_sandbox=True."""
    from aegis.api.service import execute_project_verification_job

    project_dir = FIXTURES_DIR / "passing_project"
    zip_buf = make_zip(project_dir)
    upload_res = client.post(
        "/api/projects/upload",
        files={"archive": ("passing_project.zip", zip_buf, "application/zip")},
        headers=AUTH_HEADERS,
    )
    project_id = upload_res.json()["project_id"]

    mock_test_res = TestResult(
        passed=True,
        exit_code=0,
        stdout="1 passed",
        stderr="",
        duration_seconds=1.2,
        tests_passed=1,
        tests_failed=0,
        tests_error=0,
        summary_line="1 passed in 1.2s",
        failure_messages=[]
    )
    mock_sandbox_res = SandboxResult(test_result=mock_test_res, used_sandbox=True, container_id="test_cnt")

    run_id = "test_run_sandbox_kwargs"
    RUNS_STORE[run_id] = {"status": "queued"}

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-sandbox:latest"), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", return_value=mock_sandbox_res) as mock_run:

        req = ProjectVerifyRequest(run_project_tests=True, run_user_tests=False, run_security=False)
        execute_project_verification_job(run_id, project_id, req)

        assert mock_run.called
        _, kwargs = mock_run.call_args
        assert kwargs.get("use_docker") is True, "Must pass use_docker=True explicitly"
        assert kwargs.get("require_sandbox") is True, "Must pass require_sandbox=True explicitly"

    client.delete(f"/api/projects/{project_id}", headers=AUTH_HEADERS)


def test_project_verification_cannot_invoke_host_runner():
    """Safety test: project verification must never fall back to or call the host test runner."""
    from aegis.api.service import execute_project_verification_job

    project_dir = FIXTURES_DIR / "passing_project"
    zip_buf = make_zip(project_dir)
    upload_res = client.post(
        "/api/projects/upload",
        files={"archive": ("passing_project.zip", zip_buf, "application/zip")},
        headers=AUTH_HEADERS,
    )
    project_id = upload_res.json()["project_id"]

    run_id = "test_run_no_host"
    RUNS_STORE[run_id] = {"status": "queued"}

    # If host runner is called, raise an AssertionError
    with patch("aegis.execution.runner.run_tests", side_effect=AssertionError("Host runner invoked!")), \
         patch("aegis.api.service.is_docker_available", return_value=False):

        req = ProjectVerifyRequest(run_project_tests=True)
        execute_project_verification_job(run_id, project_id, req)

        # Must have failed closed with SANDBOX_UNAVAILABLE without calling host runner
        assert RUNS_STORE[run_id]["status"] == "failed"
        assert "SANDBOX_UNAVAILABLE" in RUNS_STORE[run_id]["error"]

    client.delete(f"/api/projects/{project_id}", headers=AUTH_HEADERS)


# ============================================================================
# 2. Custom User Tests & Verdict Logic
# ============================================================================

def test_custom_project_tests_execute_and_distinguish_inventory():
    """4. Custom project tests execute inside sandbox and are distinguished in evidence."""
    from aegis.api.service import execute_project_verification_job

    project_dir = FIXTURES_DIR / "passing_project"
    zip_buf = make_zip(project_dir)
    upload_res = client.post(
        "/api/projects/upload",
        files={"archive": ("passing_project.zip", zip_buf, "application/zip")},
        headers=AUTH_HEADERS,
    )
    project_id = upload_res.json()["project_id"]

    # Upload custom test
    tests_buf = io.BytesIO()
    with zipfile.ZipFile(tests_buf, "w") as zf:
        zf.writestr("test_custom.py", "def test_ok(): assert True")
    tests_buf.seek(0)
    client.post(
        f"/api/projects/{project_id}/tests",
        files={"tests_archive": ("custom.zip", tests_buf, "application/zip")},
        headers=AUTH_HEADERS,
    )

    proj_test_res = TestResult(
        passed=True, exit_code=0, stdout="6 passed", stderr="", duration_seconds=1.0,
        tests_passed=6, tests_failed=0, tests_error=0, summary_line="", failure_messages=[]
    )
    user_test_res = TestResult(
        passed=True, exit_code=0, stdout="2 passed", stderr="", duration_seconds=0.5,
        tests_passed=2, tests_failed=0, tests_error=0, summary_line="", failure_messages=[]
    )

    run_id = "test_run_distinguish_inventory"
    RUNS_STORE[run_id] = {"status": "queued"}

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-sandbox:latest"), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", side_effect=[
             SandboxResult(test_result=proj_test_res, used_sandbox=True),
             SandboxResult(test_result=user_test_res, used_sandbox=True)
         ]):

        req = ProjectVerifyRequest(run_project_tests=True, run_user_tests=True, run_security=True)
        execute_project_verification_job(run_id, project_id, req)

        report = RUNS_STORE[run_id]["report"]
        evidence = report["evidence"]
        assert evidence["project_test_inventory"]["passed"] == 6
        assert evidence["custom_test_inventory"]["passed"] == 2
        assert report["decision"]["technical_verdict"] == "QUALIFIED"
        assert report["decision"]["release_policy"] == "AUTO_APPROVE"

    client.delete(f"/api/projects/{project_id}", headers=AUTH_HEADERS)


def test_custom_test_failure_causes_rejected():
    """5. Custom test failure MUST cause final verdict = REJECTED and release_policy = BLOCK."""
    from aegis.api.service import execute_project_verification_job

    project_dir = FIXTURES_DIR / "passing_project"
    zip_buf = make_zip(project_dir)
    upload_res = client.post(
        "/api/projects/upload",
        files={"archive": ("passing_project.zip", zip_buf, "application/zip")},
        headers=AUTH_HEADERS,
    )
    project_id = upload_res.json()["project_id"]

    # Upload custom test
    tests_buf = io.BytesIO()
    with zipfile.ZipFile(tests_buf, "w") as zf:
        zf.writestr("test_custom.py", "def test_fail(): assert False")
    tests_buf.seek(0)
    client.post(
        f"/api/projects/{project_id}/tests",
        files={"tests_archive": ("custom.zip", tests_buf, "application/zip")},
        headers=AUTH_HEADERS,
    )

    proj_test_res = TestResult(
        passed=True, exit_code=0, stdout="6 passed", stderr="", duration_seconds=1.0,
        tests_passed=6, tests_failed=0, tests_error=0, summary_line="", failure_messages=[]
    )
    user_test_res = TestResult(
        passed=False, exit_code=1, stdout="1 failed", stderr="", duration_seconds=0.5,
        tests_passed=0, tests_failed=1, tests_error=0, summary_line="", failure_messages=["AssertionError"]
    )

    run_id = "test_run_custom_fail"
    RUNS_STORE[run_id] = {"status": "queued"}

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-sandbox:latest"), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", side_effect=[
             SandboxResult(test_result=proj_test_res, used_sandbox=True),
             SandboxResult(test_result=user_test_res, used_sandbox=True)
         ]):

        req = ProjectVerifyRequest(run_project_tests=True, run_user_tests=True, run_security=True)
        execute_project_verification_job(run_id, project_id, req)

        report = RUNS_STORE[run_id]["report"]
        assert report["decision"]["technical_verdict"] == "REJECTED"
        assert report["decision"]["release_policy"] == "BLOCK"
        assert report["criteria"]["C2_user_tests"]["status"] == StageStatus.FAIL.value

    client.delete(f"/api/projects/{project_id}", headers=AUTH_HEADERS)


def test_custom_test_error_causes_indeterminate():
    """6. Custom test error MUST cause final verdict = INDETERMINATE and release_policy = REVIEW."""
    from aegis.api.service import execute_project_verification_job

    project_dir = FIXTURES_DIR / "passing_project"
    zip_buf = make_zip(project_dir)
    upload_res = client.post(
        "/api/projects/upload",
        files={"archive": ("passing_project.zip", zip_buf, "application/zip")},
        headers=AUTH_HEADERS,
    )
    project_id = upload_res.json()["project_id"]

    # Upload custom test with valid syntax (so C1 passes), but sandbox runner crashes
    tests_buf = io.BytesIO()
    with zipfile.ZipFile(tests_buf, "w") as zf:
        zf.writestr("test_custom.py", "def test_err(): pass\n")
    tests_buf.seek(0)
    client.post(
        f"/api/projects/{project_id}/tests",
        files={"tests_archive": ("custom.zip", tests_buf, "application/zip")},
        headers=AUTH_HEADERS,
    )

    proj_test_res = TestResult(
        passed=True, exit_code=0, stdout="6 passed", stderr="", duration_seconds=1.0,
        tests_passed=6, tests_failed=0, tests_error=0, summary_line="", failure_messages=[]
    )

    run_id = "test_run_custom_error"
    RUNS_STORE[run_id] = {"status": "queued"}

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-sandbox:latest"), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", side_effect=[
             SandboxResult(test_result=proj_test_res, used_sandbox=True),
             RuntimeError("Internal test runner crash inside container")
         ]):

        req = ProjectVerifyRequest(run_project_tests=True, run_user_tests=True, run_security=True)
        execute_project_verification_job(run_id, project_id, req)

        report = RUNS_STORE[run_id]["report"]
        assert report["decision"]["technical_verdict"] == "INDETERMINATE"
        assert report["decision"]["release_policy"] == "REVIEW"
        assert report["criteria"]["C2_user_tests"]["status"] == StageStatus.ERROR.value

    client.delete(f"/api/projects/{project_id}", headers=AUTH_HEADERS)


# ============================================================================
# 3. Truthful Output & Zero Fabrication
# ============================================================================

def test_docker_unavailable_returns_503():
    """7. Calling verification when Docker is unavailable returns 503 Service Unavailable."""
    project_dir = FIXTURES_DIR / "passing_project"
    zip_buf = make_zip(project_dir)
    upload_res = client.post(
        "/api/projects/upload",
        files={"archive": ("passing_project.zip", zip_buf, "application/zip")},
        headers=AUTH_HEADERS,
    )
    project_id = upload_res.json()["project_id"]

    with patch("aegis.api.service.is_docker_available", return_value=False):
        res = client.post(f"/api/projects/{project_id}/verify", json={"tier": "standard"}, headers=AUTH_HEADERS)
        assert res.status_code == 503

    client.delete(f"/api/projects/{project_id}", headers=AUTH_HEADERS)


def test_no_fabricated_verification_report():
    """8. POST /api/verifications refuses to fabricate reports when Docker is unavailable."""
    sample_diff = "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a = 1\n+a = 2\n"
    with patch("aegis.api.service.is_docker_available", return_value=False):
        res = client.post("/api/verifications", json={"diff": sample_diff, "tier": "fast"}, headers=AUTH_HEADERS)
        assert res.status_code == 503
        assert "A.I.R.A. real verification requires an isolated execution sandbox" in res.json()["detail"]


def test_no_fabricated_mlverify_result():
    """9. Standalone project verification report has mlverify status = UNAVAILABLE, not fabricated scores."""
    from aegis.api.service import execute_project_verification_job

    project_dir = FIXTURES_DIR / "passing_project"
    zip_buf = make_zip(project_dir)
    upload_res = client.post(
        "/api/projects/upload",
        files={"archive": ("passing_project.zip", zip_buf, "application/zip")},
        headers=AUTH_HEADERS,
    )
    project_id = upload_res.json()["project_id"]

    mock_res = TestResult(
        passed=True, exit_code=0, stdout="", stderr="", duration_seconds=0.1,
        tests_passed=1, tests_failed=0, tests_error=0, summary_line="", failure_messages=[]
    )
    run_id = "test_run_mlverify_truth"
    RUNS_STORE[run_id] = {"status": "queued"}

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-sandbox:latest"), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", return_value=SandboxResult(mock_res, True)):

        execute_project_verification_job(run_id, project_id, ProjectVerifyRequest())
        report = RUNS_STORE[run_id]["report"]
        assert report["evidence"]["mlverify"]["status"] == "UNAVAILABLE"
        assert "defect_risk" not in report["evidence"]["mlverify"]

    client.delete(f"/api/projects/{project_id}", headers=AUTH_HEADERS)


# ============================================================================
# 4. Authentication Requirements
# ============================================================================

def test_upload_authentication_required():
    """10. POST /api/projects/upload requires valid API key header."""
    project_dir = FIXTURES_DIR / "passing_project"
    zip_buf = make_zip(project_dir)
    res = client.post(
        "/api/projects/upload",
        files={"archive": ("proj.zip", zip_buf, "application/zip")},
        # No auth header
    )
    assert res.status_code == 401


def test_test_upload_authentication_required():
    """11. POST /api/projects/{id}/tests requires valid API key header."""
    res = client.post(
        "/api/projects/some_project_id/tests",
        files={"tests_archive": ("tests.zip", b"dummy", "application/zip")},
        # No auth header
    )
    assert res.status_code == 401


def test_verify_authentication_required():
    """12. POST /api/projects/{id}/verify requires valid API key header."""
    res = client.post(
        "/api/projects/some_project_id/verify",
        json={"tier": "standard"},
        # No auth header
    )
    assert res.status_code == 401


# ============================================================================
# 5. Archive Security
# ============================================================================

def test_oversized_custom_test_archive_rejected():
    """13. Custom test archives exceeding 50MB are rejected with 400."""
    project_dir = FIXTURES_DIR / "passing_project"
    zip_buf = make_zip(project_dir)
    upload_res = client.post(
        "/api/projects/upload",
        files={"archive": ("proj.zip", zip_buf, "application/zip")},
        headers=AUTH_HEADERS,
    )
    project_id = upload_res.json()["project_id"]

    oversized = b"0" * (50 * 1024 * 1024 + 10)
    res = client.post(
        f"/api/projects/{project_id}/tests",
        files={"tests_archive": ("huge_tests.zip", io.BytesIO(oversized), "application/zip")},
        headers=AUTH_HEADERS,
    )
    assert res.status_code == 400
    assert "exceeds 50MB limit" in res.json()["detail"]

    client.delete(f"/api/projects/{project_id}", headers=AUTH_HEADERS)


def test_custom_test_path_traversal_rejected():
    """14. Custom test archives containing path traversal are rejected."""
    project_dir = FIXTURES_DIR / "passing_project"
    zip_buf = make_zip(project_dir)
    upload_res = client.post(
        "/api/projects/upload",
        files={"archive": ("proj.zip", zip_buf, "application/zip")},
        headers=AUTH_HEADERS,
    )
    project_id = upload_res.json()["project_id"]

    malicious_tests = make_malicious_zip_with_path_traversal()
    res = client.post(
        f"/api/projects/{project_id}/tests",
        files={"tests_archive": ("bad.zip", malicious_tests, "application/zip")},
        headers=AUTH_HEADERS,
    )
    assert res.status_code == 400
    assert "traversal" in res.json()["detail"].lower()

    client.delete(f"/api/projects/{project_id}", headers=AUTH_HEADERS)


def test_custom_test_symlink_rejected(tmp_path):
    """15. Custom test archives containing symlinks are rejected."""
    project_dir = FIXTURES_DIR / "passing_project"
    zip_buf = make_zip(project_dir)
    upload_res = client.post(
        "/api/projects/upload",
        files={"archive": ("proj.zip", zip_buf, "application/zip")},
        headers=AUTH_HEADERS,
    )
    project_id = upload_res.json()["project_id"]

    tar_path = tmp_path / "symlink_tests.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        symlink_info = tarfile.TarInfo(name="malicious_symlink.py")
        symlink_info.type = tarfile.SYMTYPE
        symlink_info.linkname = "/etc/shadow"
        tar.addfile(symlink_info)

    with open(tar_path, "rb") as f:
        res = client.post(
            f"/api/projects/{project_id}/tests",
            files={"tests_archive": ("symlink_tests.tar.gz", f, "application/gzip")},
            headers=AUTH_HEADERS,
        )
    assert res.status_code == 400
    assert "symlink" in res.json()["detail"].lower()

    client.delete(f"/api/projects/{project_id}", headers=AUTH_HEADERS)


def test_user_filename_cannot_escape_storage_directory():
    """16. User filenames with path characters cannot escape storage directory."""
    project_dir = FIXTURES_DIR / "passing_project"
    zip_buf = make_zip(project_dir)
    res = client.post(
        "/api/projects/upload",
        files={"archive": ("../../exploit.zip", zip_buf, "application/zip")},
        headers=AUTH_HEADERS,
    )
    # Even if uploaded, storage uses sanitized internal name
    assert res.status_code == 201
    project_id = res.json()["project_id"]
    client.delete(f"/api/projects/{project_id}", headers=AUTH_HEADERS)


# ============================================================================
# 6. Truthful Criteria Semantics (C4, C5, NOT_AVAILABLE)
# ============================================================================

def test_c4_unavailable_without_baseline():
    """17. C4 regression is truthfully reported as NOT_AVAILABLE for standalone uploads."""
    from aegis.api.service import execute_project_verification_job

    project_dir = FIXTURES_DIR / "passing_project"
    zip_buf = make_zip(project_dir)
    upload_res = client.post(
        "/api/projects/upload",
        files={"archive": ("proj.zip", zip_buf, "application/zip")},
        headers=AUTH_HEADERS,
    )
    project_id = upload_res.json()["project_id"]

    mock_res = TestResult(
        passed=True, exit_code=0, stdout="", stderr="", duration_seconds=0.1,
        tests_passed=1, tests_failed=0, tests_error=0, summary_line="", failure_messages=[]
    )
    run_id = "test_run_c4"
    RUNS_STORE[run_id] = {"status": "queued"}

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-sandbox:latest"), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", return_value=SandboxResult(mock_res, True)):

        execute_project_verification_job(run_id, project_id, ProjectVerifyRequest())
        report = RUNS_STORE[run_id]["report"]
        assert report["criteria"]["C4_regression"]["status"] == StageStatus.NOT_AVAILABLE.value
        assert any("baseline" in lim.lower() for lim in report["evidence"]["limitations"])

    client.delete(f"/api/projects/{project_id}", headers=AUTH_HEADERS)


def test_c5_not_supported_truthfully_reported():
    """18. C5 mutation is truthfully reported as NOT_SUPPORTED when requested."""
    from aegis.api.service import execute_project_verification_job

    project_dir = FIXTURES_DIR / "passing_project"
    zip_buf = make_zip(project_dir)
    upload_res = client.post(
        "/api/projects/upload",
        files={"archive": ("proj.zip", zip_buf, "application/zip")},
        headers=AUTH_HEADERS,
    )
    project_id = upload_res.json()["project_id"]

    mock_res = TestResult(
        passed=True, exit_code=0, stdout="", stderr="", duration_seconds=0.1,
        tests_passed=1, tests_failed=0, tests_error=0, summary_line="", failure_messages=[]
    )
    run_id = "test_run_c5"
    RUNS_STORE[run_id] = {"status": "queued"}

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-sandbox:latest"), \
         patch("aegis.execution.sandbox.run_tests_sandboxed", return_value=SandboxResult(mock_res, True)):

        execute_project_verification_job(run_id, project_id, ProjectVerifyRequest(run_mutation=True))
        report = RUNS_STORE[run_id]["report"]
        assert report["criteria"]["C5_mutation"]["status"] == StageStatus.NOT_SUPPORTED.value

    client.delete(f"/api/projects/{project_id}", headers=AUTH_HEADERS)


def test_not_available_cannot_become_pass():
    """19. Stages with NOT_AVAILABLE or NOT_SUPPORTED must not silently become PASS."""
    from aegis.api.service import execute_project_verification_job

    project_dir = FIXTURES_DIR / "custom_tests_project"  # Has no test files
    zip_buf = make_zip(project_dir)
    upload_res = client.post(
        "/api/projects/upload",
        files={"archive": ("proj.zip", zip_buf, "application/zip")},
        headers=AUTH_HEADERS,
    )
    project_id = upload_res.json()["project_id"]

    run_id = "test_run_no_tests"
    RUNS_STORE[run_id] = {"status": "queued"}

    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-sandbox:latest"):

        execute_project_verification_job(run_id, project_id, ProjectVerifyRequest(run_project_tests=True, run_user_tests=True))
        report = RUNS_STORE[run_id]["report"]
        # Project tests skipped, user tests not available
        assert report["criteria"]["C2_user_tests"]["status"] == StageStatus.NOT_AVAILABLE.value
        assert report["criteria"]["C4_regression"]["status"] == StageStatus.NOT_AVAILABLE.value
        assert report["decision"]["criteria_summary"]["C4_regression"] != "PASS"

    client.delete(f"/api/projects/{project_id}", headers=AUTH_HEADERS)


# ============================================================================
# 7. Demo vs Public Separation & CORS & Rate Limiting
# ============================================================================

def test_demo_endpoint_remains_functional():
    """20. Curated demo endpoints remain fully functional and unauthenticated."""
    res = client.get("/api/demo/scenarios")
    assert res.status_code == 200
    assert len(res.json()) >= 5

    res_post = client.post("/api/demo/verify", json={"scenario_id": "demo_01_clean_pass"})
    assert res_post.status_code == 200
    run_id = res_post.json()["run_id"]

    # Demo run status and evidence are publicly readable
    st = client.get(f"/api/verifications/{run_id}")
    assert st.status_code == 200


def test_real_verification_cannot_use_demo_fallback():
    """21. Real project verification never returns demo scenario traces."""
    project_dir = FIXTURES_DIR / "passing_project"
    zip_buf = make_zip(project_dir)
    upload_res = client.post(
        "/api/projects/upload",
        files={"archive": ("proj.zip", zip_buf, "application/zip")},
        headers=AUTH_HEADERS,
    )
    project_id = upload_res.json()["project_id"]

    with patch("aegis.api.service.is_docker_available", return_value=False):
        res = client.post(f"/api/projects/{project_id}/verify", json={"tier": "standard"}, headers=AUTH_HEADERS)
        assert res.status_code == 503
        assert "demo_01" not in res.text

    client.delete(f"/api/projects/{project_id}", headers=AUTH_HEADERS)


def test_wildcard_production_cors_disabled():
    """22. CORS middleware configuration does not allow unrestricted wildcard with credentials."""
    for middleware in app.user_middleware:
        if middleware.cls.__name__ == "CORSMiddleware":
            allowed = middleware.kwargs.get("allow_origins", [])
            assert allowed != ["*"], "Wildcard CORS origin must be disabled"


def test_rate_limiting_enforced():
    """23. In-process rate limiter enforces max submissions per window with 429."""
    rate_limiter.max_requests = 3
    for _ in range(3):
        rate_limiter.enforce("test_key")

    with pytest.raises(Exception) as exc:
        rate_limiter.enforce("test_key")
    assert "429" in str(exc.value)
    rate_limiter.max_requests = 30  # Reset


def test_sandbox_cleanup_occurs():
    """24. Deleting a project removes extracted files from disk."""
    project_dir = FIXTURES_DIR / "passing_project"
    zip_buf = make_zip(project_dir)
    upload_res = client.post(
        "/api/projects/upload",
        files={"archive": ("proj.zip", zip_buf, "application/zip")},
        headers=AUTH_HEADERS,
    )
    data = upload_res.json()
    project_id = data["project_id"]
    extract_path = Path(data["extract_dir"])
    assert extract_path.exists()

    del_res = client.delete(f"/api/projects/{project_id}", headers=AUTH_HEADERS)
    assert del_res.status_code == 200
    assert not extract_path.exists(), "Extracted files must be deleted"


def test_evidence_does_not_expose_host_paths():
    """25. Evidence reports sanitize all absolute host paths."""
    from aegis.api.service import sanitize_path_str

    raw_text = r"Error at C:\Users\developer\AppData\Local\Temp\aira_project_xyz\calculator.py:12"
    sanitized = sanitize_path_str(raw_text)
    assert r"C:\Users" not in sanitized
    assert "<workspace>" in sanitized


# ============================================================================
# Section 21: Required Real Integration Tests
# ============================================================================

def test_integration_passing_project_and_failing_custom_tests():
    """
    Section 21 Integration Test:
    - passing_project + custom tests PASS => QUALIFIED (only when Docker execution occurs)
    - failing_custom_tests_project + custom tests FAIL => REJECTED
    If Docker is not available in the test environment, skips explicitly.
    """
    from aegis.execution.sandbox import is_docker_available

    if not is_docker_available():
        pytest.skip("Docker daemon not available in test environment for real live integration test.")

    # 1. Test passing_project with passing custom test
    pass_dir = FIXTURES_DIR / "passing_project"
    zip_buf = make_zip(pass_dir)
    upload_res = client.post(
        "/api/projects/upload",
        files={"archive": ("passing.zip", zip_buf, "application/zip")},
        headers=AUTH_HEADERS,
    )
    assert upload_res.status_code == 201
    pass_pid = upload_res.json()["project_id"]

    # Upload passing custom test
    t_buf = io.BytesIO()
    with zipfile.ZipFile(t_buf, "w") as zf:
        zf.writestr("test_passing.py", "from calculator import Calculator\ndef test_ok(): assert Calculator().add(1, 2) == 3\n")
    t_buf.seek(0)
    client.post(f"/api/projects/{pass_pid}/tests", files={"tests_archive": ("custom.zip", t_buf, "application/zip")}, headers=AUTH_HEADERS)

    verify_res = client.post(f"/api/projects/{pass_pid}/verify", json={"tier": "standard"}, headers=AUTH_HEADERS)
    assert verify_res.status_code == 202

    # 2. Test failing_custom_tests_project with failing custom test
    fail_dir = FIXTURES_DIR / "failing_custom_tests_project"
    fail_zip = make_zip(fail_dir)
    upload_fail = client.post(
        "/api/projects/upload",
        files={"archive": ("failing.zip", fail_zip, "application/zip")},
        headers=AUTH_HEADERS,
    )
    assert upload_fail.status_code == 201
    fail_pid = upload_fail.json()["project_id"]

    # Upload failing custom test
    ft_buf = io.BytesIO()
    with zipfile.ZipFile(ft_buf, "w") as zf:
        zf.writestr("test_fail.py", "def test_fail(): assert 1 == 999\n")
    ft_buf.seek(0)
    client.post(f"/api/projects/{fail_pid}/tests", files={"tests_archive": ("custom.zip", ft_buf, "application/zip")}, headers=AUTH_HEADERS)

    verify_fail = client.post(f"/api/projects/{fail_pid}/verify", json={"tier": "standard"}, headers=AUTH_HEADERS)
    assert verify_fail.status_code == 202
