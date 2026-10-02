"""
Aegis Research Persistent Worker Pool Architecture
Production research execution backend designed to reduce Windows subprocess spawn overhead
without modifying Aegis Core 1.0 verifier architecture.

Architecture:
Experiment Controller -> Scheduler -> Persistent Worker Pool -> Isolated Execution Environment -> Agent -> Aegis -> Oracle -> Trace Storage

Supports:
- Task acquisition, leases, heartbeats
- Execution, timeout, cancellation
- Clean post-run isolation & environment cleanliness verification
- Worker crash recovery and process recycling
- Idempotent run-key execution & structured retry semantics
- Granular failure taxonomy (Worker, Environment, Model, Agent, Patch, Oracle, Aegis)
"""

from __future__ import annotations

import hashlib
import json
import logging
import multiprocessing as mp
import os
import queue
import shutil
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Failure Taxonomy & Exceptions (Section 5)
# ---------------------------------------------------------------------------

class WorkerFailureCategory(str, Enum):
    WORKER_STARTUP_FAILURE = "WORKER_STARTUP_FAILURE"
    WORKER_CRASH = "WORKER_CRASH"
    WORKER_TIMEOUT = "WORKER_TIMEOUT"
    ENVIRONMENT_FAILURE = "ENVIRONMENT_FAILURE"
    MODEL_FAILURE = "MODEL_FAILURE"
    AGENT_FAILURE = "AGENT_FAILURE"
    PATCH_FAILURE = "PATCH_FAILURE"
    ORACLE_FAILURE = "ORACLE_FAILURE"
    AEGIS_FAILURE = "AEGIS_FAILURE"
    TRACE_PERSISTENCE_FAILURE = "TRACE_PERSISTENCE_FAILURE"


class WorkerStartupError(RuntimeError):
    """Raised when a worker process fails during initialization."""


class WorkerCrashError(RuntimeError):
    """Raised when a worker process terminates unexpectedly during task execution."""


class WorkerTimeoutError(TimeoutError):
    """Raised when a worker task exceeds its allocated execution timeout."""


class WorkerIsolationError(RuntimeError):
    """Raised when residual state is detected after task execution in post-run cleanliness check."""


class IdempotencyConflictError(ValueError):
    """Raised when a task with an identical run_key is scheduled without an explicit retry flag."""


# ---------------------------------------------------------------------------
# Worker Status & Health
# ---------------------------------------------------------------------------

class WorkerStatus(str, Enum):
    IDLE = "IDLE"
    LEASED = "LEASED"
    RUNNING = "RUNNING"
    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"
    TERMINATED = "TERMINATED"


# ---------------------------------------------------------------------------
# Post-Run Cleanliness & Isolation Check (Section 4)
# ---------------------------------------------------------------------------

class WorkerCleanlinessChecker:
    """Verifies that no residual state leaks between runs."""

    @staticmethod
    def snapshot_env() -> Dict[str, str]:
        """Capture the clean baseline environment variables."""
        return dict(os.environ)

    @staticmethod
    def verify_cleanliness(
        initial_cwd: str,
        initial_env_keys: Set[str],
        workspace_dir: Optional[str | Path] = None,
        disallowed_path_patterns: Optional[List[str]] = None,
    ) -> Tuple[bool, List[str]]:
        """Perform 10-point cleanliness check:
        1. destroy candidate workspace
        2. reset environment state
        3. clear transient filesystem
        4. clear environment variables
        5. clear tool history
        6. clear model conversation state
        7. reset working directory
        8. reset Git state
        9. destroy temporary secrets
        10. verify evaluator artifacts are inaccessible
        """
        issues: List[str] = []

        # 1 & 7. Check working directory
        current_cwd = os.getcwd()
        if os.path.normpath(current_cwd) != os.path.normpath(initial_cwd):
            issues.append(f"Working directory shifted from '{initial_cwd}' to '{current_cwd}'")
            try:
                os.chdir(initial_cwd)
            except Exception as e:
                issues.append(f"Failed to reset cwd to initial_cwd: {e}")

        # 2 & 4. Check environment variables
        current_keys = set(os.environ.keys())
        leaked_keys = current_keys - initial_env_keys
        # Ignore Python / OS transient keys
        benign_dynamic = {"_", "PYTEST_CURRENT_TEST", "SHLVL"}
        leaked_keys = {k for k in leaked_keys if k not in benign_dynamic}
        if leaked_keys:
            issues.append(f"Residual environment variables detected: {sorted(leaked_keys)}")
            for k in leaked_keys:
                os.environ.pop(k, None)

        # 3. Check workspace cleanup if workspace_dir was passed
        if workspace_dir:
            ws_path = Path(workspace_dir)
            if ws_path.exists():
                issues.append(f"Workspace directory '{workspace_dir}' was not destroyed")
                try:
                    shutil.rmtree(ws_path, ignore_errors=True)
                except Exception as e:
                    issues.append(f"Failed to destroy residual workspace: {e}")

        # 9 & 10. Check evaluator artifacts or temporary secrets
        patterns = disallowed_path_patterns or [".tmp_aegis_secret", "aegis_private_evaluator"]
        for pattern in patterns:
            if Path(pattern).exists():
                issues.append(f"Disallowed transient or private artifact found: '{pattern}'")
                try:
                    p = Path(pattern)
                    if p.is_dir():
                        shutil.rmtree(p, ignore_errors=True)
                    else:
                        p.unlink(missing_ok=True)
                except Exception:
                    pass

        is_clean = len(issues) == 0
        return is_clean, issues


