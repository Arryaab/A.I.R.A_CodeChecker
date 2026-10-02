from solution import RunContext

def test_parent_run_id_propagated():
    ctx = RunContext(run_id="child_1", parent_id="parent_0")
    ctx.init_tags()
    assert ctx.tags.get("mlflow.parentRunId") == "parent_0"
