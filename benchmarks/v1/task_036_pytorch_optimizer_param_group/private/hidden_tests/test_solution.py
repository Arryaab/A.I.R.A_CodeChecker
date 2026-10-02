from solution import step_lr_scheduler

def test_single_group_decay():
    groups = [{"lr": 0.5}]
    step_lr_scheduler(groups, 0.5)
    assert groups[0]["lr"] == 0.25
