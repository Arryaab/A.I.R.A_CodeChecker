from __future__ import annotations

import argparse
import sys
import logging
import json
import uuid
from datetime import datetime, timezone
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
    verify_parser.add_argument(
        "--tier",
        type=str,
        choices=["fast", "standard", "deep", "auto"],
        default="auto",
        help="Verification depth: fast, standard, deep, or auto (adaptive based on patch risk)"
    )
    verify_parser.add_argument(
        "-o", "--output-dir",
        type=str,
        default=None,
        help="Directory to store audit artifacts, execution traces, and logs (default: .aegis/runs/<run-id>)"
    )
    
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
            from aegis.verification.adversarial import run_mutation_tests
            from aegis.integrations.git import get_git_diff, PatchChange

            proj = Path(args.project_dir).resolve()
            
            # Check if this is a diff / PR verification
            is_diff_mode = bool(args.base or args.diff)
            affected_files = []
            patches = {}
            target_desc = str(proj)

            if args.diff:
                diff_path = Path(args.diff)
                target_desc = f"Patch file: {diff_path.name}"
                raw = diff_path.read_text(encoding="utf-8")
                # Parse files from unified diff
                for line in raw.splitlines():
                    if line.startswith("+++ b/"):
                        f = line.replace("+++ b/", "").strip()
                        affected_files.append(f)
                        patches[f] = PatchChange(path=f, new_content=(proj / f).read_text(encoding="utf-8") if (proj / f).exists() else "")
            elif args.base:
                target_desc = f"Git Diff: {args.base}..{args.head}"
                git_change = get_git_diff(proj, base=args.base, head=args.head)
                affected_files = list(dict.fromkeys(
                    git_change.modified_files + 
                    git_change.added_files + 
                    git_change.deleted_files + 
                    [new_p for _, new_p in git_change.renamed_files]
                ))
                patches = git_change.patches
            else:
                affected_files = [
                    str(f.relative_to(proj)).replace("\\", "/")
                    for f in proj.rglob("*.py")
                    if "venv" not in f.parts and "test_" not in f.name
                ]
                for f in affected_files:
                    code = (proj / f).read_text(encoding="utf-8", errors="replace")
                    patches[f] = PatchChange(path=f, new_content=code, added_lines=code.splitlines())

            # 1. Compute Heuristic Patch Risk Baseline to determine verification budget
            risk_model = PatchRiskModel()
            risk = risk_model.predict_risk(patches, patches, "")

            # Resolve Verification Tier
            active_tier = args.tier.upper()
            if active_tier == "AUTO":
                if risk.risk_level == "LOW":
                    active_tier = "FAST"
                elif risk.risk_level == "MEDIUM":
                    active_tier = "STANDARD"
                else:
                    active_tier = "DEEP"

            print("=" * 68)
            print("🛡️  AEGIS AI CHANGE VERIFICATION PLATFORM")
            print("=" * 68)
            print(f"Target:             {target_desc}")
            print(f"Affected Files:     {len(affected_files)} ({', '.join(affected_files[:3])}{'...' if len(affected_files) > 3 else ''})")
            print(f"Verification Tier:  {active_tier} (Risk: {risk.risk_score:.2f} {risk.risk_level})")
            print("-" * 68)

            # 2. Structured Patch Security Scan (inspects added_lines only for secrets/injection, new_content for AST)
            sec = SecurityScanner()
            sec_res = sec.scan_patch_changes(patches)
            security_verdict = "✅ Passed" if sec_res.safe else "❌ FAILED"

            # 3. Hermetic Commit-Pure Execution Sandbox
            from aegis.integrations.git import create_commit_snapshot
            with create_commit_snapshot(proj, commit_ref=args.head if is_diff_mode else "HEAD") as exec_dir:
                # 3a. Targeted Test Execution (Fast Feedback - All Tiers)
                selector = TestSelector(exec_dir)
                selected_tests = selector.select_tests_for_patch(affected_files)
                selected_res = run_tests_sandboxed(exec_dir, test_files=selected_tests)
                targeted_passed = selected_res.test_result.passed
                correctness_verdict = "✅ Passed" if targeted_passed else "❌ FAILED"

                # 3b. Regression & Mutation Verification (STANDARD & DEEP Tiers)
                full_passed = True
                full_res = None
                mut_score = None
                mut_killed = 0
                mut_total = 0

                # Identify production source files for mutation analysis (exclude tests, docs, configs)
                mutation_targets = [
                    f for f in affected_files
                    if f.endswith(".py")
                    and not f.startswith("tests/")
                    and "tests" not in Path(f).parts
                    and not Path(f).name.startswith("test_")
                    and (exec_dir / f).exists()
                    and getattr(patches.get(f), "status", "") != "D"
                ]

                if active_tier in ("STANDARD", "DEEP"):
                    full_res = run_tests_sandboxed(exec_dir)
                    full_passed = full_res.test_result.passed
                    regression_verdict = f"✅ Passed (0 regressed, {full_res.test_result.summary_line})" if full_passed else "❌ FAILED (Regressions detected)"
                    
                    if mutation_targets:
                        max_mutants = 2 if active_tier == "STANDARD" else 4
                        mut_res = run_mutation_tests(exec_dir, mutation_targets[:2], max_mutants_per_file=max_mutants)
                        if mut_res.total_mutants > 0:
                            mut_score = mut_res.score
                            mut_killed = mut_res.killed_mutants
                            mut_total = mut_res.total_mutants
                            mut_pct = mut_res.score * 100
                            mutation_verdict = f"✅ {mut_pct:.1f}% ({mut_res.killed_mutants}/{mut_res.total_mutants} killed)"
                        else:
                            mutation_verdict = "➖ N/A (No mutable AST nodes)"
                    else:
                        mutation_verdict = "➖ N/A (No production source files modified)"
                else:
                    regression_verdict = "⚡ Skipped (FAST Tier)"
                    mutation_verdict = "⚡ Skipped (FAST Tier)"

            # Print Verification Card
            print(f"Correctness:        {correctness_verdict} ({len(selected_tests)} targeted test files passed in {selected_res.test_result.duration_seconds}s)")
            print(f"Regression:         {regression_verdict}")
            print(f"Security:           {security_verdict} (AST imports + added lines scanned)")
            print(f"Mutation Score:     {mutation_verdict}")
            print(f"Risk Score:         {risk.risk_score:.2f} ({risk.risk_level} RISK)")
            if risk.factors:
                for factor in risk.factors:
                    print(f"  - Risk factor: {factor}")
            print("-" * 68)

            # Determine Technical Verdict (Objective Verification Gates)
            if not sec_res.safe:
                technical_verdict = "FAILED"
                tech_reason = "Security vulnerabilities detected in change"
            elif not targeted_passed:
                technical_verdict = "FAILED"
                tech_reason = "Targeted test failure in modified modules"
            elif not full_passed:
                technical_verdict = "FAILED"
                tech_reason = "Regression detected in full test suite"
            else:
                technical_verdict = "QUALIFIED"
                tech_reason = "All automated verification gates passed"

            # Determine Release Policy (Governance & Risk Assessment)
            if technical_verdict == "FAILED":
                release_policy = "BLOCK"
                policy_reason = tech_reason
            elif risk.risk_level == "LOW":
                release_policy = "AUTO_APPROVE"
                policy_reason = "Low risk change meets criteria for automated production merge"
            elif risk.risk_level == "MEDIUM":
                release_policy = "REVIEW"
                policy_reason = "Medium risk change requires peer review before release"
            else:  # HIGH
                release_policy = "REVIEW"
                policy_reason = "High risk change requires mandatory senior/security review"

            tech_icon = "✅" if technical_verdict == "QUALIFIED" else "❌"
            policy_icon = "🚀" if release_policy == "AUTO_APPROVE" else "⚠️" if release_policy == "REVIEW" else "⛔"

            print(f"Technical Verdict:  {technical_verdict} {tech_icon}")
            if technical_verdict == "FAILED":
                print(f"  - Failure cause:   {tech_reason}")
                for issue in sec_res.issues:
                    print(f"  - Security issue:  {issue}")

            print(f"Release Policy:     {release_policy} {policy_icon} ({policy_reason})")

            # Generate Machine-Readable Audit Report Artifact (Schema 1.0)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            run_id = f"run_{timestamp}_{uuid.uuid4().hex[:6]}"

            if args.output_dir:
                run_dir = Path(args.output_dir).resolve()
            else:
                run_dir = proj / ".aegis" / "runs" / run_id

            run_dir.mkdir(parents=True, exist_ok=True)
            report_path = run_dir / "report.json"

            audit_report = {
                "schema_version": "1.0",
                "run_id": run_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "repository": proj.name,
                "base": args.base or "HEAD~1",
                "head": args.head or "HEAD",
                "change": {
                    "files_affected": len(affected_files),
                    "files_added": sum(1 for p in patches.values() if getattr(p, "status", "") == "A"),
                    "files_modified": sum(1 for p in patches.values() if getattr(p, "status", "") in ("M", "")),
                    "files_deleted": sum(1 for p in patches.values() if getattr(p, "status", "") == "D"),
                    "files_renamed": sum(1 for p in patches.values() if getattr(p, "status", "") == "R"),
                    "lines_added": sum(len(getattr(p, "added_lines", [])) for p in patches.values()),
                    "lines_deleted": sum(len(getattr(p, "deleted_lines", [])) for p in patches.values()),
                    "affected_files": affected_files,
                },
                "verification": {
                    "tier": active_tier,
                    "targeted_tests": {
                        "passed": targeted_passed,
                        "test_files_count": len(selected_tests),
                        "duration_seconds": selected_res.test_result.duration_seconds,
                    },
                    "regression": {
                        "passed": full_passed,
                        "status": "passed" if full_passed and active_tier in ("STANDARD", "DEEP") else "failed" if not full_passed else "skipped",
                        "summary": full_res.test_result.summary_line if full_res else "Skipped (FAST tier)",
                        "duration_seconds": full_res.test_result.duration_seconds if full_res else 0.0,
                    },
                    "mutation": {
                        "status": "completed" if active_tier in ("STANDARD", "DEEP") and mut_total > 0 else "skipped" if active_tier == "FAST" else "not_applicable",
                        "score": mut_score,
                        "killed": mut_killed,
                        "total": mut_total,
                        "target_files": mutation_targets[:2] if active_tier in ("STANDARD", "DEEP") else [],
                    },
                    "security": {
                        "safe": sec_res.safe,
                        "issues_count": len(sec_res.issues),
                        "issues": sec_res.issues,
                    },
                },
                "risk": {
                    "score": risk.risk_score,
                    "level": risk.risk_level,
                    "factors": risk.factors,
                },
                "decision": {
                    "technical_verdict": technical_verdict,
                    "release_policy": release_policy,
                    "reason": policy_reason,
                },
            }

            try:
                report_path.write_text(json.dumps(audit_report, indent=2), encoding="utf-8")
                
                # Write supplementary execution traces artifact
                traces = {
                    "run_id": run_id,
                    "timestamp": audit_report["timestamp"],
                    "targeted_tests": selected_tests,
                    "targeted_duration_seconds": selected_res.test_result.duration_seconds,
                    "regression_summary": full_res.test_result.summary_line if full_res else None,
                    "regression_duration_seconds": full_res.test_result.duration_seconds if full_res else None,
                    "mutation_targets": mutation_targets[:2] if active_tier in ("STANDARD", "DEEP") else [],
                }
                (run_dir / "traces.json").write_text(json.dumps(traces, indent=2), encoding="utf-8")

                try:
                    display_path = report_path.relative_to(proj)
                except ValueError:
                    display_path = report_path
                print(f"Audit Artifact:     {display_path} (Schema v1.0)")
            except Exception as e:
                logging.warning(f"Failed to write audit artifact: {e}")

            if release_policy == "BLOCK":
                sys.exit(1)
            elif release_policy == "REVIEW":
                sys.exit(2)
                
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
