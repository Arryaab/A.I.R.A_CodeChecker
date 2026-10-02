from solution import BatchNorm1D

def test_running_mean_updates_in_train_mode():
    bn = BatchNorm1D(momentum=0.5)
    bn.running_mean = 10.0
    bn.training = True
    bn.forward(20.0)
    assert bn.running_mean == 15.0
