import os
import sys
import shutil
import platform
import logging
import subprocess
import json
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List

from aegis.execution.runner import (
    TestResult,
    run_tests,
    PYTEST_EXIT_INTERNAL_ERROR,
    _parse_counts,
    _parse_structured_test_results,
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
    command: List[str] = field(default_factory=list)
    working_directory: str = "/workspace"

def _ensure_in_path(parent_dir: Path) -> None:
    p_str = str(parent_dir)
    cur = os.environ.get("PATH", "")
    cur_parts = [p.strip().lower() for p in cur.split(os.pathsep) if p.strip()]
    if p_str.lower() not in cur_parts:
        os.environ["PATH"] = f"{p_str}{os.pathsep}{cur}"

def get_docker_executable() -> Optional[str]:
    """
    Finds the docker CLI executable on PATH or in standard OS installation directories.
    Handles Windows Docker Desktop paths (both machine and per-user), where.exe discovery,
    and Windows Registry PATH values so it survives mid-session Docker installations.
    Ensures the discovered binary's directory is prepended to os.environ["PATH"] so that
    companion executables (e.g. docker-credential-desktop) are accessible.
    """
    # 1. Check current process PATH via shutil.which
    docker_bin = shutil.which("docker") or shutil.which("docker.exe")
    if docker_bin and Path(docker_bin).is_file():
        _ensure_in_path(Path(docker_bin).parent)
        return str(Path(docker_bin).resolve())

    # 2. On Windows, check where.exe docker
    if sys.platform == "win32":
        try:
            where_res = subprocess.run(["where.exe", "docker"], capture_output=True, text=True, timeout=2)
            if where_res.returncode == 0:
                for line in where_res.stdout.splitlines():
                    cand = line.strip()
                    if cand and Path(cand).is_file():
                        _ensure_in_path(Path(cand).parent)
                        return str(Path(cand).resolve())
        except Exception:
            pass

        # 3. Discover from Windows Registry (Machine and User PATH)
        try:
            import winreg
            reg_paths: List[str] = []
            for hkey, subkey in [
                (winreg.HKEY_CURRENT_USER, r"Environment"),
                (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
            ]:
                try:
                    with winreg.OpenKey(hkey, subkey) as k:
                        val, _ = winreg.QueryValueEx(k, "Path")
                        if val:
                            reg_paths.extend(val.split(";"))
                except Exception:
                    pass

            for rp in reg_paths:
                clean_rp = rp.strip()
                if not clean_rp:
                    continue
                cand1 = Path(clean_rp) / "docker.exe"
                if cand1.is_file():
                    _ensure_in_path(cand1.parent)
                    return str(cand1.resolve())
                cand2 = Path(clean_rp) / "resources" / "bin" / "docker.exe"
                if cand2.is_file():
                    _ensure_in_path(cand2.parent)
                    return str(cand2.resolve())
        except Exception:
            pass

        # 4. Standard Windows Docker Desktop locations (no hardcoded usernames)
        candidates = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "DockerDesktop" / "resources" / "bin" / "docker.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Docker" / "Docker" / "resources" / "bin" / "docker.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Docker" / "resources" / "bin" / "docker.exe",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Docker" / "Docker" / "resources" / "bin" / "docker.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Docker" / "resources" / "bin" / "docker.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Docker" / "resources" / "bin" / "docker.exe",
            Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "DockerDesktop" / "version-bin" / "docker.exe",
            Path(os.environ.get("USERPROFILE", "")) / "AppData" / "Local" / "Programs" / "DockerDesktop" / "resources" / "bin" / "docker.exe",
        ]
        for candidate in candidates:
            if candidate.is_file():
                _ensure_in_path(candidate.parent)
                return str(candidate.resolve())

    return None

def is_docker_available() -> bool:
    """
    Checks if Docker CLI is present and the Docker daemon is responding.
    """
    docker_bin = get_docker_executable()
    if not docker_bin:
        return False
    try:
        result = subprocess.run([docker_bin, "info"], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return False

def check_sandbox_health(docker_image: str = "") -> Dict[str, Any]:
    """
    Performs comprehensive diagnostic inspection of container runtime and sandbox image.
    Sequence:
      1. locate docker executable
      2. execute docker version
      3. verify Docker daemon/server is reachable
      4. verify required sandbox image
    Returns structured health report with exact states:
      - DOCKER_CLI_MISSING
      - DOCKER_DAEMON_UNAVAILABLE
      - SANDBOX_IMAGE_MISSING
      - SANDBOX_READY
    """
    if not docker_image:
        docker_image = os.environ.get("DOCKER_SANDBOX_IMAGE", "aegis-sandbox:latest")

    docker_bin = get_docker_executable()
    docker_binary_found = docker_bin is not None
    docker_daemon_reachable = False
    docker_version: Optional[str] = None
    docker_api_version: Optional[str] = None
    required_image_present = False
    failure_reason: Optional[str] = None
    remediation: Optional[str] = None
    error_detail: Optional[str] = None

    checked_paths: List[str] = ["PATH"]
    if sys.platform == "win32":
        checked_paths.extend([
            str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "DockerDesktop" / "resources" / "bin" / "docker.exe"),
            str(Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Docker" / "Docker" / "resources" / "bin" / "docker.exe"),
        ])
    else:
        checked_paths.extend(["/usr/bin/docker", "/usr/local/bin/docker"])

    if not docker_binary_found:
        sandbox_health = "DOCKER_CLI_MISSING"
        failure_reason = "Docker CLI binary not found on PATH or standard system locations."
        if sys.platform == "win32":
            remediation = "Install Docker Desktop for Windows (https://docs.docker.com/desktop/install/windows/ or 'winget install Docker.DockerDesktop') and ensure Docker is running."
        else:
            remediation = "Install Docker Engine (https://docs.docker.com/engine/install/) and ensure the docker CLI is on PATH."
    else:
        # Step 2: execute docker version & verify Docker daemon/server is reachable
        try:
            ver_res = subprocess.run(
                [docker_bin, "version", "--format", "{{json .}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if ver_res.returncode == 0:
                try:
                    ver_data = json.loads(ver_res.stdout)
                    server_data = ver_data.get("Server", {})
                    if server_data:
                        docker_daemon_reachable = True
                        docker_version = server_data.get("Version")
                        docker_api_version = server_data.get("APIVersion")
                except Exception:
                    docker_daemon_reachable = True
            else:
                error_detail = ver_res.stderr.strip()
        except subprocess.TimeoutExpired:
            error_detail = "Timed out connecting to Docker daemon after 5s"
        except Exception as e:
            error_detail = str(e)

        # Fallback check with docker info if json parsing or version check was incomplete
        if not docker_daemon_reachable:
            try:
                info_res = subprocess.run(
                    [docker_bin, "info", "--format", "{{json .}}"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if info_res.returncode == 0:
                    docker_daemon_reachable = True
                    try:
                        info_data = json.loads(info_res.stdout)
                        if not docker_version:
                            docker_version = info_data.get("ServerVersion")
                    except Exception:
                        pass
                else:
                    error_detail = info_res.stderr.strip() or error_detail or "Docker daemon returned non-zero exit code"
            except Exception as e:
                error_detail = str(e)

        if not docker_daemon_reachable:
            sandbox_health = "DOCKER_DAEMON_UNAVAILABLE"
            failure_reason = "Docker Engine is not reachable. Start Docker Desktop and retry."
            if sys.platform == "win32":
                remediation = "Launch Docker Desktop from Start menu, wait for the whale icon to show 'Engine running', and retry the check."
            else:
                remediation = "Start the Docker daemon (e.g. 'sudo systemctl start docker') and ensure permissions are configured."
        else:
            # Step 3: verify required sandbox image
            try:
                inspect_res = subprocess.run(
                    [docker_bin, "image", "inspect", docker_image],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                required_image_present = (inspect_res.returncode == 0)
            except Exception as e:
                required_image_present = False
                error_detail = str(e)

            if not required_image_present:
                sandbox_health = "SANDBOX_IMAGE_MISSING"
                failure_reason = f"Sandbox image '{docker_image}' is not present."
                remediation = f"Build the required image by running 'aira doctor --build-image' or 'docker build -t {docker_image} - < Dockerfile.sandbox'."
            else:
                # Step 4: report READY
                sandbox_health = "SANDBOX_READY"
                failure_reason = None
                remediation = None

    available = (sandbox_health == "SANDBOX_READY")

    return {
        "available": available,
        "runtime": "docker",
        "docker_binary_found": docker_binary_found,
        "docker_binary_path": docker_bin,
        "docker_daemon_reachable": docker_daemon_reachable,
        "docker_version": docker_version,
        "docker_api_version": docker_api_version,
        "required_image_present": required_image_present,
        "image_available": required_image_present,
        "image_tag": docker_image,
        "sandbox_health": sandbox_health,
        "failure_reason": failure_reason,
        "remediation": remediation,
        "diagnostic": {
            "os": sys.platform,
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "checked_paths": checked_paths,
            "docker_host_env": os.environ.get("DOCKER_HOST"),
            "error_detail": error_detail,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }

def print_sandbox_startup_banner() -> None:
    """
    Prints the A.I.R.A. sandbox startup diagnostic banner.
    Outputs Docker CLI, Docker daemon, Sandbox image, and Status without leaking any API keys.
    """
    diag = check_sandbox_health()
    cli_str = "FOUND" if diag.get("docker_binary_found") else "MISSING"
    daemon_str = "REACHABLE" if diag.get("docker_daemon_reachable") else "UNREACHABLE"
    image_str = "FOUND" if diag.get("required_image_present") else "MISSING"
    status_str = "READY" if diag.get("sandbox_health") == "SANDBOX_READY" else "DEGRADED"

    print("A.I.R.A. SANDBOX", flush=True)
    print(f"Docker CLI:     {cli_str}", flush=True)
    print(f"Docker daemon:  {daemon_str}", flush=True)
    print(f"Sandbox image:  {image_str}", flush=True)
    print(f"Status:         {status_str}", flush=True)

def get_docker_create_command(
    docker_image: str = "",
    test_files: list[str] | None = None,
    stream_junit_xml: bool = False,
) -> list[str]:
    """
    Constructs hardened Docker create command explicitly passing selected test files.
    Applies zero-network, read-only rootfs, tmpfs, ulimits, dropped capabilities, and no-new-privileges.
    If stream_junit_xml is True, wraps in a shell script that generates and streams JUnit XML report.
    """
    docker_bin = get_docker_executable() or "docker"
    if not docker_image:
        docker_image = os.environ.get("DOCKER_SANDBOX_IMAGE", "aegis-sandbox:latest")

    if stream_junit_xml:
        pytest_args = ["python", "-m", "pytest", "-v", "--tb=short", "--color=no", "-p", "no:cacheprovider"]
        if test_files:
            pytest_args.extend([str(t).replace("\\", "/") for t in test_files])
        else:
            pytest_args.append("--ignore=user_tests")

        cmd_script = (
            f"{' '.join(pytest_args)} --junitxml=/tmp/aira-pytest-results.xml; "
            "ret=$?; "
            "echo '===AIRA_JUNIT_XML_START==='; "
            "cat /tmp/aira-pytest-results.xml 2>/dev/null; "
            "echo '===AIRA_JUNIT_XML_END==='; "
            "exit $ret"
        )
        entrypoint_args = ["sh", "-c", cmd_script]
    else:
        entrypoint_args = ["pytest", "-v", "--tb=short", "--color=no", "-p", "no:cacheprovider"]
        if test_files:
            entrypoint_args.extend([str(t).replace("\\", "/") for t in test_files])

    return [
        docker_bin, "create",
        "--network", "none",
        "--cpus", "1.0",
        "--memory", "512m",
        "--pids-limit", "50",
        "--security-opt", "no-new-privileges",
        "--cap-drop", "ALL",
        "--read-only",
        "-v", "/workspace",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
        "--ulimit", "nofile=1024:2048",
        "--ulimit", "fsize=50000000",
        docker_image,
        *entrypoint_args
    ]

def build_sandbox_image(docker_image: str = "") -> bool:
    success, _ = build_sandbox_image_with_output(docker_image)
    return success

def build_sandbox_image_with_output(docker_image: str = "") -> Tuple[bool, str]:
    if not docker_image:
        docker_image = os.environ.get("DOCKER_SANDBOX_IMAGE", "aegis-sandbox:latest")
    docker_bin = get_docker_executable()
    if not docker_bin or not is_docker_available():
        return False, "Docker daemon is not reachable."
    try:
        dockerfile_content = (
            "FROM python:3.12-slim\n"
            "RUN pip install --no-cache-dir pytest==8.3.4\n"
            "WORKDIR /workspace\n"
            "CMD [\"python\", \"-m\", \"pytest\", \"-v\", \"--tb=short\", \"--color=no\", \"-p\", \"no:cacheprovider\"]\n"
        )
        result = subprocess.run(
            [docker_bin, "build", "-t", docker_image, "-"],
            input=dockerfile_content,
            text=True,
            capture_output=True,
            timeout=180
        )
        if result.returncode != 0:
            err = result.stderr.strip() or result.stdout.strip()
            logger.error(f"Failed to build sandbox image: {err}")
            return False, f"Failed to build sandbox image: {err}"
        return True, f"Successfully built image '{docker_image}'"
    except Exception as e:
        logger.error(f"Docker build exception: {e}")
        return False, f"Docker build exception: {e}"

def parse_pytest_collection_output(stdout: str) -> list[str]:
    """
    Authoritative parser for pytest collection output.
    Supports both flat (-q) node ID format and hierarchical (<Dir>, <Module>, <Function>) tree output.
    """
    tests, _ = parse_pytest_collection_detailed(stdout)
    return tests


class CollectionResult(list):
    """List of collected test node IDs with collection error metadata."""
    def __init__(self, nodeids: list[str] = None, collection_error_nodeids: list[str] = None):
        super().__init__(nodeids or [])
        self.collected_nodeids = list(nodeids or [])
        self.collection_error_nodeids = list(collection_error_nodeids or [])
        self.collected_count = len(self.collected_nodeids)
        self.collection_error_count = len(self.collection_error_nodeids)


def parse_pytest_collection_detailed(stdout: str) -> tuple[list[str], list[str]]:
    """
    Parses pytest --collect-only output into:
    (collected_test_nodeids, collection_error_nodeids)
    Separates actual test item node IDs from files with collection failures.
    """
    import re
    nodeids = []
    error_nodeids = []

    # 1. Flat node ID format:
    for line in stdout.splitlines():
        line = line.strip()
        if "::" in line and not line.startswith("<") and not line.startswith("=") and not line.startswith("user_tests"):
            nodeids.append(line.replace("\\", "/"))

    # 2. Parse collection errors from pytest summary info:
    for m in re.finditer(r"^ERROR\s+(\S+)", stdout, re.MULTILINE):
        err_path = m.group(1).replace("\\", "/")
        if not any(skip in err_path for skip in ["__pycache__"]):
            error_nodeids.append(err_path)

    for m in re.finditer(r"ERROR collecting\s+(\S+)", stdout):
        err_path = m.group(1).replace("\\", "/")
        if err_path not in error_nodeids:
            error_nodeids.append(err_path)

    # 3. Hierarchical tree format fallback if flat yielded no items:
    if not nodeids:
        stack = []
        for line in stdout.splitlines():
            m = re.match(r"^( *)\<(Dir|Package|Module|Class|UnitTestCase|Function|Item)\s+([^>]+)\>", line)
            if not m:
                continue
            indent = len(m.group(1))
            tag = m.group(2)
            name = m.group(3).strip()
            while stack and stack[-1][0] >= indent:
                stack.pop()
            stack.append((indent, tag, name))
            if tag in ("Function", "Item"):
                parts_path = []
                parts_nodes = []
                for _, t, n in stack:
                    if t in ("Dir", "Package"):
                        if n not in ("workspace", "."):
                            parts_path.append(n)
                    elif t == "Module":
                        parts_path.append(n)
                    elif t in ("Class", "UnitTestCase", "Function", "Item"):
                        parts_nodes.append(n)
                file_part = "/".join(parts_path)
                node_id = file_part + "::" + "::".join(parts_nodes) if parts_nodes else file_part
                nodeids.append(node_id.replace("\\", "/"))

    collected_unique = list(dict.fromkeys(nodeids))
    error_unique = list(dict.fromkeys(error_nodeids))
    return collected_unique, error_unique


def collect_tests_sandboxed(
    project_dir: str | Path,
    *,
    timeout: int = 30,
    docker_image: str = "",
) -> CollectionResult:
    """
    Authoritative test discovery executing 'pytest --collect-only -q' inside the Docker sandbox.
    Discovers all test node IDs (e.g. 'test_calc.py::test_add') exactly as collected by pytest.
    Returns a CollectionResult list with separate collected_nodeids and collection_error_nodeids.
    Falls back to AST-based discovery if Docker is unavailable.
    """
    project_dir = Path(project_dir)
    if not is_docker_available():
        from aegis.uploads.detection import discover_project_tests
        return CollectionResult(discover_project_tests(project_dir), [])

    docker_bin = get_docker_executable() or "docker"
    if not docker_image:
        docker_image = os.environ.get("DOCKER_SANDBOX_IMAGE", "aegis-sandbox:latest")

    container_id = ""
    try:
        create_cmd = [
            docker_bin, "create",
            "--network", "none",
            "--read-only",
            "-v", "/workspace",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            docker_image,
            "python", "-m", "pytest", "-o", "addopts=", "--collect-only", "-q", "--continue-on-collection-errors", "-p", "no:cacheprovider", "--ignore=user_tests"
        ]
        res = subprocess.run(create_cmd, capture_output=True, text=True, check=True)
        container_id = res.stdout.strip()
        subprocess.run(
            [docker_bin, "cp", f"{project_dir}/.", f"{container_id}:/workspace/"],
            check=True, capture_output=True
        )
        run_res = subprocess.run(
            [docker_bin, "start", "-a", container_id],
            capture_output=True, text=True, timeout=timeout
        )
        tests, errors = parse_pytest_collection_detailed(run_res.stdout)
        return CollectionResult(tests, errors)
    except Exception as e:
        logger.warning(f"Sandbox test collection failed, falling back to AST: {e}")
    finally:
        if container_id:
            subprocess.run([docker_bin, "rm", "-f", "-v", container_id], capture_output=True)

    from aegis.uploads.detection import discover_project_tests
    return CollectionResult(discover_project_tests(project_dir), [])


def run_tests_sandboxed(
    project_dir: str | Path,
    *,
    timeout: int = 60,
    use_docker: bool = False,
    require_sandbox: bool = False,
    docker_image: str = "",
    test_files: list[str] | None = None,
) -> SandboxResult:
    if not docker_image:
        docker_image = os.environ.get("DOCKER_SANDBOX_IMAGE", "aegis-sandbox:latest")
    project_dir = Path(project_dir)
    
    if require_sandbox and not is_docker_available():
        raise SandboxUnavailableError(
            "Aegis Security Failure: Docker sandbox is required for executing untrusted changes, "
            "but the Docker daemon is unavailable. To bypass for local non-production testing, "
            "pass --unsafe-local."
        )

    if not use_docker or not is_docker_available():
        test_result = run_tests(project_dir, timeout=timeout, test_files=test_files)
        exec_cmd = ["python", "-m", "pytest", "-v", "--tb=short", "--color=no", "-p", "no:cacheprovider", "--junitxml=/tmp/aira-pytest-results.xml"]
        if test_files:
            exec_cmd.extend([str(t).replace("\\", "/") for t in test_files])
        return SandboxResult(test_result=test_result, used_sandbox=False, command=exec_cmd, working_directory="/workspace")

    container_id = ""
    docker_bin = get_docker_executable() or "docker"
    exec_cmd = ["python", "-m", "pytest", "-v", "--tb=short", "--color=no", "-p", "no:cacheprovider", "--junitxml=/tmp/aira-pytest-results.xml"]
    if test_files:
        exec_cmd.extend([str(t).replace("\\", "/") for t in test_files])
    else:
        exec_cmd.append("--ignore=user_tests")

    try:
        create_cmd = get_docker_create_command(docker_image=docker_image, test_files=test_files, stream_junit_xml=True)
        create_res = subprocess.run(
            create_cmd,
            capture_output=True, text=True, check=True
        )
        container_id = create_res.stdout.strip()
        subprocess.run(
            [docker_bin, "cp", f"{project_dir}/.", f"{container_id}:/workspace/"],
            check=True, capture_output=True
        )
        start_exec = time.monotonic()
        run_res = subprocess.run(
            [docker_bin, "start", "-a", container_id],
            capture_output=True, text=True, timeout=timeout
        )
        duration_seconds = round(time.monotonic() - start_exec, 3)
        stdout = run_res.stdout
        stderr = run_res.stderr
        exit_code = run_res.returncode
        passed = exit_code == 0
        
        parsed = None
        if "===AIRA_JUNIT_XML_START===" in stdout:
            parts = stdout.split("===AIRA_JUNIT_XML_START===", 1)
            test_stdout = parts[0]
            if "===AIRA_JUNIT_XML_END===" in parts[1]:
                xml_content = parts[1].split("===AIRA_JUNIT_XML_END===", 1)[0].strip()
                try:
                    from aegis.execution.runner import parse_junit_xml
                    parsed = parse_junit_xml(xml_content)
                except Exception as e:
                    logger.warning(f"Error parsing JUnit XML from container: {e}")
            stdout = test_stdout.strip()

        # Text-based fallback: ONLY when JUnit XML was not available or completely
        # failed to parse. When JUnit XML parsed successfully, ALWAYS trust it —
        # it has authoritative collection error classification that the text parser
        # cannot replicate. The text parser treats pytest's "errors" summary
        # (which are collection errors) as execution errors, causing the
        # "365 executed, 365 errors" miscount.
        if not parsed:
            text_parsed = _parse_structured_test_results(stdout)
            parsed = text_parsed

        summary_line = _extract_summary_line(stdout) or "Docker run completed"
        failure_messages = parsed.get("failure_messages") or _extract_failures(stdout)

        test_result = TestResult(
            passed=passed,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=duration_seconds,
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
            raw_junit_testcase_count=parsed.get("raw_junit_testcase_count", 0),
            unique_junit_testcase_count=parsed.get("unique_junit_testcase_count", 0),
        )
        return SandboxResult(test_result=test_result, used_sandbox=True, container_id=container_id, command=exec_cmd, working_directory="/workspace")
    except subprocess.TimeoutExpired as e:
        tr = TestResult(False, PYTEST_EXIT_INTERNAL_ERROR, "", str(e), float(timeout), 0, 0, 0, "Timeout")
        return SandboxResult(test_result=tr, used_sandbox=True, container_id=container_id, command=exec_cmd, working_directory="/workspace")
    except Exception as e:
        tr = TestResult(False, PYTEST_EXIT_INTERNAL_ERROR, "", str(e), 0.0, 0, 0, 0, "Error")
        return SandboxResult(test_result=tr, used_sandbox=True, container_id=container_id if 'container_id' in locals() else "", command=exec_cmd, working_directory="/workspace")
    finally:
        if 'container_id' in locals() and container_id:
            subprocess.run([docker_bin, "rm", "-f", "-v", container_id], capture_output=True)
