import pytest
from solution import step_lr_scheduler

def test_oracle_happy_path_all_groups_decay():
    groups = [
        {"name": "backbone", "lr": 1e-3},
        {"name": "head", "lr": 1e-2},
        {"name": "bias", "lr": 1e-1}
    ]
    step_lr_scheduler(groups, 0.1)
    assert abs(groups[0]["lr"] - 1e-4) < 1e-7
    assert abs(groups[1]["lr"] - 1e-3) < 1e-7
    assert abs(groups[2]["lr"] - 1e-2) < 1e-7

def test_oracle_boundary_empty():
    groups = []
    step_lr_scheduler(groups, 0.5)
    assert groups == []

def test_oracle_boundary_single():
    groups = [{"lr": 0.5}]
    step_lr_scheduler(groups, 0.2)
    assert abs(groups[0]["lr"] - 0.1) < 1e-7
