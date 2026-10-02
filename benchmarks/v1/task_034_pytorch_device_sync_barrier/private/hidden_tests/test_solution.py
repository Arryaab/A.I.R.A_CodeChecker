from solution import StreamManager

def test_pending_tasks_not_idle():
    mgr = StreamManager()
    mgr.record_event("conv2d")
    assert mgr.is_idle() is False
