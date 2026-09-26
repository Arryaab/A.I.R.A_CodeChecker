# Bug 015: Unsupported Tuple Elements in Recursive Flattener

## Description
The `flatten(nested_list)` function checks `isinstance(item, list)`, failing to flatten nested tuples.

## Requirements
- Flatten arbitrary nestings of lists and tuples recursively.
