import pytest
import sys
from pathlib import Path
import json

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
