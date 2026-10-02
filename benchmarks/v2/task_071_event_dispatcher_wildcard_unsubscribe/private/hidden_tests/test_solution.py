import pytest
from solution import EventDispatcher

def test_targeted_unsubscribe():
    bus = EventDispatcher()
    calls_a = []
    calls_b = []
    cb_a = lambda p: calls_a.append(p)
    cb_b = lambda p: calls_b.append(p)
    bus.subscribe("alert", cb_a)
    bus.subscribe("alert", cb_b)
    # Unsubscribe only A
    bus.unsubscribe("alert", cb_a)
    bus.dispatch("alert", {"msg": "fire"})
    assert len(calls_a) == 0
    # B must STILL receive the event!
    assert len(calls_b) == 1
