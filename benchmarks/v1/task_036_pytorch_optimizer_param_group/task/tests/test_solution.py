from solution import step_lr_scheduler

def test_all_param_groups_decay():
    groups = [{"name": "backbone", "lr": 1e-3}, {"name": "head", "lr": 1e-2}]
    step_lr_scheduler(groups, 0.1)
    assert abs(groups[0]["lr"] - 1e-4) < 1e-7
    assert abs(groups[1]["lr"] - 1e-3) < 1e-7