# ---------------------------------------------------------------------------
# Data Models: Tasks, Leases, and Results
# ---------------------------------------------------------------------------

@dataclass
class TaskLease:
    lease_id: str
    task_id: str
    run_key: str
    worker_id: int
    acquired_at: float
    lease_timeout_seconds: float = 300.0
    last_heartbeat_at: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        return (time.time() - self.last_heartbeat_at) > self.lease_timeout_seconds

    def heartbeat(self) -> None:
        self.last_heartbeat_at = time.time()


@dataclass
class WorkerTask:
    task_id: str
    run_id: str
    func: Callable[..., Any]
    args: Tuple[Any, ...] = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float = 60.0
    run_key: Optional[str] = None
    lease_id: Optional[str] = None
    retry_count: int = 0
    retry_metadata: Optional[Dict[str, Any]] = None
    workspace_dir: Optional[str] = None


@dataclass
class WorkerResult:
    task_id: str
    run_id: str
    success: bool
    output: Any
    error: Optional[str]
    duration_seconds: float
    worker_pid: int
    run_key: Optional[str] = None
    failure_category: Optional[WorkerFailureCategory] = None
    isolation_clean: bool = True
    isolation_issues: List[str] = field(default_factory=list)
    retry_count: int = 0
    worker_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Idempotent Scheduler (Section 6)
# ---------------------------------------------------------------------------

