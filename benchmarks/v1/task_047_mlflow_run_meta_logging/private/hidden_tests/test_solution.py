from solution import RunContext

def test_root_run_has_no_parent():
    ctx = RunContext(run_id="root")
    ctx.init_tags()
    assert "mlflow.parentRunId" not in ctx.tags
