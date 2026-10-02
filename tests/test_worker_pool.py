"""
Unit test for Aegis Research Persistent Worker Pool Architecture.
"""

import time
import pytest
from aegis.research.worker_pool import PersistentWorkerPool, WorkerTask, WorkerResult

def dummy_work(x: int, y: int) -> int:
    return x * y + 42

def test_persistent_worker_pool_execution():
    with PersistentWorkerPool(num_workers=2) as pool:
        for i in range(4):
            task = WorkerTask(
                task_id=f"test_task_{i}",
                run_id=f"run_{i}",
                func=dummy_work,
                args=(i, 10)
            )
            pool.submit(task)

        results = pool.collect_results(expected_count=4, timeout=10.0)
        assert len(results) == 4
        for r in results:
            assert r.success is True
            assert r.output is not None
            assert r.error is None
            assert r.worker_pid > 0
