import asyncio
import pytest
from solution import AsyncDependencyResolver

history = []

async def make_dep(name):
    global history
    try:
        yield f"val_{name}"
    finally:
        history.append(f"clean_{name}")

def test_oracle_happy_path_single_dependency():
    async def run():
        global history
        history = []
        resolver = AsyncDependencyResolver()
        val = await resolver.resolve(lambda: make_dep("X"))
        assert val == "val_X"
        await resolver.cleanup()
        assert history == ["clean_X"]
    asyncio.run(run())

def test_oracle_boundary_multiple_and_empty():
    async def run():
        resolver = AsyncDependencyResolver()
        await resolver.cleanup()
        assert resolver.cleanups == []
    asyncio.run(run())

def test_oracle_lifo_order_invariance():
    async def run():
        global history
        history = []
        resolver = AsyncDependencyResolver()
        a = await resolver.resolve(lambda: make_dep("A"))
        b = await resolver.resolve(lambda: make_dep("B"))
        c = await resolver.resolve(lambda: make_dep("C"))
        assert (a, b, c) == ("val_A", "val_B", "val_C")
        await resolver.cleanup()
        assert history == ["clean_C", "clean_B", "clean_A"]
    asyncio.run(run())

def test_oracle_idempotent_cleanup():
    async def run():
        global history
        history = []
        resolver = AsyncDependencyResolver()
        await resolver.resolve(lambda: make_dep("1"))
        await resolver.cleanup()
        assert history == ["clean_1"]
        assert len(resolver.cleanups) == 0
        await resolver.cleanup()
        assert history == ["clean_1"]
        assert len(resolver.cleanups) == 0
    asyncio.run(run())

def test_oracle_adversarial_shallow_fix():
    async def run():
        global history
        history = []
        resolver = AsyncDependencyResolver()
        for i in range(5):
            await resolver.resolve(lambda i=i: make_dep(str(i)))
        await resolver.cleanup()
        assert len(history) == 5
        assert history == [f"clean_{i}" for i in reversed(range(5))]
    asyncio.run(run())
