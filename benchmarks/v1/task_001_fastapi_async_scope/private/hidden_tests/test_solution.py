import asyncio
import pytest
from solution import AsyncDependencyResolver

cleanups = []

async def dep1():
    try:
        yield 1
    finally:
        cleanups.append(1)

async def dep2():
    try:
        yield 2
    finally:
        cleanups.append(2)

def test_multiple_async_cleanups_reverse_order():
    async def run():
        global cleanups
        cleanups = []
        resolver = AsyncDependencyResolver()
        v1 = await resolver.resolve(dep1)
        v2 = await resolver.resolve(dep2)
        assert (v1, v2) == (1, 2)
        await resolver.cleanup()
        assert cleanups == [2, 1]
    asyncio.run(run())
