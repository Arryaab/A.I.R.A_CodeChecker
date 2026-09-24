from __future__ import annotations

"""Quick-start evaluation script.
Usage: python run_evaluation.py --benchmark benchmarks/dev --model gemini-2.0-flash
"""

import argparse
from pathlib import Path

from aegis.config import load_config
from aegis.llm import GeminiProvider
from aegis.benchmark import Benchmark
from aegis.evaluation import evaluate_benchmark, generate_json_report, generate_markdown_report

def main():
    parser = argparse.ArgumentParser(description="Evaluate Aegis-Lite")
    parser.add_argument("--benchmark", type=str, required=True, help="Path to benchmark directory")
    parser.add_argument("--model", type=str, default="gemini-2.0-flash", help="Model to use")
    parser.add_argument("--output", type=str, default="results", help="Output directory")
    parser.add_argument("--max-retries", type=int, default=3, help="Max repair retries")
    parser.add_argument("--api-key", type=str, default="", help="API key")
    
    args = parser.parse_args()
    
    config = load_config()
    config.model = args.model
    config.max_retries = args.max_retries
    if args.api_key:
        config.api_key = args.api_key
        
    provider = GeminiProvider(api_key=config.api_key, model=config.model)
    benchmark = Benchmark.load(args.benchmark)
    
    print(benchmark.summary())
    
    def progress(bug_id, i, total):
        print(f"[{i}/{total}] Repairing {bug_id}...")
        
    report = evaluate_benchmark(benchmark, provider, config, progress_callback=progress)
    
    out_dir = Path(args.output)
    json_path = generate_json_report(report, out_dir)
    md_path = generate_markdown_report(report, out_dir)
    
    print(f"\nEvaluation complete!")
    print(f"Pass@1: {report.metrics.pass_at_1:.2f}%")
    print(f"Overall Success (Pass@3): {report.metrics.pass_at_3:.2f}%")
    print(f"Reports saved to {json_path} and {md_path}")

if __name__ == "__main__":
    main()
