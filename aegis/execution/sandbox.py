from __future__ import annotations

import logging
import subprocess
import json
import time
from dataclasses import dataclass
from pathlib import Path

from aegis.execution.runner import (
    TestResult,
    run_tests,
    PYTEST_EXIT_INTERNAL_ERROR,
    _parse_counts,
    _extract_summary_line,
    _extract_failures,
)

logger = logging.getLogger(__name__)

class SandboxUnavailableError(RuntimeError):
    """Raised when sandbox execution is required by security policy but unavailable."""
    pass

@dataclass
class SandboxResult:
    test_result: TestResult
    used_sandbox: bool
    container_id: str = ""

def is_docker_available() -> bool:
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, text=True)
        return result.returncode == 0
    except (FileNotFoundError, Exception):
        return False

def get_docker_create_command(
    docker_image: str = "aegis-sandbox:latest",
    test_files: list[str] | None = None
) -> list[str]:
    """
    Constructs hardened Docker create command explicitly passing selected test files.
    Applies zero-network, read-only rootfs, tmpfs, ulimits, dropped capabilities, and no-new-privileges.
    """
    pytest_args = ["python", "-m", "pytest", "-v", "--tb=short", "--color=no", "-p", "no:cacheprovider"]
    if test_files:
        pytest_args.extend([str(t).replace("\\", "/") for t in test_files])

    return [
        "docker", "create",
        "--network", "none",
        "--cpus", "1.0",
        "--memory", "512m",
        "--pids-limit", "50",
        "--security-opt", "no-new-privileges",
        "--cap-drop", "ALL",
        "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
        "--tmpfs", "/workspace/.pytest_cache:rw,noexec,nosuid,size=32m",
        "--ulimit", "nofile=1024:2048",
        "--ulimit", "fsize=50000000",
        docker_image,
        *pytest_args
    ]

def build_sandbox_image(docker_image: str = "aegis-sandbox:latest") -> bool:
    try:
        dockerfile_content = "FROM python:3.12-slim\nRUN pip install --no-cache-dir pytest==8.3.4\nWORKDIR /workspace\nCMD [\"python\", \"-m\", \"pytest\", \"-v\", \"--tb=short\", \"--color=no\", \"-p\", \"no:cacheprovider\"]"
        result = subprocess.run(
            ["docker", "build", "-t", docker_image, "-"],
            input=dockerfile_content,
            text=True,
            capture_output=True
        )
        if result.returncode != 0:
            logger.error(f"Failed to build sandbox image: {result.stderr}")
            return False
        return True
    except Exception as e:
        logger.error(f"Docker build exception: {e}")
        return False

def run_tests_sandboxed(
    project_dir: str | Path,
    *,
    timeout: int = 60,
    use_docker: bool = False,
    require_sandbox: bool = False,
    docker_image: str = "aegis-sandbox:latest",
    test_files: list[str] | None = None,
) -> SandboxResult:
    project_dir = Path(project_dir)
    
    if require_sandbox and not is_docker_available():
        raise SandboxUnavailableError(
            "Aegis Security Failure: Docker sandbox is required for executing untrusted changes, "
            "but the Docker daemon is unavailable. To bypass for local non-production testing, "
            "pass --unsafe-local."
        )

    if not use_docker or not is_docker_available():
        test_result = run_tests(project_dir, timeout=timeout, test_files=test_files)
        return SandboxResult(test_result=test_result, used_sandbox=False)

    container_id = ""
    try:
        create_cmd = get_docker_create_command(docker_image=docker_image, test_files=test_files)
        create_res = subprocess.run(
            create_cmd,
            capture_output=True, text=True, check=True
        )
        container_id = create_res.stdout.strip()
        subprocess.run(
            ["docker", "cp", f"{project_dir}/.", f"{container_id}:/workspace/"],
            check=True, capture_output=True
        )
        start_exec = time.monotonic()
        run_res = subprocess.run(
            ["docker", "start", "-a", container_id],
            capture_output=True, text=True, timeout=timeout
        )
        duration_seconds = round(time.monotonic() - start_exec, 3)
        stdout = run_res.stdout
        stderr = run_res.stderr
        exit_code = run_res.returncode
        passed = exit_code == 0
        
        tests_passed, tests_failed, tests_error = _parse_counts(stdout)
        summary_line = _extract_summary_line(stdout) or "Docker run completed"
        failure_messages = _extract_failures(stdout)

        test_result = TestResult(
            passed=passed,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=duration_seconds,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            tests_error=tests_error,
            summary_line=summary_line,
            failure_messages=failure_messages,
        )
        return SandboxResult(test_result=test_result, used_sandbox=True, container_id=container_id)
    except subprocess.TimeoutExpired as e:
        tr = TestResult(False, PYTEST_EXIT_INTERNAL_ERROR, "", str(e), float(timeout), 0, 0, 0, "Timeout")
        return SandboxResult(test_result=tr, used_sandbox=True, container_id=container_id)
    except Exception as e:
        tr = TestResult(False, PYTEST_EXIT_INTERNAL_ERROR, "", str(e), 0.0, 0, 0, 0, "Error")
        return SandboxResult(test_result=tr, used_sandbox=True, container_id=container_id if 'container_id' in locals() else "")
    finally:
        if 'container_id' in locals() and container_id:
            subprocess.run(["docker", "rm", "-f", container_id], capture_output=True)
