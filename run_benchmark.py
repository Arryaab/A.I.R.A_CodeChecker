"""Full benchmark evaluation with rate-limit-aware pacing.

The free-tier Gemini API allows 5 requests/minute.
Each bug repair can use 1-3 requests (initial + retries).
We add a delay between bugs to stay under the limit.
"""
import os, sys, time, json, logging
from pathlib import Path
from dataclasses import asdict

sys.path.insert(0, str(Path(__file__).parent))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s",
                    datefmt="%H:%M:%S")

from aegis.config import load_config
from aegis.llm import GeminiProvider
from aegis.evals.benchmark import Benchmark
from aegis.evals.evaluation import evaluate_benchmark, calculate_metrics, generate_markdown_report
from aegis.core.orchestrator import repair_bug
from aegis.verification.taxonomy import FailureType

DELAY_BETWEEN_BUGS = 65  # seconds — ensures rate limit resets between bugs


def main():
    api_key = os.environ.get("AEGIS_API_KEY", "")
    if not api_key:
        print("ERROR: Set AEGIS_API_KEY"); sys.exit(1)

    config = load_config()
    config.api_key = api_key
    config.max_retries = 3

    provider = GeminiProvider(api_key=api_key, model=config.model)
    benchmark = Benchmark.load(Path("benchmarks/dev"))

    print(f"{'='*60}")
    print(f"AEGIS-LITE FULL BENCHMARK EVALUATION")
    print(f"{'='*60}")
    print(f"Model:      {config.model}")
    print(f"Benchmark:  {benchmark.name} ({len(benchmark)} bugs)")
    print(f"Max retries: {config.max_retries}")
    print(f"Rate limit delay: {DELAY_BETWEEN_BUGS}s between bugs")
    print(f"{'='*60}\n")

    results = []
    for i, bug in enumerate(benchmark):
        print(f"\n[{i+1}/{len(benchmark)}] Repairing: {bug.bug_id}")
        print(f"  Description: {bug.description}")

        start = time.time()
        try:
            result = repair_bug(
                bug_dir=bug.buggy_dir,
                provider=provider,
                config=config,
                visible_tests_dir=bug.visible_tests_dir,
                hidden_tests_dir=bug.hidden_tests_dir,
                bug_id=bug.bug_id,
            )
            results.append(result)

            status = "REPAIRED" if result.success else "FAILED"
            emoji = "+" if result.success else "x"
            print(f"  [{emoji}] {status} | attempts={len(result.attempts)} | "
                  f"visible={result.visible_pass} | hidden={result.hidden_pass} | "
                  f"tokens={result.total_tokens} | time={result.total_duration_seconds:.1f}s")

            if result.failure_record:
                print(f"  Failure: {result.failure_record.failure_type.value}")

        except Exception as e:
            print(f"  [!] ERROR: {e}")

        # Rate limit pause between bugs (skip after last)
        if i < len(benchmark) - 1:
            elapsed = time.time() - start
            wait = max(0, DELAY_BETWEEN_BUGS - elapsed)
            if wait > 0:
                print(f"  Waiting {wait:.0f}s for rate limit...")
                time.sleep(wait)

    # Calculate and display metrics
    print(f"\n{'='*60}")
    print(f"EVALUATION RESULTS")
    print(f"{'='*60}")

    metrics = calculate_metrics(results)

    print(f"  Total bugs:          {metrics.total_bugs}")
    print(f"  Pass@1:              {metrics.pass_at_1:.1f}%")
    print(f"  Pass@3:              {metrics.pass_at_3:.1f}%")
    print(f"  Visible pass rate:   {metrics.visible_pass_rate:.1f}%")
    print(f"  Hidden pass rate:    {metrics.hidden_pass_rate:.1f}%")
    print(f"  Invalid Python rate: {metrics.invalid_python_rate:.1f}%")
    print(f"  Avg attempts:        {metrics.avg_attempts:.1f}")
    print(f"  Avg duration:        {metrics.avg_duration_seconds:.1f}s")
    print(f"  Avg tokens:          {metrics.avg_tokens}")

    print(f"\n  Failure distribution:")
    for ft, count in metrics.failure_distribution.items():
        if count > 0:
            print(f"    {ft}: {count}")

    # Per-bug results table
    print(f"\n{'='*60}")
    print(f"{'Bug ID':<35} {'Result':<10} {'Attempts':<10} {'Hidden':<8} {'Tokens'}")
    print(f"{'-'*35} {'-'*10} {'-'*10} {'-'*8} {'-'*8}")
    for r in results:
        status = "REPAIRED" if r.success else "FAILED"
        hidden = str(r.hidden_pass) if r.hidden_pass is not None else "N/A"
        print(f"{r.bug_id:<35} {status:<10} {len(r.attempts):<10} {hidden:<8} {r.total_tokens}")

    # Save report
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    report_file = reports_dir / f"eval_{config.model}_{time.strftime('%Y%m%d_%H%M%S')}.json"

    report_data = {
        "model": config.model,
        "benchmark": benchmark.name,
        "total_bugs": metrics.total_bugs,
        "pass_at_1": metrics.pass_at_1,
        "pass_at_3": metrics.pass_at_3,
        "visible_pass_rate": metrics.visible_pass_rate,
        "hidden_pass_rate": metrics.hidden_pass_rate,
        "results": [
            {
                "bug_id": r.bug_id,
                "success": r.success,
                "visible_pass": r.visible_pass,
                "hidden_pass": r.hidden_pass,
                "attempts": len(r.attempts),
                "tokens": r.total_tokens,
                "duration": r.total_duration_seconds,
                "failure_type": r.failure_record.failure_type.value if r.failure_record else None,
            }
            for r in results
        ],
    }

    with open(report_file, "w") as f:
        json.dump(report_data, f, indent=2)
    print(f"\nReport saved to: {report_file}")


if __name__ == "__main__":
    main()
