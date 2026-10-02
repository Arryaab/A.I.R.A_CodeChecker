"""
Tests for Worker Pool Isolation, Crash Recovery, Timeout, Retry Semantics, and Idempotency.
Requirements from Directive Sections 3, 4, 5, 6, 29.
"""

import os
import time
import pytest
from aegis.research.worker_pool import (
    PersistentWorkerPool,
    WorkerTask,
    WorkerResult,
    WorkerFailureCategory,
    WorkerCleanlinessChecker,
    IdempotentScheduler,
    IdempotencyConflictError,
    WorkerStatus,
)


def task_clean(x: int) -> int:
    return x * 2


def task_dirty_env(x: int) -> int:
    os.environ["LEAKED_SECRET_KEY"] = "super_secret_token_123"
    return x * 3


def task_timeout_simulation(x: int) -> int:
    time.sleep(2.0)
    return x


def task_crash_simulation(x: int) -> int:
    # Deliberate exit to simulate process crash
    os._exit(42)


def test_worker_cleanliness_checker():
    """Verify that WorkerCleanlinessChecker detects environment and cwd changes."""
    initial_cwd = os.getcwd()
    initial_keys = set(os.environ.keys())

    # 1. Clean check
    is_clean, issues = WorkerCleanlinessChecker.verify_cleanliness(initial_cwd, initial_keys)
    assert is_clean is True
    assert len(issues) == 0

    # 2. Dirty check: injected env var
    os.environ["TEST_DIRTY_KEY"] = "leak"
    is_clean, issues = WorkerCleanlinessChecker.verify_cleanliness(initial_cwd, initial_keys)
    assert is_clean is False
    assert any("TEST_DIRTY_KEY" in issue for issue in issues)
    # Ensure it cleaned it up
    assert "TEST_DIRTY_KEY" not in os.environ


def test_run_key_idempotency():
    """Verify that duplicate run_key is blocked unless marked as retry."""
    scheduler = IdempotentScheduler(experiment_id="empirical_100_v1")
    rk = scheduler.compute_run_key(
        experiment_id="empirical_100_v1",
        task_id="task_001",
        model_id="gpt-4o-mini-2024-07-18",
        seed=42,
        temperature=0.0,
    )

    # First registration passes
    rec1 = scheduler.register_execution(run_key=rk, run_id="run_001")
    assert rec1["attempt"] == 1
    scheduler.mark_completed(rk, "run_001")

    # Second registration with same run_key without retry raises IdempotencyConflictError
    with pytest.raises(IdempotencyConflictError) as exc_info:
        scheduler.register_execution(run_key=rk, run_id="run_002", is_retry=False)
    assert "Duplicate execution blocked" in str(exc_info.value)


def test_retry_semantics():
    """Verify that retries record attempt history and link to parent attempt."""
    scheduler = IdempotentScheduler(experiment_id="empirical_100_v1")
    rk = scheduler.compute_run_key(
        experiment_id="empirical_100_v1",
        task_id="task_002",
        model_id="gemini-1.5-flash-002",
        seed=100,
        temperature=0.0,
    )

    # Initial failed attempt
    rec1 = scheduler.register_execution(run_key=rk, run_id="run_orig")
    assert rec1["attempt"] == 1

    # Retry attempt
    rec2 = scheduler.register_execution(
        run_key=rk,
        run_id="run_retry_1",
        is_retry=True,
        retry_reason="WORKER_TIMEOUT",
        parent_run_id="run_orig",
    )
    assert rec2["attempt"] == 2
    assert rec2["is_retry"] is True
    assert rec2["retry_reason"] == "WORKER_TIMEOUT"

    attempts = scheduler.get_attempts(rk)
    assert len(attempts) == 2
    assert attempts[0]["run_id"] == "run_orig"
    assert attempts[1]["run_id"] == "run_retry_1"


def test_worker_state_isolation():
    """Verify that worker pool execution catches residual state and flags failure."""
    with PersistentWorkerPool(num_workers=2) as pool:
        # First submit clean task
        t_clean = WorkerTask(
            task_id="task_clean",
            run_id="run_c1",
            func=task_clean,
            args=(10,),
        )
        pool.submit(t_clean)
        res_clean = pool.collect_results(1, timeout=5.0)
        assert len(res_clean) == 1
        assert res_clean[0].success is True
        assert res_clean[0].isolation_clean is True

        # Second submit task that leaks an env var
        t_dirty = WorkerTask(
            task_id="task_dirty",
            run_id="run_d1",
            func=task_dirty_env,
            args=(5,),
        )
        pool.submit(t_dirty)
        res_dirty = pool.collect_results(1, timeout=5.0)
        assert len(res_dirty) == 1
        # The pool catches that LEAKED_SECRET_KEY was set and fails the run for isolation
        assert res_dirty[0].isolation_clean is False
        assert any("LEAKED_SECRET_KEY" in issue for issue in res_dirty[0].isolation_issues)
        assert res_dirty[0].success is False


def test_worker_crash_recovery():
    """Verify that worker crash is detected and replacement worker can be recovered."""
    with PersistentWorkerPool(num_workers=2) as pool:
        health_before = pool.check_health()
        assert health_before["healthy"] is True

        # Submit task that crashes the process via os._exit
        t_crash = WorkerTask(
            task_id="task_crash",
            run_id="run_crash_1",
            func=task_crash_simulation,
            args=(1,),
        )
        pool.submit(t_crash)
        # Give process time to die
        time.sleep(1.0)

        health_mid = pool.check_health()
        assert health_mid["crashed_count"] >= 1

        recovered = pool.recover_crashed_workers()
        assert recovered >= 1

        health_after = pool.check_health()
        assert health_after["healthy"] is True

        # Verify new worker can process work
        t_followup = WorkerTask(
            task_id="task_after_recovery",
            run_id="run_rec_1",
            func=task_clean,
            args=(21,),
        )
        pool.submit(t_followup)
        results = pool.collect_results(1, timeout=5.0)
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].output == 42
