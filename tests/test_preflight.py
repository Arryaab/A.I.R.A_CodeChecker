"""
Unit tests for Aegis Research Pre-Flight Command.
Directive Section 28 & 29 and Founder Directive P0.
"""

from pathlib import Path
import os
import tempfile
import pytest

from aegis.research.preflight import run_preflight, PreflightReport


def test_preflight_empirical_100_v2_ready():
    """Verify that empirical_100_v2 passes pre-flight when credentials exist."""
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set in environment (required for v2)")
    report = run_preflight("empirical_100_v2")
    assert isinstance(report, PreflightReport)
    assert report.verdict == "READY", f"empirical_100_v2 should be READY, got reasons: {report.reasons}"
    assert report.failed_checks == 0
    assert report.passed_checks == 14
    assert len(report.reasons) == 0


def test_preflight_empirical_100_v3_ready():
    """Verify that empirical_100_v3 passes pre-flight when credentials exist."""
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set in environment (required for v3)")
    report = run_preflight("empirical_100_v3")
    assert isinstance(report, PreflightReport)
    assert report.verdict == "READY", f"empirical_100_v3 should be READY, got reasons: {report.reasons}"
    assert report.failed_checks == 0
    assert report.passed_checks == 14
    assert len(report.reasons) == 0


def test_preflight_empirical_100_v1_truthfully_blocked():
    """Verify that empirical_100_v1 truthfully blocks because OpenAI credentials are required but missing."""
    report = run_preflight("empirical_100_v1")
    assert isinstance(report, PreflightReport)
    assert report.verdict == "BLOCKED"
    assert report.failed_checks > 0
    assert any("OPENAI_API_KEY" in r for r in report.reasons)


def test_preflight_blocks_on_nonexistent_manifest():
    """Verify that a nonexistent manifest is BLOCKED with explicit reasons."""
    report = run_preflight("nonexistent_experiment_manifest_xyz")
    assert report.verdict == "BLOCKED"
    assert report.failed_checks > 0
    assert any("manifest" in r.lower() for r in report.reasons)
