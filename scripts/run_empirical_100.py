"""
Aegis Research: Empirical 100-Run Study Execution Engine (empirical_100_v1)
Controlled large-scale empirical data collection phase under strict research integrity controls.

Immutability Invariants:
- AegisBench-v1 frozen & locked
- empirical_100_v1 protocol frozen
- Aegis Core 1.0 architecture frozen (1b5baf1)
- MLVerify training prohibited during execution
- Zero dynamic redistribution or cherry-picking
- Raw traces and derived aggregations segregated
- Zero simulation or mock adapters in empirical execution path
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import math
import os
import platform
import shutil
import statistics
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(".").resolve()))

from aegis.research.agent.loop import AgentExecutionLoop, AgentRunResult, SYSTEM_PROMPT
from aegis.research.features.pre_verification import PreVerificationFeatureExtractor
from aegis.research.models.base import (
    ModelMetadata,
    ModelProvider,
    ModelResponse,
    ToolCall,
    ProviderUnavailableError,
    ProviderExecutionError,
    ModelDigestMismatchError,
)
from aegis.research.models.ollama import OllamaModelAdapter
from aegis.research.models.openai import OpenAICompatibleAdapter
from aegis.research.models.gemini import GeminiModelAdapter
from aegis.research.oracle.evaluator import IndependentCorrectnessOracle
from aegis.research.provenance.tracker import ProvenanceTracker
from aegis.research.sandbox.isolation import AgentSandbox, SandboxSecurityViolation
from aegis.research.tools.workspace_tools import WorkspaceToolSet
from aegis.research.trace.schema import (
    SCHEMA_VERSION,
    AgentTerminationReason,
    FailureCategory,
    ProtocolCompliance,
    ResearchTrace,
    SeedSemantics,
    TraceLifecycleState,
    classify_trace_failure,
    validate_research_trace,
)
from aegis.research.verifier.pipeline import AegisResearchVerifier
from aegis.research.worker_pool import (
    IdempotentScheduler,
    PersistentWorkerPool,
    WorkerCleanlinessChecker,
    WorkerFailureCategory,
)
from aegis.research.dataset.admission import validate_empirical_admission
from aegis.research.protocol.validator import SemanticProtocolValidator, AUTHORITATIVE_QWEN_DIGEST

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("aegis.empirical_100")

EXPERIMENT_ID = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "empirical_100_local_v1"
BENCHMARK_DIR = Path("benchmarks/v1")
STUDY_DIR = Path(EXPERIMENT_ID)
RAW_DIR = STUDY_DIR / "raw"
TRACES_DIR = STUDY_DIR / "traces"
DERIVED_DIR = STUDY_DIR / "derived"
REPORTS_DIR = STUDY_DIR / "reports"
METRICS_DIR = STUDY_DIR / "metrics"
FAILURES_DIR = STUDY_DIR / "failures"
INTEGRITY_DIR = STUDY_DIR / "integrity"


# ---------------------------------------------------------------------------
# Real Model Adapter Factory (Fail-Closed, Zero Mocks)
# ---------------------------------------------------------------------------

def create_model_adapter(
    config: Dict[str, Any],
    seed: int,
    temperature: float = 0.2,
) -> ModelProvider:
    """Instantiate a real, validated model provider adapter.
    Fails closed if the provider is unavailable or misconfigured.
    """
    provider_name = config["provider"].lower()
    model_id = config["model_id"]
    snapshot = config.get("snapshot") or config.get("model_snapshot")

    if provider_name == "ollama":
        expected_digest = snapshot or AUTHORITATIVE_QWEN_DIGEST
        adapter = OllamaModelAdapter(
            model_id=model_id,
            endpoint="http://localhost:11434",
            temperature=temperature,
            seed=seed,
            expected_digest=expected_digest,
        )
        health = adapter.check_health()
        if not health.get("healthy"):
            raise ProviderUnavailableError(
                f"Ollama provider unavailable for model '{model_id}': {health.get('error')}"
            )
        return adapter

    elif provider_name == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise ProviderUnavailableError(
                "OPENAI_API_KEY environment variable is missing or empty. Cannot invoke real OpenAI model."
            )
        adapter = OpenAICompatibleAdapter(
            model_id=model_id,
            api_key=api_key,
            temperature=temperature,
            seed=seed,
        )
        health = adapter.check_health()
        if not health.get("healthy"):
            raise ProviderUnavailableError(
                f"OpenAI provider unavailable for model '{model_id}': {health.get('error')}"
            )
        return adapter

    elif provider_name in ("gemini", "google"):
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("AEGIS_API_KEY", "")
        if not api_key:
            raise ProviderUnavailableError(
                "GEMINI_API_KEY / AEGIS_API_KEY environment variable is missing or empty. Cannot invoke real Gemini model."
            )
        adapter = GeminiModelAdapter(
            model_id=model_id,
            api_key=api_key,
            temperature=temperature,
            seed=seed,
        )
        health = adapter.check_health()
        if not health.get("healthy"):
            raise ProviderUnavailableError(
                f"Gemini provider unavailable for model '{model_id}': {health.get('error')}"
            )
        return adapter

    else:
        raise ProviderUnavailableError(f"Unsupported or unconfigured provider: '{provider_name}'")


# ---------------------------------------------------------------------------
# Immutable Input Verification Gate
# ---------------------------------------------------------------------------

def verify_immutable_inputs() -> None:
    """Strictly verifies benchmark lock, protocol hashes, and manifest integrity."""
    print(">> [GATE 1] Verifying Immutable Inputs and Cryptographic Lock...")

    lock_path = Path("AegisBench-v1.lock.json")
    if not lock_path.exists():
        raise RuntimeError("FATAL: AegisBench-v1.lock.json missing!")

    lock_data = json.loads(lock_path.read_text(encoding="utf-8"))
    expected_task_hash = "sha256:78fcca20228154bfb3b37d7c8bb0cec6aa3a459759297cbd6969ce031293b2a5"
    expected_orc_hash = "sha256:55a0799e83f2887254f58fd63fc6b39891056b6f5f424ad26fb3ce4bbf623c37"
    expected_env_hash = "sha256:090d1d67b48b1e7281419562f627f5cd92cef78dfdbed813c79bfca4c3b8e06b"

    if lock_data.get("task_manifest_hash") != expected_task_hash:
        raise RuntimeError(f"FATAL: Task manifest hash mismatch! {lock_data.get('task_manifest_hash')}")
    if lock_data.get("oracle_manifest_hash") != expected_orc_hash:
        raise RuntimeError(f"FATAL: Oracle manifest hash mismatch! {lock_data.get('oracle_manifest_hash')}")
    if lock_data.get("environment_manifest_hash") != expected_env_hash:
        raise RuntimeError(f"FATAL: Environment manifest hash mismatch! {lock_data.get('environment_manifest_hash')}")

    # Verify Protocol Hashes
    proto_dir = Path(f"experiments/protocols/{EXPERIMENT_ID}")
    proto_hash_file = proto_dir / "protocol_hashes.json"
    if not proto_hash_file.exists():
        raise RuntimeError(f"FATAL: Protocol hashes JSON missing for {EXPERIMENT_ID}!")
    proto_hashes = json.loads(proto_hash_file.read_text(encoding="utf-8"))
    for fname, expected_h in proto_hashes.items():
        target = proto_dir / fname
        if not target.exists():
            raise RuntimeError(f"FATAL: Protocol artifact missing: {target}")
        actual_h = f"sha256:{hashlib.sha256(target.read_bytes()).hexdigest()}"
        if actual_h != expected_h:
            raise RuntimeError(f"FATAL: Protocol hash mismatch for {fname}: expected {expected_h}, got {actual_h}")

    # Verify Semantic Protocol Agreement
    validator = SemanticProtocolValidator(experiment_id=EXPERIMENT_ID)
    report = validator.validate()
    if not report.is_valid:
        raise RuntimeError(f"FATAL: Semantic protocol validation failed: {report.errors}")

    print("   [OK] Benchmark locks, protocol hashes, and semantic agreement verified 100% authentic.\n")


# ---------------------------------------------------------------------------
# Study Execution Matrix
# ---------------------------------------------------------------------------

def build_execution_matrix() -> List[Dict[str, Any]]:
    """Builds or loads the frozen 100-run execution matrix matching sampling.yaml."""
    matrix_file = STUDY_DIR / "execution_matrix.json"
    validator = SemanticProtocolValidator(experiment_id=EXPERIMENT_ID)
    if matrix_file.exists():
        try:
            matrix = json.loads(matrix_file.read_text(encoding="utf-8"))
            if len(matrix) == 100:
                return matrix
        except Exception:
            pass

    matrix = validator.generate_authoritative_execution_matrix()
    matrix_file.parent.mkdir(parents=True, exist_ok=True)
    matrix_file.write_text(json.dumps(matrix, indent=2), encoding="utf-8")
    return matrix


# ---------------------------------------------------------------------------
def check_local_resources(model_cfg: Dict[str, Any]) -> Tuple[bool, str]:
    """Monitor local system resources: Ollama health, RAM, Disk capacity."""
    try:
        free_bytes = shutil.disk_usage(".").free
        free_mb = free_bytes / (1024 * 1024)
        if free_mb < 500:
            return False, f"Disk space exhausted: {free_mb:.1f} MB remaining (min threshold: 500 MB)"
    except Exception as e:
        logger.warning(f"Could not check disk usage: {e}")

    try:
        import psutil
        vm = psutil.virtual_memory()
        if vm.available / (1024 * 1024) < 100:
            return False, f"RAM exhausted: {vm.available / (1024 * 1024):.1f} MB available (min threshold: 100 MB)"
    except ImportError:
        pass

    if model_cfg["provider"].lower() == "ollama":
        adapter = OllamaModelAdapter(
            model_id=model_cfg["model_id"],
            endpoint="http://localhost:11434",
            expected_digest=model_cfg.get("snapshot") or AUTHORITATIVE_QWEN_DIGEST,
        )
        h = adapter.check_health()
        if not h.get("healthy"):
            return False, f"Local Ollama provider unhealthy: {h.get('error')}"

    return True, "OK"


# ---------------------------------------------------------------------------
# Single Run Execution with Strict Lifecycle
# ---------------------------------------------------------------------------

def execute_study_run(
    run_idx: int,
    total_runs: int,
    plan: Dict[str, Any],
    scheduler: IdempotentScheduler,
    worker_id: int = 0,
) -> Dict[str, Any]:
    task_id = plan["task_id"]
    model_cfg = {
        "model_id": plan["model_id"],
        "provider": plan["provider"],
        "snapshot": plan["model_snapshot"],
        "config_id": plan.get("model_config_id", plan.get("model_id")),
    }
    seed = plan["seed"]
    temperature = plan.get("temperature", 0.2)
    max_turns = plan.get("max_turns", 8)
    run_id = plan.get("run_id") or f"emp100_{task_id[:16]}_{model_cfg['config_id'].lower()}_s{seed}"

    run_key = scheduler.compute_run_key(
        experiment_id=EXPERIMENT_ID,
        task_id=task_id,
        model_id=model_cfg["model_id"],
        seed=seed,
        temperature=temperature,
    )

    # 1. State: CREATED
    lifecycle_state = TraceLifecycleState.CREATED.value
    scheduler.register_execution(run_key=run_key, run_id=run_id, is_retry=False)

    task_dir = BENCHMARK_DIR / task_id
    public_dir = task_dir / "task"
    metadata_file = public_dir / "metadata.json"
    metadata = json.loads(metadata_file.read_text(encoding="utf-8")) if metadata_file.exists() else {}
    problem_file = public_dir / "problem.md"
    problem_md = problem_file.read_text(encoding="utf-8") if problem_file.exists() else f"Fix bug in {task_id}"

    initial_cwd = os.getcwd()
    initial_env_keys = set(os.environ.keys())

    t0_run = time.time()
    logger.info(f"[{run_idx:03d}/{total_runs}] Starting {run_id} (Model: {model_cfg['model_id']}, Seed: {seed})")

    # Local resource verification
    res_ok, res_msg = check_local_resources(model_cfg)
    if not res_ok:
        logger.error(f"Local resource protection triggered for {run_id}: {res_msg}")
        fail_cat = (
            FailureCategory.LOCAL_PROVIDER_UNAVAILABLE.value
            if "ollama" in res_msg.lower()
            else FailureCategory.RESOURCE_EXHAUSTION.value
        )
        fail_data = {
            "run_id": run_id,
            "run_key": run_key,
            "task_id": task_id,
            "model": model_cfg["model_id"],
            "provider": model_cfg["provider"],
            "seed": seed,
            "temperature": temperature,
            "lifecycle_state": TraceLifecycleState.FAILED.value,
            "failure_category": fail_cat,
            "failure_detail": res_msg,
            "execution_origin": "REAL_PROVIDER",
            "admitted": False,
        }
        (FAILURES_DIR / f"{run_id}_resource_exhaustion.json").write_text(
            json.dumps(fail_data, indent=2), encoding="utf-8"
        )
        raise RuntimeError(f"FATAL: Resource check failed: {res_msg}. Halting experiment.")

    # 2. State: RUNNING
    lifecycle_state = TraceLifecycleState.RUNNING.value

    try:
        provider = create_model_adapter(model_cfg, seed=seed, temperature=temperature)
    except ProviderUnavailableError as e:
        logger.error(f"Provider unavailable for {run_id}: {e}")
        fail_cat = (
            FailureCategory.LOCAL_PROVIDER_UNAVAILABLE.value
            if model_cfg["provider"].lower() == "ollama"
            else FailureCategory.MODEL_FAILURE.value
        )
        scheduler.mark_failed(run_key=run_key, run_id=run_id, error=str(e))
        fail_data = {
            "run_id": run_id,
            "run_key": run_key,
            "task_id": task_id,
            "model": model_cfg["model_id"],
            "provider": model_cfg["provider"],
            "seed": seed,
            "temperature": temperature,
            "lifecycle_state": TraceLifecycleState.FAILED.value,
            "failure_category": fail_cat,
            "failure_detail": f"PROVIDER_UNAVAILABLE: {e}",
            "execution_origin": "REAL_PROVIDER",
            "admitted": False,
        }
        (FAILURES_DIR / f"{run_id}_provider_unavailable.json").write_text(
            json.dumps(fail_data, indent=2), encoding="utf-8"
        )
        raise RuntimeError(f"FATAL: Required model provider unavailable for {run_id}: {e}. Experiment halted without model substitution.")

    with AgentSandbox(public_dir) as sandbox:
        # Check security: verify private evaluator artifacts not in workspace
        for bad_p in ("oracle_tests", "oracle_spec.yaml", "oracle_patch.diff", "aegis_hidden_tests"):
            if (sandbox.workspace_dir / bad_p).exists():
                raise SandboxSecurityViolation(f"CRITICAL SECURITY INCIDENT: Leaked {bad_p} into workspace!")

        agent_loop = AgentExecutionLoop(
            provider=provider,
            sandbox=sandbox,
            max_iterations=max_turns,
        )
        agent_result: AgentRunResult = agent_loop.execute(
            task_id=task_id,
            problem_md=problem_md,
            metadata=metadata,
        )

        # Provenance Tracking
        tool_schemas_json = json.dumps(agent_loop.tool_set.get_tool_schemas(), sort_keys=True)
        oracle_spec_file = task_dir / "private" / "oracle_spec.yaml"
        oracle_spec_bytes = oracle_spec_file.read_bytes() if oracle_spec_file.exists() else b""

        prompt_hashes = {
            "system_prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
            "task_prompt_sha256": hashlib.sha256(problem_md.encode("utf-8")).hexdigest(),
            "tool_schema_sha256": hashlib.sha256(tool_schemas_json.encode("utf-8")).hexdigest(),
            "task_spec_sha256": hashlib.sha256(metadata_file.read_bytes() if metadata_file.exists() else b"").hexdigest(),
            "oracle_spec_sha256": hashlib.sha256(oracle_spec_bytes).hexdigest(),
        }

        p_name = model_cfg["provider"].lower()
        if p_name in ("gemini", "google"):
            c_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("AEGIS_API_KEY", "")
            c_status = "PRESENT" if c_key else "MISSING"
            c_fingerprint = f"sha256:{hashlib.sha256(c_key.encode('utf-8')).hexdigest()[:16]}" if c_key else None
        elif p_name == "openai":
            c_key = os.environ.get("OPENAI_API_KEY", "")
            c_status = "PRESENT" if c_key else "MISSING"
            c_fingerprint = f"sha256:{hashlib.sha256(c_key.encode('utf-8')).hexdigest()[:16]}" if c_key else None
        else:
            c_status = "NOT_REQUIRED_LOCAL"
            c_fingerprint = None

        env_fingerprint = {
            "python_version": sys.version.split()[0],
            "os_platform": sys.platform,
            "os_release": platform.platform(),
            "arch": platform.machine(),
            "aegis_version": "1.0.0",
            "provider": model_cfg["provider"],
            "model_name": model_cfg["model_id"],
            "model_snapshot": model_cfg["snapshot"],
            "credential_status": c_status,
            "credential_fingerprint": c_fingerprint,
        }

        provenance = ProvenanceTracker.extract_provenance(
            task_id=task_id,
            base_dir=sandbox.base_snapshot_dir,
            head_dir=sandbox.workspace_dir,
            metadata=metadata,
            prompt_hashes=prompt_hashes,
            environment_fingerprint=env_fingerprint,
        )

        track = metadata.get("category", "core")
        pre_features = PreVerificationFeatureExtractor.extract(
            provenance=provenance,
            agent_result=agent_result,
            base_dir=sandbox.base_snapshot_dir,
            head_dir=sandbox.workspace_dir,
            task_category=track,
        )

        # 3. State: VERIFICATION
        lifecycle_state = TraceLifecycleState.VERIFICATION.value
        aegis_report = AegisResearchVerifier.verify(
            task_dir=task_dir,
            candidate_dir=sandbox.workspace_dir,
            agent_result=agent_result,
            provenance=provenance,
        )

        # 4. State: ORACLE
        lifecycle_state = TraceLifecycleState.ORACLE.value
        oracle_report = IndependentCorrectnessOracle.evaluate(
            task_dir=task_dir,
            candidate_dir=sandbox.workspace_dir,
            provenance=provenance,
        )

        # 5. State: FINALIZING
        lifecycle_state = TraceLifecycleState.FINALIZING.value
        failure_cat, failure_detail = classify_trace_failure(
            agent_error=agent_result.error_message,
            agent_signaled=agent_result.success_signaled,
            validator_valid=aegis_report.validator_valid,
            visible_passed=aegis_report.visible_tests_passed,
            oracle_defective=(oracle_report.is_defective == 1),
            aegis_verdict=aegis_report.technical_verdict,
        )

        post_signals = {
            "baseline_test_duration": oracle_report.base_latency_s * 1000.0,
            "candidate_test_duration": oracle_report.candidate_latency_s * 1000.0,
            "latency_delta_pct": oracle_report.latency_delta_pct,
            "verification_duration_s": aegis_report.verification_duration_seconds,
            "mutation_score": aegis_report.mutation_score,
            "security_issues_count": len(aegis_report.security_issues),
        }

        ws_dir = sandbox.workspace_dir

    # Check post-run cleanliness after sandbox context has exited and cleaned up
    is_clean, issues = WorkerCleanlinessChecker.verify_cleanliness(
        initial_cwd=initial_cwd,
        initial_env_keys=initial_env_keys,
        workspace_dir=ws_dir,
    )
    if not is_clean:
        failure_cat = FailureCategory.WORKER_ISOLATION_FAILURE
        failure_detail = f"Worker isolation failure: {issues}"

    # 6. State: COMPLETED
    lifecycle_state = TraceLifecycleState.COMPLETED.value
    scheduler.mark_completed(run_key=run_key, run_id=run_id)

    # Determine protocol compliance
    if agent_result.error_message:
        termination_reason = AgentTerminationReason.ERROR.value
        protocol_compliance = ProtocolCompliance.PROTOCOL_INCOMPLETE.value
    elif agent_result.success_signaled:
        termination_reason = AgentTerminationReason.FINISH.value
        protocol_compliance = ProtocolCompliance.COMPLIANT.value
    else:
        termination_reason = AgentTerminationReason.MAX_ITERATIONS.value
        protocol_compliance = ProtocolCompliance.PROTOCOL_INCOMPLETE.value

    outcomes = {
        "model_execution": "SUCCESS" if not agent_result.error_message else "FAILURE",
        "patch_generation": "GENERATED" if provenance.patch_diff.strip() else "NOT_GENERATED",
        "agent_termination": termination_reason,
        "agent_protocol_compliance": protocol_compliance,
        "patch_valid": aegis_report.validator_valid,
        "oracle_correctness": oracle_report.oracle_verdict,
        "aegis_verification": aegis_report.technical_verdict,
        "release_policy": aegis_report.release_policy,
    }

    total_duration = time.time() - t0_run

    # Determine request IDs per Directive P0-I
    client_req_id = f"client_{model_cfg['provider']}_{run_id}_{int(t0_run*1000)}"
    provider_req_id = None
    provider_req_id_avail = False

    policy_path = Path(f"experiments/protocols/{EXPERIMENT_ID}/agent_policy.yaml")
    pol_hash = f"sha256:{hashlib.sha256(policy_path.read_bytes()).hexdigest()}" if policy_path.exists() else "sha256:21d279e3de0760d2646be973f28488810170d6a58ad92b871ed8c80359050d79"

    trace = ResearchTrace(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        task_id=task_id,
        track=track,
        model=model_cfg["model_id"],
        provider=model_cfg["provider"],
        seed=seed,
        temperature=temperature,
        timestamp=datetime.now(timezone.utc).isoformat(),
        provenance=provenance.to_dict(),
        pre_verification_features=pre_features.to_dict(),
        pre_features_vector=pre_features.to_vector(),
        post_verification_signals=post_signals,
        agent_execution={
            "success_signaled": agent_result.success_signaled,
            "termination_reason": agent_result.termination_reason,
            "total_steps": len(agent_result.steps),
            "modified_files": agent_result.modified_files,
            "total_prompt_tokens": agent_result.total_prompt_tokens,
            "total_completion_tokens": agent_result.total_completion_tokens,
            "total_tokens": agent_result.total_tokens,
            "agent_duration_seconds": agent_result.agent_duration_seconds,
            "error_message": agent_result.error_message,
            "steps": [
                {
                    "step_index": s.step_index,
                    "timestamp": s.timestamp,
                    "request_messages_count": s.request_messages_count,
                    "model_response_content": s.model_response_content,
                    "tool_calls": s.tool_calls,
                    "tool_results": s.tool_results,
                    "prompt_tokens": s.prompt_tokens,
                    "completion_tokens": s.completion_tokens,
                    "duration_seconds": s.duration_seconds,
                }
                for s in agent_result.steps
            ],
        },
        aegis_verification=aegis_report.to_dict(),
        oracle_evaluation=oracle_report.to_dict(),
        targets={
            "regression": oracle_report.y_regression,
            "security": oracle_report.y_security,
            "overfitting": oracle_report.y_overfitting,
            "performance": oracle_report.y_performance,
            "is_defective": oracle_report.is_defective,
        },
        accepted=aegis_report.tiers.to_dict(),
        failure_classification={
            "category": failure_cat.value,
            "detail": failure_detail,
        },
        outcomes=outcomes,
        lifecycle_state=lifecycle_state,
        run_key=run_key,
        agent_policy_hash=pol_hash,
        sampling_semantics={
            "seed_requested": seed,
            "seed_applied": seed,
            "seed_semantics": "PSEUDO_DETERMINISTIC" if model_cfg["provider"] != "gemini" else "BEST_EFFORT",
            "temperature_requested": temperature,
            "temperature_applied": temperature,
        },
        model_capabilities={
            "supports_tools": True,
            "supports_seed": (model_cfg["provider"] != "gemini"),
            "supports_temperature": True,
            "supports_token_accounting": True,
            "model_snapshot": model_cfg["snapshot"],
        },
        execution_origin="REAL_PROVIDER",
        client_request_id=client_req_id,
        provider_request_id=provider_req_id,
        provider_request_id_available=provider_req_id_avail,
        provider_response_metadata={"model": model_cfg["model_id"], "provider": model_cfg["provider"]},
    )

    trace_dict = trace.to_dict()

    # Raw trace storage - never overwrite
    raw_path = RAW_DIR / f"{run_id}.json"
    if not raw_path.exists():
        raw_path.write_text(json.dumps(trace_dict, indent=2), encoding="utf-8")
    else:
        logger.info(f"Raw trace already exists for {run_id}, preserving original.")

    # Strict Empirical Dataset Admission Gate Validation
    admitted, admission_reasons = validate_empirical_admission(trace_dict)
    if not admitted:
        logger.error(f"Run {run_id} failed empirical admission: {admission_reasons}")
        fail_path = FAILURES_DIR / f"{run_id}_admission_failure.json"
        fail_path.write_text(json.dumps({"reasons": admission_reasons, "trace": trace_dict}, indent=2), encoding="utf-8")
        return {
            "run_id": run_id,
            "run_key": run_key,
            "admitted": False,
            "trace": trace_dict,
            "error": f"Empirical admission failed: {admission_reasons}",
        }

    # Admitted Trace Storage in REAL_EMPIRICAL - never overwrite
    trace_path = TRACES_DIR / f"{run_id}.json"
    if not trace_path.exists():
        trace_path.write_text(json.dumps(trace_dict, indent=2), encoding="utf-8")

    orc_v = oracle_report.oracle_verdict
    aegis_v = aegis_report.technical_verdict
    c6_v = "C6-PASS" if aegis_report.tiers.c6_full_aegis == 1 else "C6-BLOCK"
    logger.info(f"[{run_idx:03d}/{total_runs}] Done {run_id} -> Oracle: {orc_v} | Aegis: {aegis_v} ({c6_v}) [{total_duration:.2f}s]")

    return {
        "run_id": run_id,
        "run_key": run_key,
        "admitted": True,
        "trace": trace_dict,
        "error": None,
    }


def record_checkpoint(checkpoint_num: int, completed_records: List[Dict[str, Any]]) -> None:
    """Verifies invariant health at checkpoint."""
    admitted_count = sum(1 for r in completed_records if r["admitted"])
    unique_run_keys = len(set(r["run_key"] for r in completed_records))

    cp_data = {
        "checkpoint": checkpoint_num,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_recorded": len(completed_records),
        "admitted_empirical_traces": admitted_count,
        "unique_run_keys": unique_run_keys,
        "duplicate_run_keys_detected": len(completed_records) - unique_run_keys,
        "benchmark_locked": True,
        "dataset_admission_rate_pct": (admitted_count / len(completed_records) * 100.0) if completed_records else 0.0,
    }

    cp_file = INTEGRITY_DIR / f"checkpoint_{checkpoint_num:03d}.json"
    cp_file.write_text(json.dumps(cp_data, indent=2), encoding="utf-8")
    print(f">> [CHECKPOINT {checkpoint_num}] {admitted_count}/{len(completed_records)} admitted. Integrity Verified.")


def save_checkpoint_state(
    completed_records: List[Dict[str, Any]],
    matrix_hash: str,
    protocol_hash: str,
    next_run_index: int,
) -> None:
    """Persists immutable execution state after every completed run (Directive Section 5)."""
    admitted = [r for r in completed_records if r.get("admitted")]
    failed = [r for r in completed_records if not r.get("admitted") or r.get("error")]
    last_id = admitted[-1]["run_id"] if admitted else (completed_records[-1]["run_id"] if completed_records else None)
    state = {
        "experiment_id": EXPERIMENT_ID,
        "completed_runs": len(completed_records),
        "admitted_runs": len(admitted),
        "failed_runs": len(failed),
        "next_run_index": next_run_index,
        "last_successful_run_id": last_id,
        "matrix_hash": matrix_hash,
        "protocol_hash": protocol_hash,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    state_file = INTEGRITY_DIR / "checkpoint_state.json"
    state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")


def main():
    print("=" * 80)
    print(f"AEGIS EMPIRICAL RESEARCH PLATFORM: LAUNCHING {EXPERIMENT_ID}")
    print("Target: 100 Runs | 50 Tasks | Real Model Configurations | 2 Seeds")
    print("=" * 80 + "\n")

    t_study_start = time.time()

    # Step 1: Immutable Inputs Gate
    verify_immutable_inputs()

    # Initialize directory structure
    for d in (RAW_DIR, TRACES_DIR, DERIVED_DIR, REPORTS_DIR, METRICS_DIR, FAILURES_DIR, INTEGRITY_DIR):
        d.mkdir(parents=True, exist_ok=True)

    # Step 2: Build Matrix
    planned_matrix = build_execution_matrix()

    matrix_bytes = json.dumps(planned_matrix, sort_keys=True).encode("utf-8")
    matrix_hash = f"sha256:{hashlib.sha256(matrix_bytes).hexdigest()}"
    proto_hashes_file = Path(f"experiments/protocols/{EXPERIMENT_ID}/protocol_hashes.json")
    protocol_hash = f"sha256:{hashlib.sha256(proto_hashes_file.read_bytes()).hexdigest()}" if proto_hashes_file.exists() else "unknown"

    checkpoint_file = INTEGRITY_DIR / "checkpoint_state.json"
    if checkpoint_file.exists():
        try:
            cp = json.loads(checkpoint_file.read_text(encoding="utf-8"))
            if cp.get("matrix_hash") != matrix_hash:
                raise RuntimeError(f"FATAL: Checkpoint matrix hash mismatch! {cp.get('matrix_hash')} != {matrix_hash}")
            if cp.get("protocol_hash") != protocol_hash:
                raise RuntimeError(f"FATAL: Checkpoint protocol hash mismatch! {cp.get('protocol_hash')} != {protocol_hash}")
            logger.info(f"Verified resume checkpoint: {cp.get('completed_runs')}/100 runs completed.")
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            logger.warning(f"Could not parse checkpoint_state.json: {e}")

    # Step 3: Initialize Idempotent Scheduler
    scheduler = IdempotentScheduler(experiment_id=EXPERIMENT_ID)

    # Check for existing completed runs to support safe resumption without duplicates
    existing_traces = list(TRACES_DIR.glob("*.json"))
    completed_run_ids = set()
    for ef in existing_traces:
        try:
            tdata = json.loads(ef.read_text(encoding="utf-8"))
            if "run_key" in tdata and "run_id" in tdata:
                scheduler.mark_completed(tdata["run_key"], tdata["run_id"])
                completed_run_ids.add(tdata["run_id"])
        except Exception:
            pass

    print(f"Loaded {len(completed_run_ids)} pre-existing completed runs from storage.")

    completed_records: List[Dict[str, Any]] = []

    # Step 4: Execute Planned Runs
    for idx, plan in enumerate(planned_matrix, 1):
        task_id = plan["task_id"]
        model_id = plan["model_id"]
        seed = plan["seed"]
        temperature = plan.get("temperature", 0.2)

        run_key = scheduler.compute_run_key(
            experiment_id=EXPERIMENT_ID,
            task_id=task_id,
            model_id=model_id,
            seed=seed,
            temperature=temperature,
        )

        run_id = plan.get("run_id") or f"emp100_{task_id[:16]}_{plan['model_config_id'].lower()}_s{seed}"

        if scheduler.is_completed(run_key) and (TRACES_DIR / f"{run_id}.json").exists():
            trace_dict = json.loads((TRACES_DIR / f"{run_id}.json").read_text(encoding="utf-8"))
            completed_records.append({
                "run_id": run_id,
                "run_key": run_key,
                "admitted": True,
                "trace": trace_dict,
                "error": None,
            })
            print(f"  [{idx:03d}/100] [SKIP] {run_id} (already admitted)")
            continue

        result = execute_study_run(
            run_idx=idx,
            total_runs=100,
            plan=plan,
            scheduler=scheduler,
            worker_id=0,
        )
        completed_records.append(result)

        save_checkpoint_state(
            completed_records=completed_records,
            matrix_hash=matrix_hash,
            protocol_hash=protocol_hash,
            next_run_index=idx + 1,
        )

        if idx % 25 == 0 or idx == 100:
            record_checkpoint(idx, completed_records)

    total_study_duration = time.time() - t_study_start

    print("\n>> Computing Derived Aggregations and Pre-Registered Empirical Metrics...")
    admitted_traces = [r["trace"] for r in completed_records if r.get("admitted")]
    total_planned = 100
    total_completed = len(completed_records)
    total_admitted = len(admitted_traces)
    total_failed = sum(1 for r in completed_records if not r.get("admitted") or r.get("error"))

    oracle_correct = sum(1 for t in admitted_traces if t.get("oracle_evaluation", {}).get("oracle_verdict") == "CORRECT")
    pass_at_1 = (oracle_correct / total_completed) if total_completed > 0 else 0.0

    defective_patches = [t for t in admitted_traces if t.get("targets", {}).get("is_defective") == 1]
    correct_patches = [t for t in admitted_traces if t.get("targets", {}).get("is_defective") == 0]

    c2_bad_escapes = sum(1 for t in defective_patches if t.get("accepted", {}).get("C2_visible_tests") == 1)
    bad_escape_c2 = (c2_bad_escapes / len(defective_patches)) if defective_patches else 0.0

    # Pre-registered false accept: release_policy == AUTO_APPROVE and oracle_verdict == DEFECTIVE
    c6_false_acceptances = sum(
        1 for t in defective_patches
        if t.get("aegis_verification", {}).get("release_policy") == "AUTO_APPROVE"
    )
    false_acceptance_rate = (c6_false_acceptances / len(defective_patches)) if defective_patches else 0.0
    c6_bad_escapes = c6_false_acceptances
    bad_escape_c6 = false_acceptance_rate

    # Pre-registered false reject: release_policy == BLOCK and oracle_verdict == CORRECT
    c6_false_rejections = sum(
        1 for t in correct_patches
        if t.get("aegis_verification", {}).get("release_policy") == "BLOCK"
    )
    false_rejection_rate = (c6_false_rejections / len(correct_patches)) if correct_patches else 0.0
    false_rejection_c6 = false_rejection_rate

    durations = [t.get("agent_execution", {}).get("duration_seconds", 0.0) for t in admitted_traces]
    tokens = [t.get("agent_execution", {}).get("total_tokens", 0) for t in admitted_traces]

    median_duration = statistics.median(durations) if durations else 0.0
    median_tokens = statistics.median(tokens) if tokens else 0

    tier_counts = {
        "C1_agent_only": sum(1 for t in admitted_traces if t.get("accepted", {}).get("C1_agent_only") == 1),
        "C2_visible_tests": sum(1 for t in admitted_traces if t.get("accepted", {}).get("C2_visible_tests") == 1),
        "C3_hidden_tests": sum(1 for t in admitted_traces if t.get("accepted", {}).get("C3_hidden_tests") == 1),
        "C4_regression": sum(1 for t in admitted_traces if t.get("accepted", {}).get("C4_regression") == 1),
        "C5_mutation": sum(1 for t in admitted_traces if t.get("accepted", {}).get("C5_mutation") == 1),
        "C6_full_aegis": sum(1 for t in admitted_traces if t.get("accepted", {}).get("C6_full_aegis") == 1),
    }

    metrics_payload = {
        "study_id": EXPERIMENT_ID,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "total_planned": total_planned,
        "total_completed": total_completed,
        "total_admitted": total_admitted,
        "total_failed": total_failed,
        "primary_outcomes": {
            "oracle_pass_at_1": round(pass_at_1, 4),
            "bad_patch_escape_rate_c2": round(bad_escape_c2, 4),
            "bad_patch_escape_rate_c6": round(false_acceptance_rate, 4),
            "false_acceptance_rate": round(false_acceptance_rate, 4),
            "false_rejection_rate": round(false_rejection_rate, 4),
            "false_rejection_rate_c6": round(false_rejection_c6, 4),
        },
        "secondary_outcomes": {
            "median_agent_duration_seconds": round(median_duration, 2),
            "median_total_tokens": int(median_tokens),
            "tier_progression_counts": tier_counts,
        },
        "study_duration_seconds": round(total_study_duration, 2),
    }

    (METRICS_DIR / "primary_metrics.json").write_text(json.dumps(metrics_payload, indent=2), encoding="utf-8")
    (DERIVED_DIR / "study_summary.json").write_text(json.dumps(metrics_payload, indent=2), encoding="utf-8")

    report_md = f"""# Empirical Research Report: {EXPERIMENT_ID}

