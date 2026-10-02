import pytest
from solution import Context

def test_oracle_happy_path_child_copies_data():
    parent = Context({"env": "prod"})
    child = parent.child()
    assert child.data == {"env": "prod"}
    assert child.data is not parent.data

def test_oracle_negative_child_mutation_isolated():
    parent = Context({"env": "prod"})
    child = parent.child()
    child.data["env"] = "staging"
    child.data["new"] = 123
    assert parent.data["env"] == "prod"
    assert "new" not in parent.data

def test_oracle_boundary_empty_parent():
    parent = Context()
    child = parent.child()
    child.data["k"] = "v"
    assert len(parent.data) == 0
