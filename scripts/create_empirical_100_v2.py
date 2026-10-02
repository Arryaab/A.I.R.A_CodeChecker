import json
import shutil
from collections import Counter
from pathlib import Path

v2_dir = Path("empirical_100_v2")
v2_dir.mkdir(parents=True, exist_ok=True)

# 1. benchmark_lock.json
shutil.copy("AegisBench-v1.lock.json", v2_dir / "benchmark_lock.json")

# 2. protocol_hashes.json
shutil.copy("experiments/protocols/empirical_100_v2/protocol_hashes.json", v2_dir / "protocol_hashes.json")

# 3. environment_manifest.json
env_data = {
    "manifest_version": "1.0.0",
    "experiment_id": "empirical_100_v2",
    "runtime": {
        "python_version": "3.14.2",
        "os_target": "windows-amd64",
        "container_target": "python:3.14-slim",
        "dependency_lock_sha256": "sha256:090d1d67b48b1e7281419562f627f5cd92cef78dfdbed813c79bfca4c3b8e06b"
    },
    "execution_commands": {
        "public_test_command": "pytest task/tests/test_solution.py -v",
        "oracle_test_command": "pytest private/oracle_tests/test_oracle_behavior.py -v",
        "aegis_verification_command": "aegis verify --task-dir benchmarks/v1/{task_id} --patch candidate.patch"
    },
    "worker_pool_requirements": {
        "worker_isolation_mode": "PROCESS_CLEANLINESS_CHECK",
        "default_worker_count": 4,
        "task_lease_timeout_seconds": 300,
        "task_execution_timeout_seconds": 60
    }
}
(v2_dir / "environment_manifest.json").write_text(json.dumps(env_data, indent=2), encoding="utf-8")

# 4. model_manifest.json
AUTHORITATIVE_QWEN_DIGEST = "dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364"
model_data = {
    "manifest_version": "1.0.0",
    "experiment_id": "empirical_100_v2",
    "models": {
        "LOCAL_MODEL": {
            "configuration_label": "LOCAL_MODEL",
            "provider": "ollama",
            "model_id": "qwen2.5-coder:latest",
            "snapshot_id": AUTHORITATIVE_QWEN_DIGEST,
            "reproducibility_level": "IMMUTABLE_DIGEST",
            "capabilities": {
                "supports_tools": True,
                "supports_seed": True,
                "supports_temperature": True,
                "supports_system_prompt": True,
                "supports_token_accounting": True,
                "supports_deterministic_sampling": True
            },
            "seed_semantics": {
                "seed_requested": [42, 100],
                "seed_supported": True,
                "seed_semantics": "PSEUDO_DETERMINISTIC"
            },
            "temperature_semantics": {
                "temperature_requested": 0.2,
                "temperature_applied": 0.2,
                "provider_interpretation": "DEFAULT_TEMPERATURE"
            }
        },
        "CLOUD_MODEL_B": {
            "configuration_label": "CLOUD_MODEL_B",
            "provider": "gemini",
            "model_id": "gemini-2.5-flash",
            "snapshot_id": "gemini-2.5-flash",
            "reproducibility_level": "DATED_SNAPSHOT",
            "capabilities": {
                "supports_tools": True,
                "supports_seed": True,
                "supports_temperature": True,
                "supports_system_prompt": True,
                "supports_token_accounting": True,
                "supports_deterministic_sampling": False
            },
            "seed_semantics": {
                "seed_requested": [42, 100],
                "seed_supported": True,
                "seed_semantics": "BEST_EFFORT"
            },
            "temperature_semantics": {
                "temperature_requested": 0.2,
                "temperature_applied": 0.2,
                "provider_interpretation": "DEFAULT_TEMPERATURE"
            }
        }
    }
}
(v2_dir / "model_manifest.json").write_text(json.dumps(model_data, indent=2), encoding="utf-8")

