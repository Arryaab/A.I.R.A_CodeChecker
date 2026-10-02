import pytest
from solution import EventDispatcher

def test_subscribe_dispatch():
    bus = EventDispatcher()
    called = []
    bus.subscribe("order.created", lambda p: called.append(p))
    bus.dispatch("order.created", {"id": 1})
    assert len(called) == 1
