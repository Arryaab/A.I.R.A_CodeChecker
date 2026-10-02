"""
Setup script for empirical_100_local_v1 protocol and study structure.
Per Founder Directive: Local-First Empirical Execution.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from pathlib import Path

sys.path.insert(0, str(Path(".").resolve()))

EXPERIMENT_ID = "empirical_100_local_v1"
AUTHORITATIVE_QWEN_DIGEST = "dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364"
BENCHMARK_DIR = Path("benchmarks/v1")
PROTO_DIR = Path(f"experiments/protocols/{EXPERIMENT_ID}")
STUDY_DIR = Path(EXPERIMENT_ID)


def setup_protocol():
    PROTO_DIR.mkdir(parents=True, exist_ok=True)

    # 1. experiment.yaml
    exp_yaml = f"""protocol_id: "{EXPERIMENT_ID}"
protocol_version: "1.0.0"
benchmark_version: "AegisBench-v1"
benchmark_lock_file: "AegisBench-v1.lock.json"
total_planned_runs: 100
provider_scope: "LOCAL_OLLAMA_ONLY"
model_scope: "qwen2.5-coder"
external_provider_dependency: "NONE"
network_dependency: "NONE_FOR_PRIMARY_MODEL_EXECUTION"
cost_model: "LOCAL_ZERO_COST"

execution:
  backend: "persistent_worker_pool"
  max_concurrent_workers: 1
  worker_timeout_seconds: 120.0
  turn_timeout_seconds: 45.0

retry_policy:
  max_retries: 1
  allowed_failure_types:
    - "WORKER_STARTUP_FAILURE"
    - "WORKER_CRASH"
    - "WORKER_TIMEOUT"
    - "ENVIRONMENT_FAILURE"
    - "LOCAL_PROVIDER_TIMEOUT"
  disallowed_failure_types:
    - "MODEL_FAILURE"
    - "AGENT_FAILURE"
    - "PATCH_FAILURE"
    - "ORACLE_FAILURE"
    - "AEGIS_FAILURE"
    - "LOCAL_PROVIDER_UNAVAILABLE"
  preserve_failed_attempt: true
  retry_trace_linkage: true

cancellation_policy:
  stop_on_integrity_violation: true
  stop_on_benchmark_hash_mismatch: true
  stop_on_schema_drift: true
  stop_on_oracle_crash_rate_threshold: 0.05
  stop_on_worker_isolation_leak: true
  stop_on_provider_unavailable: true

environment_requirements:
  python_version: ">=3.10"
  virtual_environment_required: true
  clean_environment_enforced: true
  prohibited_env_keys:
    - "AEGIS_API_KEY"
    - "GEMINI_API_KEY"
    - "OPENAI_API_KEY"
    - "ANTHROPIC_API_KEY"
    - "AWS_ACCESS_KEY_ID"
    - "AWS_SECRET_ACCESS_KEY"
    - "GITHUB_TOKEN"
    - "GIT_TOKEN"
"""
    (PROTO_DIR / "experiment.yaml").write_text(exp_yaml, encoding="utf-8")

    # 2. models.yaml
    models_yaml = f"""models:
  - id: "local_qwen_coder_7b"
    provider: "ollama"
    model_name: "qwen2.5-coder:latest"
    immutable_identifier: "{AUTHORITATIVE_QWEN_DIGEST}"
    reproducibility: "IMMUTABLE_DIGEST"
    required: true
    capabilities:
      supports_tools: true
      supports_system_prompt: true
      supports_seed: true
      supports_temperature: true
      supports_token_accounting: true
      supports_deterministic_sampling: true
    seed_semantics:
      seed_supported: true
      seed_parameter: "seed"
      behavior: "deterministic_per_digest"
    temperature_semantics:
      temperature_supported: true
      parameter: "temperature"
      default: 0.2

optional_providers:
  - id: "cloud_google_gemini_flash"
    provider: "google"
    model_name: "gemini-2.5-flash"
    required: false
  - id: "cloud_openai_gpt4o_mini"
    provider: "openai"
    model_name: "gpt-4o-mini-2024-07-18"
    required: false
"""
    (PROTO_DIR / "models.yaml").write_text(models_yaml, encoding="utf-8")

    # 3. sampling.yaml
    sampling_yaml = """sampling_plan:
  total_runs: 100
  tasks_covered: 50
  runs_per_task: 2

allocation_strategy:
  description: "100-run local-only empirical evaluation of Aegis Core 1.0 against Qwen2.5-Coder across all 50 AegisBench-v1 tasks with balanced seeds 42 and 100"
  model_pairing_rule:
    track_1_core_frameworks:
      tasks: 20
      models: ["local_qwen_coder_7b"]
      seeds: [42, 100]
    track_2_scientific_computing:
      tasks: 12
      models: ["local_qwen_coder_7b"]
      seeds: [42, 100]
    track_3_ai_ml_systems:
      tasks: 18
      models: ["local_qwen_coder_7b"]
      seeds: [42, 100]

