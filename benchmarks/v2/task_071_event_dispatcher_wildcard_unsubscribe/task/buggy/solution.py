from collections import defaultdict
from typing import Callable, Dict, List

class EventDispatcher:
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = defaultdict(list)

    def subscribe(self, event_name: str, callback: Callable) -> None:
        self._listeners[event_name].append(callback)

    def unsubscribe(self, event_name: str, callback: Callable) -> None:
        # BUG: Clears all listeners for event_name or crashes if callback missing
        if event_name in self._listeners:
            self._listeners[event_name].clear()

    def dispatch(self, event_name: str, payload: dict) -> None:
        for cb in list(self._listeners.get(event_name, [])):
            cb(payload)
