class ChunkStreamReader:
    def __init__(self, chunks, timeout_s=1.0):
        self.chunks = chunks
        self.timeout_s = timeout_s
        self.buffer = []

    def read_all(self, time_limit: float):
        self.buffer = []
        total_time = 0.0
        for data, delay in self.chunks:
            total_time += delay
            # BUG: appends data before checking timeout limit
            self.buffer.append(data)
            if total_time > time_limit:
                raise TimeoutError("Read timeout exceeded")
        return b"".join(self.buffer)
