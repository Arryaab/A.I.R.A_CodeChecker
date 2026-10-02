class RunContext:
    def __init__(self, run_id: str, parent_id: str | None = None):
        self.run_id = run_id
        self.parent_id = parent_id
        self.tags = {}

    def init_tags(self):
        # BUG: forgets to set mlflow.parentRunId when parent_id is present
        self.tags["run_id"] = self.run_id
