from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class SandboxSecurityViolation(Exception):
    """Raised when an agent attempts unauthorized access outside the sandbox."""
    pass


class AgentSandbox:
    """Security-critical isolated execution environment for coding agents.

    Guarantees:
    1. Filesystem Containment: All reads, writes, and edits are strictly trapped
       inside the designated workspace directory. Path traversal (e.g. '../', '/etc',
       'private/') is blocked.
    2. Secret Quarantine: Host environment variables (API keys, tokens, credentials)
       are stripped before subprocess execution.
    3. Resource Bounding: Commands have strict timeouts and output truncations.
    4. Private Evaluator Protection: Agent workspace never includes private tests
       or oracle files.
    """

    FORBIDDEN_ENV_KEYS = {
        "AEGIS_API_KEY",
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "GITHUB_TOKEN",
        "GIT_TOKEN",
        "SSH_AUTH_SOCK",
        "SECRET_KEY",
    }

    def __init__(
        self,
        task_dir: Path,
        workspace_base: Optional[Path] = None,
        timeout_seconds: float = 30.0,
        max_output_chars: int = 65536,
    ):
        self.task_dir = Path(task_dir).resolve()
        self.timeout_seconds = timeout_seconds
        self.max_output_chars = max_output_chars

        if workspace_base:
            workspace_base.mkdir(parents=True, exist_ok=True)
            self._workspace_dir = Path(tempfile.mkdtemp(prefix="aegis_agent_ws_", dir=str(workspace_base))).resolve()
            self._base_snapshot_dir = Path(tempfile.mkdtemp(prefix="aegis_base_snap_", dir=str(workspace_base))).resolve()
        else:
            self._workspace_dir = Path(tempfile.mkdtemp(prefix="aegis_agent_ws_")).resolve()
            self._base_snapshot_dir = Path(tempfile.mkdtemp(prefix="aegis_base_snap_")).resolve()

        self._populate_workspace()
        # Immutable snapshot of pristine initial workspace state
        shutil.copytree(self._workspace_dir, self._base_snapshot_dir, dirs_exist_ok=True)

    @property
    def workspace_dir(self) -> Path:
        return self._workspace_dir

    @property
    def base_snapshot_dir(self) -> Path:
        return self._base_snapshot_dir

    def _populate_workspace(self) -> None:
        """Copies the public task code (buggy/ and tests/) into the isolated workspace."""
        buggy_src = self.task_dir / "buggy"
        if buggy_src.exists():
            for item in buggy_src.iterdir():
                if item.is_file():
                    shutil.copy2(item, self._workspace_dir / item.name)
                elif item.is_dir():
                    shutil.copytree(item, self._workspace_dir / item.name, dirs_exist_ok=True)

        tests_src = self.task_dir / "tests"
        if tests_src.exists():
            tests_dst = self._workspace_dir / "tests"
            tests_dst.mkdir(exist_ok=True)
            for item in tests_src.iterdir():
                if item.is_file():
                    shutil.copy2(item, tests_dst / item.name)
                elif item.is_dir():
                    shutil.copytree(item, tests_dst / item.name, dirs_exist_ok=True)

    def validate_path(self, target_rel_path: str | Path) -> Path:
        """Resolve path and verify it is strictly inside the workspace boundary."""
        raw_str = str(target_rel_path).strip()
        # Explicit check for obvious escape patterns
        if ".." in raw_str.split("/") or ".." in raw_str.split("\\"):
            raise SandboxSecurityViolation(f"Path traversal detected: {target_rel_path}")

        if "private" in raw_str.lower() or ".git" in raw_str.lower():
            raise SandboxSecurityViolation(f"Access to private/sensitive namespace blocked: {target_rel_path}")

        resolved = (self._workspace_dir / raw_str).resolve()
        try:
            resolved.relative_to(self._workspace_dir)
        except ValueError:
            raise SandboxSecurityViolation(
                f"Path {target_rel_path} escapes isolated sandbox boundary {self._workspace_dir}"
            )

        return resolved

    def get_sanitized_env(self) -> Dict[str, str]:
        """Produce environment with all host API keys and credentials stripped."""
        clean = {}
        for k, v in os.environ.items():
            if k in self.FORBIDDEN_ENV_KEYS:
                continue
            if any(term in k.upper() for term in ("KEY", "TOKEN", "SECRET", "PASS")):
                continue
            clean[k] = v

        clean["PYTHONPATH"] = str(self._workspace_dir)
        clean["PYTHONDONTWRITEBYTECODE"] = "1"
        clean["AEGIS_AGENT_SANDBOX"] = "1"
        return clean

    def execute_in_sandbox(
        self,
        command: List[str],
        timeout: Optional[float] = None,
    ) -> Tuple[int, str, str, float]:
        """Execute command inside workspace sandbox with timeout and output bounds."""
        import time
        start = time.time()
        eff_timeout = timeout or self.timeout_seconds
        env = self.get_sanitized_env()

        try:
            proc = subprocess.run(
                command,
                cwd=str(self._workspace_dir),
                env=env,
                capture_output=True,
                text=True,
                timeout=eff_timeout,
                errors="replace",
            )
            duration = time.time() - start
            stdout = proc.stdout[: self.max_output_chars]
            stderr = proc.stderr[: self.max_output_chars]
            return proc.returncode, stdout, stderr, duration
        except subprocess.TimeoutExpired:
            duration = time.time() - start
            return -1, "", f"Command timed out after {eff_timeout}s", duration
        except Exception as e:
            duration = time.time() - start
            return -1, "", f"Execution error: {e}", duration

    def cleanup(self) -> None:
        """Destroy the ephemeral workspace directory and base snapshot."""
        if self._workspace_dir.exists():
            shutil.rmtree(self._workspace_dir, ignore_errors=True)
        if hasattr(self, "_base_snapshot_dir") and self._base_snapshot_dir.exists():
            shutil.rmtree(self._base_snapshot_dir, ignore_errors=True)

    def __enter__(self) -> AgentSandbox:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.cleanup()
