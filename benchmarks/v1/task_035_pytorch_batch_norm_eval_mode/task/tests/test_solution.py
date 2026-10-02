from solution import BatchNorm1D

def test_running_mean_frozen_in_eval_mode():
    bn = BatchNorm1D(momentum=0.5)
    bn.running_mean = 10.0
    bn.training = False
    bn.forward(100.0)
    assert bn.running_mean == 10.0
