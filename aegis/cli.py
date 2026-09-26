from __future__ import annotations

import argparse
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="AEGIS-AGENT [%(levelname)s]: %(message)s")

from aegis.evals.benchmark import Benchmark
from aegis.config import load_config, AegisConfig
from aegis.evals.evaluation import evaluate_benchmark, generate_json_report, generate_markdown_report
from aegis.core.orchestrator import repair_bug
from aegis.verification.validator import validate_python
from aegis.llm import GeminiProvider, OllamaProvider

def get_provider_for_cli(config: AegisConfig):
    if config.model.startswith("ollama/"):
        return OllamaProvider(model=config.model.replace("ollama/", ""))
    return GeminiProvider(api_key=config.api_key, model=config.model)

def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        
    parser = argparse.ArgumentParser(description="Aegis: Autonomous Engineering & Guardrail Intelligence System")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Repair
    repair_parser = subparsers.add_parser("repair", help="Repair a single buggy project")
    repair_parser.add_argument("--project-dir", type=str, required=True)
    repair_parser.add_argument("--model", type=str, default="gemini-3.8-flash")
    repair_parser.add_argument("--max-retries", type=int, default=3)
    
    # Evaluate
    eval_parser = subparsers.add_parser("evaluate", help="Run evaluation on a benchmark suite")
    eval_parser.add_argument("--benchmark", type=str, required=True)
    eval_parser.add_argument("--model", type=str, default="gemini-3.8-flash")
    eval_parser.add_argument("--output", type=str, default="results")
    
    # Validate
    val_parser = subparsers.add_parser("validate", help="Validate a Python file's syntax")
    val_parser.add_argument("--file", type=str, required=True)
    
    # Benchmark
    bench_parser = subparsers.add_parser("benchmark", help="List and validate benchmark bugs")
    bench_parser.add_argument("--dir", type=str, required=True)
    
    # Verify (Production AI Change Verification Platform)
    verify_parser = subparsers.add_parser("verify", help="Verify proposed AI code changes for correctness, security, and risk")
    verify_parser.add_argument("--project-dir", type=str, required=True)
    
    args = parser.parse_args()
    
    try:
        if args.command == "repair":
            config = load_config()
            config.model = args.model
            config.max_retries = args.max_retries
            provider = get_provider_for_cli(config)
            
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
            provider = get_provider_for_cli(config)
            
            benchmark = Benchmark.load(args.benchmark)
            print(benchmark.summary())
            
            def progress(bug_id, i, total):
                print(f"Evaluating {bug_id} ({i}/{total})...")
                
            report = evaluate_benchmark(benchmark, provider, config, progress_callback=progress)
            
            out_dir = Path(args.output)
            json_path = generate_json_report(report, out_dir)
            md_path = generate_markdown_report(report, out_dir)
            
            print(f"Evaluation complete. Saved to {json_path} and {md_path}")
            print(f"Success@1: {report.metrics.pass_at_1:.2f}% | Overall: {report.metrics.pass_at_3:.2f}%")
            
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

        elif args.command == "verify":
            from aegis.verification.security import SecurityScanner
            from aegis.evals.test_selection import TestSelector
            from aegis.evals.risk_model import PatchRiskModel
            from aegis.execution.sandbox import run_tests_sandboxed

            proj = Path(args.project_dir)
            print(f"🛡️  AEGIS Verification Layer: Auditing {proj.resolve()}")
            print("-" * 60)

            # 1. Collect files
            py_files = {
                str(f.relative_to(proj)): f.read_text(encoding="utf-8")
                for f in proj.rglob("*.py")
                if "venv" not in f.parts and "test_" not in f.name
            }

            # 2. Security Guardrail
            print("🔍 [1/4] Running Security Guardrail Scan...")
            sec = SecurityScanner()
            sec_res = sec.scan_patch(py_files)
            if not sec_res.safe:
                print("❌ SECURITY VULNERABILITIES DETECTED:")
                for issue in sec_res.issues:
                    print(f"   - {issue}")
                print("\n⛔ VERIFICATION FAILED: UNTRUSTED CODE")
                sys.exit(1)
            print("   ✅ Security scan passed (No secrets, prompt injections, or dangerous imports)")

            # 3. Intelligent Test Selection
            print("🎯 [2/4] Selecting Relevant Test Suite...")
            selector = TestSelector(proj)
            selected_tests = selector.select_tests_for_patch(list(py_files.keys()))
            print(f"   ✅ Selected {len(selected_tests)} relevant test files to execute first")

            # 4. Sandboxed Execution
            print("🔒 [3/4] Running Sandboxed Test Execution...")
            sandbox_res = run_tests_sandboxed(proj)
            if not sandbox_res.test_result.passed:
                print("❌ TEST SUITE FAILED:")
                print(sandbox_res.test_result.summary_line)
                print("\n⛔ VERIFICATION FAILED: FUNCTIONAL REGRESSION")
                sys.exit(1)
            print(f"   ✅ Tests passed: {sandbox_res.test_result.summary_line}")

            # 5. Risk Model Prediction
            print("📊 [4/4] Computing AI Patch Risk Model Score...")
            risk_model = PatchRiskModel()
            risk = risk_model.predict_risk(py_files, py_files, sandbox_res.test_result.stdout)
            print(f"   Risk Score: {risk.risk_score:.2f} ({risk.risk_level} RISK)")
            for factor in risk.factors:
                print(f"   - Factor: {factor}")

            print("-" * 60)
            if risk.risk_level == "HIGH":
                print("⚠️  VERIFICATION WARN: High risk change. Requires manual human approval.")
                sys.exit(2)
            else:
                print("🚀 VERIFICATION SUCCESS: Change qualified for production merge!")
                
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
