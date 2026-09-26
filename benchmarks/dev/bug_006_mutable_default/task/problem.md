# Bug 006: Mutable Default Argument in List Appender

## Description
The `append_to_list(item, lst=[])` function uses a mutable default list argument, which persists state across multiple function calls.

## Requirements
- Default argument should be `None` and instantiate a fresh list on each invocation.