execution_parameters:
  max_turns: 8
  temperatures:
    default: 0.2
    exploration: 0.0
  seed_candidates: [42, 100]
  seed_allocation:
    seed_42_runs: 50
    seed_100_runs: 50
"""
    (PROTO_DIR / "sampling.yaml").write_text(sampling_yaml, encoding="utf-8")

    # 4. agent_policy.yaml (copy from v3)
    v3_policy = Path("experiments/protocols/empirical_100_v3/agent_policy.yaml").read_text(encoding="utf-8")
    (PROTO_DIR / "agent_policy.yaml").write_text(v3_policy, encoding="utf-8")

    # 5. verification.yaml (copy from v3)
    v3_verif = Path("experiments/protocols/empirical_100_v3/verification.yaml").read_text(encoding="utf-8")
    (PROTO_DIR / "verification.yaml").write_text(v3_verif, encoding="utf-8")

    # 6. analysis.yaml
    analysis_yaml = f"""pre_registered_analysis:
  study_id: "{EXPERIMENT_ID}"
  registration_status: "FROZEN_PRE_EXECUTION"

primary_outcomes:
  - metric: "oracle_pass_at_1"
    definition: "Fraction of candidate solutions passing the independent ground-truth oracle on first attempt."
    formula: "sum(oracle_evaluation.oracle_verdict == 'CORRECT') / total_completed_runs"
  - metric: "bad_patch_escape_rate_c2"
    definition: "Fraction of oracle-defective patches accepted by visible CI (C2)."
    formula: "sum(accepted.C2_visible_tests == 1 and targets.is_defective == 1) / sum(targets.is_defective == 1)"
  - metric: "bad_patch_escape_rate_c6"
    definition: "Fraction of oracle-defective patches accepted by Aegis Core 1.0 release policy (C6 AUTO_APPROVE)."
    formula: "sum(aegis_verification.release_policy == 'AUTO_APPROVE' and oracle_evaluation.oracle_verdict == 'DEFECTIVE') / sum(targets.is_defective == 1)"
  - metric: "false_acceptance_rate"
    definition: "Fraction of oracle-defective patches erroneously given AUTO_APPROVE release policy."
    formula: "sum(aegis_verification.release_policy == 'AUTO_APPROVE' and oracle_evaluation.oracle_verdict == 'DEFECTIVE') / sum(targets.is_defective == 1)"
  - metric: "false_rejection_rate"
    definition: "Fraction of oracle-correct patches erroneously given BLOCK release policy."
    formula: "sum(aegis_verification.release_policy == 'BLOCK' and oracle_evaluation.oracle_verdict == 'CORRECT') / sum(targets.is_defective == 0)"

secondary_outcomes:
  - metric: "median_agent_duration_seconds"
    aggregation: "median"
  - metric: "median_total_tokens"
    aggregation: "median"
  - metric: "tier_progression_attrition"
    definition: "Drop-off rates across C1 -> C2 -> C3 -> C4 -> C5 -> C6"

ablation_configurations:
  - "C1_agent_only"
  - "C2_visible_ci"
  - "C3_hidden_tests"
  - "C4_regression"
  - "C5_mutation"
  - "C6_full_aegis"

decision_semantics:
  technical_verdict_vocabulary:
    - "QUALIFIED"
    - "QUALIFIED_WITHIN_SCOPE"
    - "FAILED"
    - "INDETERMINATE"
  release_policy_vocabulary:
    - "AUTO_APPROVE"
    - "REVIEW"
    - "BLOCK"

missing_data_policy:
  silent_drops_allowed: false
  failed_runs_retained: true
  dataset_admission_required: true
"""
    (PROTO_DIR / "analysis.yaml").write_text(analysis_yaml, encoding="utf-8")

    # 7. README.md
    readme = f"""# Protocol: {EXPERIMENT_ID}

## Status: IMMUTABLE & FROZEN PRE-EXECUTION

This protocol governs the authoritative zero-cost empirical study of Aegis Core 1.0.

