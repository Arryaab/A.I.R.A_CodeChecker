from __future__ import annotations

import logging
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from aegis.config import AegisConfig
from aegis.llm import LLMProvider, LLMResponse, build_repair_prompt, SYSTEM_PROMPT
from aegis.patcher import apply_patch, copy_project, parse_llm_patch
from aegis.execution.runner import TestResult
from aegis.execution.sandbox import run_tests_sandboxed
from aegis.verification.taxonomy import FailureRecord, classify_failure
from aegis.verification.validator import ValidationResult

logger = logging.getLogger(__name__)

@dataclass
class RepairAttempt:
    attempt_number: int
    patch: dict[str, str]
    validation: ValidationResult
    test_result: TestResult | None
    llm_response: LLMResponse
    duration_seconds: float
    diagnosis: str = ""

@dataclass
class RepairResult:
    bug_id: str
    success: bool
    visible_pass: bool
    hidden_pass: bool | None
    attempts: list[RepairAttempt] = field(default_factory=list)
    original_test_result: TestResult | None = None
    final_visible_result: TestResult | None = None
    final_hidden_result: TestResult | None = None
    failure_record: FailureRecord | None = None
    total_duration_seconds: float = 0.0
    total_tokens: int = 0

from aegis.intelligence.repo_mapper import RepoMapper
from aegis.core.agents import PlannerAgent, CriticAgent
from aegis.core.observability import start_trace

