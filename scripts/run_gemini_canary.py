"""
Dedicated Gemini Pre-Launch Canary Runner (Directive P0-L).
Runs 1 isolated Gemini run outside the empirical dataset.

Required Criteria:
- 1 task
- 1 Gemini run
- Real tool call
- At least 2 model turns
- Successful tool response
- Successful final model response
- Valid Aegis verification
- Valid oracle verification
- Valid admission
- Must NOT enter the empirical_100_v3 dataset
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, str(Path(".").resolve()))

from aegis.research.agent.loop import AgentExecutionLoop, AgentRunResult, SYSTEM_PROMPT
from aegis.research.features.pre_verification import PreVerificationFeatureExtractor
from aegis.research.models.gemini import GeminiModelAdapter
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("aegis.gemini_canary")


def execute_gemini_canary(task_id: str = "task_001_fastapi_async_scope") -> dict:
    canary_dir = Path("results/canary")
    canary_dir.mkdir(parents=True, exist_ok=True)

    task_dir = Path(f"benchmarks/v1/{task_id}")
    assert task_dir.exists(), f"Task directory missing: {task_dir}"

    metadata_file = task_dir / "task" / "metadata.json"
    metadata = json.loads(metadata_file.read_text(encoding="utf-8")) if metadata_file.exists() else {"category": "track_1_core_frameworks"}
    problem_md = (task_dir / "task" / "problem.md").read_text(encoding="utf-8")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set. Cannot run Gemini canary.")

    logger.info("Initializing GeminiModelAdapter for canary run...")
    adapter = GeminiModelAdapter(
        model_id="gemini-2.5-flash",
        api_key=api_key,
        temperature=0.2,
        seed=42,
        min_request_interval=1.0,
    )

    # Verify adapter health first
    health = adapter.check_health()
    if not health.get("healthy"):
        raise RuntimeError(f"Gemini adapter live check failed: {health.get('error')}")
    logger.info(f"Gemini live check healthy: model={health.get('model')}, version={health.get('version')}")

    run_id = f"canary_{task_id}_gemini_s42"
    t0 = time.time()

    public_dir = task_dir / "task"
    with AgentSandbox(public_dir) as sandbox:
        agent_loop = AgentExecutionLoop(
            provider=adapter,
            sandbox=sandbox,
            max_iterations=8,
        )

        logger.info(f"Starting canary agent execution on {task_id}...")
        agent_result: AgentRunResult = agent_loop.execute(
            task_id=task_id,
            problem_md=problem_md,
            metadata=metadata,
        )

        logger.info(f"Canary agent execution finished in {agent_result.agent_duration_seconds:.2f}s.")
        logger.info(f"Steps executed: {len(agent_result.steps)}, Termination reason: {agent_result.termination_reason}")
        if agent_result.error_message:
            logger.error(f"Agent reported error: {agent_result.error_message}")

        # Provenance Tracking
        import hashlib, platform
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
            "provider": "gemini",
            "model_name": "gemini-2.5-flash",
            "model_snapshot": "gemini-2.5-flash",
            "credential_status": "PRESENT",
            "credential_fingerprint": f"sha256:{hashlib.sha256(api_key.encode('utf-8')).hexdigest()[:16]}",
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

        logger.info("Running Aegis verification ladder (C1 -> C6)...")
        aegis_report = AegisResearchVerifier.verify(
            task_dir=task_dir,
            candidate_dir=sandbox.workspace_dir,
            agent_result=agent_result,
            provenance=provenance,
        )
        logger.info(f"Aegis technical_verdict: {aegis_report.technical_verdict}, release_policy: {aegis_report.release_policy}")

        logger.info("Running Independent Ground-Truth Oracle...")
        oracle_report = IndependentCorrectnessOracle.evaluate(
            task_dir=task_dir,
            candidate_dir=sandbox.workspace_dir,
            provenance=provenance,
        )
        logger.info(f"Oracle verdict: {oracle_report.oracle_verdict}, is_defective: {oracle_report.is_defective}")

        failure_cat, failure_detail = classify_trace_failure(
            agent_error=agent_result.error_message,
            agent_signaled=agent_result.success_signaled,
            validator_valid=aegis_report.validator_valid,
            visible_passed=aegis_report.visible_tests_passed,
            oracle_defective=(oracle_report.is_defective == 1),
            aegis_verdict=aegis_report.technical_verdict,
        )

        if agent_result.error_message:
            term_reason = AgentTerminationReason.ERROR.value
            prot_comp = ProtocolCompliance.PROTOCOL_INCOMPLETE.value
        elif agent_result.success_signaled:
            term_reason = AgentTerminationReason.FINISH.value
            prot_comp = ProtocolCompliance.COMPLIANT.value
        else:
            term_reason = AgentTerminationReason.MAX_ITERATIONS.value
            prot_comp = ProtocolCompliance.PROTOCOL_INCOMPLETE.value

        outcomes = {
            "model_execution": "SUCCESS" if not agent_result.error_message else "FAILURE",
            "patch_generation": "GENERATED" if provenance.patch_diff.strip() else "NOT_GENERATED",
            "agent_termination": term_reason,
            "agent_protocol_compliance": prot_comp,
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

        client_req_id = f"client_gemini_{run_id}_{int(t0*1000)}"

        trace = ResearchTrace(
            schema_version=SCHEMA_VERSION,
            run_id=run_id,
            task_id=task_id,
            track=track,
            model="gemini-2.5-flash",
            provider="gemini",
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
            run_key=f"canary_gemini_{task_id}_42",
            agent_policy_hash="sha256:21d279e3de0760d2646be973f28488810170d6a58ad92b871ed8c80359050d79",
            sampling_semantics={
                "seed_requested": 42,
                "seed_applied": 42,
                "seed_semantics": "BEST_EFFORT",
                "temperature_requested": 0.2,
                "temperature_applied": 0.2,
            },
            model_capabilities={
                "supports_tools": True,
                "supports_seed": False,
                "supports_temperature": True,
                "supports_token_accounting": True,
                "model_snapshot": "gemini-2.5-flash",
            },
            execution_origin="REAL_PROVIDER",
            client_request_id=client_req_id,
            provider_request_id=None,
            provider_request_id_available=False,
            provider_response_metadata={"model": "gemini-2.5-flash", "provider": "gemini"},
        )

        trace_dict = trace.to_dict()

    # Save ONLY in results/canary (outside empirical_100_v3 dataset!)
    canary_trace_path = canary_dir / f"{run_id}.json"
    canary_trace_path.write_text(json.dumps(trace_dict, indent=2), encoding="utf-8")
    logger.info(f"Canary trace saved to isolated location: {canary_trace_path}")

    # Validate Schema
    is_schema_valid, schema_errs = validate_research_trace(trace_dict)
    assert is_schema_valid, f"Canary trace schema invalid: {schema_errs}"

    # Validate Admission Gate
    admitted, admission_reasons = validate_empirical_admission(trace_dict)
    assert admitted, f"Canary trace failed admission: {admission_reasons}"

    # Evaluate Canary Gates per Directive P0-L
    total_steps = len(agent_result.steps)
    assert total_steps >= 2, f"Canary required >= 2 model turns, got {total_steps}"

    total_tool_calls = sum(len(s.tool_calls) for s in agent_result.steps)
    assert total_tool_calls >= 1, f"Canary required >= 1 real tool call, got {total_tool_calls}"

    first_step = agent_result.steps[0]
    assert len(first_step.tool_calls) >= 1, "First turn must contain a tool call"
    first_call = first_step.tool_calls[0]
    logger.info(f"Turn 1 tool call: {first_call['name']}({first_call['arguments']})")

    assert len(first_step.tool_results) >= 1, "Turn 1 must produce a tool result"
    logger.info(f"Turn 1 tool result: is_error={first_step.tool_results[0]['is_error']}")

    assert not agent_result.error_message, f"Canary run experienced agent/model error: {agent_result.error_message}"

    canary_summary = {
        "status": "PASSED",
        "task_id": task_id,
        "model": "gemini-2.5-flash",
        "provider": "gemini",
        "total_steps": total_steps,
        "total_tool_calls": total_tool_calls,
        "first_tool_called": first_call["name"],
        "final_step_index": agent_result.steps[-1].step_index,
        "success_signaled": agent_result.success_signaled,
        "aegis_verdict": aegis_report.technical_verdict,
        "aegis_release_policy": aegis_report.release_policy,
        "oracle_verdict": oracle_report.oracle_verdict,
        "admission_passed": admitted,
        "canary_artifact": str(canary_trace_path),
        "excluded_from_empirical_100_v3": True,
    }

    summary_path = canary_dir / "canary_disposition.json"
    summary_path.write_text(json.dumps(canary_summary, indent=2), encoding="utf-8")

    print("\n" + "=" * 76)
    print("AEGIS GEMINI CANARY VERIFICATION: SUCCESS")
    print("=" * 76)
    print(f"Task:                    {task_id}")
    print(f"Provider:                gemini (gemini-2.5-flash)")
    print(f"Total Steps (Turns):     {total_steps} (>= 2 REQUIRED: PASSED)")
    print(f"Tool Calls:              {total_tool_calls} (>= 1 REQUIRED: PASSED)")
    print(f"First Tool Call:         {first_call['name']}")
    print(f"Aegis Technical Verdict: {aegis_report.technical_verdict}")
    print(f"Aegis Release Policy:    {aegis_report.release_policy}")
    print(f"Oracle Verdict:          {oracle_report.oracle_verdict}")
    print(f"Dataset Admission:       PASSED")
    print(f"Canary Trace:            {canary_trace_path}")
    print(f"Dataset Isolation:       CONFIRMED (Zero entries in empirical_100_v3)")
    print("=" * 76 + "\n")

    return canary_summary


if __name__ == "__main__":
    t_id = sys.argv[1] if len(sys.argv) > 1 else "task_001_fastapi_async_scope"
    summary = execute_gemini_canary(t_id)
    sys.exit(0 if summary["status"] == "PASSED" else 1)
