import pytest
import sys
from pathlib import Path
import json

flask = pytest.importorskip("flask")

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aegis_editor import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_index(client):
    rv = client.get("/")
    assert rv.status_code == 200
    assert b"Aegis-Lite Editor" in rv.data
    assert b"id=\"codeEditor\"" in rv.data

def test_check_valid_code(client):
    rv = client.post("/api/check", json={"code": "x = 1\ny = 2"})
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["valid"] is True
    assert len(data["errors"]) == 0

def test_check_invalid_code(client):
    rv = client.post("/api/check", json={"code": "def func(:\n    pass"})
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["valid"] is False
    assert len(data["errors"]) > 0
    assert data["errors"][0]["type"] == "SyntaxError"
    assert data["errors"][0]["line"] == 1

def test_run_valid_code(client):
    rv = client.post("/api/run", json={"code": "print('hello aegis')"})
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["exit_code"] == 0
    assert "hello aegis" in data["output"]
    assert len(data["errors"]) == 0

def test_run_runtime_error(client):
    rv = client.post("/api/run", json={"code": "x = 1 / 0"})
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["exit_code"] != 0
    assert len(data["errors"]) > 0
    assert data["errors"][0]["type"] == "ZeroDivisionError"
    assert data["errors"][0]["line"] == 1

def test_research_console(client):
    rv = client.get("/research")
    assert rv.status_code == 200
    assert b"AEGIS RESEARCH CONSOLE" in rv.data
    assert b"Overfitting Phenomenon" in rv.data
    assert b"C1_agent_only" in rv.data

def test_research_metrics_api(client):
    rv = client.get("/api/research/metrics")
    assert rv.status_code == 200
    data = rv.get_json()
    assert "ablation" in data
    assert "mlverify" in data
    assert "real_pilot" in data
    assert data["real_pilot"]["status"] in ("COMPLETED", "IN_PROGRESS")
    assert len(data["real_pilot"]["runs"]) == 20

def test_research_run_trace_api(client):
    rv = client.get("/api/research/metrics")
    runs = rv.get_json()["real_pilot"]["runs"]
    assert len(runs) > 0
    first_run_id = runs[0]["run_id"]

    trace_rv = client.get(f"/api/research/run/{first_run_id}")
    assert trace_rv.status_code == 200
    trace_data = trace_rv.get_json()
    assert trace_data["run_id"] == first_run_id
    assert "provenance" in trace_data
    assert "agent_execution" in trace_data
    assert "aegis_verification" in trace_data
    assert "oracle_evaluation" in trace_data
