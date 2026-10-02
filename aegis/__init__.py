"""Aegis-Lite: LLM-based, test-guided Python program repair."""

from __future__ import annotations

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from aegis.execution.runner import TestResult, run_tests
from aegis.config import AegisConfig, load_config
from aegis.verification.validator import ValidationResult, validate_python, validate_patch  
from aegis.verification.taxonomy import FailureType, FailureRecord, classify_failure
from aegis.llm import LLMProvider, LLMResponse, GeminiProvider, MockProvider
from aegis.patcher import PatchResult, copy_project, parse_llm_patch, apply_patch
from aegis.core.orchestrator import RepairAttempt, RepairResult, repair_bug
from aegis.evals.benchmark import BenchmarkBug, Benchmark
from aegis.evals.evaluation import EvaluationMetrics, EvaluationReport, evaluate_benchmark

__version__ = "0.1.0"
