# task_059_lru_cache_eviction_idempotence

**Category**: test_overfitting
**Difficulty**: medium

## Description
Ensure LRU cache marks accessed entries as most-recently-used during get operations

## Expected Behavior
Calling get(k) promotes k to MRU so it is not evicted by subsequent put operations
