from fastapi.testclient import TestClient
from aegis.api.service import app

client = TestClient(app)

def test_api_health():
    res = client.get("/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["service"] == "aegis-verifier"
    assert data["version"] == "1.0.0"
    assert "docker_available" in data

def test_create_and_get_verification_status():
    payload = {
        "repository": ".",
        "base": "HEAD~1",
        "head": "HEAD",
        "tier": "fast",
        "unsafe_local": True
    }
    res = client.post("/v1/verifications", json=payload)
    assert res.status_code == 202
    data = res.json()
    assert "run_id" in data
    assert data["status"] == "queued"
    assert data["tier"] == "FAST"

    run_id = data["run_id"]
    status_res = client.get(f"/v1/verifications/{run_id}")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["run_id"] == run_id
    assert status_data["status"] in ("queued", "running", "completed")

    events_res = client.get(f"/v1/verifications/{run_id}/events")
    assert events_res.status_code == 200
    events_data = events_res.json()
    assert "events" in events_data
    assert len(events_data["events"]) > 0

def test_get_nonexistent_run_404():
    res = client.get("/v1/verifications/run_does_not_exist_99999")
    assert res.status_code == 404
