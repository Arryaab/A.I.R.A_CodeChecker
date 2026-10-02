import pytest
from solution import RunContext

def test_oracle_happy_path_parent_run_id_propagated():
    ctx = RunContext(run_id="child_1", parent_id="parent_0")
    ctx.init_tags()
    assert ctx.tags.get("mlflow.parentRunId") == "parent_0"
    assert ctx.tags.get("run_id") == "child_1"

def test_oracle_boundary_root_run_no_parent():
    ctx = RunContext(run_id="root_0", parent_id=None)
    ctx.init_tags()
    assert "mlflow.parentRunId" not in ctx.tags
    assert ctx.tags["run_id"] == "root_0"

def test_oracle_boundary_empty_string_parent():
    ctx = RunContext(run_id="child_empty", parent_id="")
    ctx.init_tags()
    assert "mlflow.parentRunId" not in ctx.tags
    assert ctx.tags["run_id"] == "child_empty"
