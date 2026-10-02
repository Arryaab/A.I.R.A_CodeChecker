"""
Harden All 50 AegisBench v1 Oracles:
Writes task-specific behavioral oracle test suites, specifications, mutations,
plausible bad patches, and enriched metadata across all 50 tasks.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))
import json
import shutil
import yaml

from scripts.oracle_definitions_track1 import ORACLE_DATA_TRACK1
from scripts.oracle_definitions_track2 import ORACLE_DATA_TRACK2
from scripts.oracle_definitions_track3 import ORACLE_DATA_TRACK3

def main():
    bench_dir = Path("benchmarks/v1")
    all_oracle_data = {}
    all_oracle_data.update(ORACLE_DATA_TRACK1)
    all_oracle_data.update(ORACLE_DATA_TRACK2)
    all_oracle_data.update(ORACLE_DATA_TRACK3)

    print(f"Hardening {len(all_oracle_data)} tasks in {bench_dir}...")

    updated_count = 0
    for task_id, data in all_oracle_data.items():
        task_dir = bench_dir / task_id
        if not task_dir.exists():
            print(f"Warning: {task_dir} does not exist!")
            continue

        public_dir = task_dir / "task"
        private_dir = task_dir / "private"
        oracle_tests_dir = private_dir / "oracle_tests"
        oracle_tests_dir.mkdir(parents=True, exist_ok=True)

        # 1. Write private/oracle_tests/test_oracle_behavior.py
        test_file = oracle_tests_dir / "test_oracle_behavior.py"
        test_file.write_text(data["test_code"], encoding="utf-8")

        # 2. Write private/oracle_spec.yaml
        spec_content = {
            "task_id": task_id,
            "oracle_version": "1.0.0",
            "evaluator_namespace": "private/oracle_tests",
            "aegis_namespace": "private/aegis_hidden_tests",
            "behavioral_specification": data["behavioral_spec"],
            "invariants": [
                "No modification of private/ files allowed",
                "Public interface contract strictly preserved",
                "No unhandled fatal exceptions on boundary inputs",
                "Behavioral contract satisfied across all test categories"
            ],
            "constraints": {
                "public_api_unchanged": True,
                "max_files_modified": 1,
                "forbidden_modules": ["subprocess", "socket", "pty"],
                "max_latency_regression_pct": 10.0
            }
        }
        spec_file = private_dir / "oracle_spec.yaml"
        spec_file.write_text(yaml.dump(spec_content, sort_keys=False), encoding="utf-8")

        # 3. Write private/mutations.json
        mutations_file = private_dir / "mutations.json"
        mutations_file.write_text(json.dumps(data["mutations"], indent=2), encoding="utf-8")

        # 4. Write private/plausible_bad_patches.json
        bad_patches_file = private_dir / "plausible_bad_patches.json"
        bad_patches_file.write_text(json.dumps(data["plausible_bad_patches"], indent=2), encoding="utf-8")

        # 5. Enrich task/metadata.json
        meta_file = public_dir / "metadata.json"
        current_meta = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}
        current_meta.update({
            "task_id": task_id,
            "difficulty_dimensions": data["difficulty"],
            "environment": {
                "python_version": "3.11+",
                "dependencies_lock": "pytest>=8.0.0, pyyaml>=6.0.0",
                "os_target": "cross-platform (Linux/Windows/macOS)",
                "test_command": "pytest task/tests/test_solution.py -v",
                "oracle_command": "pytest private/oracle_tests/test_oracle_behavior.py -v",
                "verification_command": "aegis verify --task-dir ."
            }
        })
        meta_file.write_text(json.dumps(current_meta, indent=2), encoding="utf-8")

        # Clean __pycache__ inside oracle_tests if present
        for pycache in task_dir.rglob("__pycache__"):
            try:
                shutil.rmtree(pycache)
            except Exception:
                pass

        updated_count += 1
        print(f"  [OK] Hardened: {task_id}")

    print(f"\nSuccessfully hardened all {updated_count}/50 benchmark tasks!")

if __name__ == "__main__":
    main()
