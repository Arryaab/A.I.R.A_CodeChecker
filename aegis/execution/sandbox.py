from __future__ import annotations

import logging
import subprocess
import json
from dataclasses import dataclass
from pathlib import Path

from aegis.execution.runner import TestResult, run_tests, PYTEST_EXIT_INTERNAL_ERROR

logger = logging.getLogger(__name__)

@dataclass
class SandboxResult:
    test_result: TestResult
    used_sandbox: bool
    container_id: str = ""

def is_docker_available() -> bool:
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def build_sandbox_image(docker_image: str = "aegis-sandbox:latest") -> bool:
    try:
        dockerfile_content = "FROM python:3.12-slim\nRUN pip install pytest\nWORKDIR /workspace\nCMD [\"python\", \"-m\", \"pytest\", \"-v\", \"--tb=short\", \"--color=no\", \"-p\", \"no:cacheprovider\"]"
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
    docker_image: str = "aegis-sandbox:latest",
) -> SandboxResult:
    project_dir = Path(project_dir)
    
    if not use_docker or not is_docker_available():
        test_result = run_tests(project_dir, timeout=timeout)
        return SandboxResult(test_result=test_result, used_sandbox=False)

    try:
        create_res = subprocess.run(
            [
                "docker", "create",
                "--network", "none",
                "--cpus", "1.0",
                "--memory", "512m",
                "--pids-limit", "50",
                "--security-opt", "no-new-privileges",
                "--cap-drop", "ALL",
                docker_image
            ],
            capture_output=True, text=True, check=True
        )
        container_id = create_res.stdout.strip()
        subprocess.run(
            ["docker", "cp", f"{project_dir}/.", f"{container_id}:/workspace/"],
            check=True, capture_output=True
        )
        run_res = subprocess.run(
            ["docker", "start", "-a", container_id],
            capture_output=True, text=True, timeout=timeout
        )
        stdout = run_res.stdout
        stderr = run_res.stderr
        exit_code = run_res.returncode
        passed = exit_code == 0
        test_result = TestResult(
            passed=passed,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=timeout,
            tests_passed=0,
            tests_failed=0,
            tests_error=0,
            summary_line="Docker run completed",
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
