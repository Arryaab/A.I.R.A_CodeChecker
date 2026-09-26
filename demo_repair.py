"""Run a single bug repair to demonstrate Aegis-Lite end-to-end."""

import os
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

from aegis.config import load_config
from aegis.llm import GeminiProvider
from aegis.repair import repair_bug

API_KEY = os.environ.get("AEGIS_API_KEY", "")

def run_single_repair(bug_name: str) -> dict:
    config = load_config()
    config.api_key = API_KEY
    config.max_retries = 3

    print(f"\n{'='*60}")
    print(f"AEGIS-LITE: Repairing {bug_name}")
    print(f"{'='*60}")
    print(f"Model: {config.model}")

    provider = GeminiProvider(api_key=config.api_key, model=config.model)

    bug_base = Path(f"benchmarks/dev/{bug_name}")
    bug_dir = bug_base / "buggy"
    tests_dir = bug_base / "tests"
    hidden_dir = bug_base / "hidden_tests"

    # Show the buggy code
    for py_file in bug_dir.glob("*.py"):
        print(f"\nBuggy code ({py_file.name}):")
        print("-" * 40)
        print(py_file.read_text(encoding="utf-8"))
        print("-" * 40)

    result = repair_bug(
        bug_dir=bug_dir,
        provider=provider,
        config=config,
        visible_tests_dir=tests_dir,
        hidden_tests_dir=hidden_dir,
        bug_id=bug_name,
    )

    print(f"\n--- RESULT ---")
    print(f"  Success:        {result.success}")
    print(f"  Visible Pass:   {result.visible_pass}")
    print(f"  Hidden Pass:    {result.hidden_pass}")
    print(f"  Attempts:       {len(result.attempts)}")
    print(f"  Duration:       {result.total_duration_seconds:.1f}s")
    print(f"  Total Tokens:   {result.total_tokens}")

    for a in result.attempts:
        test_status = "N/A"
        if a.test_result:
            test_status = "PASSED" if a.test_result.passed else "FAILED"
        print(f"  Attempt {a.attempt_number}: valid={a.validation.valid}, tests={test_status}")

    if result.failure_record:
        print(f"  Failure Type:   {result.failure_record.failure_type.value}")
        print(f"  Failure Detail: {result.failure_record.description}")

    return result


if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: Set AEGIS_API_KEY environment variable first.")
        sys.exit(1)

    # Repair 3 bugs of varying difficulty
    bugs = [
        "bug_001_wrong_operator",
        "bug_008_string_error",
        "bug_014_logic_error",
    ]

    results = {}
    for bug in bugs:
        try:
            r = run_single_repair(bug)
            results[bug] = r
        except Exception as e:
            print(f"\nERROR repairing {bug}: {e}")
            results[bug] = None

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for bug, r in results.items():
        if r:
            status = "REPAIRED" if r.success else "FAILED"
            print(f"  {bug}: {status} (attempts: {len(r.attempts)}, tokens: {r.total_tokens})")
        else:
            print(f"  {bug}: ERROR")
