from __future__ import annotations

import enum
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class ProtocolCompliance(str, enum.Enum):
    COMPLIANT = "COMPLIANT"
    PROTOCOL_INCOMPLETE = "PROTOCOL_INCOMPLETE"


class AgentTerminationReason(str, enum.Enum):
    FINISH = "FINISH"
    MAX_ITERATIONS = "MAX_ITERATIONS"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    ABORT = "ABORT"


class FailureCategory(str, enum.Enum):
    SUCCESS = "SUCCESS"
    MODEL_FAILURE = "MODEL_FAILURE"
    LOCAL_PROVIDER_UNAVAILABLE = "LOCAL_PROVIDER_UNAVAILABLE"
    LOCAL_PROVIDER_TIMEOUT = "LOCAL_PROVIDER_TIMEOUT"
    WORKER_CRASH = "WORKER_CRASH"
    WORKER_ISOLATION_FAILURE = "WORKER_ISOLATION_FAILURE"
    SANDBOX_FAILURE = "SANDBOX_FAILURE"
    TRACE_CORRUPTION = "TRACE_CORRUPTION"
    ORACLE_FAILURE = "ORACLE_FAILURE"
    AEGIS_VERIFICATION_FAILURE = "AEGIS_VERIFICATION_FAILURE"
    DATASET_ADMISSION_FAILURE = "DATASET_ADMISSION_FAILURE"
    AGENT_FAILURE = "AGENT_FAILURE"
    PROTOCOL_INCOMPLETE = "PROTOCOL_INCOMPLETE"
    ENVIRONMENT_FAILURE = "ENVIRONMENT_FAILURE"
    AEGIS_FAILURE = "AEGIS_FAILURE"
    TIMEOUT = "TIMEOUT"
    RESOURCE_EXHAUSTION = "RESOURCE_EXHAUSTION"
    INVALID_PATCH = "INVALID_PATCH"


class TraceLifecycleState(str, enum.Enum):
    """Explicit Research Trace Lifecycle States (Directive Section 13)."""
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    VERIFICATION = "VERIFICATION"
    ORACLE = "ORACLE"
    FINALIZING = "FINALIZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INVALID = "INVALID"


class SeedSemantics(str, enum.Enum):
    """Explicit Seed Semantics (Directive Section 10)."""
    DETERMINISTIC = "DETERMINISTIC"
    PSEUDO_DETERMINISTIC = "PSEUDO_DETERMINISTIC"
    BEST_EFFORT = "BEST_EFFORT"
    UNSUPPORTED = "UNSUPPORTED"


class AegisTechnicalVerdict(str, enum.Enum):
    """Canonical Aegis Core 1.0 Technical Verdicts (Directive P0-F)."""
    QUALIFIED = "QUALIFIED"
    QUALIFIED_WITHIN_SCOPE = "QUALIFIED_WITHIN_SCOPE"
    FAILED = "FAILED"
    INDETERMINATE = "INDETERMINATE"


class AegisReleasePolicy(str, enum.Enum):
    """Canonical Aegis Core 1.0 Release Policies (Directive P0-F)."""
    AUTO_APPROVE = "AUTO_APPROVE"
    REVIEW = "REVIEW"
    BLOCK = "BLOCK"


SCHEMA_VERSION = "1.0.0"

REQUIRED_TOP_LEVEL_KEYS = {
    "schema_version",
    "run_id",
    "task_id",
    "track",
    "model",
    "provider",
    "seed",
    "temperature",
    "timestamp",
    "provenance",
    "pre_verification_features",
    "pre_features_vector",
    "post_verification_signals",
    "agent_execution",
    "aegis_verification",
    "oracle_evaluation",
    "targets",
    "accepted",
    "failure_classification",
}