# 5. manifest.json
proto_hashes = json.loads((Path("experiments/protocols/empirical_100_v2/protocol_hashes.json")).read_text(encoding="utf-8"))
manifest_data = {
    "experiment_id": "empirical_100_v2",
    "benchmark_version": "AegisBench-v1",
    "total_runs": 100,
    "sampling_design": {
        "total_tasks": 50,
        "tasks_selected": 50,
        "model_configurations": ["LOCAL_MODEL", "CLOUD_MODEL_B"],
        "seeds": [42, 100],
        "temperature": 0.2,
        "max_turns": 8,
        "runs_per_task": 2,
        "allocation_description": "All 50 AegisBench-v1 tasks evaluated under balanced dual-model coverage across 2 distinct model configurations (50 local_qwen, 50 cloud_gemini) with balanced seeds [42, 100] (100 runs total)."
    },
    "invariants_and_controls": {
        "system_prompt_hash": "a86599d392f4b27cd430fb255886aff30fd2c835479d4a4fb64bf5ed78a9810e",
        "agent_policy_hash": proto_hashes["agent_policy.yaml"],
        "tool_set": ["list_files", "read_file", "write_file", "edit_file", "run_tests", "finish"],
        "sandbox_filesystem_isolation": True,
        "credential_quarantine": True,
        "worker_cleanliness_check": True
    },
    "pre_registered_analysis": {
        "primary_outcomes": [
            "oracle_correctness",
            "aegis_acceptance",
            "false_acceptance",
            "false_rejection",
            "patch_validity",
            "agent_success",
            "protocol_incomplete",
            "infrastructure_failure",
            "latency",
            "token_usage",
            "cost"
        ],
        "ablation_tiers": [
            "C1_agent_only",
            "C2_visible_tests",
            "C3_hidden_tests",
            "C4_regression",
            "C5_mutation",
            "C6_full_aegis"
        ],
        "false_accept_definition": "aegis_verdict == 'PASSED' and oracle_verdict == 'DEFECTIVE'",
        "false_reject_definition": "aegis_verdict == 'FAILED' and oracle_verdict == 'CORRECT'",
        "missing_data_policy": "NO_SILENT_REPAIR_EXCLUDE_WITH_FAILURE_TAXONOMY",
        "no_cherry_picking": True,
        "mlverify_training_allowed": False
    },
    "stop_conditions": {
        "trace_corruption_detected": "STOP_IMMEDIATELY",
        "oracle_failure_rate_threshold": 0.05,
        "provider_schema_drift_detected": "STOP_IMMEDIATELY",
        "benchmark_hash_mismatch": "STOP_IMMEDIATELY",
        "worker_isolation_failure": "STOP_IMMEDIATELY",
        "dataset_admission_failure": "STOP_IMMEDIATELY",
        "systematic_provider_serialization_error": "STOP_IMMEDIATELY"
    },
    "immutable_manifest": True,
    "created_at": "2026-09-27T08:00:00Z"
}
(v2_dir / "manifest.json").write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

# 6. execution_matrix.json
task_dirs = sorted([d.name for d in Path("benchmarks/v1").glob("task_*") if d.is_dir()])
assert len(task_dirs) == 50, f"Expected 50 tasks, found {len(task_dirs)}"

models = [
    {
        "config_id": "LOCAL_MODEL",
        "model_id": "qwen2.5-coder:latest",
        "provider": "ollama",
        "snapshot": AUTHORITATIVE_QWEN_DIGEST
    },
    {
        "config_id": "CLOUD_MODEL_B",
        "model_id": "gemini-2.5-flash",
        "provider": "gemini",
        "snapshot": "gemini-2.5-flash"
    }
]

matrix = []
run_idx = 1
for i, task_id in enumerate(task_dirs):
    if i < 20:
        track = "track_1_core_frameworks"
    elif i < 32:
        track = "track_2_scientific_computing"
    else:
        track = "track_3_ai_ml_systems"

    s1, s2 = (42, 100) if i % 2 == 0 else (100, 42)
    clean_task = task_id[:16]

    # run 1: LOCAL_MODEL
    matrix.append({
        "run_index": run_idx,
        "task_id": task_id,
        "track": track,
        "model_config_id": models[0]["config_id"],
        "model_id": models[0]["model_id"],
        "provider": models[0]["provider"],
        "model_snapshot": models[0]["snapshot"],
        "seed": s1,
        "temperature": 0.2,
        "max_turns": 8,
        "run_id": f"emp100_{clean_task}_local_model_s{s1}"
    })
    run_idx += 1

    # run 2: CLOUD_MODEL_B
    matrix.append({
        "run_index": run_idx,
        "task_id": task_id,
        "track": track,
        "model_config_id": models[1]["config_id"],
        "model_id": models[1]["model_id"],
        "provider": models[1]["provider"],
        "model_snapshot": models[1]["snapshot"],
        "seed": s2,
        "temperature": 0.2,
        "max_turns": 8,
        "run_id": f"emp100_{clean_task}_cloud_model_b_s{s2}"
    })
    run_idx += 1

assert len(matrix) == 100
(v2_dir / "execution_matrix.json").write_text(json.dumps(matrix, indent=2), encoding="utf-8")

m_counts = Counter(r["model_config_id"] for r in matrix)
s_counts = Counter(r["seed"] for r in matrix)
t_counts = Counter(r["track"] for r in matrix)
print("Matrix counts:", dict(m_counts))
print("Seed counts:", dict(s_counts))
print("Track counts:", dict(t_counts))
print("empirical_100_v2 files created successfully!")
