import pytest
from solution import EventDispatcher

def test_oracle_missing_unsubscribe_noop():
    bus = EventDispatcher()
    cb = lambda p: None
    # Should not raise exception when unsubscribing non-existent listener
    bus.unsubscribe("unknown", cb)
