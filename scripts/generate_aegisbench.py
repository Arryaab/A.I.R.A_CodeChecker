"""
AegisBench Task Generator & Validator:
Enforces that every benchmark task adheres to the formal AegisBench specification
with metadata, provenance, problem description, constraints, and test suites.
"""

from pathlib import Path
import json

REQUIRED_FILES = [
    "metadata.json",
    "provenance.json",
    "problem.md",
    "solution.py",
    "tests/test_solution.py",
    "hidden_tests/test_hidden.py"
]

def validate_benchmark_task(task_dir: Path) -> list[str]:
    """Verify that a task meets the AegisBench integrity requirements."""
    errors = []
    for f in REQUIRED_FILES:
        p = task_dir / f
        if not p.exists():
            errors.append(f"Missing required artifact: {f}")
            
    meta_path = task_dir / "metadata.json"
    if meta_path.exists():
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            for key in ["id", "category", "difficulty", "description"]:
                if key not in data or data[key] == "TODO":
                    errors.append(f"Incomplete metadata field: {key}")
        except Exception as e:
            errors.append(f"Invalid metadata JSON: {e}")
            
    return errors

if __name__ == "__main__":
    dev_dir = Path("benchmarks/dev")
    print(f"Validating verified development tasks in {dev_dir}...")
    valid = 0
    for bug in dev_dir.glob("bug_*"):
        errs = validate_benchmark_task(bug)
        if not errs:
            valid += 1
    print(f"Found {valid} benchmark tasks in dev suite.")