@dataclass
class ResearchTrace:
    schema_version: str
    run_id: str
    task_id: str
    track: str
    model: str
    provider: str
    seed: int
    temperature: float
    timestamp: str
    provenance: Dict[str, Any]
    pre_verification_features: Dict[str, Any]
    pre_features_vector: List[float]
    post_verification_signals: Dict[str, Any]
    agent_execution: Dict[str, Any]
    aegis_verification: Dict[str, Any]
    oracle_evaluation: Dict[str, Any]
    targets: Dict[str, int]
    accepted: Dict[str, int]
    failure_classification: Dict[str, str]
    outcomes: Optional[Dict[str, Any]] = None
    lifecycle_state: str = TraceLifecycleState.COMPLETED.value
    run_key: Optional[str] = None
    agent_policy_hash: Optional[str] = None
    sampling_semantics: Optional[Dict[str, Any]] = None
    model_capabilities: Optional[Dict[str, Any]] = None
    execution_origin: str = "REAL_PROVIDER"
    client_request_id: Optional[str] = None
    provider_request_id: Optional[str] = None
    provider_request_id_available: bool = False
    provider_response_metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def validate_research_trace(trace: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validates that a trace dictionary strictly conforms to Research Trace Schema 1.0."""
    errors = []

    # Check top-level keys
    missing_keys = REQUIRED_TOP_LEVEL_KEYS - set(trace.keys())
    if missing_keys:
        errors.append(f"Missing required top-level keys: {sorted(list(missing_keys))}")

    # Version check
    if trace.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"Invalid schema_version: expected {SCHEMA_VERSION}, got {trace.get('schema_version')}")

    # Pre-verification feature vector check (must have exactly 19 elements)
    pre_vec = trace.get("pre_features_vector")
    if not isinstance(pre_vec, list) or len(pre_vec) != 19:
        errors.append(f"pre_features_vector must be a list of exactly 19 floats, got {len(pre_vec) if isinstance(pre_vec, list) else type(pre_vec)}")

    # Targets check
    targets = trace.get("targets", {})
    for t_key in ("regression", "security", "overfitting", "performance", "is_defective"):
        if t_key not in targets or targets[t_key] not in (0, 1):
            errors.append(f"targets['{t_key}'] must be binary (0 or 1), got {targets.get(t_key)}")

    # Accepted configurations check
    accepted = trace.get("accepted", {})
    for a_key in ("C1_agent_only", "C2_visible_tests", "C3_hidden_tests", "C4_regression", "C5_mutation", "C6_full_aegis"):
        if a_key not in accepted or accepted[a_key] not in (0, 1):
            errors.append(f"accepted['{a_key}'] must be binary (0 or 1), got {accepted.get(a_key)}")

    # Failure category check
    fc = trace.get("failure_classification", {})
    cat = fc.get("category")
    valid_cats = {f.value for f in FailureCategory}
    if cat not in valid_cats:
        errors.append(f"Invalid failure category: {cat}, expected one of {sorted(list(valid_cats))}")

    # Provenance checks
    prov = trace.get("provenance", {})
    for p_key in ("base_snapshot_sha256", "head_snapshot_sha256", "patch_sha256", "patch_diff"):
        if p_key not in prov:
            errors.append(f"Missing provenance key: {p_key}")

    # Aegis verification check (Directive P0-F)
    aegis_verif = trace.get("aegis_verification")
    if isinstance(aegis_verif, dict):
        tech_v = aegis_verif.get("technical_verdict")
        if tech_v is not None:
            valid_tech = {v.value for v in AegisTechnicalVerdict}
            if tech_v in ("PASSED", "ERROR"):
                errors.append(f"Obsolete aegis technical_verdict rejected: '{tech_v}'. Use canonical: {sorted(list(valid_tech))}")
            elif tech_v not in valid_tech:
                errors.append(f"Invalid aegis technical_verdict: '{tech_v}', expected one of {sorted(list(valid_tech))}")
        rel_p = aegis_verif.get("release_policy")
        if rel_p is not None:
            valid_rel = {p.value for p in AegisReleasePolicy}
            if rel_p == "RELEASE":
                errors.append(f"Obsolete aegis release_policy rejected: '{rel_p}'. Use canonical: {sorted(list(valid_rel))}")
            elif rel_p not in valid_rel:
                errors.append(f"Invalid aegis release_policy: '{rel_p}', expected one of {sorted(list(valid_rel))}")

    # Outcomes check (if present, validate structure)
    outcomes = trace.get("outcomes")
    if outcomes is not None:
        if not isinstance(outcomes, dict):
            errors.append("outcomes must be a dictionary")
        else:
            required_outcome_keys = {
                "model_execution",
                "patch_generation",
                "agent_termination",
                "agent_protocol_compliance",
                "patch_valid",
                "oracle_correctness",
                "aegis_verification",
                "release_policy",
            }
            missing_outcomes = required_outcome_keys - set(outcomes.keys())
            if missing_outcomes:
                errors.append(f"Missing outcome keys: {sorted(list(missing_outcomes))}")

    # Lifecycle state check (if present)
    if "lifecycle_state" in trace:
        state = trace["lifecycle_state"]
        valid_states = {s.value for s in TraceLifecycleState}
        if state not in valid_states:
            errors.append(f"Invalid lifecycle_state: '{state}'. Expected one of {sorted(list(valid_states))}")

    return len(errors) == 0, errors


def classify_trace_failure(
    agent_error: Optional[str],
    agent_signaled: bool,
    validator_valid: bool,
    visible_passed: bool,
    oracle_defective: bool,
    aegis_verdict: str,
) -> Tuple[FailureCategory, str]:
    """Taxonomize the outcome of a research run."""
    if agent_error:
        err_lower = agent_error.lower()
        if "local_provider_unavailable" in err_lower or "provider unavailable" in err_lower or "connection refused" in err_lower:
            return FailureCategory.LOCAL_PROVIDER_UNAVAILABLE, agent_error
        elif "local_provider_timeout" in err_lower or "provider timeout" in err_lower:
            return FailureCategory.LOCAL_PROVIDER_TIMEOUT, agent_error
        elif "worker_crash" in err_lower or "worker crash" in err_lower:
            return FailureCategory.WORKER_CRASH, agent_error
        elif "isolation" in err_lower or "cleanliness" in err_lower:
            return FailureCategory.WORKER_ISOLATION_FAILURE, agent_error
        elif "sandbox" in err_lower or "security" in err_lower or "path traversal" in err_lower:
            return FailureCategory.SANDBOX_FAILURE, agent_error
        elif "corruption" in err_lower or "corrupt" in err_lower:
            return FailureCategory.TRACE_CORRUPTION, agent_error
        elif "admission" in err_lower:
            return FailureCategory.DATASET_ADMISSION_FAILURE, agent_error
        elif "timeout" in err_lower:
            return FailureCategory.TIMEOUT, agent_error
        elif "model" in err_lower:
            return FailureCategory.MODEL_FAILURE, agent_error
        else:
            return FailureCategory.AGENT_FAILURE, agent_error

    if not validator_valid:
        return FailureCategory.INVALID_PATCH, "Patch failed static code validation"

    if not agent_signaled:
        # Software correctness separated from protocol compliance:
        # If candidate code is valid, passes visible tests, and oracle passes (not defective),
        # failure is solely protocol compliance (budget exhausted without finish),
        # NEVER a software defect!
        if visible_passed and not oracle_defective:
            return (
                FailureCategory.PROTOCOL_INCOMPLETE,
                "Agent generated correct patch but exhausted iteration budget before signaling finish",
            )
        return FailureCategory.AGENT_FAILURE, "Agent reached max iterations without signaling finish"

    if not visible_passed:
        return FailureCategory.AGENT_FAILURE, "Agent failed to solve visible tests"

    if oracle_defective:
        return FailureCategory.ORACLE_FAILURE, "Agent solution introduced defect caught by oracle"

    return FailureCategory.SUCCESS, "Clean verification pass"
