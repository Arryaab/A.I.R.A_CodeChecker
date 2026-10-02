from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from aegis.api.service import app, init_local_dev_auth
from aegis.execution.sandbox import (
    check_sandbox_health,
    get_docker_executable,
    is_docker_available,
    build_sandbox_image_with_output,
    print_sandbox_startup_banner,
    SandboxUnavailableError,
)
from aegis.cli import execute_doctor

client = TestClient(app)
AUTH_HEADERS = {"X-API-Key": "test-key"}


# ============================================================================
# 1. Diagnostic Health Check Unit Tests (Exact 4 States)
# ============================================================================

def test_docker_cli_missing_state():
    """When docker CLI is not found on PATH or standard locations, reports DOCKER_CLI_MISSING."""
    with patch("aegis.execution.sandbox.get_docker_executable", return_value=None):
        diag = check_sandbox_health()

        assert diag["available"] is False
        assert diag["docker_binary_found"] is False
        assert diag["docker_daemon_reachable"] is False
        assert diag["required_image_present"] is False
        assert diag["image_available"] is False
        assert diag["sandbox_health"] == "DOCKER_CLI_MISSING"
        assert "not found" in diag["failure_reason"].lower()
        assert diag["remediation"] is not None
        assert "diagnostic" in diag
        assert diag["diagnostic"]["os"] == sys.platform


def test_docker_daemon_unavailable_state():
    """When docker binary is found but daemon fails/times out, reports DOCKER_DAEMON_UNAVAILABLE."""
    with patch("aegis.execution.sandbox.get_docker_executable", return_value="docker"), \
         patch("subprocess.run") as mock_run:

        mock_run.return_value = subprocess.CompletedProcess(
            args=["docker", "version"],
            returncode=1,
            stdout="",
            stderr="Cannot connect to the Docker daemon at //./pipe/docker_engine"
        )

        diag = check_sandbox_health()

        assert diag["available"] is False
        assert diag["docker_binary_found"] is True
        assert diag["docker_daemon_reachable"] is False
        assert diag["sandbox_health"] == "DOCKER_DAEMON_UNAVAILABLE"
        assert "not reachable" in diag["failure_reason"].lower()
        assert diag["remediation"] is not None


def test_sandbox_image_missing_state():
    """When docker daemon is reachable but required sandbox image is missing, reports SANDBOX_IMAGE_MISSING."""
    def mock_subprocess(args, **kwargs):
        if "version" in args:
            return subprocess.CompletedProcess(args, 0, stdout=json.dumps({"Server": {"Version": "27.3.1"}}), stderr="")
        if "info" in args:
            return subprocess.CompletedProcess(args, 0, stdout=json.dumps({"ServerVersion": "27.3.1"}), stderr="")
        if "inspect" in args:
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="Error: No such image: aegis-sandbox:latest")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    with patch("aegis.execution.sandbox.get_docker_executable", return_value="docker"), \
         patch("subprocess.run", side_effect=mock_subprocess):

        diag = check_sandbox_health()

        assert diag["available"] is False
        assert diag["docker_binary_found"] is True
        assert diag["docker_daemon_reachable"] is True
        assert diag["required_image_present"] is False
        assert diag["image_available"] is False
        assert diag["sandbox_health"] == "SANDBOX_IMAGE_MISSING"
        assert "not present" in diag["failure_reason"].lower()
        assert "doctor --build-image" in diag["remediation"]


def test_sandbox_ready_state():
    """When docker CLI, daemon, and required image are all present, reports SANDBOX_READY."""
    def mock_subprocess(args, **kwargs):
        if "version" in args:
            return subprocess.CompletedProcess(args, 0, stdout=json.dumps({"Server": {"Version": "27.3.1"}}), stderr="")
        if "info" in args:
            return subprocess.CompletedProcess(args, 0, stdout=json.dumps({"ServerVersion": "27.3.1"}), stderr="")
        if "inspect" in args:
            return subprocess.CompletedProcess(args, 0, stdout="{}", stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    with patch("aegis.execution.sandbox.get_docker_executable", return_value="docker"), \
         patch("subprocess.run", side_effect=mock_subprocess):

        diag = check_sandbox_health()

        assert diag["available"] is True
        assert diag["docker_binary_found"] is True
        assert diag["docker_daemon_reachable"] is True
        assert diag["required_image_present"] is True
        assert diag["image_available"] is True
        assert diag["sandbox_health"] == "SANDBOX_READY"
        assert diag["failure_reason"] is None
        assert diag["remediation"] is None


# ============================================================================
# 2. Windows-Specific Discovery & Retry State Transitions
# ============================================================================

def test_docker_found_via_path(tmp_path, monkeypatch):
    """Verifies docker binary discovery when on PATH."""
    fake_docker = tmp_path / ("docker.exe" if sys.platform == "win32" else "docker")
    fake_docker.write_text("#!/bin/sh\nexit 0\n")
    fake_docker.chmod(0o755)

    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ.get('PATH', '')}")
    discovered = get_docker_executable()
    assert discovered is not None
    assert Path(discovered).name.startswith("docker")


