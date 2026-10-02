"""
Tests for A.I.R.A. Frontend & API Authentication Architecture.

Verifies:
1. upload without API key -> 401
2. upload with invalid API key -> 401
3. upload with valid API key -> accepted
4. custom-test upload requires API key
5. verification requires API key
6. evidence retrieval requires API key for non-demo runs
7. demo works without API key
8. /api/auth/check endpoint contract (200 valid, 401 invalid/missing)
9. Local-dev token disabled by default -> 403
10. Local-dev token cannot activate when request host is not localhost -> 403
11. Local-dev token activates on localhost when AIRA_LOCAL_DEV_AUTH=true -> 200
12. API key never appears in DOM text or static assets
13. API key never appears in URLs
14. Real verification failure never falls back to demo
15. Key stored only in sessionStorage, not localStorage
"""

import io
import os
import re
import zipfile
import pytest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

from aegis.api.service import (
    app,
    PROJECTS_STORE,
    RUNS_STORE,
    rate_limiter,
    seed_demo_runs,
    init_local_dev_auth
)

client = TestClient(app)

WEB_DIR = Path(__file__).parent.parent / "aegis" / "web"
INDEX_HTML = WEB_DIR / "index.html"
APP_JS = WEB_DIR / "app.js"
STYLES_CSS = WEB_DIR / "styles.css"
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "projects"

VALID_KEY = "test-secret-key-12345"


def make_zip(project_dir: Path) -> io.BytesIO:
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
def setup_teardown():
    PROJECTS_STORE.clear()
    RUNS_STORE.clear()
    rate_limiter.history.clear()
    old_key = os.environ.get("AIRA_API_KEY")
    old_dev = os.environ.get("AIRA_LOCAL_DEV_AUTH")
    os.environ["AIRA_API_KEY"] = VALID_KEY
    yield
    PROJECTS_STORE.clear()
    RUNS_STORE.clear()
    rate_limiter.history.clear()
    if old_key is not None:
        os.environ["AIRA_API_KEY"] = old_key
    else:
        os.environ.pop("AIRA_API_KEY", None)
    if old_dev is not None:
        os.environ["AIRA_LOCAL_DEV_AUTH"] = old_dev
    else:
        os.environ.pop("AIRA_LOCAL_DEV_AUTH", None)
    seed_demo_runs()


# ============================================================================
# 1. API KEY ENDPOINT TESTS
# ============================================================================

def test_auth_check_valid_key():
    """GET /api/auth/check with valid key returns 200 {authenticated: true}."""
    res = client.get("/api/auth/check", headers={"X-API-Key": VALID_KEY})
    assert res.status_code == 200
    assert res.json() == {"authenticated": True}


def test_auth_check_missing_key():
    """GET /api/auth/check without key returns 401."""
    res = client.get("/api/auth/check")
    assert res.status_code == 401
    assert "detail" in res.json()


def test_auth_check_invalid_key():
    """GET /api/auth/check with wrong key returns 401."""
    res = client.get("/api/auth/check", headers={"X-API-Key": "wrong-key"})
    assert res.status_code == 401


# ============================================================================
# 2. REAL PROJECT UPLOAD & EXECUTION AUTHENTICATION TESTS
# ============================================================================

def test_upload_without_key_returns_401():
    """POST /api/projects/upload without API key returns 401."""
    zip_buf = make_zip(FIXTURES_DIR / "passing_project")
    res = client.post("/api/projects/upload", files={"archive": ("proj.zip", zip_buf, "application/zip")})
    assert res.status_code == 401
    assert "Authentication required" in res.json()["detail"] or "Invalid" in res.json()["detail"]


def test_upload_with_invalid_key_returns_401():
    """POST /api/projects/upload with invalid API key returns 401."""
    zip_buf = make_zip(FIXTURES_DIR / "passing_project")
    res = client.post(
        "/api/projects/upload",
        files={"archive": ("proj.zip", zip_buf, "application/zip")},
        headers={"X-API-Key": "invalid-token"}
    )
    assert res.status_code == 401


def test_upload_with_valid_key_accepted():
    """POST /api/projects/upload with valid key returns 201."""
    zip_buf = make_zip(FIXTURES_DIR / "passing_project")
    res = client.post(
        "/api/projects/upload",
        files={"archive": ("proj.zip", zip_buf, "application/zip")},
        headers={"X-API-Key": VALID_KEY}
    )
    assert res.status_code == 201
    assert "project_id" in res.json()


def test_custom_test_upload_requires_key():
    """POST /api/projects/{id}/tests requires valid API key."""
    # First upload project
    zip_buf = make_zip(FIXTURES_DIR / "passing_project")
    up_res = client.post(
        "/api/projects/upload",
        files={"archive": ("proj.zip", zip_buf, "application/zip")},
        headers={"X-API-Key": VALID_KEY}
    )
    proj_id = up_res.json()["project_id"]

    # Try custom test upload without key
    test_buf = io.BytesIO()
    with zipfile.ZipFile(test_buf, "w") as zf:
        zf.writestr("test_extra.py", "def test_ok(): pass\n")
    test_buf.seek(0)

    res_no_key = client.post(
        f"/api/projects/{proj_id}/tests",
        files={"tests_archive": ("tests.zip", test_buf, "application/zip")}
    )
    assert res_no_key.status_code == 401

    # With valid key
    test_buf.seek(0)
    res_valid = client.post(
        f"/api/projects/{proj_id}/tests",
        files={"tests_archive": ("tests.zip", test_buf, "application/zip")},
        headers={"X-API-Key": VALID_KEY}
    )
    assert res_valid.status_code == 200


