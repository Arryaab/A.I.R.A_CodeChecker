import pytest
from solution import StreamManager

def test_oracle_happy_path_synchronize_drains():
    mgr = StreamManager()
    mgr.record_event("matmul")
    mgr.record_event("conv")
    assert mgr.is_idle() is False
    mgr.synchronize()
    assert mgr.is_idle() is True
    assert mgr.pending_tasks == []

def test_oracle_boundary_empty_sync():
    mgr = StreamManager()
    mgr.synchronize()
    assert mgr.is_idle() is True

def test_oracle_repeated_events():
    mgr = StreamManager()
    mgr.record_event("t1")
    mgr.synchronize()
    assert mgr.is_idle() is True
    mgr.record_event("t2")
    assert mgr.is_idle() is False
