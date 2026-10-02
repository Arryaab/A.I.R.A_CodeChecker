# task_071_event_dispatcher_wildcard_unsubscribe

**Category**: regression_defect
**Difficulty**: medium

## Description
Safely remove specific listener without mutating shared listener registry during dispatch

## Expected Behavior
Unsubscribing a listener removes only the target callback and does not break active dispatch
