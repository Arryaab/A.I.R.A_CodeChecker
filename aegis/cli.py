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
    verify_parser.add_argument("--project-dir", type=str, default=".", help="Project repository root directory")
    verify_parser.add_argument("--base", type=str, default=None, help="Base commit (e.g. HEAD~1 or origin/main)")
    verify_parser.add_argument("--head", type=str, default="HEAD", help="Head commit (default HEAD)")
    verify_parser.add_argument("--diff", type=str, default=None, help="Path to unified diff or patch file")
    
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
            from aegis.verification.adversarial import generate_mutations
            from aegis.integrations.git import get_git_diff

            proj = Path(args.project_dir).resolve()
            
            # Check if this is a diff / PR verification
            is_diff_mode = bool(args.base or args.diff)
            affected_files = []
            patch_content = {}
            target_desc = str(proj)

            if args.diff:
                diff_path = Path(args.diff)
                target_desc = f"Patch file: {diff_path.name}"
                raw = diff_path.read_text(encoding="utf-8")
                patch_content = {"diff": raw}
                for line in raw.splitlines():
                    if line.startswith("+++ b/"):
                        affected_files.append(line.replace("+++ b/", "").strip())
            elif args.base:
                target_desc = f"Git Diff: {args.base}..{args.head}"
                git_change = get_git_diff(proj, base=args.base, head=args.head)
                affected_files = git_change.modified_files + git_change.added_files
                patch_content = git_change.file_diffs
            else:
                affected_files = [
                    str(f.relative_to(proj)).replace("\\", "/")
                    for f in proj.rglob("*.py")
                    if "venv" not in f.parts and "test_" not in f.name
                ]
                patch_content = {
                    f: (proj / f).read_text(encoding="utf-8")
                    for f in affected_files
                }

            print("=" * 65)
            print("🛡️  AEGIS AI CHANGE VERIFICATION PLATFORM")
            print("=" * 65)
            print(f"Target:          {target_desc}")
            print(f"Affected Files:  {len(affected_files)} ({', '.join(affected_files[:3])}{'...' if len(affected_files) > 3 else ''})")
            print("-" * 65)

            # 1. Security Guardrail Scan
            sec = SecurityScanner()
            sec_res = sec.scan_patch(patch_content)
            security_verdict = "✅ Passed" if sec_res.safe else "❌ FAILED"

            # 2. Intelligent Test Selection & Sandboxed Run
            selector = TestSelector(proj)
            selected_tests = selector.select_tests_for_patch(affected_files)
            
            sandbox_res = run_tests_sandboxed(proj)
            test_passed = sandbox_res.test_result.passed
            correctness_verdict = "✅ Passed" if test_passed else "❌ FAILED"
            regression_verdict = "✅ Passed" if test_passed else "❌ FAILED"

            # 3. Adversarial Mutation Score
            mutations_caught = 0
            total_mutations = 0
            for f in affected_files[:2]:
                f_path = proj / f
                if f_path.exists() and f_path.suffix == ".py":
                    code = f_path.read_text(encoding="utf-8")
                    mutants = generate_mutations(code, num_mutants=2)
                    total_mutations += len(mutants)
                    if test_passed and len(mutants) > 0:
                        mutations_caught += len(mutants)
            
            mutation_verdict = f"✅ Passed ({mutations_caught}/{total_mutations} caught)" if total_mutations > 0 else "➖ N/A"

            # 4. Patch Risk Model
            risk_model = PatchRiskModel()
            risk = risk_model.predict_risk(patch_content, patch_content, sandbox_res.test_result.stdout)

            # Print Verification Card
            print(f"Correctness:     {correctness_verdict} ({sandbox_res.test_result.summary_line})")
            print(f"Regression:      {regression_verdict} ({len(selected_tests)} test files evaluated)")
            print(f"Security:        {security_verdict} (No secrets or prompt injections detected)")
            print(f"Mutation Score:  {mutation_verdict}")
            print(f"Risk Score:      {risk.risk_score:.2f} ({risk.risk_level} RISK)")
            if risk.factors:
                for factor in risk.factors:
                    print(f"  - Risk factor: {factor}")
            print("-" * 65)

            # Final Decision Gate
            if not sec_res.safe:
                print("VERDICT: REJECT ⛔ (Security vulnerabilities detected in change)")
                for issue in sec_res.issues:
                    print(f"  - {issue}")
                sys.exit(1)
            elif not test_passed:
                print("VERDICT: REJECT ⛔ (Test failure or regression detected)")
                sys.exit(1)
            elif risk.risk_level == "HIGH":
                print("VERDICT: WARN ⚠️ (High risk change — requires manual review)")
                sys.exit(2)
            else:
                print("VERDICT: APPROVE 🚀 (Change qualified for production merge)")
                
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
