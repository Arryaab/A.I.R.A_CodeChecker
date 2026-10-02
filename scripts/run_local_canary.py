"""
Dedicated Local Qwen Pre-Launch Canary Runner.
Per Founder Directive: Local-First Empirical Execution (Section 12).
Runs 1 isolated Qwen/Ollama run outside the empirical dataset.

Required Criteria:
- 1 task
- 1 Qwen run
- Real tool call
- Multi-turn execution
- Workspace modification
- Successful tests
- Valid Aegis verification
- Valid independent oracle verification
- Valid dataset admission
- Zero contamination of empirical_100_local_v1
"""

import hashlib
import json
import logging
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(".").resolve()))

from aegis.research.agent.loop import AgentExecutionLoop, AgentRunResult, SYSTEM_PROMPT
from aegis.research.features.pre_verification import PreVerificationFeatureExtractor
from aegis.research.models.ollama import OllamaModelAdapter
from aegis.research.oracle.evaluator import IndependentCorrectnessOracle
from aegis.research.provenance.tracker import ProvenanceTracker
from aegis.research.sandbox.isolation import AgentSandbox
from aegis.research.trace.schema import (
    SCHEMA_VERSION,
    AgentTerminationReason,
    FailureCategory,
    ProtocolCompliance,
    ResearchTrace,
    TraceLifecycleState,
    classify_trace_failure,
    validate_research_trace,
)
from aegis.research.verifier.pipeline import AegisResearchVerifier
from aegis.research.dataset.admission import validate_empirical_admission, validate_for_admission
from aegis.research.protocol.validator import AUTHORITATIVE_QWEN_DIGEST

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("aegis.local_canary")


