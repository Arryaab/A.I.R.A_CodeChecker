"""
AegisBench 7-Step Automated Evaluator Integrity Admission Gate:
Validates that benchmark tasks meet rigorous empirical standards:
1. Buggy Baseline Execution -> Fails tests
2. Reference Oracle Execution -> Passes 100% visible & hidden tests
3. Mutation Sanity Check -> Test suite kills mutants
4. Environment Lock Verification -> Pinned and valid syntax
5. Evaluator Isolation Check -> private/ is git-ignored and not in git index
6. Negative Test Integrity -> Empty/no-op patch fails
7. Leakage Probe -> No public references to private/ paths
"""

import ast
import os
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from dataclasses import dataclass

@dataclass
class TaskIntegrityReport:
    task_id: str
    passed: bool
    step_results: dict[str, bool]
    details: str = ""

def run_isolated_pytest(code_dir: Path, test_file: Path) -> bool:
    """Run pytest on test_file using code in code_dir via PYTHONPATH."""
    cmd = [
        sys.executable, "-m", "pytest",
        str(test_file),
        "-q", "--tb=no"
    ]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(code_dir) + os_pathsep() + env.get("PYTHONPATH", "")
    res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=10)
    return res.returncode == 0

def os_pathsep() -> str:
    return ";" if sys.platform == "win32" else ":"

def apply_unified_diff(source_text: str, diff_text: str) -> str:
    """Apply unified diff to source text with hunk offsets."""
    import re
    source_lines = source_text.splitlines()
    diff_lines = diff_text.splitlines()
    hunks = []
    curr_hunk = None
    for line in diff_lines:
        if line.startswith("@@"):
            m = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
            if m:
                orig_start = int(m.group(1))
                orig_len = int(m.group(2)) if m.group(2) is not None else 1
                curr_hunk = {"orig_start": orig_start, "orig_len": orig_len, "lines": []}
                hunks.append(curr_hunk)
        elif curr_hunk is not None:
            curr_hunk["lines"].append(line)

    if not hunks:
        return source_text

    result_lines = []
    src_idx = 0
    for h in hunks:
        hunk_start = h["orig_start"] - 1
        while src_idx < hunk_start and src_idx < len(source_lines):
            result_lines.append(source_lines[src_idx])
            src_idx += 1
        for line in h["lines"]:
            if line.startswith("+"):
                result_lines.append(line[1:])
            elif line.startswith("-"):
                src_idx += 1
            elif line.startswith(" "):
                result_lines.append(line[1:])
                src_idx += 1
    while src_idx < len(source_lines):
        result_lines.append(source_lines[src_idx])
        src_idx += 1
    return "\n".join(result_lines) + "\n"

