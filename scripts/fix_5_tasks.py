import re
from pathlib import Path

p3 = Path("scripts/oracle_definitions_track3.py")
content3 = p3.read_text(encoding="utf-8")

old_47 = """def test_oracle_boundary_root_run_no_parent():
    ctx = RunContext(run_id="root_0", parent_id=None)
    ctx.init_tags()
    assert "mlflow.parentRunId" not in ctx.tags
    assert ctx.tags["run_id"] == "root_0"
'''"""

new_47 = """def test_oracle_boundary_root_run_no_parent():
    ctx = RunContext(run_id="root_0", parent_id=None)
    ctx.init_tags()
    assert "mlflow.parentRunId" not in ctx.tags
    assert ctx.tags["run_id"] == "root_0"

def test_oracle_boundary_empty_string_parent():
    ctx = RunContext(run_id="child_empty", parent_id="")
    ctx.init_tags()
    assert "mlflow.parentRunId" not in ctx.tags
    assert ctx.tags["run_id"] == "child_empty"
'''"""

if old_47 in content3:
    content3 = content3.replace(old_47, new_47)
    p3.write_text(content3, encoding="utf-8")
    print("Task 047 updated successfully in track3!")
else:
    # Try normalizing newlines
    c_norm = content3.replace("\r\n", "\n")
    if old_47 in c_norm:
        c_norm = c_norm.replace(old_47, new_47)
        p3.write_text(c_norm, encoding="utf-8")
        print("Task 047 updated with newline normalization!")
    else:
        print("Could not find old_47 in track3")
