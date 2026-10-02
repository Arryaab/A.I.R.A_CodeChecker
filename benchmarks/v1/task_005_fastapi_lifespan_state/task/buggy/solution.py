class AppState:
    def __init__(self):
        self._state = {}

    def set(self, key, value):
        self._state[key] = value

    def get(self, key, default=None):
        return self._state.get(key, default)

    def clear(self):
        # BUG: reassigns self._state to new dict, breaking references
        self._state = {}
