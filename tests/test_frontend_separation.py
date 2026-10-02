"""
Tests for A.I.R.A. Frontend Separation between Real Verification and Explore Demo.
Verifies:
1. Strict mode and view separation between Verify My Code and Explore Demo.
2. Index.html has no pre-populated fake values or misleading claims.
3. Pre-recorded demo is explicitly marked as PRE-RECORDED DEMO and DEMO TRACE.
4. "Safe for Automated Release" is removed from headlines.
5. Real verification results strictly originate from backend API responses.
6. /verify and /demo routes correctly serve SPA index.html.
"""

import io
import os
import re
import zipfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from aegis.api.service import app, PROJECTS_STORE, RUNS_STORE, rate_limiter, seed_demo_runs
from aegis.uploads.models import ProjectVerifyRequest, StageStatus
from aegis.execution.runner import TestResult
from aegis.execution.sandbox import SandboxResult

AUTH_HEADERS = {"X-API-Key": "test-key"}
client = TestClient(app)

WEB_DIR = Path(__file__).parent.parent / "aegis" / "web"
INDEX_HTML = WEB_DIR / "index.html"
APP_JS = WEB_DIR / "app.js"
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "projects"


def make_zip(project_dir: Path) -> io.BytesIO:
    """Create in-memory zip archive from fixture directory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for f in files:
                full_path = Path(root) / f
                arc_name = full_path.relative_to(project_dir)
                zf.write(full_path, arc_name)
    buf.seek(0)
    return buf


@pytest.fixture(autouse=True)
def reset_stores():
    """Clear in-memory stores and rate limiter before and after tests."""
    PROJECTS_STORE.clear()
    RUNS_STORE.clear()
    rate_limiter.history.clear()
    yield
    PROJECTS_STORE.clear()
    RUNS_STORE.clear()
    rate_limiter.history.clear()
    seed_demo_runs()



# ============================================================================
# 1. Route Serving & SPA Mount Tests
# ============================================================================

def test_spa_routes_serve_index_html():
    """Verify that /, /verify, and /demo all serve index.html with 200 OK."""
    res_home = client.get("/")
    assert res_home.status_code == 200
    assert "A.I.R.A. — AI Release Assurance" in res_home.text

    res_verify = client.get("/verify")
    assert res_verify.status_code == 200
    assert "A.I.R.A. — AI Release Assurance" in res_verify.text

    res_demo = client.get("/demo")
    assert res_demo.status_code == 200
    assert "A.I.R.A. — AI Release Assurance" in res_demo.text


# ============================================================================
# 2. Navigation Distinctness Tests
# ============================================================================

def test_navigation_has_distinct_verify_and_demo_links():
    """Verify top navigation differentiates Verify Code and Demo."""
    html = INDEX_HTML.read_text(encoding="utf-8")

    # Primary nav links
    assert 'href="#verify"' in html
    assert 'href="#demo"' in html
    assert 'id="nav-link-verify"' in html
    assert 'id="nav-link-demo"' in html

    # Action buttons
    assert 'id="nav-btn-verify"' in html
    assert 'id="nav-btn-demo"' in html


# ============================================================================
# 3. Hero Section Honesty Tests
# ============================================================================

def test_hero_section_no_fake_results_or_duplicate_demo():
    """Hero section must not display fake durations or duplicate demo workbenches."""
    html = INDEX_HTML.read_text(encoding="utf-8")

    hero_match = re.search(r'<section class="hero-section">([\s\S]*?)</section>', html)
    assert hero_match is not None, "Hero section not found"
    hero_content = hero_match.group(1)

    # Must NOT have fake duration or fake approval
    assert "EXECUTION TIME: 1,420 ms" not in hero_content
    assert "1,420 ms" not in hero_content
    assert "Safe for Automated Release" not in hero_content
    assert "Token Bucket Rate Limiter" not in hero_content
    assert "services/rate_limiter.py" not in hero_content


# ============================================================================
# 4. Real Verification Workflow Isolation Tests
# ============================================================================

def test_verify_workflow_contains_no_demo_scenario_data():
    """#verify section markup must not contain hardcoded demo data."""
    html = INDEX_HTML.read_text(encoding="utf-8")

    verify_match = re.search(r'<section class="verify-section[^>]*" id="verify">([\s\S]*?)</section>', html)
    assert verify_match is not None, "Verify section not found"
    verify_content = verify_match.group(1)

    # Must not contain demo scenario IDs or names
    assert "demo_01_clean_pass" not in verify_content
    assert "demo_02_hidden_overfit" not in verify_content
    assert "demo_03_path_traversal" not in verify_content
    assert "demo_04_regression_break" not in verify_content
    assert "demo_05_mutation_survivor" not in verify_content
    assert "Token Bucket Rate Limiter" not in verify_content
    assert "1,420 ms" not in verify_content
    assert "Safe for Automated Release" not in verify_content

    # Step 5 must contain honest project summary fields with initial placeholders
    assert 'id="res-project-id"' in verify_content
    assert 'id="res-framework"' in verify_content
    assert 'id="res-project-tests"' in verify_content
    assert 'id="res-custom-tests"' in verify_content
    assert 'id="res-project-hash"' in verify_content
    assert 'id="verify-verdict-reason"' in verify_content
    assert 'id="btn-inspect-evidence-real"' in verify_content


