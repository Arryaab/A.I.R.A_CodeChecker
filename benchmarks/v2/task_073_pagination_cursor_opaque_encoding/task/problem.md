# task_073_pagination_cursor_opaque_encoding

**Category**: regression_defect
**Difficulty**: medium

## Description
Support backward compatibility for legacy integer offset cursor strings

## Expected Behavior
decode_cursor parses base64 JSON tokens as well as plain legacy integer offset strings
