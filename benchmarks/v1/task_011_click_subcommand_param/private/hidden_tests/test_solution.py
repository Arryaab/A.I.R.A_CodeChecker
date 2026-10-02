import pytest
from solution import CLIContext, CommandGroup

def test_unknown_subcommand_raises():
    grp = CommandGroup()
    ctx = CLIContext()
    with pytest.raises(ValueError):
        grp.invoke(ctx, "missing")