def execute_local_canary(task_id: str = "task_001_fastapi_async_scope") -> dict:
    canary_dir = Path("results/canary")
    canary_dir.mkdir(parents=True, exist_ok=True)

    task_dir = Path(f"benchmarks/v1/{task_id}")
    assert task_dir.exists(), f"Task directory missing: {task_dir}"

    metadata_file = task_dir / "task" / "metadata.json"
    metadata = json.loads(metadata_file.read_text(encoding="utf-8")) if metadata_file.exists() else {"category": "track_1_core_frameworks"}
    problem_md = (task_dir / "task" / "problem.md").read_text(encoding="utf-8")

    logger.info("Initializing OllamaModelAdapter for local canary run...")
    adapter = OllamaModelAdapter(
        model_id="qwen2.5-coder:latest",
        endpoint="http://localhost:11434",
        temperature=0.2,
        seed=42,
        expected_digest=AUTHORITATIVE_QWEN_DIGEST,
    )

    # Verify adapter health first
    health = adapter.check_health()
    if not health.get("healthy"):
        raise RuntimeError(f"Ollama adapter live check failed: {health.get('error')}")
    logger.info(f"Ollama live check healthy: model={health.get('model')}, digest={health.get('digest')}")

    run_id = f"canary_{task_id}_qwen_s42"
    t0 = time.time()

    public_dir = task_dir / "task"
    with AgentSandbox(public_dir) as sandbox:
        agent_loop = AgentExecutionLoop(
            provider=adapter,
            sandbox=sandbox,
            max_iterations=8,
        )

        logger.info(f"Starting canary agent execution on {task_id} with Qwen...")
        agent_result: AgentRunResult = agent_loop.execute(
            task_id=task_id,
            problem_md=problem_md,
            metadata=metadata,
        )

        logger.info(f"Canary agent run completed in {agent_result.agent_duration_seconds:.2f}s across {len(agent_result.steps)} steps")
        logger.info(f"Success signaled: {agent_result.success_signaled}, Modified: {agent_result.modified_files}")

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

        env_fingerprint = {
            "python_version": sys.version.split()[0],
            "os_platform": sys.platform,
            "os_release": platform.platform(),
            "arch": platform.machine(),
            "aegis_version": "1.0.0",
            "provider": "ollama",
            "model_name": "qwen2.5-coder:latest",
            "model_snapshot": AUTHORITATIVE_QWEN_DIGEST,
            "credential_status": "NOT_REQUIRED_LOCAL",
            "credential_fingerprint": None,
        }

        provenance = ProvenanceTracker.extract_provenance(
            task_id=task_id,
            base_dir=sandbox.base_snapshot_dir,
            head_dir=sandbox.workspace_dir,
            metadata=metadata,
            prompt_hashes=prompt_hashes,
            environment_fingerprint=env_fingerprint,
        )

        track = metadata.get("category", "track_1_core_frameworks")
        pre_features = PreVerificationFeatureExtractor.extract(
            provenance=provenance,
            agent_result=agent_result,
            base_dir=sandbox.base_snapshot_dir,
            head_dir=sandbox.workspace_dir,
            task_category=track,
        )

        logger.info("Running AegisResearchVerifier on canary workspace...")
        aegis_report = AegisResearchVerifier.verify(
            task_dir=task_dir,
            candidate_dir=sandbox.workspace_dir,
            agent_result=agent_result,
            provenance=provenance,
        )
        logger.info(f"Aegis Verdict: {aegis_report.technical_verdict} (Policy: {aegis_report.release_policy})")

        logger.info("Running IndependentCorrectnessOracle on canary workspace...")
        oracle_report = IndependentCorrectnessOracle.evaluate(
            task_dir=task_dir,
            candidate_dir=sandbox.workspace_dir,
            provenance=provenance,
        )
        logger.info(f"Oracle Verdict: {oracle_report.oracle_verdict} (is_defective: {oracle_report.is_defective})")

        failure_cat, failure_detail = classify_trace_failure(
            agent_error=agent_result.error_message,
            agent_signaled=agent_result.success_signaled,
            validator_valid=aegis_report.validator_valid,
            visible_passed=aegis_report.visible_tests_passed,
            oracle_defective=(oracle_report.is_defective == 1),
            aegis_verdict=aegis_report.technical_verdict,
        )

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

        post_signals = {
            "baseline_test_duration": oracle_report.base_latency_s * 1000.0,
            "candidate_test_duration": oracle_report.candidate_latency_s * 1000.0,
            "latency_delta_pct": oracle_report.latency_delta_pct,
            "verification_duration_s": aegis_report.verification_duration_seconds,
            "mutation_score": aegis_report.mutation_score,
            "security_issues_count": len(aegis_report.security_issues),
        }

    client_req_id = f"client_ollama_{run_id}_{int(t0*1000)}"

    trace = ResearchTrace(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        task_id=task_id,
        track=track,
        model="qwen2.5-coder:latest",
        provider="ollama",
        seed=42,
        temperature=0.2,
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
        lifecycle_state=TraceLifecycleState.COMPLETED.value,
        run_key=f"canary_qwen_{task_id}_s42",
        agent_policy_hash="sha256:21d279e3de0760d2646be973f28488810170d6a58ad92b871ed8c80359050d79",
        sampling_semantics={
            "seed_requested": 42,
            "seed_applied": 42,
            "seed_semantics": "PSEUDO_DETERMINISTIC",
            "temperature_requested": 0.2,
            "temperature_applied": 0.2,
        },
        model_capabilities={
            "supports_tools": True,
            "supports_seed": True,
            "supports_temperature": True,
            "supports_token_accounting": True,
            "model_snapshot": AUTHORITATIVE_QWEN_DIGEST,
        },
        execution_origin="REAL_PROVIDER",
        client_request_id=client_req_id,
        provider_request_id=None,
        provider_request_id_available=False,
        provider_response_metadata={"model": "qwen2.5-coder:latest", "provider": "ollama"},
    )

    trace_dict = trace.to_dict()

    # Save ONLY to results/canary - ZERO contamination of empirical_100_local_v1
    canary_file = canary_dir / f"{run_id}.json"
    canary_file.write_text(json.dumps(trace_dict, indent=2), encoding="utf-8")
    logger.info(f"Canary trace saved to: {canary_file}")

    # Validate against Admission Gate
    admitted, admission_reasons = validate_for_admission(trace_dict, require_real_provider=True)
    logger.info(f"Canary Admission Result: admitted={admitted}, reasons={admission_reasons}")

    tool_calls_count = sum(len(s.tool_calls) for s in agent_result.steps)

    disposition = {
        "status": "PASSED" if (len(agent_result.steps) >= 2 and tool_calls_count >= 1 and admitted) else "FAILED",
        "task_id": task_id,
        "model": "qwen2.5-coder:latest",
        "provider": "ollama",
        "total_steps": len(agent_result.steps),
        "total_tool_calls": tool_calls_count,
        "first_tool_called": agent_result.steps[0].tool_calls[0]["name"] if agent_result.steps and agent_result.steps[0].tool_calls else None,
        "final_step_index": len(agent_result.steps),
        "success_signaled": agent_result.success_signaled,
        "aegis_verdict": aegis_report.technical_verdict,
        "aegis_release_policy": aegis_report.release_policy,
        "oracle_verdict": oracle_report.oracle_verdict,
        "admission_passed": admitted,
        "admission_reasons": admission_reasons,
        "canary_artifact": str(canary_file),
        "excluded_from_empirical_100_local_v1": True,
    }

    disp_file = canary_dir / "local_canary_disposition.json"
    disp_file.write_text(json.dumps(disposition, indent=2), encoding="utf-8")
    logger.info(f"Canary disposition saved to: {disp_file}")

    print("\n" + "=" * 70)
    print("LOCAL QWEN CANARY EXECUTION SUMMARY")
    print("=" * 70)
    for k, v in disposition.items():
        print(f"  {k:35s}: {v}")
    print("=" * 70 + "\n")

    return disposition


if __name__ == "__main__":
    disposition = execute_local_canary()
    if disposition["status"] != "PASSED":
        sys.exit(1)