# ============================================================================
# 5. Demo Section Marking & Honesty Tests
# ============================================================================

def test_demo_section_is_unambiguously_prerecorded():
    """#demo section must be prominently labeled as pre-recorded."""
    html = INDEX_HTML.read_text(encoding="utf-8")

    demo_match = re.search(r'<section class="interactive-demo-section[^>]*" id="demo">([\s\S]*?)</section>', html)
    assert demo_match is not None, "Demo section not found"
    demo_content = demo_match.group(1)

    # Title and badge
    assert "EXPLORE THE A.I.R.A. DEMO" in demo_content
    assert "PRE-RECORDED DEMO" in demo_content
    assert "DEMO TRACE" in demo_content

    # No fake approval claims
    assert "Safe for Automated Release" not in demo_content
    assert "1,420 ms" not in demo_content

    # Initial state should be neutral
    assert 'id="demo-badge-C1">—' in demo_content
    assert 'id="demo-badge-C2">—' in demo_content


# ============================================================================
# 6. Separation Divider Exists Between Workflows
# ============================================================================

def test_separation_divider_present():
    """Separation divider must exist between real verification and explore demo."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="flow-isolation-divider"' in html
    assert "PRE-RECORDED DEMOS BELOW" in html or "END OF REAL VERIFICATION WORKFLOW" in html


# ============================================================================
# 7. JavaScript Mode Isolation and State Machine Tests
# ============================================================================

def test_app_js_implements_mode_isolation_and_router():
    """app.js must implement setAppMode, initRouter, and state clearing."""
    js = APP_JS.read_text(encoding="utf-8")

    assert "function setAppMode" in js
    assert "function initRouter" in js
    assert "function clearDemoState" in js
    assert "clearRealVerificationState" in js

    # initializeApp must call initRouter, NOT renderScenario unconditionally
    init_match = re.search(r'async function initializeApp\(\)\s*\{([\s\S]*?)\}', js)
    assert init_match is not None
    init_body = init_match.group(1)
    assert "initRouter()" in init_body
    assert "renderScenario(" not in init_body

    # None of the DOMAIN_SCENARIOS should have Safe for Automated Release
    assert "Safe for Automated Release" not in js


# ============================================================================
# 8. Real Backend Verification Data Integrity Tests
# ============================================================================

@patch("aegis.api.service.is_docker_available", return_value=True)
@patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-sandbox:latest")
@patch("aegis.execution.sandbox.run_tests_sandboxed")
def test_real_verification_results_have_zero_demo_pollution(mock_sandbox, mock_build_img, mock_docker):
    """Real verification run produce evidence without any demo traces."""
    mock_sandbox.return_value = SandboxResult(
        test_result=TestResult(
            passed=True,
            exit_code=0,
            stdout="==== 6 passed in 1.12s ====",
            stderr="",
            duration_seconds=1.12,
            tests_passed=6,
            tests_failed=0,
            tests_error=0,
            summary_line="6 passed",
            failure_messages=[]
        ),
        used_sandbox=True
    )

    passing_proj_dir = FIXTURES_DIR / "passing_project"
    zip_buf = make_zip(passing_proj_dir)

    upload_res = client.post(
        "/api/projects/upload",
        files={"archive": ("calculator.zip", zip_buf, "application/zip")},
        headers=AUTH_HEADERS
    )
    assert upload_res.status_code == 201
    proj_id = upload_res.json()["project_id"]

    verify_res = client.post(
        f"/api/projects/{proj_id}/verify",
        json={"tier": "standard", "run_project_tests": True, "run_security": True},
        headers=AUTH_HEADERS
    )
    assert verify_res.status_code == 202
    run_id = verify_res.json()["run_id"]

    run_status = client.get(f"/api/verifications/{run_id}", headers=AUTH_HEADERS)
    assert run_status.status_code == 200
    data = run_status.json()

    assert data["status"] == "completed"
    assert data["technical_verdict"] == "QUALIFIED"
    assert data["release_policy"] == "AUTO_APPROVE"

    evidence = data["report"]["evidence"]
    assert evidence["project_id"] == proj_id
    assert evidence["framework"] == "pytest"
    assert evidence["project_test_inventory"]["passed"] == 6
    assert evidence["custom_test_inventory"]["status"] == "NOT_AVAILABLE"

    # Confirm ZERO demo contamination in evidence
    evidence_str = str(evidence)
    assert "demo_01_clean_pass" not in evidence_str
    assert "Token Bucket Rate Limiter" not in evidence_str
    assert "services/rate_limiter.py" not in evidence_str
    assert "1420" not in evidence_str


@patch("aegis.api.service.is_docker_available", return_value=True)
@patch("aegis.execution.environment.build_sandbox_environment_image", return_value="aegis-sandbox:latest")
@patch("aegis.execution.sandbox.run_tests_sandboxed")
def test_real_verification_results_for_failing_project(mock_sandbox, mock_build_img, mock_docker):
    """Failing test project must produce honest REJECTED verdict with failure detail."""
    mock_sandbox.return_value = SandboxResult(
        test_result=TestResult(
            passed=False,
            exit_code=1,
            stdout="1 failed, 3 passed in 0.85s",
            stderr="",
            duration_seconds=0.85,
            tests_passed=3,
            tests_failed=1,
            tests_error=0,
            summary_line="1 failed, 3 passed",
            failure_messages=["AssertionError: assert count_vowels('umbrella') == 3"]
        ),
        used_sandbox=True
    )

    failing_proj_dir = FIXTURES_DIR / "failing_test_project"
    zip_buf = make_zip(failing_proj_dir)

    upload_res = client.post(
        "/api/projects/upload",
        files={"archive": ("failing.zip", zip_buf, "application/zip")},
        headers=AUTH_HEADERS
    )
    assert upload_res.status_code == 201
    proj_id = upload_res.json()["project_id"]

    verify_res = client.post(
        f"/api/projects/{proj_id}/verify",
        json={"tier": "standard", "run_project_tests": True, "run_security": True},
        headers=AUTH_HEADERS
    )
    assert verify_res.status_code == 202
    run_id = verify_res.json()["run_id"]

    run_status = client.get(f"/api/verifications/{run_id}", headers=AUTH_HEADERS)
    assert run_status.status_code == 200
    data = run_status.json()

    assert data["status"] == "completed"
    assert data["technical_verdict"] == "REJECTED"
    assert data["release_policy"] == "BLOCK"

    criteria = data["report"]["criteria"]
    assert criteria["C2_visible_tests"]["status"] == "FAIL"
    assert "1 failed" in criteria["C2_visible_tests"]["detail"]

    evidence = data["report"]["evidence"]
    assert evidence["project_test_inventory"]["failed"] == 1
    assert evidence["project_test_inventory"]["passed"] == 3


def test_styles_css_contains_isolation_and_badges():
    """styles.css must style separation divider and pre-recorded badges."""
    css = (WEB_DIR / "styles.css").read_text(encoding="utf-8")
    assert ".flow-isolation-divider" in css
    assert ".demo-prerecorded-badge" in css
    assert ".demo-trace-tag" in css
    assert ".project-summary-card" in css
    assert ".verdict-reason-text" in css
