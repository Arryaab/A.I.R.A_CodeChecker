"""Aegis Research Platform: Empirical agent evaluation, telemetry, and verification analysis."""

from aegis.research.agent.loop import AgentExecutionLoop, AgentRunResult, AgentStepRecord
from aegis.research.features.pre_verification import (
    PRE_VERIFICATION_FEATURE_NAMES,
    PreVerificationFeatureExtractor,
    PreVerificationFeatures,
)
from aegis.research.oracle.evaluator import (
    IndependentCorrectnessOracle,
    OracleEvaluationResult,
)
from aegis.research.provenance.tracker import (
    AstSymbolDelta,
    ProvenanceRecord,
    ProvenanceTracker,
)
from aegis.research.sandbox.isolation import AgentSandbox, SandboxSecurityViolation
from aegis.research.storage.experiment import (
    ExperimentManifest,
    ExperimentStorage,
)
from aegis.research.trace.schema import (
    FailureCategory,
    ResearchTrace,
    SCHEMA_VERSION,
    classify_trace_failure,
    validate_research_trace,
)
from aegis.research.verifier.pipeline import (
    AegisResearchVerifier,
    AegisVerificationReport,
    VerificationTierResults,
)

__all__ = [
    "AgentExecutionLoop",
    "AgentRunResult",
    "AgentStepRecord",
    "AgentSandbox",
    "SandboxSecurityViolation",
    "ProvenanceTracker",
    "ProvenanceRecord",
    "AstSymbolDelta",
    "PreVerificationFeatureExtractor",
    "PreVerificationFeatures",
    "PRE_VERIFICATION_FEATURE_NAMES",
    "AegisResearchVerifier",
    "AegisVerificationReport",
    "VerificationTierResults",
    "IndependentCorrectnessOracle",
    "OracleEvaluationResult",
    "ResearchTrace",
    "SCHEMA_VERSION",
    "FailureCategory",
    "validate_research_trace",
    "classify_trace_failure",
    "ExperimentStorage",
    "ExperimentManifest",
]
