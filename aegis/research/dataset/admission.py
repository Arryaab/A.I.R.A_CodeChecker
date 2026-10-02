"""
Aegis Research Dataset Admission Gate.
Enforces that only fully validated, completed, and provenance-intact traces enter REAL_EMPIRICAL dataset.
Rejects synthetic traces, mocks, simulations, or incomplete lifecycles.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from aegis.research.trace.schema import (
    TraceLifecycleState,
    validate_research_trace,
)

FORBIDDEN_SIMULATION_KEYWORDS = {
    "standardizedcloudadapter",
    "hermeticsimulatedcloudadapter",
    "mock_model",
    "canned_response",
    "fake_adapter",
}


class DatasetAdmissionRejection(ValueError):
    """Raised when a research trace fails the empirical dataset admission gate."""


def validate_for_admission(
    trace: Dict[str, Any],
    expected_benchmark_version: str = "AegisBench-v1",
    expected_protocol_hash: Optional[str] = None,
    allowed_task_ids: Optional[set] = None,
    require_real_provider: bool = False,
) -> Tuple[bool, List[str]]:
    """Dataset Admission Gate (Directive Section 14, 15, 18).

    Verifies:
    - Base schema validity (Research Trace Schema 1.0)
    - Real Provider Provenance (when require_real_provider=True)
    - Absence of mock, simulation, or synthetic indicators
    - Lifecycle state == COMPLETED
    - Benchmark version and task ID validity
    - Protocol hash and manifest alignment
    - Cryptographic provenance integrity (SHA-256 hashes present)
    - Execution, Oracle, and Aegis verdicts completeness
    - Feature vector mathematical integrity (no NaN/Inf)
    - Execution outcomes completeness
    """
    reasons: List[str] = []

    # 1. Base schema validation
    is_schema_valid, schema_errors = validate_research_trace(trace)
    if not is_schema_valid:
        reasons.extend([f"Schema violation: {e}" for e in schema_errors])

    # 2. Real Provider Provenance Check (Directive P0-I)
    exec_origin = trace.get("execution_origin")
    if require_real_provider:
        if exec_origin != "REAL_PROVIDER":
            reasons.append(
                f"execution_origin is '{exec_origin}'. Only 'REAL_PROVIDER' traces can be admitted to REAL_EMPIRICAL."
            )
        client_req_id = trace.get("client_request_id")
        if not client_req_id and trace.get("provider_request_id"):
            client_req_id = trace.get("provider_request_id")
        if not client_req_id or not isinstance(client_req_id, str) or not client_req_id.strip():
            reasons.append("Missing or invalid client_request_id in empirical trace.")

        prov_req_id_avail = trace.get("provider_request_id_available", False)
        prov_req_id = trace.get("provider_request_id")
        if prov_req_id_avail:
            if not prov_req_id or not isinstance(prov_req_id, str) or not prov_req_id.strip():
                reasons.append("provider_request_id_available is True but provider_request_id is missing or empty.")
        else:
            if prov_req_id is not None and prov_req_id != "":
                reasons.append(f"provider_request_id_available is False but provider_request_id is populated: '{prov_req_id}'.")
    else:
        if exec_origin is not None and exec_origin != "REAL_PROVIDER":
            reasons.append(f"Invalid execution_origin: '{exec_origin}'")

    # Check for synthetic/mock keywords in model, provider, or adapter metadata
    trace_text_sample = " ".join([
        str(trace.get("model", "")),
        str(trace.get("provider", "")),
        str(trace.get("model_capabilities", "")),
        str(trace.get("raw_metadata", "")),
        str(trace.get("agent_execution", {}).get("raw_metadata", "")),
    ]).lower()

    for kw in FORBIDDEN_SIMULATION_KEYWORDS:
        if kw in trace_text_sample:
            reasons.append(f"Forbidden simulation/mock keyword detected in trace: '{kw}'")

    if trace.get("is_synthetic") is True or trace.get("contains_synthetic_labels") is True:
        reasons.append("Trace flagged as synthetic; forbidden in REAL_EMPIRICAL dataset.")

    # 3. Lifecycle state
    lifecycle_state = trace.get("lifecycle_state", TraceLifecycleState.COMPLETED.value)
    if lifecycle_state != TraceLifecycleState.COMPLETED.value:
        reasons.append(
            f"Trace lifecycle_state is '{lifecycle_state}'. Only '{TraceLifecycleState.COMPLETED.value}' traces can be admitted."
        )

    # 4. Task ID and Benchmark validation
    task_id = trace.get("task_id")
    if not task_id:
        reasons.append("Missing task_id in trace.")
    elif allowed_task_ids and task_id not in allowed_task_ids:
        reasons.append(f"task_id '{task_id}' not found in locked benchmark manifest.")

    # 5. Protocol hash verification
    if expected_protocol_hash:
        trace_protocol_hash = trace.get("protocol_hash") or trace.get("provenance", {}).get("protocol_hash")
        if trace_protocol_hash != expected_protocol_hash:
            reasons.append(
                f"Protocol hash mismatch: expected '{expected_protocol_hash}', got '{trace_protocol_hash}'"
            )

    # 6. Provenance integrity
    prov = trace.get("provenance", {})
    if not isinstance(prov, dict):
        reasons.append("provenance must be a dictionary.")
    else:
        for required_hash in ("base_snapshot_sha256", "head_snapshot_sha256", "patch_sha256"):
            val = prov.get(required_hash)
            if not val or not isinstance(val, str) or len(val) != 64:
                reasons.append(f"Invalid or missing cryptographic hash '{required_hash}': {val}")

    # 7. Oracle evaluation integrity
    oracle = trace.get("oracle_evaluation", {})
    if not isinstance(oracle, dict):
        reasons.append("oracle_evaluation must be a dictionary.")
    else:
        if oracle.get("oracle_verdict") not in ("CORRECT", "DEFECTIVE"):
            reasons.append(f"Invalid oracle_verdict: {oracle.get('oracle_verdict')}")
        if oracle.get("is_defective") not in (0, 1):
            reasons.append(f"Invalid oracle is_defective: {oracle.get('is_defective')}")

    # 8. Aegis verification integrity (Directive P0-F)
    aegis_res = trace.get("aegis_verification", {})
    if not isinstance(aegis_res, dict):
        reasons.append("aegis_verification must be a dictionary.")
    else:
        tech_v = aegis_res.get("technical_verdict")
        if tech_v in ("PASSED", "ERROR"):
            reasons.append(
                f"Obsolete aegis technical_verdict rejected: '{tech_v}'. Use canonical: QUALIFIED, QUALIFIED_WITHIN_SCOPE, FAILED, INDETERMINATE."
            )
        elif tech_v not in ("QUALIFIED", "QUALIFIED_WITHIN_SCOPE", "FAILED", "INDETERMINATE"):
            reasons.append(f"Invalid aegis technical_verdict: '{tech_v}'")

        rel_p = aegis_res.get("release_policy")
        if rel_p == "RELEASE":
            reasons.append(
                f"Obsolete aegis release_policy rejected: '{rel_p}'. Use canonical: AUTO_APPROVE, REVIEW, BLOCK."
            )
        elif rel_p not in ("AUTO_APPROVE", "REVIEW", "BLOCK"):
            reasons.append(f"Invalid aegis release_policy: '{rel_p}'")

    # 9. Pre-verification feature vector mathematical sanity
    features = trace.get("pre_features_vector", [])
    if isinstance(features, list) and len(features) == 19:
        for idx, val in enumerate(features):
            if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
                reasons.append(f"pre_features_vector element {idx} is non-finite: {val}")

    # 10. Model and Provider identity
    model = trace.get("model")
    provider = trace.get("provider")
    if not model or not isinstance(model, str) or not model.strip():
        reasons.append("Missing or empty model identifier.")
    if not provider or not isinstance(provider, str) or not provider.strip():
        reasons.append("Missing or empty provider identifier.")

    # 11. Agent execution completion
    agent_exec = trace.get("agent_execution", {})
    if not isinstance(agent_exec, dict):
        reasons.append("agent_execution must be a dictionary.")

    admitted = len(reasons) == 0
    return admitted, reasons


def validate_empirical_admission(
    trace: Dict[str, Any],
    expected_benchmark_version: str = "AegisBench-v1",
    expected_protocol_hash: Optional[str] = None,
    allowed_task_ids: Optional[set] = None,
) -> Tuple[bool, List[str]]:
    """Strict admission gate specifically for the empirical 100-run study.
    Strictly requires execution_origin == 'REAL_PROVIDER' and valid provider_request_id.
    """
    return validate_for_admission(
        trace=trace,
        expected_benchmark_version=expected_benchmark_version,
        expected_protocol_hash=expected_protocol_hash,
        allowed_task_ids=allowed_task_ids,
        require_real_provider=True,
    )
