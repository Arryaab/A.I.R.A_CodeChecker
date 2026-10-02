import asyncio
import pytest
from solution import AsyncDependencyResolver

cleaned_up = False

async def sample_dep():
    global cleaned_up
    cleaned_up = False
    try:
        yield "resource"
    finally:
        cleaned_up = True

def test_async_scope_cleanup():
    async def run():
        resolver = AsyncDependencyResolver()
        val = await resolver.resolve(sample_dep)
        assert val == "resource"
        await resolver.cleanup()
        assert cleaned_up is True
    asyncio.run(run())
