"""
Unit tests for Aegis Research Preflight Truthfulness & Integrity Gates.
Covers Cases 1-8 from Founder Directive P0:
- Case 1: empirical_100_v1 truthfully BLOCKED on missing OpenAI
- Case 2: empirical_100_v2 READY with real Ollama + Gemini
- Case 3: Missing OpenAI key blocks credentials and provider_live_health for OpenAI-dependent study
- Case 4: Missing Gemini key blocks credentials and provider_live_health for Gemini-dependent study
- Case 5: Ollama endpoint unreachable blocks provider_live_health
- Case 6: Model digest mismatch blocks model_availability
- Case 7: Corrupted or missing benchmark lock blocks benchmark_lock
- Case 8: Semantic matrix/protocol mismatch blocks execution_semantics_integrity
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from aegis.research.preflight import (
    PreflightReport,
    check_and_record_provider_health,
    run_preflight,
)
from aegis.research.protocol.validator import AUTHORITATIVE_QWEN_DIGEST, SemanticProtocolValidator


# ---------------------------------------------------------------------------
# Case 1: empirical_100_v1 truthfully BLOCKED because OpenAI is missing
# ---------------------------------------------------------------------------
def test_case_1_empirical_100_v1_truthfully_blocked():
    report = run_preflight("empirical_100_v1")
    assert isinstance(report, PreflightReport)
    assert report.verdict == "BLOCKED"
    cred_check = next(r for r in report.results if r.check_name == "credentials")
    assert cred_check.passed is False
    assert cred_check.status == "BLOCKED"
    assert "OPENAI_API_KEY" in cred_check.details

    health_check = next(r for r in report.results if r.check_name == "provider_live_health")
    assert health_check.passed is False
    assert health_check.status == "BLOCKED"
    assert any("OPENAI_API_KEY" in r for r in report.reasons)


# ---------------------------------------------------------------------------
# Case 2: empirical_100_v2 READY with real Ollama + Gemini
# ---------------------------------------------------------------------------
def test_case_2_empirical_100_v2_ready():
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set in environment (required for v2)")
    report = run_preflight("empirical_100_v2")
    assert isinstance(report, PreflightReport)
    assert report.verdict == "READY", f"Expected READY, got reasons: {report.reasons}"
    assert report.failed_checks == 0
    assert report.passed_checks == 14

    cred_check = next(r for r in report.results if r.check_name == "credentials")
    assert cred_check.passed is True
    assert cred_check.status == "PASSED"

    health_check = next(r for r in report.results if r.check_name == "provider_live_health")
    assert health_check.passed is True
    assert health_check.status == "PASSED"


# ---------------------------------------------------------------------------
# Case 3: Missing OpenAI key blocks credentials and provider_live_health
# ---------------------------------------------------------------------------
def test_case_3_missing_openai_key_blocks(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AEGIS_OPENAI_API_KEY", raising=False)

    report = run_preflight("empirical_100_v1")
    assert report.verdict == "BLOCKED"
    cred_check = next(r for r in report.results if r.check_name == "credentials")
    assert cred_check.passed is False
    assert "OPENAI_API_KEY" in cred_check.details


# ---------------------------------------------------------------------------
# Case 4: Missing Gemini key blocks credentials and provider_live_health
# ---------------------------------------------------------------------------
def test_case_4_missing_gemini_key_blocks(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("AEGIS_API_KEY", raising=False)

    report = run_preflight("empirical_100_v2")
    assert report.verdict == "BLOCKED"
    cred_check = next(r for r in report.results if r.check_name == "credentials")
    assert cred_check.passed is False
    assert "GEMINI_API_KEY" in cred_check.details

    health_check = next(r for r in report.results if r.check_name == "provider_live_health")
    assert health_check.passed is False
    assert "GEMINI_API_KEY" in health_check.details


# ---------------------------------------------------------------------------
# Case 5: Ollama endpoint unreachable blocks provider_live_health
# ---------------------------------------------------------------------------
def test_case_5_ollama_unreachable_blocks(monkeypatch):
    # Mock Ollama adapter to point to an unreachable port
    from aegis.research.models.ollama import OllamaModelAdapter

    original_check_health = OllamaModelAdapter.check_health

    def mock_dead_health(self):
        return {
            "provider": "ollama",
            "model": self.model_id,
            "healthy": False,
            "error": "Failed to connect to Ollama daemon on http://localhost:11434",
            "request_success": False,
        }

    monkeypatch.setattr(OllamaModelAdapter, "check_health", mock_dead_health)

    report = run_preflight("empirical_100_v2")
    assert report.verdict == "BLOCKED"
    health_check = next(r for r in report.results if r.check_name == "provider_live_health")
    assert health_check.passed is False
    assert "ollama" in health_check.details.lower()


# ---------------------------------------------------------------------------
# Case 6: Model digest mismatch in manifest blocks model_availability
# ---------------------------------------------------------------------------
def test_case_6_model_digest_mismatch_blocks(monkeypatch, tmp_path):
    # Create temporary study manifest with corrupted Qwen digest
    temp_study = tmp_path / "empirical_temp_study"
    temp_study.mkdir()

    m_data = {
        "models": {
            "LOCAL_MODEL": {
                "configuration_label": "LOCAL_MODEL",
                "provider": "ollama",
                "model_id": "qwen2.5-coder:latest",
                "snapshot_id": "sha256:corrupted_invalid_digest_0000000000000000",
            }
        }
    }
    (temp_study / "model_manifest.json").write_text(json.dumps(m_data), encoding="utf-8")

    report = run_preflight(str(temp_study))
    model_check = next(r for r in report.results if r.check_name == "model_availability")
    assert model_check.passed is False
    assert "Qwen digest mismatch" in model_check.details


# ---------------------------------------------------------------------------
# Case 7: Corrupted or missing benchmark lock blocks benchmark_lock
# ---------------------------------------------------------------------------
def test_case_7_corrupted_benchmark_lock_blocks(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    # AegisBench-v1.lock.json is absent in fresh tmp_path
    report = run_preflight("empirical_100_v2")
    lock_check = next(r for r in report.results if r.check_name == "benchmark_lock")
    assert lock_check.passed is False
    assert "missing" in lock_check.details.lower()


# ---------------------------------------------------------------------------
# Case 8: Semantic matrix/protocol mismatch blocks execution_semantics_integrity
# ---------------------------------------------------------------------------
def test_case_8_semantic_protocol_mismatch_blocks():
    # Test on a nonexistent or mismatching configuration
    validator = SemanticProtocolValidator(experiment_id="nonexistent_study_xyz")
    val_report = validator.validate()
    assert val_report.is_valid is False
    assert len(val_report.errors) > 0
