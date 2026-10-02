from solution import StreamManager

def test_synchronize_drains_stream():
    mgr = StreamManager()
    mgr.record_event("matmul")
    mgr.synchronize()
    assert mgr.is_idle() is True
