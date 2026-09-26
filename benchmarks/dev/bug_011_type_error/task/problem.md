# Bug 011: TypeError on Non-String Elements in List Stringifier

## Description
The `stringify_list(items)` function calls `','.join(items)` without converting non-string elements to strings.

## Requirements
- Convert all items to `str` before joining with commas.
