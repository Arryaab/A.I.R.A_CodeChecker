# task_039_hf_pipeline_batch_leak

**Category**: ml_serving
**Difficulty**: medium

## Description
Reset internal batch accumulation buffer between inference pipeline calls

## Expected Behavior
Ensures second inference batch does not contain residual outputs from first batch
