"""Quick demo: run Aegis's test runner against the sample project.

Usage:
    python demo_runner.py

This shows you exactly what the runner captures and how the
structured TestResult looks. Run this to understand the output
before we build Stage 2.
"""

import json
import sys
from pathlib import Path
from dataclasses import asdict

# Add aegis to the path for development use.
sys.path.insert(0, str(Path(__file__).parent / "aegis"))

from runner import run_tests


def main():
    sample = Path(__file__).parent / "examples" / "sample_project"

    print(f"Running tests in: {sample}\n")
    result = run_tests(sample)

    # Print a clean summary (not the raw stdout).
    print("=" * 60)
    print("AEGIS TEST RESULT")
    print("=" * 60)
    print(f"  Passed:          {result.passed}")
    print(f"  Exit code:       {result.exit_code}")
    print(f"  Tests passed:    {result.tests_passed}")
    print(f"  Tests failed:    {result.tests_failed}")
    print(f"  Tests errored:   {result.tests_error}")
    print(f"  Duration:        {result.duration_seconds}s")
    print(f"  Summary:         {result.summary_line}")
    print()

    if result.failure_messages:
        print(f"  Failure details ({len(result.failure_messages)} failure(s)):")
        print("  " + "-" * 56)
        for i, msg in enumerate(result.failure_messages, 1):
            print(f"\n  [{i}]")
            for line in msg.splitlines():
                print(f"      {line}")
        print()

    # Also print as JSON — this is the format that later stages will use.
    print("=" * 60)
    print("AS JSON (for pipeline use):")
    print("=" * 60)
    data = asdict(result)
    # Truncate stdout/stderr for readable output.
    data["stdout"] = data["stdout"][:200] + "..." if len(data["stdout"]) > 200 else data["stdout"]
    data["stderr"] = data["stderr"][:200] + "..." if len(data["stderr"]) > 200 else data["stderr"]
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
