from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aegis.benchmark import Benchmark
from aegis.config import load_config, AegisConfig
from aegis.evaluation import evaluate_benchmark, generate_json_report, generate_markdown_report
from aegis.llm import GeminiProvider
from aegis.repair import repair_bug
from aegis.validator import validate_python

def main() -> None:
    parser = argparse.ArgumentParser(description="Aegis-Lite: LLM-based program repair")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Repair
    repair_parser = subparsers.add_parser("repair", help="Repair a single buggy project")
    repair_parser.add_argument("--project-dir", type=str, required=True)
    repair_parser.add_argument("--model", type=str, default="gemini-2.0-flash")
    repair_parser.add_argument("--max-retries", type=int, default=3)
    
    # Evaluate
    eval_parser = subparsers.add_parser("evaluate", help="Run evaluation on a benchmark suite")
    eval_parser.add_argument("--benchmark", type=str, required=True)
    eval_parser.add_argument("--model", type=str, default="gemini-2.0-flash")
    eval_parser.add_argument("--output", type=str, default="results")
    
    # Validate
    val_parser = subparsers.add_parser("validate", help="Validate a Python file's syntax")
    val_parser.add_argument("--file", type=str, required=True)
    
    # Benchmark
    bench_parser = subparsers.add_parser("benchmark", help="List and validate benchmark bugs")
    bench_parser.add_argument("--dir", type=str, required=True)
    
    args = parser.parse_args()
    
    try:
        if args.command == "repair":
            config = load_config()
            config.model = args.model
            config.max_retries = args.max_retries
            provider = GeminiProvider(api_key=config.api_key, model=config.model)
            
            print(f"Repairing project in {args.project_dir} with {args.model}...")
            result = repair_bug(
                bug_dir=Path(args.project_dir),
                provider=provider,
                config=config,
                visible_tests_dir=Path(args.project_dir) / "tests"
            )
            print(f"Success: {result.success}")
            
        elif args.command == "evaluate":
            config = load_config()
            config.model = args.model
            provider = GeminiProvider(api_key=config.api_key, model=config.model)
            
            benchmark = Benchmark.load(args.benchmark)
            print(benchmark.summary())
            
            def progress(bug_id, i, total):
                print(f"Evaluating {bug_id} ({i}/{total})...")
                
            report = evaluate_benchmark(benchmark, provider, config, progress_callback=progress)
            
            out_dir = Path(args.output)
            json_path = generate_json_report(report, out_dir)
            md_path = generate_markdown_report(report, out_dir)
            
            print(f"Evaluation complete. Saved to {json_path} and {md_path}")
            print(f"Pass@1: {report.metrics.pass_at_1:.2f}% | Overall: {report.metrics.pass_at_3:.2f}%")
            
        elif args.command == "validate":
            code = Path(args.file).read_text(encoding="utf-8")
            res = validate_python(code, args.file)
            if res.valid:
                print(f"{args.file} is valid Python.")
            else:
                print(f"{args.file} is invalid:")
                for err in res.errors:
                    print(f"  - {err}")
                sys.exit(1)
                
        elif args.command == "benchmark":
            benchmark = Benchmark.load(args.dir)
            print(benchmark.summary())
            for bug in benchmark:
                print(f" - {bug.bug_id}: {bug.description}")
                
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
