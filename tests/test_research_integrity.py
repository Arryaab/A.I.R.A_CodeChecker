from __future__ import annotations

import ast
import json
import tempfile
from pathlib import Path

import pytest

from aegis.research.benchmark.validator import validate_benchmark_task
from aegis.research.dataset.contract import (
    DatasetIntegrityViolation,
    DatasetKind,
    DatasetProvenanceContract,
)
from aegis.research.models.ollama import OllamaModelAdapter
from aegis.research.storage.experiment import ExperimentManifest, ExperimentStorage
from aegis.research.trace.schema import (
    AgentTerminationReason,
    FailureCategory,
    ProtocolCompliance,
    ResearchTrace,
    classify_trace_failure,
    validate_research_trace,
)


def test_oracle_zero_aegis_verification_imports():
    """Verify that aegis.research.oracle has ZERO imports of aegis.verification or release policy."""
    oracle_dir = Path("aegis/research/oracle").resolve()
    assert oracle_dir.exists(), f"Oracle directory {oracle_dir} not found"

    forbidden_modules = [
        "aegis.verification",
        "aegis.core",
        "aegis.release",
        "aegis.policy",
    ]
    forbidden_names = [
        "SecurityScanner",
        "ReleasePolicyEngine",
        "AegisCoreVerifier",
        "AegisResearchVerifier",
    ]

    for py_file in oracle_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for fmod in forbidden_modules:
                        assert not alias.name.startswith(fmod), (
                            f"Illegal circular import in {py_file.name}: imports '{alias.name}'"
                        )
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for fmod in forbidden_modules:
                    assert not mod.startswith(fmod), (
                        f"Illegal circular import in {py_file.name}: from '{mod}' import ..."
                    )
                for alias in node.names:
                    assert alias.name not in forbidden_names, (
                        f"Illegal circular import in {py_file.name}: imports symbol '{alias.name}'"
                    )


def test_empirical_dataset_ingestion_gate():
    """Verify that the dataset ingestion gate strictly rejects synthetic data for empirical analysis."""
    # Synthetic contract must be rejected
    synthetic_contract = DatasetProvenanceContract(
        dataset_type=DatasetKind.SYNTHETIC_VALIDATION.value,
        generator_version="1.0.0",
        created_at="2026-09-26T20:00:00Z",
        experiment_ids=["synthetic_validation_750"],
        contains_synthetic_labels=True,
        contains_real_model_execution=False,
    )

    with pytest.raises(DatasetIntegrityViolation) as exc_info:
        DatasetProvenanceContract.validate_for_empirical_analysis(synthetic_contract)
    assert "strictly" in str(exc_info.value).lower() or "synthetic" in str(exc_info.value).lower()

    # Real empirical contract must pass
    real_contract = DatasetProvenanceContract(
        dataset_type=DatasetKind.REAL_EMPIRICAL.value,
        generator_version="2.0.0",
        created_at="2026-09-27T08:00:00Z",
        experiment_ids=["pilot_real_v2"],
        contains_synthetic_labels=False,
        contains_real_model_execution=True,
    )
    assert DatasetProvenanceContract.validate_for_empirical_analysis(real_contract) is True


def test_completed_experiments_cannot_be_overwritten():
    """Verify that completed experiments and existing run traces cannot be overwritten."""
    with tempfile.TemporaryDirectory() as td:
        exp_dir = Path(td)
        manifest = ExperimentStorage.init_experiment(
            exp_dir=exp_dir,
            experiment_id="test_exp_immutability",
            tasks=["task_001"],
            model_configs=[{"name": "test_model", "model": "test", "provider": "ollama"}],
            seeds=[42],
        )

        manifest.status = "COMPLETED"
        manifest.completed_runs.append("run_task_001_test_model_s42")
        ExperimentStorage.save_manifest(manifest, exp_dir)

        # Attempting to re-init a completed experiment must raise PermissionError
        with pytest.raises(PermissionError):
            ExperimentStorage.init_experiment(
                exp_dir=exp_dir,
                experiment_id="test_exp_immutability",
                tasks=["task_001"],
                model_configs=[{"name": "test_model", "model": "test", "provider": "ollama"}],
                seeds=[42],
            )