def repair_bug(
    *,
    bug_dir: Path,
    provider: LLMProvider,
    config: AegisConfig,
    visible_tests_dir: Path | None = None,
    hidden_tests_dir: Path | None = None,
    bug_id: str = "",
) -> RepairResult:
    """Orchestrate the full repair loop."""
    start_time = time.time()
    trace_id = f"trace_{bug_id or 'run'}_{int(start_time)}"
    trace = start_trace(trace_id, str(bug_dir))
    
    # Create working directory
    work_dir = copy_project(bug_dir)
    
    # Generate repository intelligence map
    repo_span = trace.add_span("repo_mapping")
    try:
        mapper = RepoMapper(work_dir)
        mapper.map_repository()
        repo_map = mapper.generate_prompt_context()
        logger.info(f"Generated repository intelligence map for {bug_id}")
        repo_span.complete(status="success")
    except Exception as e:
        logger.warning(f"Failed to generate repository map: {e}")
        repo_map = None
        repo_span.complete(status="error", error=str(e))
    
    # Copy visible tests if provided
    if visible_tests_dir and visible_tests_dir.exists():
        shutil.copytree(visible_tests_dir, work_dir, dirs_exist_ok=True)
        
    # Get initial visible test result
    test_span = trace.add_span("initial_test")
    sandbox_result = run_tests_sandboxed(
        work_dir,
        timeout=config.timeout_seconds,
        use_docker=config.sandbox_enabled,
        docker_image=config.docker_image
    )
    original_result = sandbox_result.test_result
    test_span.complete(passed=original_result.passed if original_result else False)
    
    # ----- AEGIS 0.3: ORCHESTRATOR & PLANNER -----
    planner = PlannerAgent(provider)
    critic = CriticAgent(provider)
    
    initial_test_output = original_result.stdout + original_result.stderr if original_result else ""
    plan = planner.plan(repo_map or "No repo map", initial_test_output)
    logger.info(f"Planner strategy: {plan.strategy}")
    
    # Read target files based on the plan
    target_files = {}
    if not plan.files_to_modify:
        # Fallback: grab all non-test Python files if planner failed to specify
        for py_file in work_dir.rglob("*.py"):
            if "test_" not in py_file.name and "venv" not in py_file.parts:
                rel = str(py_file.relative_to(work_dir)).replace("\\", "/")
                target_files[rel] = py_file.read_text(encoding="utf-8")
    else:
        for f in plan.files_to_modify:
            p = work_dir / f
            if p.exists() and p.is_file():
                rel = str(p.relative_to(work_dir)).replace("\\", "/")
                target_files[rel] = p.read_text(encoding="utf-8")
            else:
                logger.warning(f"Planner requested file {f} but it does not exist.")
            
    attempts = []
    visible_pass = False
    final_visible_result = original_result
    total_tokens = 0
    previous_attempt = None
    
    for attempt_num in range(1, config.max_retries + 1):
        attempt_start = time.time()
        
        # Inject the Planner's strategy and target files into the Repair Agent's prompt
        prompt = build_repair_prompt(
            files=target_files,
            test_output=final_visible_result.stdout + final_visible_result.stderr if final_visible_result else "",
            previous_attempt=previous_attempt,
            repo_map=repo_map
        )
        prompt = f"PLANNER STRATEGY: {plan.strategy}\n\n" + prompt
        
        try:
            llm_res = provider.ask(prompt, system=SYSTEM_PROMPT)
            total_tokens += llm_res.prompt_tokens + llm_res.completion_tokens
            patch = parse_llm_patch(llm_res.content)
            
            # Use original bug_dir for patching copy
            attempt_dir = copy_project(bug_dir)
            
            patch_result = apply_patch(attempt_dir, patch, validate=True, protect_tests=True)
            validation_res = ValidationResult(
                valid=patch_result.success, 
                errors=patch_result.validation_errors
            )
            
            # Security Scan Guardrail
            from aegis.verification.security import SecurityScanner
            security_scanner = SecurityScanner()
            sec_res = security_scanner.scan_patch(patch)
            if not sec_res.safe:
                logger.warning(f"Security violations detected in patch: {sec_res.issues}")
                validation_res = ValidationResult(valid=False, errors=sec_res.issues)
                attempts.append(RepairAttempt(
                    attempt_number=attempt_num,
                    patch=patch,
                    validation=validation_res,
                    test_result=None,
                    llm_response=llm_res,
                    duration_seconds=time.time() - attempt_start,
                    diagnosis=f"Security scan rejected patch: {', '.join(sec_res.issues)}"
                ))
                previous_attempt = f"Security violation: {sec_res.issues}"
                shutil.rmtree(attempt_dir)
                continue

            if not patch_result.success:
                attempts.append(RepairAttempt(
                    attempt_number=attempt_num,
                    patch=patch,
                    validation=validation_res,
                    test_result=None,
                    llm_response=llm_res,
                    duration_seconds=time.time() - attempt_start
                ))
                previous_attempt = f"Failed validation: {patch_result.validation_errors}"
                shutil.rmtree(attempt_dir)
                continue
                
            # Run tests
            if visible_tests_dir and visible_tests_dir.exists():
                shutil.copytree(visible_tests_dir, attempt_dir, dirs_exist_ok=True)
                
            sandbox_res = run_tests_sandboxed(
                attempt_dir,
                timeout=config.timeout_seconds,
                use_docker=config.sandbox_enabled,
                docker_image=config.docker_image
            )
            test_res = sandbox_res.test_result
            
            # ----- AEGIS 0.3: CRITIC EVALUATION -----
            test_out = test_res.stdout + "\n" + test_res.stderr
            feedback = critic.critique(target_files, patch, test_out)
            
            attempts.append(RepairAttempt(
                attempt_number=attempt_num,
                patch=patch,
                validation=validation_res,
                test_result=test_res,
                llm_response=llm_res,
                duration_seconds=time.time() - attempt_start,
                diagnosis=feedback.feedback
            ))
            
            final_visible_result = test_res
            shutil.rmtree(attempt_dir)
            
            if test_res.passed:
                if feedback.approved:
                    visible_pass = True
                    for k, v in patch.items():
                        if k in target_files:
                            target_files[k] = v
                    logger.info("Patch accepted by tests AND Critic.")
                    break
                else:
                    previous_attempt = f"Tests passed, but Critic rejected the patch: {feedback.feedback}"
                    logger.info("Tests passed but Critic rejected.")
            else:
                previous_attempt = f"Tests failed. Output:\n{test_res.stdout}\n{test_res.stderr}"
                
        except Exception as e:
            logger.error(f"Attempt {attempt_num} failed due to error: {e}")
            previous_attempt = f"System error: {e}"
    
    hidden_pass = None
    final_hidden_result = None
    
    if visible_pass and hidden_tests_dir and hidden_tests_dir.exists():
        final_dir = copy_project(bug_dir)
        apply_patch(final_dir, attempts[-1].patch, validate=False)
        shutil.copytree(hidden_tests_dir, final_dir, dirs_exist_ok=True)
        
        h_sandbox_res = run_tests_sandboxed(
            final_dir,
            timeout=config.timeout_seconds,
            use_docker=config.sandbox_enabled
        )
        final_hidden_result = h_sandbox_res.test_result
        hidden_pass = final_hidden_result.passed
        shutil.rmtree(final_dir)
        
    shutil.rmtree(work_dir)
    
    success = visible_pass and (hidden_pass is True or hidden_pass is None)
    
    failure_record = None
    if not success:
        failure_record = classify_failure(
            visible_result=final_visible_result,
            hidden_result=final_hidden_result,
            validation=attempts[-1].validation if attempts else None,
            original_result=original_result
        )

    # Save complete trace
    try:
        trace.save()
    except Exception as e:
        logger.warning(f"Failed to save trace: {e}")

    return RepairResult(
        bug_id=bug_id,
        success=success,
        visible_pass=visible_pass,
        hidden_pass=hidden_pass,
        attempts=attempts,
        original_test_result=original_result,
        final_visible_result=final_visible_result,
        final_hidden_result=final_hidden_result,
        failure_record=failure_record,
        total_duration_seconds=time.time() - start_time,
        total_tokens=total_tokens
    )
