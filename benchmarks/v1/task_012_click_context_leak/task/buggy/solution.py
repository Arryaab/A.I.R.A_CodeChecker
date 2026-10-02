class Context:
    def __init__(self, data=None):
        self.data = data or {}

    def child(self):
        # BUG: shares same reference instead of shallow copy
        return Context(self.data)
