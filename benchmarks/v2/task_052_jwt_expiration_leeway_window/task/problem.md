# task_052_jwt_expiration_leeway_window

**Category**: boundary_violation
**Difficulty**: medium

## Description
Fix clock-skew leeway evaluation in JWT expiration validator

## Expected Behavior
Tokens are valid if current_time <= exp + leeway; expired if current_time > exp + leeway
