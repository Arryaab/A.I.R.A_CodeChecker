class AsyncDependencyResolver:
    def __init__(self):
        self.cleanups = []

    async def resolve(self, dep_func):
        gen = dep_func()
        val = await gen.__anext__()
        # BUG: Forgot to store generator for cleanup
        return val

    async def cleanup(self):
        for gen in reversed(self.cleanups):
            try:
                await gen.__anext__()
            except StopAsyncIteration:
                pass
        self.cleanups.clear()
