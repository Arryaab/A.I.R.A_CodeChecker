import pytest
from solution import BatchNorm1D

def test_oracle_happy_path_train_mode_updates():
    bn = BatchNorm1D(momentum=0.5)
    bn.running_mean = 0.0
    bn.training = True
    res = bn.forward(10.0)
    assert res == 5.0
    assert bn.running_mean == 5.0

def test_oracle_negative_eval_mode_freezes_running_mean():
    bn = BatchNorm1D(momentum=0.5)
    bn.running_mean = 10.0
    bn.training = False
    res = bn.forward(100.0)
    assert res == 10.0
    assert bn.running_mean == 10.0

def test_oracle_boundary_zero_momentum():
    bn = BatchNorm1D(momentum=0.0)
    bn.running_mean = 4.0
    bn.training = True
    assert bn.forward(20.0) == 4.0
