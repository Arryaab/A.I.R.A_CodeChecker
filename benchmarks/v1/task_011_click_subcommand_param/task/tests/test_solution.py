from solution import CLIContext, CommandGroup

def status_handler(ctx):
    return f"verbose={ctx.verbose}"

def test_context_passed_to_subcommand():
    grp = CommandGroup()
    grp.add("status", status_handler)
    ctx = CLIContext(verbose=True)
    assert grp.invoke(ctx, "status") == "verbose=True"