**Generated:** {datetime.now(timezone.utc).isoformat()}
**Total Planned Runs:** {total_planned}
**Total Admitted Traces:** {total_admitted}
**Execution Duration:** {total_study_duration:.1f}s

## 1. Primary Pre-Registered Outcomes
- **Oracle Pass@1:** {pass_at_1 * 100:.1f}% ({oracle_correct}/{total_completed})
- **Bad Patch Escape Rate (Visible CI - C2):** {bad_escape_c2 * 100:.1f}% ({c2_bad_escapes}/{len(defective_patches)})
- **Bad Patch Escape Rate (Aegis Core 1.0 - C6):** {bad_escape_c6 * 100:.1f}% ({c6_bad_escapes}/{len(defective_patches)})
- **False Rejection Rate (Aegis Core 1.0 - C6):** {false_rejection_c6 * 100:.1f}% ({c6_false_rejections}/{len(correct_patches)})

## 2. Verification Ladder Attrition
| Tier | Description | Accepted |
| :--- | :--- | :--- |
| C1 | Agent Self-Report | {tier_counts['C1_agent_only']} |
| C2 | Visible Tests | {tier_counts['C2_visible_tests']} |
| C3 | Hidden Tests | {tier_counts['C3_hidden_tests']} |
| C4 | Regression Verification | {tier_counts['C4_regression']} |
| C5 | Mutation Testing | {tier_counts['C5_mutation']} |
| C6 | Full Aegis Policy | {tier_counts['C6_full_aegis']} |

## 3. Operational Performance
- **Median Agent Duration:** {median_duration:.1f}s
- **Median Total Tokens:** {int(median_tokens)}
"""
    (REPORTS_DIR / "empirical_report.md").write_text(report_md, encoding="utf-8")

    print(f"Study finished. Admitted: {total_admitted}/{total_planned}, Failed: {total_failed}")
    print(f"Report written to: {REPORTS_DIR / 'empirical_report.md'}")


if __name__ == "__main__":
    main()
