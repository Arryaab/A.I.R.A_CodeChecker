"""
AegisBench-v1 Cryptographic Immutability CI Gate.
Ensures that once qualified and locked, NO file within benchmarks/v1 is mutated in place.
Any change to task code, public tests, oracle tests, hidden tests, diffs, or metadata
will alter the cryptographic manifest hashes and immediately fail this test.
"""

import hashlib
import json
from pathlib import Path
import pytest


def compute_manifest_sha256(files: list[Path]) -> str:
    hasher = hashlib.sha256()
    for f in sorted(files, key=lambda p: str(p)):
        if f.exists() and f.is_file() and "__pycache__" not in f.parts and not f.name.endswith(".pyc"):
            hasher.update(str(f).encode("utf-8"))
            hasher.update(f.read_bytes())
    return "sha256:" + hasher.hexdigest()


def test_aegisbench_v1_cryptographic_lock_integrity():
    lock_file = Path("AegisBench-v1.lock.json")
    assert lock_file.exists(), "AegisBench-v1.lock.json is missing!"

    lock_data = json.loads(lock_file.read_text(encoding="utf-8"))
    assert lock_data.get("benchmark_version") == "AegisBench-v1"
    assert lock_data.get("status") == "QUALIFIED"
    assert lock_data.get("task_count") == 50

    bench_dir = Path("benchmarks/v1")
    assert bench_dir.exists(), "benchmarks/v1 directory missing!"

    tasks = sorted([d for d in bench_dir.iterdir() if d.is_dir()])
    assert len(tasks) == 50, f"Expected 50 tasks, found {len(tasks)}"

    task_files = []
    oracle_files = []
    env_files = []

    for td in tasks:
        task_files.extend(list((td / "task").rglob("*")))
        oracle_files.extend(list((td / "private").rglob("*")))
        env_files.append(td / "task" / "metadata.json")

    computed_task_hash = compute_manifest_sha256(task_files)
    computed_oracle_hash = compute_manifest_sha256(oracle_files)
    computed_env_hash = compute_manifest_sha256(env_files)

    expected_task_hash = lock_data["task_manifest_hash"]
    expected_oracle_hash = lock_data["oracle_manifest_hash"]
    expected_env_hash = lock_data["environment_manifest_hash"]

    assert computed_task_hash == expected_task_hash, (
        f"Benchmark Task Manifest mutated! Expected {expected_task_hash}, got {computed_task_hash}. "
        "AegisBench-v1 is frozen and immutable."
    )
    assert computed_oracle_hash == expected_oracle_hash, (
        f"Benchmark Oracle Manifest mutated! Expected {expected_oracle_hash}, got {computed_oracle_hash}. "
        "AegisBench-v1 is frozen and immutable."
    )
    assert computed_env_hash == expected_env_hash, (
        f"Benchmark Environment Manifest mutated! Expected {expected_env_hash}, got {computed_env_hash}. "
        "AegisBench-v1 is frozen and immutable."
    )
