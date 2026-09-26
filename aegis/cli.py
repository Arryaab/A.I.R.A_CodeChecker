from __future__ import annotations

import argparse
import hashlib
import json
import logging
import subprocess
import sys
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
from aegis.execution.environment import inspect_repository_environment, resolve_executed_environment

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
    bench_parser = subparsers.add_parser("benchmark", help="List and validate benchmark tasks")
    bench_parser.add_argument("--dir", type=str, required=True, help="Directory containing benchmark tasks")
    bench_parser.add_argument("--evaluator-dir", type=str, default=None, help="Optional external directory containing private evaluator harness")
    bench_parser.add_argument("--validate", action="store_true", help="Perform strict schema, provenance, and task integrity validation")
    
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
    verify_parser.add_argument(
        "--unsafe-local",
        action="store_true",
        help="Allow running verification tests directly on host without Docker sandbox (DANGEROUS: use for local testing only)"
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
            benchmark = Benchmark.load(args.dir, evaluator_dir=getattr(args, "evaluator_dir", None))
            print(benchmark.summary())
            if getattr(args, "validate", False):
                print(f"Validating {len(benchmark)} tasks in '{args.dir}' against canonical AegisBench schema...")
                issues = benchmark.validate()
                errors = [i for i in issues if i.severity == "ERROR"]
                warnings = [i for i in issues if i.severity == "WARNING"]
                if warnings:
                    print(f"⚠️  {len(warnings)} benchmark warning(s):")
                    for w in warnings:
                        print(f"  - [{w.bug_id}] {w.issue}")
                if errors:
                    print(f"❌ {len(errors)} benchmark validation error(s):")
                    for err in errors:
                        print(f"  - [{err.bug_id}] {err.issue}")
                    sys.exit(1)
                else:
                    print(f"✅ All {len(benchmark)} benchmark tasks strictly conform to AegisBench schema.")
            else:
                for bug in benchmark:
                    print(f" - {bug.bug_id}: {bug.description}")

        elif args.command == "verify":
            import hashlib
            from aegis.verification.security import SecurityScanner
            from aegis.evals.test_selection import TestSelector
            from aegis.evals.risk_model import PatchRiskModel
            from aegis.execution.sandbox import run_tests_sandboxed, is_docker_available, SandboxUnavailableError
            from aegis.verification.adversarial import run_mutation_tests
            from aegis.integrations.git import get_git_diff, PatchChange

            proj = Path(args.project_dir).resolve()
            
            # Check sandbox requirements (production fails closed if Docker is unavailable)
            require_sandbox = not getattr(args, "unsafe_local", False)
            use_docker = not getattr(args, "unsafe_local", False)

            if getattr(args, "unsafe_local", False):
                print("⚠️  SECURITY WARNING: Running with --unsafe-local. Docker sandbox disabled; untrusted code runs on host.")
            elif not is_docker_available():
                print(
                    "\n❌ Aegis Security Error: Docker sandbox is required for executing untrusted changes, "
                    "but the Docker daemon is unavailable.\n"
                    "Aegis refuses to execute untrusted AI-generated code directly on the host in production mode.\n"
                    "For local debugging without Docker, explicitly run with: --unsafe-local",
                    file=sys.stderr
                )
                sys.exit(1)

            # Check if this is a diff / PR verification
            is_diff_mode = bool(args.base or args.diff)
            affected_files = []
            patches = {}
            target_desc = str(proj)
            raw = ""

            if args.diff:
                diff_path = Path(args.diff).resolve()
                if not diff_path.exists():
                    raise FileNotFoundError(f"Patch file not found: {diff_path}")
                base_ref = args.base or "HEAD"
                target_desc = f"Patch file: {diff_path.name} (Base: {base_ref})"
                raw = diff_path.read_text(encoding="utf-8", errors="replace")
                from aegis.integrations.git import parse_unified_diff, apply_patch_file
                affected_files, patches = parse_unified_diff(proj, raw, base_ref=base_ref)
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

            # Check for test files or testing configuration modifications (elevate risk)
            test_files_touched = [
                f for f in affected_files
                if f.startswith("tests/") or "/tests/" in f or Path(f).name.startswith("test_")
                or Path(f).name in {"conftest.py", "pytest.ini", "pyproject.toml", "tox.ini"}
                or f.startswith(".github/")
            ]
            if test_files_touched:
                risk.factors.append(f"Test suite or testing configuration modified ({len(test_files_touched)} files)")
                risk.risk_score = min(1.0, round(risk.risk_score + 0.25, 2))
                if risk.risk_score >= 0.70:
                    risk.risk_level = "HIGH"
                elif risk.risk_score >= 0.30:
                    risk.risk_level = "MEDIUM"

            # Resolve Verification Tier
            active_tier = args.tier.upper()
            if active_tier == "AUTO":
                if risk.risk_level == "LOW":
                    active_tier = "FAST"
                elif risk.risk_level == "MEDIUM":
                    active_tier = "STANDARD"
                else:
                    active_tier = "DEEP"

            est_mutants = 2 if active_tier == "STANDARD" else 4 if active_tier == "DEEP" else 0
            est_detail = f"targeted checks only (~2-5s)" if active_tier == "FAST" else f"full suite + {est_mutants} mutants (~25-45s)" if active_tier == "STANDARD" else f"full suite + {est_mutants} mutants + perf benchmark (~1-2m)"

            print("=" * 68)
            print("🛡️  AEGIS AI CHANGE VERIFICATION PLATFORM")
            print("=" * 68)
            print(f"Target:             {target_desc}")
            print(f"Affected Files:     {len(affected_files)} ({', '.join(affected_files[:3])}{'...' if len(affected_files) > 3 else ''})")
            print(f"Verification Tier:  {active_tier} (Risk: {risk.risk_score:.2f} {risk.risk_level} | {est_detail})")
            print("-" * 68)

            # 2. Hermetic Commit-Pure Execution Sandbox
            from aegis.integrations.git import create_commit_snapshot
            from aegis.execution.environment import build_sandbox_environment_image
            commit_to_extract = (args.base or "HEAD") if args.diff else (args.head or "HEAD")
            env_info = None
            docker_image = "aegis-sandbox:latest"
            with create_commit_snapshot(proj, commit_ref=commit_to_extract) as exec_dir:
                if args.diff:
                    # Hermetically apply patch to ephemeral snapshot FIRST
                    apply_patch_file(exec_dir, diff_path)
                    for f, p in patches.items():
                        target_f = exec_dir / f
                        if target_f.exists() and target_f.is_file():
                            p.new_content = target_f.read_text(encoding="utf-8", errors="replace")
                        else:
                            p.new_content = ""
                            p.status = "D"

                # Commit-pure environment inspection of proposed post-change state
                env_info = inspect_repository_environment(exec_dir)

                # Build or resolve reproducible container image based on proposed manifests
                docker_image = "aegis-sandbox:latest"
                if use_docker:
                    docker_image = build_sandbox_environment_image(exec_dir)

                # 3. Structured Patch Security Scan (inspects added_lines for secrets/injection, new_content for AST)
                sec = SecurityScanner()
                sec_res = sec.scan_patch_changes(patches)
                security_verdict = "✅ Passed" if sec_res.safe else "❌ FAILED"

                # 3a. Targeted Test Execution (Fast Feedback - All Tiers)
                selector = TestSelector(exec_dir)
                selected_tests = selector.select_tests_for_patch(affected_files)
                selected_res = run_tests_sandboxed(
                    exec_dir,
                    test_files=selected_tests,
                    use_docker=use_docker,
                    require_sandbox=require_sandbox,
                    docker_image=docker_image,
                )
                targeted_passed = selected_res.test_result.passed
                correctness_verdict = "✅ Passed" if targeted_passed else "❌ FAILED"

                # 3b. Regression & Mutation Verification (STANDARD & DEEP Tiers)
                full_passed = True
                full_res = None
                mut_score = None
                mut_killed = 0
                mut_total = 0
                trusted_base_passed = True
                trusted_base_reason = ""

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
                    full_res = run_tests_sandboxed(
                        exec_dir,
                        use_docker=use_docker,
                        require_sandbox=require_sandbox,
                        docker_image=docker_image,
                    )
                    full_passed = full_res.test_result.passed
                    regression_verdict = f"✅ Passed (0 regressed, {full_res.test_result.summary_line})" if full_passed else "❌ FAILED (Regressions detected)"

                    # Trusted Baseline Test Suite Verification: Run BASE tests against proposed HEAD snapshot
                    base_ref_for_tests = args.base or ("HEAD~1" if is_diff_mode else "HEAD")
                    try:
                        with create_commit_snapshot(proj, commit_ref=base_ref_for_tests) as base_dir:
                            base_test_files = [
                                str(t.relative_to(base_dir)).replace("\\", "/")
                                for t in base_dir.rglob("test_*.py")
                                if not any(p in t.parts for p in ("venv", ".venv", ".pytest_cache", "benchmarks", "benchmark", "data"))
                            ]
                            if base_test_files:
                                base_eval_res = run_tests_sandboxed(
                                    exec_dir,
                                    test_files=base_test_files,
                                    use_docker=use_docker,
                                    require_sandbox=require_sandbox,
                                    docker_image=docker_image,
                                )
                                if not base_eval_res.test_result.passed:
                                    trusted_base_passed = False
                                    trusted_base_reason = f"Base test suite failed on HEAD: {base_eval_res.test_result.summary_line}"
                    except Exception as e:
                        logging.warning(f"Could not verify base test suite against HEAD: {e}")
                    
                    if mutation_targets:
                        max_mutants = 2 if active_tier == "STANDARD" else 4
                        mut_res = run_mutation_tests(
                            exec_dir,
                            mutation_targets[:2],
                            max_mutants_per_file=max_mutants,
                            use_docker=use_docker,
                            require_sandbox=require_sandbox,
                            docker_image=docker_image,
                        )
                        if mut_res.score is not None:
                            mut_score = mut_res.score
                            mut_killed = mut_res.killed_mutants
                            mut_total = mut_res.killed_mutants + mut_res.survived_mutants
                            mut_pct = mut_res.score * 100
                            mutation_verdict = f"✅ {mut_pct:.1f}% ({mut_res.killed_mutants}/{mut_total} killed)"
                        elif mut_res.total_mutants > 0 and mut_res.invalid_mutants == mut_res.total_mutants:
                            mutation_verdict = "➖ N/A (Mutations caused AST/import errors)"
                        else:
                            mutation_verdict = "➖ N/A (No mutable AST operators)"
                    else:
                        mutation_verdict = "➖ N/A (No production source files modified)"
                else:
                    regression_verdict = "⚡ Skipped (FAST Tier)"
                    mutation_verdict = "⚡ Skipped (FAST Tier)"

                # 3c. DEEP Tier: Multi-Run Performance Regression Benchmark
                perf_regression = False
                perf_delta_pct = None
                base_duration_s = None
                head_duration_s = None

                if active_tier == "DEEP" and selected_tests:
                    base_ref_for_perf = args.base or "HEAD~1"
                    try:
                        with create_commit_snapshot(proj, commit_ref=base_ref_for_perf) as base_dir:
                            # Only benchmark common tests present in both BASE and HEAD snapshots
                            common_tests = [
                                t for t in selected_tests
                                if (base_dir / t).exists() and (exec_dir / t).exists()
                            ]
                            if common_tests:
                                import statistics
                                # Warmup + 3 measured iterations on BASE
                                run_tests_sandboxed(base_dir, test_files=common_tests, use_docker=use_docker, require_sandbox=require_sandbox, docker_image=docker_image)
                                base_runs = [
                                    run_tests_sandboxed(base_dir, test_files=common_tests, use_docker=use_docker, require_sandbox=require_sandbox, docker_image=docker_image).test_result.duration_seconds
                                    for _ in range(3)
                                ]
                                base_duration_s = round(statistics.median(base_runs), 3)

                                # Warmup + 3 measured iterations on HEAD
                                run_tests_sandboxed(exec_dir, test_files=common_tests, use_docker=use_docker, require_sandbox=require_sandbox, docker_image=docker_image)
                                head_runs = [
                                    run_tests_sandboxed(exec_dir, test_files=common_tests, use_docker=use_docker, require_sandbox=require_sandbox, docker_image=docker_image).test_result.duration_seconds
                                    for _ in range(3)
                                ]
                                head_duration_s = round(statistics.median(head_runs), 3)

                                delta_s = head_duration_s - base_duration_s
                                perf_delta_pct = (delta_s / max(base_duration_s, 0.001)) * 100.0
                                if perf_delta_pct > 15.0 and delta_s > 0.05:
                                    perf_regression = True
                                    perf_verdict = f"⚠️ Regression detected (+{perf_delta_pct:.1f}% median: {base_duration_s:.3f}s -> {head_duration_s:.3f}s)"
                                    risk.factors.append(f"Performance latency regression (+{perf_delta_pct:.1f}%)")
                                else:
                                    perf_verdict = f"✅ Passed ({perf_delta_pct:+.1f}% median: {base_duration_s:.3f}s -> {head_duration_s:.3f}s)"
                            else:
                                perf_verdict = "➖ Skipped (No common test files between BASE and HEAD)"
                    except Exception as e:
                        perf_verdict = f"➖ Skipped (Baseline benchmark error: {e})"
                else:
                    perf_verdict = f"⚡ Skipped ({active_tier} Tier)"

            # Print Verification Card
            targeted_status = "passed" if targeted_passed else "failed"
            print(f"Correctness:        {correctness_verdict} ({len(selected_tests)} targeted test files {targeted_status} in {selected_res.test_result.duration_seconds}s)")
            print(f"Regression:         {regression_verdict}")
            print(f"Security:           {security_verdict} (AST imports + added lines scanned)")
            print(f"Mutation Score:     {mutation_verdict}")
            print(f"Performance:        {perf_verdict}")
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
            elif not trusted_base_passed:
                technical_verdict = "FAILED"
                tech_reason = trusted_base_reason
            elif active_tier == "FAST":
                technical_verdict = "QUALIFIED_WITHIN_SCOPE"
                tech_reason = "Targeted checks passed within FAST scope (full regression & mutation skipped)"
            else:
                technical_verdict = "QUALIFIED"
                tech_reason = "All automated verification gates passed"

            # Determine Release Policy (Governance & Risk Assessment)
            if technical_verdict == "FAILED":
                release_policy = "BLOCK"
                policy_reason = tech_reason
            elif perf_regression:
                release_policy = "REVIEW"
                policy_reason = f"Performance latency regression (+{perf_delta_pct:.1f}%) requires review"
            elif active_tier == "FAST":
                release_policy = "REVIEW"
                policy_reason = "FAST tier provides targeted verification only; full regression & mutation required for automated production merge"
            elif risk.risk_level == "LOW":
                release_policy = "AUTO_APPROVE"
                policy_reason = "Low risk change meets criteria for automated production merge"
            elif risk.risk_level == "MEDIUM":
                release_policy = "REVIEW"
                policy_reason = "Medium risk change requires peer review before release"
            else:  # HIGH
                release_policy = "REVIEW"
                policy_reason = "High risk change requires mandatory senior/security review"

            tech_icon = "✅" if "QUALIFIED" in technical_verdict else "❌"
            policy_icon = "🚀" if release_policy == "AUTO_APPROVE" else "⚠️" if release_policy == "REVIEW" else "⛔"

            print(f"Technical Verdict:  {technical_verdict} {tech_icon}")
            if technical_verdict == "FAILED":
                print(f"  - Failure cause:   {tech_reason}")
                for issue in sec_res.issues:
                    print(f"  - Security issue:  {issue}")

            print(f"Release Policy:     {release_policy} {policy_icon} ({policy_reason})")

            # Exact Git SHAs and diff provenance (fail-closed, no silent fallback)
            def _resolve_git_sha(repo: Path, ref_name: str) -> str:
                res = subprocess.run(
                    ["git", "rev-parse", "--verify", ref_name],
                    cwd=repo,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace"
                )
                if res.returncode != 0:
                    err = res.stderr.strip() if res.stderr else f"exit code {res.returncode}"
                    raise RuntimeError(
                        f"Commit-pure verification error: Failed to resolve Git ref '{ref_name}' into commit SHA ({err}). "
                        "Aegis refuses to proceed without verified Git commit provenance."
                    )
                sha = res.stdout.strip()
                if len(sha) != 40 or not all(c in "0123456789abcdefABCDEF" for c in sha):
                    raise RuntimeError(
                        f"Commit-pure verification error: Ref '{ref_name}' resolved to invalid commit SHA '{sha}' "
                        "(expected 40-character hexadecimal SHA)."
                    )
                return sha.lower()

            if args.diff:
                base_sha = _resolve_git_sha(proj, args.base or "HEAD")
                raw_diff_content = raw
                diff_sha256 = hashlib.sha256(raw_diff_content.encode("utf-8")).hexdigest()
                head_sha = f"patch:{diff_sha256[:12]}"
            elif args.base:
                base_sha = _resolve_git_sha(proj, args.base)
                head_sha = _resolve_git_sha(proj, args.head or "HEAD")
                raw_diff_content = git_change.raw_diff if git_change else ""
                diff_sha256 = hashlib.sha256(raw_diff_content.encode("utf-8")).hexdigest()
            else:
                base_sha = _resolve_git_sha(proj, "HEAD")
                head_sha = base_sha
                raw_diff_content = ""
                diff_sha256 = hashlib.sha256(b"").hexdigest()

            if env_info is None:
                env_info = inspect_repository_environment(proj)

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
                "aegis_version": "1.0.0",
                "run_id": run_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "repository": proj.name,
                "base": args.base or "HEAD~1",
                "head": args.head or "HEAD",
                "provenance": {
                    "base_sha": base_sha,
                    "head_sha": head_sha,
                    "diff_sha256": diff_sha256,
                    "python_version": env_info.python_version,
                    "platform": env_info.platform,
                    "sandbox": {
                        "required": require_sandbox,
                        "used": use_docker,
                        "docker_available": is_docker_available(),
                    },
                    "requested_environment": {
                        "python_version": env_info.python_version,
                        "platform": env_info.platform,
                        "dependency_manifests": env_info.dependency_manifests,
                        "dependency_manifest_hash": env_info.dependency_manifest_hash,
                        "resolved_dependency_lock_hash": env_info.resolved_dependency_lock_hash,
                        "dependency_lock_hash": env_info.dependency_lock_hash,
                        "environment_fingerprint": env_info.environment_fingerprint,
                    },
                    "executed_environment": resolve_executed_environment(
                        use_docker=use_docker,
                        docker_image=docker_image,
                        host_env=env_info,
                    ).to_dict(),
                    "environment": {
                        "dependency_manifests": env_info.dependency_manifests,
                        "dependency_manifest_hash": env_info.dependency_manifest_hash,
                        "resolved_dependency_lock_hash": env_info.resolved_dependency_lock_hash,
                        "dependency_lock_hash": env_info.dependency_lock_hash,
                        "environment_fingerprint": env_info.environment_fingerprint,
                        "sandbox_engine": env_info.sandbox,
                        "sandbox_image": docker_image,
                    },
                },
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
                        "passed": full_passed if active_tier in ("STANDARD", "DEEP") else None,
                        "status": ("passed" if full_passed else "failed") if active_tier in ("STANDARD", "DEEP") else "skipped",
                        "summary": full_res.test_result.summary_line if full_res else None,
                        "duration_seconds": full_res.test_result.duration_seconds if full_res else None,
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
                    "performance": {
                        "status": "evaluated" if active_tier == "DEEP" and base_duration_s is not None else "skipped",
                        "baseline_duration_s": base_duration_s,
                        "head_duration_s": head_duration_s,
                        "delta_pct": round(perf_delta_pct, 2) if perf_delta_pct is not None else None,
                        "regression_detected": perf_regression,
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