### Experimental Design:
- **Total Runs**: 100
- **Unique Tasks**: 50 AegisBench-v1 tasks
- **Runs per Task**: 2
- **Provider**: Ollama (Local)
- **Model**: `qwen2.5-coder:latest` (Immutable Digest: `{AUTHORITATIVE_QWEN_DIGEST}`)
- **Seeds**: 42 (50 runs), 100 (50 runs)
- **Temperature**: 0.2
- **Max Iterations**: 8 turns
- **Zero Cloud Quota Dependency**: Primary empirical research requires $0 expenditure and operates locally.
"""
    (PROTO_DIR / "README.md").write_text(readme, encoding="utf-8")

    # 8. protocol_hashes.json
    proto_hashes = {}
    for p in sorted(PROTO_DIR.glob("*")):
        if p.name == "protocol_hashes.json":
            continue
        proto_hashes[p.name] = f"sha256:{hashlib.sha256(p.read_bytes()).hexdigest()}"

    (PROTO_DIR / "protocol_hashes.json").write_text(json.dumps(proto_hashes, indent=2), encoding="utf-8")
    print(f"Protocol created at {PROTO_DIR} with {len(proto_hashes)} hashed files.")


def setup_study():
    for sub in ("raw", "traces", "derived", "reports", "metrics", "failures", "integrity"):
        (STUDY_DIR / sub).mkdir(parents=True, exist_ok=True)

    task_dirs = sorted([d.name for d in BENCHMARK_DIR.glob("task_*") if d.is_dir()])
    assert len(task_dirs) == 50, f"Expected 50 tasks, found {len(task_dirs)}"

    matrix = []
    run_idx = 1
    for i, task_id in enumerate(task_dirs):
        if i < 20:
            track = "track_1_core_frameworks"
        elif i < 32:
            track = "track_2_scientific_computing"
        else:
            track = "track_3_ai_ml_systems"

        clean_task = task_id[:16]

        # First run: seed 42
        matrix.append({
            "run_index": run_idx,
            "task_id": task_id,
            "track": track,
            "model_config_id": "LOCAL_MODEL",
            "model_id": "qwen2.5-coder:latest",
            "provider": "ollama",
            "model_snapshot": AUTHORITATIVE_QWEN_DIGEST,
            "seed": 42,
            "temperature": 0.2,
            "max_turns": 8,
            "run_id": f"emp100_{clean_task}_local_model_s42",
        })
        run_idx += 1

        # Second run: seed 100
        matrix.append({
            "run_index": run_idx,
            "task_id": task_id,
            "track": track,
            "model_config_id": "LOCAL_MODEL",
            "model_id": "qwen2.5-coder:latest",
            "provider": "ollama",
            "model_snapshot": AUTHORITATIVE_QWEN_DIGEST,
            "seed": 100,
            "temperature": 0.2,
            "max_turns": 8,
            "run_id": f"emp100_{clean_task}_local_model_s100",
        })
        run_idx += 1

    assert len(matrix) == 100, f"Expected 100 runs, got {len(matrix)}"
    (STUDY_DIR / "execution_matrix.json").write_text(json.dumps(matrix, indent=2), encoding="utf-8")

    # manifest.json
    v3_policy = Path("experiments/protocols/empirical_100_v3/agent_policy.yaml").read_text(encoding="utf-8")
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "benchmark_version": "AegisBench-v1",
        "benchmark_manifest_hash": "sha256:78fcca20228154bfb3b37d7c8bb0cec6aa3a459759297cbd6969ce031293b2a5",
        "total_runs": 100,
        "sampling_design": {
            "tasks_selected": 50,
            "runs_per_task": 2,
            "seeds": [42, 100],
            "temperature": 0.2,
            "max_turns": 8,
            "provider_scope": "LOCAL_OLLAMA_ONLY",
            "model_scope": "qwen2.5-coder",
            "cost_model": "LOCAL_ZERO_COST",
        },
        "invariants_and_controls": {
            "tool_set": ["list_files", "read_file", "write_file", "edit_file", "run_tests", "finish"],
            "system_prompt_hash": hashlib.sha256(Path("experiments/protocols/empirical_100_v3/agent_policy.yaml").read_text(encoding="utf-8").split("system_prompt: |")[1].strip().split("\n\ntools:")[0].strip().encode("utf-8")).hexdigest() if False else hashlib.sha256(v3_policy.encode("utf-8")).hexdigest(),
        },
    }

    # Fetch exact system prompt hash from python loop
    from aegis.research.agent.loop import SYSTEM_PROMPT
    manifest["invariants_and_controls"]["system_prompt_hash"] = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()

    (STUDY_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # model_manifest.json
    model_manifest = {
        "models": {
            "LOCAL_MODEL": {
                "config_id": "LOCAL_MODEL",
                "model_id": "qwen2.5-coder:latest",
                "provider": "ollama",
                "snapshot_id": AUTHORITATIVE_QWEN_DIGEST,
                "reproducibility": "IMMUTABLE_DIGEST",
                "required": True,
            }
        },
        "optional_models": {
            "CLOUD_MODEL_B": {
                "config_id": "CLOUD_MODEL_B",
                "model_id": "gemini-2.5-flash",
                "provider": "gemini",
                "snapshot_id": "gemini-2.5-flash",
                "required": False,
            }
        }
    }
    (STUDY_DIR / "model_manifest.json").write_text(json.dumps(model_manifest, indent=2), encoding="utf-8")

    # environment_manifest.json
    env_manifest = {
        "experiment_id": EXPERIMENT_ID,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "arch": platform.machine(),
        "ollama_endpoint": "http://localhost:11434",
        "authoritative_qwen_digest": AUTHORITATIVE_QWEN_DIGEST,
    }
    (STUDY_DIR / "environment_manifest.json").write_text(json.dumps(env_manifest, indent=2), encoding="utf-8")

    # benchmark_lock.json
    lock_data = json.loads(Path("AegisBench-v1.lock.json").read_text(encoding="utf-8"))
    (STUDY_DIR / "benchmark_lock.json").write_text(json.dumps(lock_data, indent=2), encoding="utf-8")

    print(f"Study manifests created at {STUDY_DIR}.")


if __name__ == "__main__":
    setup_protocol()
    setup_study()
