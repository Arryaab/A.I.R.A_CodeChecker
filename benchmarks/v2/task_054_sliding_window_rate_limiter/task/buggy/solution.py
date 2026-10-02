from collections import deque
from typing import Dict

class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: float):
        if max_requests <= 0 or window_seconds <= 0:
            raise ValueError("Parameters must be positive")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.clients: Dict[str, deque] = {}

    def allow_request(self, client_id: str, timestamp: float) -> bool:
        if client_id not in self.clients:
            self.clients[client_id] = deque()
        queue = self.clients[client_id]

        cutoff = timestamp - self.window_seconds
        # BUG: Uses <= instead of <, purging events that occurred exactly at window boundary
        while queue and queue[0] <= cutoff:
            queue.popleft()

        if len(queue) < self.max_requests:
            queue.append(timestamp)
            return True
        return False
