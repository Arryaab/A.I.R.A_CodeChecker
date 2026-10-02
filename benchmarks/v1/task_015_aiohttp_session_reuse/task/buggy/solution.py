class ConnectionPool:
    def __init__(self, size=10):
        self.available = size
        self.size = size

    def acquire(self):
        if self.available <= 0:
            raise RuntimeError("Pool exhausted")
        self.available -= 1
        return "conn"

    def release(self):
        # BUG: no upper bound check permits available > size on double release
        self.available += 1