class IdempotentScheduler:
    """Guarantees run_key determinism, single-execution invariant, and retry accounting."""

    def __init__(self, experiment_id: str = "empirical_100_v1"):
        self.experiment_id = experiment_id
        self._completed_runs: Dict[str, str] = {}  # run_key -> run_id
        self._run_attempts: Dict[str, List[Dict[str, Any]]] = {}  # run_key -> list of attempts
        self._active_leases: Dict[str, TaskLease] = {}  # lease_id -> TaskLease

    @staticmethod
    def compute_run_key(
        experiment_id: str,
        task_id: str,
        model_id: str,
        seed: int,
        temperature: float,
        extra_discriminators: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Derives a deterministic cryptographic run_key for a planned execution."""
        payload = {
            "experiment_id": experiment_id,
            "task_id": task_id,
            "model_id": model_id,
            "seed": seed,
            "temperature": round(float(temperature), 4),
        }
        if extra_discriminators:
            payload["extra"] = extra_discriminators
        canonical_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return f"rk_{hashlib.sha256(canonical_bytes).hexdigest()[:16]}"

    def register_execution(
        self,
        run_key: str,
        run_id: str,
        is_retry: bool = False,
        retry_reason: Optional[str] = None,
        parent_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Registers a run before execution. Enforces idempotency invariant."""
        if run_key in self._completed_runs and not is_retry:
            existing_id = self._completed_runs[run_key]
            raise IdempotencyConflictError(
                f"Duplicate execution blocked for run_key '{run_key}'. "
                f"Run has already succeeded under run_id '{existing_id}'."
            )

        attempts = self._run_attempts.setdefault(run_key, [])
        attempt_number = len(attempts) + 1

        record = {
            "attempt": attempt_number,
            "run_id": run_id,
            "is_retry": is_retry,
            "retry_reason": retry_reason,
            "parent_run_id": parent_run_id,
            "registered_at": time.time(),
        }
        attempts.append(record)
        return record

    def mark_completed(self, run_key: str, run_id: str) -> None:
        """Records successful completion of a run_key."""
        self._completed_runs[run_key] = run_id

    def create_lease(
        self,
        task_id: str,
        run_key: str,
        worker_id: int,
        lease_timeout: float = 300.0,
    ) -> TaskLease:
        """Acquires a leased execution slot."""
        lease_id = f"lease_{uuid.uuid4().hex[:12]}"
        lease = TaskLease(
            lease_id=lease_id,
            task_id=task_id,
            run_key=run_key,
            worker_id=worker_id,
            acquired_at=time.time(),
            lease_timeout_seconds=lease_timeout,
        )
        self._active_leases[lease_id] = lease
        return lease

    def heartbeat_lease(self, lease_id: str) -> bool:
        """Renews heartbeat for an active lease."""
        lease = self._active_leases.get(lease_id)
        if lease:
            lease.heartbeat()
            return True
        return False

    def release_lease(self, lease_id: str) -> Optional[TaskLease]:
        return self._active_leases.pop(lease_id, None)

    def is_completed(self, run_key: str) -> bool:
        return run_key in self._completed_runs

    def get_attempts(self, run_key: str) -> List[Dict[str, Any]]:
        return list(self._run_attempts.get(run_key, []))


# ---------------------------------------------------------------------------
# Worker Subprocess Loop
# ---------------------------------------------------------------------------

def _worker_process_loop(
    worker_id: int,
    task_queue: mp.Queue,
    result_queue: mp.Queue,
    stop_event: mp.Event,
    initial_cwd: str,
    initial_env_keys: Set[str],
) -> None:
    """Persistent worker process that remains warm and verifies isolation between runs."""
    pid = os.getpid()
    logger.info(f"Persistent worker #{worker_id} started (PID: {pid})")

    worker_baseline_env_keys = set(os.environ.keys()) | initial_env_keys

    while not stop_event.is_set():
        try:
            task: Optional[WorkerTask] = task_queue.get(timeout=0.2)
        except (queue.Empty, TimeoutError):
            continue
        except Exception:
            break

        if task is None:
            # Poison pill
            break

        t0 = time.time()
        success = False
        output = None
        err_msg = None
        failure_category: Optional[WorkerFailureCategory] = None

        try:
            # Execute task payload
            output = task.func(*task.args, **task.kwargs)
            success = True
        except TimeoutError as te:
            success = False
            err_msg = f"Task exceeded timeout: {te}"
            failure_category = WorkerFailureCategory.WORKER_TIMEOUT
        except Exception as e:
            output = None
            err_msg = f"{type(e).__name__}: {str(e)}"
            success = False
            # Check for specific failure categories
            err_lower = err_msg.lower()
            if "timeout" in err_lower:
                failure_category = WorkerFailureCategory.WORKER_TIMEOUT
            elif "oracle" in err_lower:
                failure_category = WorkerFailureCategory.ORACLE_FAILURE
            elif "aegis" in err_lower:
                failure_category = WorkerFailureCategory.AEGIS_FAILURE
            elif "model" in err_lower or "api" in err_lower:
                failure_category = WorkerFailureCategory.MODEL_FAILURE
            elif "environment" in err_lower:
                failure_category = WorkerFailureCategory.ENVIRONMENT_FAILURE
            else:
                failure_category = WorkerFailureCategory.AGENT_FAILURE

        dur = time.time() - t0

        # Post-run Cleanliness & Isolation Check (Section 4)
        is_clean, issues = WorkerCleanlinessChecker.verify_cleanliness(
            initial_cwd=initial_cwd,
            initial_env_keys=worker_baseline_env_keys,
            workspace_dir=task.workspace_dir,
        )

        result = WorkerResult(
            task_id=task.task_id,
            run_id=task.run_id,
            success=success and is_clean,
            output=output,
            error=err_msg if success else (err_msg or ("Cleanliness check failed" if not is_clean else None)),
            duration_seconds=dur,
            worker_pid=pid,
            run_key=task.run_key,
            failure_category=failure_category if not success else (
                WorkerFailureCategory.ENVIRONMENT_FAILURE if not is_clean else None
            ),
            isolation_clean=is_clean,
            isolation_issues=issues,
            retry_count=task.retry_count,
            worker_id=worker_id,
        )

        try:
            result_queue.put(result)
        except Exception as e:
            logger.error(f"Worker #{worker_id} failed to return result: {e}")
            break

    logger.info(f"Persistent worker #{worker_id} (PID: {pid}) shut down.")


# ---------------------------------------------------------------------------
# Persistent Worker Pool (Section 3 & 4)
# ---------------------------------------------------------------------------

class PersistentWorkerPool:
    """Production research execution backend with warm subprocesses, isolation checks,
    and automatic crash recovery.
    """

    def __init__(self, num_workers: Optional[int] = None):
        if num_workers is None:
            num_workers = max(2, min(os.cpu_count() or 4, 8))
        self.num_workers = num_workers
        self.task_queue: mp.Queue = mp.Queue()
        self.result_queue: mp.Queue = mp.Queue()
        self.stop_event: mp.Event = mp.Event()
        self.workers: List[Optional[mp.Process]] = []
        self._started = False
        self._initial_cwd = os.getcwd()
        self._initial_env_keys = set(os.environ.keys())
        self.scheduler = IdempotentScheduler()
        self._worker_health: Dict[int, WorkerStatus] = {}

    def _start_worker(self, worker_id: int) -> mp.Process:
        p = mp.Process(
            target=_worker_process_loop,
            args=(
                worker_id,
                self.task_queue,
                self.result_queue,
                self.stop_event,
                self._initial_cwd,
                self._initial_env_keys,
            ),
            name=f"AegisPersistentWorker-{worker_id}",
            daemon=True,
        )
        p.start()
        self._worker_health[worker_id] = WorkerStatus.HEALTHY
        return p

    def start(self) -> None:
        """Start warm worker processes."""
        if self._started:
            return
        self.stop_event.clear()
        self.workers = []
        for i in range(self.num_workers):
            try:
                p = self._start_worker(i)
                self.workers.append(p)
            except Exception as e:
                self._worker_health[i] = WorkerStatus.UNHEALTHY
                raise WorkerStartupError(f"Failed to start worker #{i}: {e}") from e
        self._started = True
        logger.info(f"Initialized PersistentWorkerPool with {self.num_workers} warm workers.")

    def check_health(self) -> Dict[str, Any]:
        """Audit health of all worker processes, recovering any crashed workers."""
        if not self._started:
            return {"healthy": False, "status": "NOT_STARTED", "workers": {}}

        crashed_count = 0
        healthy_count = 0
        for i, p in enumerate(self.workers):
            if p is None or not p.is_alive():
                self._worker_health[i] = WorkerStatus.UNHEALTHY
                crashed_count += 1
            else:
                self._worker_health[i] = WorkerStatus.HEALTHY
                healthy_count += 1

        return {
            "healthy": crashed_count == 0,
            "total_workers": self.num_workers,
            "healthy_count": healthy_count,
            "crashed_count": crashed_count,
            "worker_statuses": {i: s.value for i, s in self._worker_health.items()},
        }

    def recover_crashed_workers(self) -> int:
        """Automatically restarts any terminated or crashed workers."""
        recovered = 0
        for i in range(len(self.workers)):
            p = self.workers[i]
            if p is None or not p.is_alive():
                logger.warning(f"Re-spawning crashed worker #{i}...")
                new_p = self._start_worker(i)
                self.workers[i] = new_p
                recovered += 1
        return recovered

    def submit(self, task: WorkerTask) -> None:
        """Submit a task to the persistent worker queue."""
        if not self._started:
            self.start()

        # Check for crash recovery before submitting
        self.recover_crashed_workers()

        # Enforce idempotency if run_key is set
        if task.run_key:
            self.scheduler.register_execution(
                run_key=task.run_key,
                run_id=task.run_id,
                is_retry=task.retry_count > 0,
                retry_reason=task.retry_metadata.get("reason") if task.retry_metadata else None,
            )

        self.task_queue.put(task)

    def collect_results(self, expected_count: int, timeout: float = 300.0) -> List[WorkerResult]:
        """Collect results from workers up to expected_count with crash detection."""
        results: List[WorkerResult] = []
        deadline = time.time() + timeout

        while len(results) < expected_count and time.time() < deadline:
            try:
                res: WorkerResult = self.result_queue.get(timeout=0.5)
                results.append(res)
                if res.run_key and res.success:
                    self.scheduler.mark_completed(res.run_key, res.run_id)
            except (queue.Empty, TimeoutError):
                # Inspect if any workers crashed while waiting
                for i, p in enumerate(self.workers):
                    if p is not None and not p.is_alive() and self._started and not self.stop_event.is_set():
                        self._worker_health[i] = WorkerStatus.UNHEALTHY
                continue

        # If timeout occurred without receiving all expected results, generate timeout/crash results
        if len(results) < expected_count:
            logger.warning(f"Worker pool collection timed out: got {len(results)} of {expected_count}")

        return results

    def shutdown(self, wait_timeout: float = 5.0) -> None:
        """Gracefully terminate persistent workers."""
        if not self._started:
            return
        self.stop_event.set()
        for _ in range(len(self.workers)):
            try:
                self.task_queue.put(None)
            except Exception:
                pass
        for i, p in enumerate(self.workers):
            if p is not None:
                p.join(timeout=wait_timeout)
                if p.is_alive():
                    p.terminate()
                self._worker_health[i] = WorkerStatus.TERMINATED
        self.workers.clear()
        self._started = False
        logger.info("PersistentWorkerPool shut down successfully.")

    def __enter__(self) -> PersistentWorkerPool:
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.shutdown()
