from unittest.mock import patch
from fastapi.testclient import TestClient
from aegis.api.service import app

client = TestClient(app)

def test_public_health_endpoints():
    for endpoint in ["/health", "/api/health"]:
        res = client.get(endpoint)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert data["service"] == "aira-release-assurance"
        assert data["product"] == "A.I.R.A."
        assert data["version"] == "1.0.0"
        assert "demo_mode" in data
        assert "docker_available" in data

def test_demo_scenarios_listing():
    res = client.get("/api/demo/scenarios")
    assert res.status_code == 200
    scenarios = res.json()
    assert isinstance(scenarios, list)
    assert len(scenarios) == 5

    ids = [s["id"] for s in scenarios]
    assert "demo_01_clean_pass" in ids
    assert "demo_02_hidden_overfit" in ids
    assert "demo_03_path_traversal" in ids
    assert "demo_04_regression_break" in ids
    assert "demo_05_mutation_survivor" in ids

def test_get_individual_scenario():
    res = client.get("/api/demo/scenarios/demo_01_clean_pass")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "demo_01_clean_pass"
    assert data["technical_verdict"] == "QUALIFIED"
    assert data["release_policy"] == "AUTO_APPROVE"
    assert "criteria" in data
    assert "events" in data

    # 404 for invalid scenario
    bad_res = client.get("/api/demo/scenarios/invalid_non_existent")
    assert bad_res.status_code == 404

def test_trigger_demo_verification():
    payload = {"scenario_id": "demo_03_path_traversal"}
    res = client.post("/api/demo/verify", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "run_id" in data
    assert data["status"] == "completed"
    assert data["technical_verdict"] == "REJECTED"
    assert data["release_policy"] == "BLOCK"
    assert "report" in data

    run_id = data["run_id"]
    # Check status endpoint
    st_res = client.get(f"/api/verifications/{run_id}")
    assert st_res.status_code == 200
    assert st_res.json()["run_id"] == run_id

    # Check events endpoint
    ev_res = client.get(f"/api/verifications/{run_id}/events")
    assert ev_res.status_code == 200
    assert len(ev_res.json()) > 0

    # Check evidence report endpoint
    rep_res = client.get(f"/api/verifications/{run_id}/evidence")
    assert rep_res.status_code == 200
    rep_data = rep_res.json()
    assert rep_data["decision"]["release_policy"] == "BLOCK"
    assert rep_data["criteria"]["C6_security"]["status"] == "FAIL"

def test_list_verifications():
    res = client.get("/api/verifications")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 5  # Seeded with demo scenarios

def test_oversized_diff_rejection():
    # Diff larger than 1MB
    large_diff = "A" * (1024 * 1024 + 10)
    res = client.post("/api/verifications", json={"diff": large_diff}, headers={"X-API-Key": "test-key"})
    assert res.status_code == 413
    assert "exceeds maximum allowed size" in res.json()["detail"]

def test_public_verification_fails_closed_without_sandbox():
    sample_diff = """--- a/calc.py\n+++ b/calc.py\n@@ -1,2 +1,2 @@\n-def add(a, b): return a\n+def add(a, b): return a + b\n"""
    with patch("aegis.api.service.is_docker_available", return_value=False):
        res = client.post("/api/verifications", json={"diff": sample_diff, "tier": "fast"}, headers={"X-API-Key": "test-key"})
        # Real verification without sandbox must return 503 — NEVER fabricate results
        assert res.status_code == 503
        assert "isolated execution sandbox" in res.json()["detail"]

def test_mlverify_research_endpoint():
    res = client.get("/api/research/mlverify")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SHADOW_MODE_ONLY"
    assert data["defect_prediction"]["status"] == "RESEARCH_SUPPORTED"
    assert data["defect_prediction"]["metrics"]["pr_auc"] == 0.9367
    assert data["methodological_boundaries"]["autonomous_routing"] == "REJECTED (Routing cannot be claimed as production-certified without larger empirical campaign)"

def test_web_static_and_root_spa():
    # Test root endpoint returns HTML
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "A.I.R.A." in res_root.text
    assert "<title>A.I.R.A. — AI Release Assurance</title>" in res_root.text

    # Test static assets are served
    res_css = client.get("/static/styles.css")
    assert res_css.status_code == 200
    assert "aira-canvas" in res_css.text

    res_js = client.get("/static/app.js")
    assert res_js.status_code == 200
    assert "A.I.R.A." in res_js.text
