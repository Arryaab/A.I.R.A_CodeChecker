class InferencePipeline:
    def __init__(self):
        self.buffer = []

    def predict(self, texts: list[str]) -> list[str]:
        # BUG: fails to clear self.buffer before processing texts
        for t in texts:
            self.buffer.append(f"pred({t})")
        return list(self.buffer)
