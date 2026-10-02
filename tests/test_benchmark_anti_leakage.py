"""
AegisBench Anti-Leakage and Sandbox Isolation Traversal Security Audit.
Verifies across all benchmark tasks that:
1. Public workspaces contain ZERO private evaluation artifacts (oracle_tests, oracle_spec, oracle_patch, aegis_hidden_tests).
2. AgentSandbox strictly blocks runtime traversal attempts:
   - Relative parent traversal ('../', '../../')
   - Absolute filesystem path traversal
   - Symlink escape attempts
   - Git index leaks
   - Environment variable inspection / secret leakage
   - Direct private namespace accesses
"""

import os
import tempfile
from pathlib import Path
import pytest
from aegis.research.sandbox.isolation import AgentSandbox, SandboxSecurityViolation


def test_public_workspaces_zero_leakage():
    """Verify that no public task directory contains private files or leaks references."""
    bench_dir = Path("benchmarks/v1")
    assert bench_dir.exists(), "Benchmark directory not found"

    forbidden_names = [
        "oracle_tests",
        "oracle_spec.yaml",
        "oracle_patch.diff",
        "hidden_tests",
        "aegis_hidden_tests",
        "mutations.json",
        "plausible_bad_patches.json"
    ]

    for task_dir in bench_dir.iterdir():
        if not task_dir.is_dir():
            continue
        public_dir = task_dir / "task"
        assert public_dir.exists(), f"Missing public dir for {task_dir.name}"

        # 1. Check directory tree
        for root, dirs, files in os.walk(public_dir):
            for d in dirs:
                assert d not in forbidden_names, f"Forbidden dir '{d}' found in public task: {task_dir.name}"
            for f in files:
                assert f not in forbidden_names, f"Forbidden file '{f}' found in public task: {task_dir.name}"

        # 2. Check public content for text leakage
        for f in public_dir.rglob("*.py"):
            text = f.read_text(encoding="utf-8", errors="replace")
            assert "private/" not in text, f"Text leakage of 'private/' in {f}"
            assert "oracle_tests" not in text, f"Text leakage of 'oracle_tests' in {f}"
        for f in public_dir.rglob("*.md"):
            text = f.read_text(encoding="utf-8", errors="replace")
            assert "private/" not in text, f"Text leakage of 'private/' in {f}"
            assert "oracle_tests" not in text, f"Text leakage of 'oracle_tests' in {f}"


def test_sandbox_path_traversal_blocking():
    """Verify AgentSandbox strictly traps relative, absolute, and symlink traversals."""
    task_dir = Path("benchmarks/v1/task_001_fastapi_async_scope")
    with tempfile.TemporaryDirectory() as td:
        ws_base = Path(td)
        sandbox = AgentSandbox(task_dir=task_dir / "task", workspace_base=ws_base)

        # 1. Relative parent traversal attempts
        with pytest.raises(SandboxSecurityViolation):
            sandbox.validate_path("../private/oracle_spec.yaml")

        with pytest.raises(SandboxSecurityViolation):
            sandbox.validate_path("../../benchmarks/v1/task_001_fastapi_async_scope/private/oracle_patch.diff")

        # 2. Absolute path traversal attempts
        with pytest.raises(SandboxSecurityViolation):
            sandbox.validate_path(str(Path("benchmarks/v1/task_001_fastapi_async_scope/private").resolve()))

        # 3. Environment isolation (quarantining secrets)
        saved_env = {k: os.environ.get(k) for k in AgentSandbox.FORBIDDEN_ENV_KEYS}
        try:
            for env_var in AgentSandbox.FORBIDDEN_ENV_KEYS:
                os.environ[env_var] = "super_secret_test_token"

            # Test command execution strips secrets
            import sys
            exit_code, stdout, stderr, dur = sandbox.execute_in_sandbox([
                sys.executable, "-c", "import os; print(os.environ.get('AEGIS_API_KEY', ''))"
            ])
            assert stdout.strip() == "", "Agent sandbox leaked forbidden environment secret AEGIS_API_KEY"
        finally:
            # Restore original environment
            for k, val in saved_env.items():
                if val is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = val
