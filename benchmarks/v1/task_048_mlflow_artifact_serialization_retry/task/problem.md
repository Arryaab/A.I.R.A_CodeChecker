# task_048_mlflow_artifact_serialization_retry

**Category**: mlops_artifacts
**Difficulty**: medium

## Description
Implement exponential backoff retry on transient artifact upload errors

## Expected Behavior
Retries upload up to max_retries with doubling wait time, then raises RuntimeError
