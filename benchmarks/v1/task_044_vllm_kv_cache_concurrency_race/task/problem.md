# task_044_vllm_kv_cache_concurrency_race

**Category**: ml_serving_vllm
**Difficulty**: hard

## Description
Prevent double-free of reference-counted KV-cache physical blocks

## Expected Behavior
Decrements block refcount and frees physical block only when refcount reaches 0
