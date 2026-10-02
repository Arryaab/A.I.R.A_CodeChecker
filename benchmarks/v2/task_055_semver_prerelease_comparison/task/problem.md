# task_055_semver_prerelease_comparison

**Category**: boundary_violation
**Difficulty**: medium

## Description
Enforce SemVer 2.0 precedence: normal version has higher precedence than pre-release

## Expected Behavior
compare_semver('1.0.0', '1.0.0-alpha') returns 1; pre-release is lower precedence
