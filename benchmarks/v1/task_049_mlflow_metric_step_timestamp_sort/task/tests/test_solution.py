from solution import sort_metric_history

def test_metrics_sorted_by_step():
    m = [{"step": 10, "val": 0.8}, {"step": 2, "val": 0.2}, {"step": 5, "val": 0.5}]
    res = sort_metric_history(m)
    assert [x["step"] for x in res] == [2, 5, 10]
