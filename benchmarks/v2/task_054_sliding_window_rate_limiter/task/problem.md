# task_054_sliding_window_rate_limiter

**Category**: boundary_violation
**Difficulty**: medium

## Description
Fix boundary timestamp pruning in sliding-window rate limiter

## Expected Behavior
Accurately discards expired timestamps strictly older than current_time - window_size
