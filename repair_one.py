"""Run a single bug repair — used for testing individual bugs."""
import os, sys, logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

from aegis.config import load_config
from aegis.llm import GeminiProvider
from aegis.core.orchestrator import repair_bug

def main():
    bug_name = sys.argv[1] if len(sys.argv) > 1 else "bug_014_logic_error"
    api_key = os.environ.get("AEGIS_API_KEY", "")
    if not api_key:
        print("ERROR: Set AEGIS_API_KEY"); sys.exit(1)

    config = load_config()
    config.api_key = api_key
    provider = GeminiProvider(api_key=api_key, model=config.model)

    bug_base = Path(f"benchmarks/dev/{bug_name}")
    print(f"\n{'='*60}")
    print(f"Repairing: {bug_name} | Model: {config.model}")
    print(f"{'='*60}")

    # Show buggy code
    for f in (bug_base / "buggy").glob("*.py"):
        print(f"\nBuggy code:\n{f.read_text()}")

    result = repair_bug(
        bug_dir=bug_base / "buggy",
        provider=provider, config=config,
        visible_tests_dir=bug_base / "tests",
        hidden_tests_dir=bug_base / "hidden_tests",
        bug_id=bug_name,
    )

    print(f"\n{'='*60}")
    print(f"RESULT: {'REPAIRED' if result.success else 'FAILED'}")
    print(f"{'='*60}")
    print(f"  Visible Pass:  {result.visible_pass}")
    print(f"  Hidden Pass:   {result.hidden_pass}")
    print(f"  Attempts:      {len(result.attempts)}")
    print(f"  Duration:      {result.total_duration_seconds:.1f}s")
    print(f"  Tokens:        {result.total_tokens}")
    for a in result.attempts:
        ts = "PASSED" if a.test_result and a.test_result.passed else ("FAILED" if a.test_result else "N/A")
        print(f"  Attempt {a.attempt_number}: valid={a.validation.valid}, tests={ts}")
    if result.failure_record:
        print(f"  Failure: {result.failure_record.failure_type.value} — {result.failure_record.description}")

if __name__ == "__main__":
    main()