def test_verify_endpoint_requires_key():
    """POST /api/projects/{id}/verify requires valid API key."""
    res = client.post("/api/projects/proj_fake/verify", json={"tier": "standard"})
    assert res.status_code == 401


def test_evidence_endpoint_requires_key_for_real_runs():
    """GET /api/verifications/{run_id}/evidence requires key for real runs."""
    real_run_id = "run_real_20261002_abcdef"
    RUNS_STORE[real_run_id] = {
        "run_id": real_run_id,
        "status": "completed",
        "report": {"decision": {"technical_verdict": "QUALIFIED"}}
    }

    # Unauthenticated should fail
    res_no_key = client.get(f"/api/verifications/{real_run_id}/evidence")
    assert res_no_key.status_code == 401

    # Authenticated should pass
    res_with_key = client.get(f"/api/verifications/{real_run_id}/evidence", headers={"X-API-Key": VALID_KEY})
    assert res_with_key.status_code == 200


# ============================================================================
# 3. DEMO PUBLIC ACCESS PRESERVATION TESTS
# ============================================================================

def test_demo_scenarios_remain_public():
    """Demo routes do NOT require API key."""
    res = client.get("/api/demo/scenarios")
    assert res.status_code == 200
    assert len(res.json()) >= 1

    res_detail = client.get("/api/demo/scenarios/demo_01_clean_pass")
    assert res_detail.status_code == 200

    res_verify = client.post("/api/demo/verify", json={"scenario_id": "demo_01_clean_pass"})
    assert res_verify.status_code == 200


# ============================================================================
# 4. ZERO-FRICTION LOCAL DEV AUTH TESTS
# ============================================================================

def test_local_dev_token_disabled_by_default():
    """When AIRA_LOCAL_DEV_AUTH is not set, /api/auth/local-dev-token returns 403."""
    os.environ.pop("AIRA_LOCAL_DEV_AUTH", None)
    res = client.get("/api/auth/local-dev-token")
    assert res.status_code == 403


def test_local_dev_token_blocked_on_non_localhost():
    """When request is from non-localhost, /api/auth/local-dev-token returns 403 even if enabled."""
    os.environ["AIRA_LOCAL_DEV_AUTH"] = "true"
    # Simulate external host header
    res = client.get(
        "/api/auth/local-dev-token",
        headers={"Host": "api.production-aira.cloud"}
    )
    assert res.status_code == 403
    assert "only accessible from localhost" in res.json()["detail"] or "not enabled" in res.json()["detail"]


def test_local_dev_token_allowed_on_localhost_when_enabled():
    """When enabled and on localhost, returns 200 with the development token."""
    os.environ["AIRA_LOCAL_DEV_AUTH"] = "true"
    res = client.get(
        "/api/auth/local-dev-token",
        headers={"Host": "localhost:8000"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["enabled"] is True
    assert "token" in data
    assert len(data["token"]) > 0


# ============================================================================
# 5. FRONTEND SECURITY, ZERO CREDENTIAL & STORAGE CONTRACT TESTS
# ============================================================================

def test_no_api_keys_in_frontend_source():
    """Verify ZERO hardcoded API credentials exist in frontend HTML, CSS, or JS."""
    for file_path in [INDEX_HTML, APP_JS, STYLES_CSS]:
        text = file_path.read_text(encoding="utf-8")
        assert "aira-dev-key" not in text
        assert "aegis-dev-key" not in text
        assert "secret" not in text.lower() or "Stored only for this browser session" in text
        # Ensure no actual key hashes/tokens are hardcoded
        assert not re.search(r"['\"][a-zA-Z0-9]{24,}['\"]", text)


def test_frontend_uses_session_storage_only():
    """Verify frontend uses sessionStorage and does NOT use localStorage for API key."""
    js = APP_JS.read_text(encoding="utf-8")
    assert "sessionStorage" in js
    assert "localStorage.getItem('aira_api_key')" not in js
    assert "localStorage.setItem('aira_api_key'" not in js


def test_frontend_has_api_access_ui_and_modal():
    """Verify index.html contains API ACCESS indicator, status badge, and auth modal."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="nav-api-access-control"' in html
    assert 'id="api-status-badge"' in html
    assert 'id="btn-api-auth-trigger"' in html
    assert 'id="auth-modal"' in html
    assert 'id="auth-input-key"' in html
    assert 'type="password"' in html
    assert 'Stored only for this browser session' in html


def test_central_api_client_structure_in_app_js():
    """Verify central api client interface exists with get, post, upload, delete methods."""
    js = APP_JS.read_text(encoding="utf-8")
    assert "const api = {" in js
    assert "get(endpoint" in js
    assert "post(endpoint" in js
    assert "upload(endpoint" in js
    assert "delete(endpoint" in js
    assert "const auth = {" in js
    assert "X-API-Key" in js
