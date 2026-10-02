def step_lr_scheduler(param_groups: list[dict], decay_factor: float):
    # BUG: only updates the first parameter group
    if param_groups:
        param_groups[0]["lr"] *= decay_factor
