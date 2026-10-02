import pytest
from solution import CLIContext, CommandGroup

def test_oracle_happy_path_context_passed():
    grp = CommandGroup()
    grp.add("status", lambda ctx: f"verbose={ctx.verbose}")
    ctx = CLIContext(verbose=True)
    assert grp.invoke(ctx, "status") == "verbose=True"

def test_oracle_happy_path_with_extra_args():
    grp = CommandGroup()
    grp.add("echo", lambda ctx, msg: f"[{ctx.verbose}] {msg}")
    ctx = CLIContext(verbose=False)
    assert grp.invoke(ctx, "echo", "hello") == "[False] hello"

def test_oracle_negative_unknown_subcommand_raises():
    grp = CommandGroup()
    ctx = CLIContext()
    with pytest.raises(ValueError, match="Unknown command nonexistent"):
        grp.invoke(ctx, "nonexistent")
