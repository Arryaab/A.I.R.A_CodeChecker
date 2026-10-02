from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from aegis.research.sandbox.isolation import AgentSandbox

logger = logging.getLogger("aegis.research.benchmark.validator")


@dataclass
class BenchmarkTaskValidationResult:
    task_id: str
    is_valid: bool
    checks: Dict[str, bool]
    errors: List[str]
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _run_pytest_in_dir(code_dir: Path, test_dir: Path, timeout: float = 15.0) -> Tuple[bool, str, float]:
    """Execute pytest hermetically with code_dir prepended to PYTHONPATH."""
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(test_dir),
        "-v",
        "--tb=short",
        "--color=no",
        "-p",
        "no:cacheprovider",
    ]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(code_dir) + (";" if sys.platform == "win32" else ":") + env.get("PYTHONPATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    t0 = time.time()
    try:
        res = subprocess.run(
            cmd,
            cwd=str(code_dir),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            errors="replace",
        )
        duration = time.time() - t0
        passed = (res.returncode == 0)
        output = res.stdout + "\n" + res.stderr
        return passed, output, duration
    except subprocess.TimeoutExpired:
        duration = time.time() - t0
        return False, f"Pytest timed out after {timeout}s", duration
    except Exception as e:
        duration = time.time() - t0
        return False, f"Pytest execution error: {e}", duration


def _apply_patch(target_dir: Path, patch_file: Path) -> Tuple[bool, str]:
    """Applies a unified diff patch to target_dir using git apply."""
    patch_file = Path(patch_file).resolve()
    target_dir = Path(target_dir).resolve()

    cmd = [
        "git",
        "apply",
        "--whitespace=nowarn",
        str(patch_file),
    ]
    try:
        res = subprocess.run(
            cmd,
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            timeout=10.0,
            errors="replace",
        )
        return (res.returncode == 0), res.stderr.strip()
    except Exception as e:
        return False, str(e)


def validate_benchmark_task(task_dir: Path, timeout: float = 15.0) -> BenchmarkTaskValidationResult:
    """Rigorous automated benchmark validation for an Aegis research benchmark task.

    Verifies:
    1. File structure completeness (public task specs + private evaluator assets)
    2. Namespace separation (zero private files in task/ public directory)
    3. Candidate workspace isolation (zero leakage when sandboxed)
    4. Baseline test failure (ensures task is genuinely defective)
    5. Reference patch application cleanly applies
    6. Reference patch passes public test suite
    7. Reference patch passes oracle test suite
    8. Reference patch passes Aegis hidden test suite
    """
    task_dir = Path(task_dir).resolve()
    task_id = task_dir.name
    errors: List[str] = []
    checks: Dict[str, bool] = {
        "files_present": False,
        "evaluator_namespaces_separated": False,
        "candidate_workspace_isolated": False,
        "baseline_fails_public_tests": False,
        "reference_patch_applies": False,
        "reference_patch_passes_public_tests": False,
        "reference_patch_passes_oracle_tests": False,
        "reference_patch_passes_hidden_tests": False,
    }
    details: Dict[str, Any] = {}

    task_public = task_dir / "task"
    task_private = task_dir / "private"

    # 1. File Structure Completeness
    required_paths = [
        task_public / "metadata.json",
        task_public / "problem.md",
        task_public / "tests",
        task_private / "oracle_tests",
        task_private / "aegis_hidden_tests",
        task_private / "oracle_patch.diff",
        task_private / "oracle_spec.yaml",
    ]
    missing = [str(p.relative_to(task_dir)) for p in required_paths if not p.exists()]
    if missing:
        errors.append(f"Missing required task files: {missing}")
        checks["files_present"] = False
    else:
        # Check non-empty test dirs
        pub_tests = list((task_public / "tests").glob("test_*.py"))
        ora_tests = list((task_private / "oracle_tests").glob("test_*.py"))
        hid_tests = list((task_private / "aegis_hidden_tests").glob("test_*.py"))
        if not pub_tests:
            errors.append("No test files in task/tests")
        if not ora_tests:
            errors.append("No test files in private/oracle_tests")
        if not hid_tests:
            errors.append("No test files in private/aegis_hidden_tests")
        checks["files_present"] = len(errors) == 0

    # 2. Namespace Separation (Leakage Check)
    leakage = []
    if task_public.exists():
        for f in task_public.rglob("*"):
            if f.is_file():
                rel = str(f.relative_to(task_public)).lower()
                if "private" in rel or "hidden_tests" in rel or "oracle_tests" in rel or "oracle_spec" in rel:
                    leakage.append(rel)
    if leakage:
        errors.append(f"Private test leakage detected in public task dir: {leakage}")
        checks["evaluator_namespaces_separated"] = False
    else:
        checks["evaluator_namespaces_separated"] = True

    if not checks["files_present"]:
        return BenchmarkTaskValidationResult(
            task_id=task_id,
            is_valid=False,
            checks=checks,
            errors=errors,
            details=details,
        )

    # 3. Candidate Workspace Isolation & Baseline Evaluation
    try:
        with AgentSandbox(task_public) as sandbox:
            ws_dir = sandbox.workspace_dir

            # Verify no private files in sandbox
            sandboxed_leaks = [
                str(f.relative_to(ws_dir))
                for f in ws_dir.rglob("*")
                if "private" in f.parts or "oracle_tests" in f.parts or "aegis_hidden_tests" in f.parts
            ]
            if sandboxed_leaks:
                errors.append(f"Sandbox isolation breach: private files copied to workspace: {sandboxed_leaks}")
                checks["candidate_workspace_isolated"] = False
            else:
                checks["candidate_workspace_isolated"] = True

            # 4. Baseline public test execution (must fail!)
            base_passed, base_out, base_dur = _run_pytest_in_dir(ws_dir, ws_dir / "tests", timeout=timeout)
            details["baseline_passed"] = base_passed
            details["baseline_duration_s"] = base_dur

            if base_passed:
                errors.append("Baseline code unexpectedly passed public tests (task is not broken)")
                checks["baseline_fails_public_tests"] = False
            else:
                checks["baseline_fails_public_tests"] = True

            # 5. Reference Patch Application
            patch_file = task_private / "oracle_patch.diff"
            patch_ok, patch_err = _apply_patch(ws_dir, patch_file)
            details["patch_applied"] = patch_ok
            if not patch_ok:
                errors.append(f"Reference oracle_patch.diff failed to apply: {patch_err}")
                checks["reference_patch_applies"] = False
            else:
                checks["reference_patch_applies"] = True

                # 6. Public tests pass with patch
                pub_passed, pub_out, pub_dur = _run_pytest_in_dir(ws_dir, ws_dir / "tests", timeout=timeout)
                details["patched_public_passed"] = pub_passed
                if not pub_passed:
                    errors.append(f"Public tests failed after applying reference patch: {pub_out[:300]}")
                    checks["reference_patch_passes_public_tests"] = False
                else:
                    checks["reference_patch_passes_public_tests"] = True

                # 7. Oracle tests pass with patch
                ora_passed, ora_out, ora_dur = _run_pytest_in_dir(ws_dir, task_private / "oracle_tests", timeout=timeout)
                details["patched_oracle_passed"] = ora_passed
                if not ora_passed:
                    errors.append(f"Oracle tests failed after applying reference patch: {ora_out[:300]}")
                    checks["reference_patch_passes_oracle_tests"] = False
                else:
                    checks["reference_patch_passes_oracle_tests"] = True

                # 8. Aegis hidden tests pass with patch
                hid_passed, hid_out, hid_dur = _run_pytest_in_dir(ws_dir, task_private / "aegis_hidden_tests", timeout=timeout)
                details["patched_hidden_passed"] = hid_passed
                if not hid_passed:
                    errors.append(f"Aegis hidden tests failed after applying reference patch: {hid_out[:300]}")
                    checks["reference_patch_passes_hidden_tests"] = False
                else:
                    checks["reference_patch_passes_hidden_tests"] = True

    except Exception as e:
        errors.append(f"Validator sandbox execution crashed: {e}")

    is_all_valid = all(checks.values())
    return BenchmarkTaskValidationResult(
        task_id=task_id,
        is_valid=is_all_valid,
        checks=checks,
        errors=errors,
        details=details,
    )


def validate_all_benchmark_tasks(benchmarks_dir: Path, timeout: float = 15.0) -> Dict[str, BenchmarkTaskValidationResult]:
    """Validates all benchmark tasks in a directory."""
    benchmarks_dir = Path(benchmarks_dir).resolve()
    results: Dict[str, BenchmarkTaskValidationResult] = {}
    for task_dir in sorted(benchmarks_dir.iterdir()):
        if task_dir.is_dir() and (task_dir / "task").exists():
            res = validate_benchmark_task(task_dir, timeout=timeout)
            results[task_dir.name] = res
    return results
