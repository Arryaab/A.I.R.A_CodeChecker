import pytest
from pathlib import Path
from aegis.execution.sandbox import (
    get_docker_create_command,
    run_tests_sandboxed,
    SandboxUnavailableError,
    is_docker_available,
)

def test_docker_command_contains_targeted_test_files():
    selected_tests = ["tests/test_auth.py", "tests/test_models.py"]
    cmd = get_docker_create_command("aegis-sandbox:latest", test_files=selected_tests)
    
    assert "docker" in cmd
    assert "create" in cmd
    assert "--network" in cmd
    assert "none" in cmd
    assert "--read-only" in cmd
    assert "--security-opt" in cmd
    assert "no-new-privileges" in cmd
    assert "--cap-drop" in cmd
    assert "ALL" in cmd
    assert "aegis-sandbox:latest" in cmd
    
    # Assert pytest command and targeted test files are explicitly in command
    assert "pytest" in cmd
    assert "tests/test_auth.py" in cmd
    assert "tests/test_models.py" in cmd

def test_docker_command_without_targeted_tests():
    cmd = get_docker_create_command("aegis-sandbox:latest", test_files=None)
    assert "pytest" in cmd
    assert "--tb=short" in cmd
    assert not any("test_" in arg for arg in cmd[cmd.index("pytest")+1:])

def test_run_tests_sandboxed_require_sandbox_fail_closed(monkeypatch, tmp_path):
    monkeypatch.setattr("aegis.execution.sandbox.is_docker_available", lambda: False)
    
    with pytest.raises(SandboxUnavailableError, match="Docker sandbox is required"):
        run_tests_sandboxed(tmp_path, require_sandbox=True)

def test_run_tests_sandboxed_local_fallback(tmp_path):
    # When require_sandbox is False and Docker is unavailable, safely runs host tests
    res = run_tests_sandboxed(tmp_path, require_sandbox=False, use_docker=False)
    assert not res.used_sandbox
    assert res.test_result is not None
