# task_065_yaml_unsafe_constructor_load

**Category**: security_defect
**Difficulty**: medium

## Description
Restrict dynamic object instantiation in YAML config deserializer to explicit allowlist

## Expected Behavior
Only instantiates classes present in ALLOWED_TYPES; raises SecurityError otherwise
