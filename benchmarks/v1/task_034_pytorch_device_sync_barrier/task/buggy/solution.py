class StreamManager:
    def __init__(self):
        self.pending_tasks = []

    def record_event(self, task_name):
        self.pending_tasks.append(task_name)

    def synchronize(self):
        # BUG: forgets to clear pending tasks on barrier completion
        pass

    def is_idle(self) -> bool:
        return len(self.pending_tasks) == 0
