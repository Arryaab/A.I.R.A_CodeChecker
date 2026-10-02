# task_074_logging_format_context_pollution

**Category**: regression_defect
**Difficulty**: medium

## Description
Handle missing or cleared contextvar in logging record formatter without crashing

## Expected Behavior
Formats record with fallback '-' when request_id contextvar is None or unset
