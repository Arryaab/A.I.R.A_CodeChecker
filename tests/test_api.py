from unittest.mock import patch
from fastapi.testclient import TestClient
from aegis.api.service import app

client = TestClient(app)
AUTH_HEADERS = {"X-API-Key": "test-key-12345"}

def test_api_health():
    res = client.get("/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["service"] == "aegis-verifier"
    assert data["version"] == "1.0.0"
    assert "docker_available" in data

def test_api_auth_required():
    # Requests without API key are rejected with 401 Unauthorized
    res = client.post("/v1/verifications", json={"repository": "."})
    assert res.status_code == 401
    assert "Authentication required" in res.json().get("detail", "")

def test_api_reject_path_traversal():
    with patch("aegis.api.service.is_docker_available", return_value=True):
        res = client.post(
            "/v1/verifications",
            json={"repository": "../../etc/shadow"},
            headers=AUTH_HEADERS
        )
        assert res.status_code == 400
        assert "strictly prohibited" in res.json().get("detail", "")

def test_api_mandatory_sandbox_rejection():
    # If Docker daemon is unavailable, API rejects with 503 Service Unavailable
    with patch("aegis.api.service.is_docker_available", return_value=False):
        res = client.post(
            "/v1/verifications",
            json={"repository": "."},
            headers=AUTH_HEADERS
        )
        assert res.status_code == 503
        assert "Mandatory sandbox requirement failed" in res.json().get("detail", "")

def test_create_and_get_verification_status():
    payload = {
        "repository": ".",
        "base": "HEAD~1",
        "head": "HEAD",
        "tier": "fast"
    }
    with patch("aegis.api.service.is_docker_available", return_value=True):
        res = client.post("/v1/verifications", json=payload, headers=AUTH_HEADERS)
        assert res.status_code == 202
        data = res.json()
        assert "run_id" in data
        assert data["status"] == "queued"
        assert data["tier"] == "FAST"

        run_id = data["run_id"]
        status_res = client.get(f"/v1/verifications/{run_id}", headers=AUTH_HEADERS)
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["run_id"] == run_id
        assert status_data["status"] in ("queued", "running", "completed", "failed")

        events_res = client.get(f"/v1/verifications/{run_id}/events", headers=AUTH_HEADERS)
        assert events_res.status_code == 200
        events_data = events_res.json()
        assert isinstance(events_data, list)
        assert len(events_data) > 0

def test_get_nonexistent_run_404():
    res = client.get("/v1/verifications/run_does_not_exist_99999", headers=AUTH_HEADERS)
    assert res.status_code == 404