def test_outcome_separation_protocol_incomplete_vs_agent_failure():
    """Verify separation of software correctness from agent protocol compliance."""
    # Case 1: Agent produced correct patch (visible pass, oracle pass) but did not call finish before iterations ended
    cat1, detail1 = classify_trace_failure(
        agent_error=None,
        agent_signaled=False,
        validator_valid=True,
        visible_passed=True,
        oracle_defective=False,
        aegis_verdict="CLEAN",
    )
    assert cat1 == FailureCategory.PROTOCOL_INCOMPLETE
    assert "exhausted iteration budget" in detail1

    # Case 2: Agent reached max iterations and code was NOT passing visible tests
    cat2, detail2 = classify_trace_failure(
        agent_error=None,
        agent_signaled=False,
        validator_valid=True,
        visible_passed=False,
        oracle_defective=True,
        aegis_verdict="INDETERMINATE",
    )
    assert cat2 == FailureCategory.AGENT_FAILURE

    # Case 3: Agent crashed with runtime/model error
    cat3, detail3 = classify_trace_failure(
        agent_error="Model context overflow",
        agent_signaled=False,
        validator_valid=False,
        visible_passed=False,
        oracle_defective=True,
        aegis_verdict="INDETERMINATE",
    )
    assert cat3 == FailureCategory.MODEL_FAILURE

    # Case 4: Success
    cat4, detail4 = classify_trace_failure(
        agent_error=None,
        agent_signaled=True,
        validator_valid=True,
        visible_passed=True,
        oracle_defective=False,
        aegis_verdict="CLEAN",
    )
    assert cat4 == FailureCategory.SUCCESS


def test_model_digest_and_version_pinning():
    """Verify that the Ollama adapter extracts model digest and server version."""
    adapter = OllamaModelAdapter(model_id="qwen2.5-coder:latest", endpoint="http://localhost:11434")
    # If Ollama server is running locally, digest and version should be populated
    if adapter.version is not None:
        assert len(adapter.version) > 0
        assert adapter.digest is not None
        assert len(adapter.digest) == 64 or "sha256" in adapter.digest
        meta = adapter.metadata()
        assert meta.extra_params["model_digest"] == adapter.digest
        assert meta.extra_params["server_version"] == adapter.version


def test_zero_root_level_synthetic_files():
    """Verify that root results directory contains zero legacy synthetic files."""
    results_dir = Path("results").resolve()
    assert results_dir.exists()

    legacy_synthetic_paths = [
        results_dir / "aegis_empirical_dataset_750.json",
        results_dir / "ablation_statistics_summary.json",
        results_dir / "mlverify_model_metrics.json",
    ]

    for p in legacy_synthetic_paths:
        assert not p.exists(), f"Contaminating synthetic file found in results root: {p}"

    # Synthetic files must be strictly quarantined under results/synthetic_validation/
    synth_dir = results_dir / "synthetic_validation"
    assert synth_dir.exists(), "results/synthetic_validation directory must exist"
    sanity_file = synth_dir / "synthetic_sanity_dataset_750.json"
    assert sanity_file.exists(), "Quarantined synthetic dataset must exist"


def test_benchmark_task_validator_on_tasks():
    """Verify automated task validator verifies baseline failure and reference patch success."""
    task_dir = Path("benchmarks/v1/task_001_fastapi_async_scope").resolve()
    res = validate_benchmark_task(task_dir)
    assert res.is_valid is True, f"Validation failed: {res.errors}"
    assert res.checks["files_present"] is True
    assert res.checks["evaluator_namespaces_separated"] is True
    assert res.checks["candidate_workspace_isolated"] is True
    assert res.checks["baseline_fails_public_tests"] is True
    assert res.checks["reference_patch_applies"] is True
    assert res.checks["reference_patch_passes_public_tests"] is True
    assert res.checks["reference_patch_passes_oracle_tests"] is True
    assert res.checks["reference_patch_passes_hidden_tests"] is True
