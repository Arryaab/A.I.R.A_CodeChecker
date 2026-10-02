class CLIContext:
    def __init__(self, verbose=False):
        self.verbose = verbose

class CommandGroup:
    def __init__(self):
        self.subcommands = {}

    def add(self, name, handler):
        self.subcommands[name] = handler

    def invoke(self, ctx: CLIContext, cmd_name: str, *args):
        # BUG: invokes handler without passing the CLIContext
        if cmd_name in self.subcommands:
            return self.subcommands[cmd_name](*args)
        raise ValueError(f"Unknown command {cmd_name}")