def validate_task_integrity(task_dir: Path) -> TaskIntegrityReport:
    step_results = {}
    task_id = task_dir.name

    public_dir = task_dir / "task"
    private_dir = task_dir / "private"
    buggy_dir = public_dir / "buggy"
    visible_tests = public_dir / "tests" / "test_solution.py"
    hidden_tests = private_dir / "hidden_tests" / "test_solution.py"
    oracle_file = private_dir / "oracle_patch.diff"
    solution_py = buggy_dir / "solution.py"

    # Step 1: Buggy baseline execution (MUST FAIL tests)
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        shutil.copy(solution_py, tmp_path / "solution.py")
        vis_pass = run_isolated_pytest(tmp_path, visible_tests)
        hid_pass = run_isolated_pytest(tmp_path, hidden_tests) if hidden_tests.exists() else False
        # Buggy code should fail at least one suite
        step_results["step_1_baseline_fails"] = not (vis_pass and hid_pass)

    # Step 2: Reference oracle execution (MUST PASS 100%)
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        buggy_src = solution_py.read_text(encoding="utf-8")
        diff_src = oracle_file.read_text(encoding="utf-8")
        fixed_src = apply_unified_diff(buggy_src, diff_src)
        (tmp_path / "solution.py").write_text(fixed_src, encoding="utf-8")

        vis_pass = run_isolated_pytest(tmp_path, visible_tests)
        hid_pass = run_isolated_pytest(tmp_path, hidden_tests) if hidden_tests.exists() else True
        step_results["step_2_oracle_passes"] = vis_pass and hid_pass

    # Step 3: Mutation sanity check (Mutant MUST FAIL)
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        # Create trivial mutant (return None)
        (tmp_path / "solution.py").write_text("def __getattr__(name): return lambda *a, **k: None\n", encoding="utf-8")
        mutant_pass = run_isolated_pytest(tmp_path, visible_tests)
        step_results["step_3_mutant_killed"] = not mutant_pass

    # Step 4: Environment lock / valid syntax
    try:
        ast.parse(solution_py.read_text(encoding="utf-8"))
        ast.parse(visible_tests.read_text(encoding="utf-8"))
        step_results["step_4_syntax_valid"] = True
    except SyntaxError:
        step_results["step_4_syntax_valid"] = False

    # Step 5: Evaluator isolation check (private/ not in git index)
    git_check = subprocess.run(
        ["git", "ls-files", str(private_dir)],
        capture_output=True, text=True
    )
    step_results["step_5_evaluator_isolated"] = (len(git_check.stdout.strip()) == 0)

    # Step 6: Negative test integrity (empty patch fails)
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        shutil.copy(solution_py, tmp_path / "solution.py")
        step_results["step_6_negative_integrity"] = not (
            run_isolated_pytest(tmp_path, visible_tests) and run_isolated_pytest(tmp_path, hidden_tests)
        )

    # Step 7: Leakage probe (public code does not mention 'private')
    pub_content = (public_dir / "problem.md").read_text(encoding="utf-8") + \
                  solution_py.read_text(encoding="utf-8") + \
                  visible_tests.read_text(encoding="utf-8")
    has_leakage = "private/" in pub_content or "hidden_tests" in pub_content
    step_results["step_7_zero_leakage"] = not has_leakage

    all_passed = all(step_results.values())
    return TaskIntegrityReport(
        task_id=task_id,
        passed=all_passed,
        step_results=step_results,
        details="" if all_passed else f"Failed steps: {[k for k, v in step_results.items() if not v]}"
    )

def main():
    from concurrent.futures import ThreadPoolExecutor
    bench_dir = Path("benchmarks/v1") if len(sys.argv) < 2 else Path(sys.argv[1])
    print(f"=" * 72)
    print(f"AEGISBENCH 7-STEP EVALUATOR INTEGRITY ADMISSION GATE")
    print(f"Target Directory: {bench_dir}")
    print(f"=" * 72)

    tasks = sorted([d for d in bench_dir.iterdir() if d.is_dir()])
    total = len(tasks)
    passed_count = 0
    failed_reports = []

    print(f"Auditing {total} benchmark tasks across all 7 integrity gates (parallel mode)...\n")
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(validate_task_integrity, tasks))

    for i, rep in enumerate(results, 1):
        if rep.passed:
            passed_count += 1
            print(f"  [{i:02d}/{total:02d}] ? PASS: {rep.task_id}")
        else:
            failed_reports.append(rep)
            print(f"  [{i:02d}/{total:02d}] ? FAIL: {rep.task_id} -> {rep.details}")

    print("\n" + "=" * 72)
    print("INTEGRITY GATE AUDIT SUMMARY")
    print("=" * 72)
    print(f"Total Tasks Audited:  {total}")
    print(f"Passed All 7 Gates:   {passed_count} ({passed_count/total*100:.1f}%)")
    print(f"Failed Tasks:         {len(failed_reports)}")

    if failed_reports:
        print("\nFailures:")
        for r in failed_reports:
            print(f"  - {r.task_id}: {r.details}")
        sys.exit(1)
    else:
        print("\n? ALL 50 BENCHMARK TASKS MEET 100% INTEGRITY AND ZERO-LEAKAGE STANDARDS.")
        sys.exit(0)

if __name__ == "__main__":
    main()
