from solution import sort_metric_history

def test_already_sorted():
    m = [{"step": 1}, {"step": 2}]
    assert sort_metric_history(m) == m