def test_docker_found_via_standard_windows_candidate_path(tmp_path, monkeypatch):
    """Verifies discovery in standard Windows Docker Desktop candidate directories."""
    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr("shutil.which", lambda x: None)

    # Mock subprocess.run for where.exe so it doesn't discover host's docker
    def mock_run(cmd, *args, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")
    monkeypatch.setattr("subprocess.run", mock_run)

    # Mock winreg so registry search doesn't find host's docker
    try:
        import winreg
        monkeypatch.setattr(winreg, "OpenKey", MagicMock(side_effect=FileNotFoundError))
    except ImportError:
        pass

    # Create fake modern Docker Desktop installation in LOCALAPPDATA
    docker_dir = tmp_path / "Programs" / "DockerDesktop" / "resources" / "bin"
    docker_dir.mkdir(parents=True, exist_ok=True)
    fake_docker = docker_dir / "docker.exe"
    fake_docker.write_text("dummy")

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(sys, "platform", "win32")

    discovered = get_docker_executable()
    assert discovered is not None
    assert Path(discovered).resolve() == fake_docker.resolve()
    # Also verify directory was prepended to PATH
    assert str(docker_dir).lower() in os.environ.get("PATH", "").lower()


def test_retry_state_transition_from_unavailable_to_ready():
    """Verifies clean state transition when daemon boots up on retry."""
    # First call: daemon is down
    with patch("aegis.execution.sandbox.get_docker_executable", return_value="docker"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(["docker", "version"], 1, stdout="", stderr="daemon off")
        diag1 = check_sandbox_health()
        assert diag1["available"] is False
        assert diag1["sandbox_health"] == "DOCKER_DAEMON_UNAVAILABLE"

    # Second call (retry): daemon is now active and image exists
    def mock_subprocess(args, **kwargs):
        if "version" in args:
            return subprocess.CompletedProcess(args, 0, stdout=json.dumps({"Server": {"Version": "27.3.1"}}), stderr="")
        if "inspect" in args:
            return subprocess.CompletedProcess(args, 0, stdout="{}", stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    with patch("aegis.execution.sandbox.get_docker_executable", return_value="docker"), \
         patch("subprocess.run", side_effect=mock_subprocess):
        diag2 = check_sandbox_health()
        assert diag2["available"] is True
        assert diag2["sandbox_health"] == "SANDBOX_READY"
        assert diag2["failure_reason"] is None


def test_print_sandbox_startup_banner(capsys):
    """Verifies startup banner output format and ensures no API key is leaked."""
    with patch("aegis.execution.sandbox.check_sandbox_health", return_value={
        "docker_binary_found": True,
        "docker_daemon_reachable": True,
        "required_image_present": True,
        "sandbox_health": "SANDBOX_READY",
    }):
        print_sandbox_startup_banner()
        captured = capsys.readouterr().out

        assert "A.I.R.A. SANDBOX" in captured
        assert "Docker CLI:     FOUND" in captured
        assert "Docker daemon:  REACHABLE" in captured
        assert "Sandbox image:  FOUND" in captured
        assert "Status:         READY" in captured
        # Security assertion: No API key or sensitive token leaked
        assert "key" not in captured.lower()
        assert "secret" not in captured.lower()


# ============================================================================
# 3. REST API /api/system/sandbox Endpoints
# ============================================================================

def test_api_system_sandbox_endpoint():
    """GET /api/system/sandbox returns 200 with full diagnostic payload and no-cache header."""
    res = client.get("/api/system/sandbox")
    assert res.status_code == 200
    assert "no-cache" in res.headers.get("Cache-Control", "")
    assert "no-store" in res.headers.get("Cache-Control", "")

    data = res.json()
    assert "available" in data
    assert "runtime" in data
    assert data["runtime"] == "docker"
    assert "docker_binary_found" in data
    assert "docker_daemon_reachable" in data
    assert "required_image_present" in data
    assert "image_available" in data
    assert "image_tag" in data
    assert "sandbox_health" in data
    assert "diagnostic" in data
    assert "platform" in data["diagnostic"]


def test_api_health_includes_sandbox_state():
    """GET /api/health includes sandbox availability and health status."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()

    assert "sandbox_available" in data
    assert "sandbox_health" in data
    assert "docker_available" in data


def test_api_system_sandbox_build_image_requires_auth():
    """POST /api/system/sandbox/build-image requires authentication."""
    res = client.post("/api/system/sandbox/build-image")
    assert res.status_code == 401


def test_api_system_sandbox_build_image_daemon_down():
    """POST /api/system/sandbox/build-image returns 503 when Docker daemon is unreachable."""
    with patch("aegis.api.service.is_docker_available", return_value=False):
        res = client.post("/api/system/sandbox/build-image", headers=AUTH_HEADERS)
        assert res.status_code == 503
        assert "SANDBOX_UNAVAILABLE" in res.json()["detail"]


def test_api_system_sandbox_build_image_success():
    """POST /api/system/sandbox/build-image returns 200 when build succeeds."""
    with patch("aegis.api.service.is_docker_available", return_value=True), \
         patch("aegis.api.service.build_sandbox_image_with_output", return_value=(True, "Built successfully")):
        res = client.post("/api/system/sandbox/build-image", headers=AUTH_HEADERS)
        assert res.status_code == 200
        assert res.json()["status"] == "success"


# ============================================================================
# 4. CLI "aira doctor" Tests
# ============================================================================

def test_aira_doctor_cli_text_matrix(capsys):
    """'aira doctor' outputs a clean matrix format with system checks."""
    exit_code = execute_doctor(json_output=False, build_image=False)
    captured = capsys.readouterr().out

    assert "A.I.R.A. SYSTEM CHECK" in captured
    assert "Python Environment" in captured
    assert "Docker CLI" in captured
    assert "Docker Engine" in captured
    assert "Sandbox Image" in captured
    assert "Network Isolation" in captured
    assert "Resource Limits" in captured
    assert "Overall Status:" in captured


def test_aira_doctor_cli_json_mode(capsys):
    """'aira doctor --json' outputs valid structured JSON."""
    exit_code = execute_doctor(json_output=True, build_image=False)
    captured = capsys.readouterr().out

    data = json.loads(captured)
    assert "status" in data
    assert "available" in data
    assert "checks" in data
    assert len(data["checks"]) == 6
    check_names = [c["name"] for c in data["checks"]]
    assert "Python Environment" in check_names
    assert "Docker CLI" in check_names
    assert "Docker Engine" in check_names
    assert "Sandbox Image" in check_names
    assert "Network Isolation" in check_names
    assert "Resource Limits" in check_names
    assert "sandbox" in data
    assert "remediation" in data


def test_aira_doctor_cli_all_pass(capsys):
    """'aira doctor' returns 0 when all checks pass."""
    def mock_subprocess(args, **kwargs):
        if "info" in args:
            return subprocess.CompletedProcess(args, 0, stdout=json.dumps({"ServerVersion": "27.3.1"}), stderr="")
        if "inspect" in args:
            return subprocess.CompletedProcess(args, 0, stdout="{}", stderr="")
        if "version" in args:
            return subprocess.CompletedProcess(args, 0, stdout="27.3.1", stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    with patch("aegis.execution.sandbox.get_docker_executable", return_value="docker"), \
         patch("subprocess.run", side_effect=mock_subprocess):

        code = execute_doctor(json_output=False, build_image=False)
        captured = capsys.readouterr().out

        assert code == 0
        assert "Overall Status:       READY" in captured
        assert "PASS" in captured


# ============================================================================
# 5. Strict Fail-Closed Verification Sandbox Enforcement
# ============================================================================

def test_project_verification_strictly_fails_closed_when_sandbox_unavailable():
    """Verify endpoint strictly fails closed with 503 and exact reason when Docker is down."""
    import zipfile

    # Create minimal in-memory project zip
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("calc.py", "def add(a, b): return a + b\n")
        zf.writestr("test_calc.py", "import calc\ndef test_add(): assert calc.add(1, 2) == 3\n")
    buf.seek(0)

    upload_res = client.post(
        "/api/projects/upload",
        files={"archive": ("proj.zip", buf, "application/zip")},
        headers=AUTH_HEADERS,
    )
    assert upload_res.status_code == 201
    project_id = upload_res.json()["project_id"]

    # When Docker is down
    with patch("aegis.api.service.is_docker_available", return_value=False):
        verify_res = client.post(
            f"/api/projects/{project_id}/verify",
            json={"tier": "standard"},
            headers=AUTH_HEADERS,
        )
        assert verify_res.status_code == 503
        detail = verify_res.json()["detail"]
        assert "Sandbox unavailable" in detail
        assert "isolated container runtime" in detail

    # Cleanup
    client.delete(f"/api/projects/{project_id}", headers=AUTH_HEADERS)
