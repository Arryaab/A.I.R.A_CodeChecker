from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from aegis.research.agent.loop import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

AUTHORITATIVE_QWEN_DIGEST = "dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364"
EXPECTED_TOOLS = ["list_files", "read_file", "write_file", "edit_file", "run_tests", "finish"]


@dataclass
class ValidationReport:
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    matrix_summary: Dict[str, Any] = field(default_factory=dict)


class SemanticProtocolValidator:
    """Validates semantic consistency across protocol specifications, manifests, and execution matrices."""

    def __init__(
        self,
        experiment_id: str = "empirical_100_v1",
        protocol_dir: Optional[Path] = None,
        study_dir: Optional[Path] = None,
        benchmark_dir: Optional[Path] = None,
    ):
        self.experiment_id = experiment_id
        self.protocol_dir = protocol_dir or Path(f"experiments/protocols/{experiment_id}")
        self.study_dir = study_dir or Path(experiment_id)
        self.benchmark_dir = benchmark_dir or Path("benchmarks/v1")

    def generate_authoritative_execution_matrix(self) -> List[Dict[str, Any]]:
        """Generates the mathematically explicit 100-run matrix matching sampling.yaml."""
        task_dirs = sorted([d.name for d in self.benchmark_dir.glob("task_*") if d.is_dir()])
        if len(task_dirs) != 50:
            raise ValueError(f"Expected 50 tasks in {self.benchmark_dir}, found {len(task_dirs)}")

        track1_tasks = task_dirs[:20]   # task_001 to task_020 (Core Frameworks)
        track2_tasks = task_dirs[20:32]  # task_021 to task_032 (Scientific Computing)
        track3_tasks = task_dirs[32:50]  # task_033 to task_050 (AI/ML Systems)

        if self.experiment_id == "empirical_100_local_v1":
            matrix: List[Dict[str, Any]] = []
            run_idx = 1
            for i, task_id in enumerate(task_dirs):
                if i < 20:
                    track = "track_1_core_frameworks"
                elif i < 32:
                    track = "track_2_scientific_computing"
                else:
                    track = "track_3_ai_ml_systems"

                clean_task = task_id[:16]

                for s in (42, 100):
                    matrix.append({
                        "run_index": run_idx,
                        "task_id": task_id,
                        "track": track,
                        "model_config_id": "LOCAL_MODEL",
                        "model_id": "qwen2.5-coder:latest",
                        "provider": "ollama",
                        "model_snapshot": AUTHORITATIVE_QWEN_DIGEST,
                        "seed": s,
                        "temperature": 0.2,
                        "max_turns": 8,
                        "run_id": f"emp100_{clean_task}_local_model_s{s}",
                    })
                    run_idx += 1

            assert len(matrix) == 100, f"Expected 100 runs, got {len(matrix)}"
            return matrix

        if self.experiment_id in ("empirical_100_v2", "empirical_100_v3"):
            model_specs = {
                "LOCAL_MODEL": {
                    "config_id": "LOCAL_MODEL",
                    "model_id": "qwen2.5-coder:latest",
                    "provider": "ollama",
                    "snapshot": AUTHORITATIVE_QWEN_DIGEST,
                },
                "CLOUD_MODEL_B": {
                    "config_id": "CLOUD_MODEL_B",
                    "model_id": "gemini-2.5-flash",
                    "provider": "gemini",
                    "snapshot": "gemini-2.5-flash",
                },
            }
            matrix: List[Dict[str, Any]] = []
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

                matrix.append({
                    "run_index": run_idx,
                    "task_id": task_id,
                    "track": track,
                    "model_config_id": "LOCAL_MODEL",
                    "model_id": model_specs["LOCAL_MODEL"]["model_id"],
                    "provider": model_specs["LOCAL_MODEL"]["provider"],
                    "model_snapshot": model_specs["LOCAL_MODEL"]["snapshot"],
                    "seed": s1,
                    "temperature": 0.2,
                    "max_turns": 8,
                    "run_id": f"emp100_{clean_task}_local_model_s{s1}",
                })
                run_idx += 1

                matrix.append({
                    "run_index": run_idx,
                    "task_id": task_id,
                    "track": track,
                    "model_config_id": "CLOUD_MODEL_B",
                    "model_id": model_specs["CLOUD_MODEL_B"]["model_id"],
                    "provider": model_specs["CLOUD_MODEL_B"]["provider"],
                    "model_snapshot": model_specs["CLOUD_MODEL_B"]["snapshot"],
                    "seed": s2,
                    "temperature": 0.2,
                    "max_turns": 8,
                    "run_id": f"emp100_{clean_task}_cloud_model_b_s{s2}",
                })
                run_idx += 1

            assert len(matrix) == 100, f"Expected 100 runs, got {len(matrix)}"
            return matrix

        model_specs = {
            "LOCAL_MODEL": {
                "config_id": "LOCAL_MODEL",
                "model_id": "qwen2.5-coder:latest",
                "provider": "ollama",
                "snapshot": AUTHORITATIVE_QWEN_DIGEST,
            },
            "CLOUD_MODEL_A": {
                "config_id": "CLOUD_MODEL_A",
                "model_id": "gpt-4o-mini-2024-07-18",
                "provider": "openai",
                "snapshot": "gpt-4o-mini-2024-07-18",
            },
            "CLOUD_MODEL_B": {
                "config_id": "CLOUD_MODEL_B",
                "model_id": "gemini-1.5-flash-002",
                "provider": "gemini",
                "snapshot": "gemini-1.5-flash-002",
            },
        }

        matrix: List[Dict[str, Any]] = []
        run_idx = 1

        # Track 1: paired ["LOCAL_MODEL", "CLOUD_MODEL_A"]
        for i, task_id in enumerate(track1_tasks):
            s1, s2 = (42, 100) if i % 2 == 0 else (100, 42)
            for m_key, s in [("LOCAL_MODEL", s1), ("CLOUD_MODEL_A", s2)]:
                m = model_specs[m_key]
                clean_task = task_id[:16]
                clean_model = m["config_id"].lower()
                matrix.append({
                    "run_index": run_idx,
                    "task_id": task_id,
                    "track": "track_1_core_frameworks",
                    "model_config_id": m["config_id"],
                    "model_id": m["model_id"],
                    "provider": m["provider"],
                    "model_snapshot": m["snapshot"],
                    "seed": s,
                    "temperature": 0.2,
                    "max_turns": 8,
                    "run_id": f"emp100_{clean_task}_{clean_model}_s{s}",
                })
                run_idx += 1

        # Track 2: paired ["LOCAL_MODEL", "CLOUD_MODEL_B"]
        for i, task_id in enumerate(track2_tasks):
            s1, s2 = (42, 100) if i % 2 == 0 else (100, 42)
            for m_key, s in [("LOCAL_MODEL", s1), ("CLOUD_MODEL_B", s2)]:
                m = model_specs[m_key]
                clean_task = task_id[:16]
                clean_model = m["config_id"].lower()
                matrix.append({
                    "run_index": run_idx,
                    "task_id": task_id,
                    "track": "track_2_scientific_computing",
                    "model_config_id": m["config_id"],
                    "model_id": m["model_id"],
                    "provider": m["provider"],
                    "model_snapshot": m["snapshot"],
                    "seed": s,
                    "temperature": 0.2,
                    "max_turns": 8,
                    "run_id": f"emp100_{clean_task}_{clean_model}_s{s}",
                })
                run_idx += 1

        # Track 3: paired ["CLOUD_MODEL_A", "CLOUD_MODEL_B"]
        for i, task_id in enumerate(track3_tasks):
            s1, s2 = (42, 100) if i % 2 == 0 else (100, 42)
            for m_key, s in [("CLOUD_MODEL_A", s1), ("CLOUD_MODEL_B", s2)]:
                m = model_specs[m_key]
                clean_task = task_id[:16]
                clean_model = m["config_id"].lower()
                matrix.append({
                    "run_index": run_idx,
                    "task_id": task_id,
                    "track": "track_3_ai_ml_systems",
                    "model_config_id": m["config_id"],
                    "model_id": m["model_id"],
                    "provider": m["provider"],
                    "model_snapshot": m["snapshot"],
                    "seed": s,
                    "temperature": 0.2,
                    "max_turns": 8,
                    "run_id": f"emp100_{clean_task}_{clean_model}_s{s}",
                })
                run_idx += 1

        assert len(matrix) == 100, f"Expected 100 runs, got {len(matrix)}"
        return matrix

    def validate(self) -> ValidationReport:
        errors: List[str] = []
        warnings: List[str] = []

        # 1. Verify protocol files existence
        expected_proto_files = [
            "experiment.yaml",
            "models.yaml",
            "sampling.yaml",
            "agent_policy.yaml",
            "verification.yaml",
            "analysis.yaml",
            "protocol_hashes.json",
        ]
        for pf in expected_proto_files:
            p = self.protocol_dir / pf
            if not p.exists():
                errors.append(f"Missing protocol file: {p}")

        if errors:
            return ValidationReport(is_valid=False, errors=errors, warnings=warnings)

        # 2. Cryptographic Protocol Hashes Check
        try:
            proto_hashes = json.loads((self.protocol_dir / "protocol_hashes.json").read_text(encoding="utf-8"))
            for fname, expected_hash in proto_hashes.items():
                fpath = self.protocol_dir / fname
                if not fpath.exists():
                    errors.append(f"Protocol file {fname} listed in hashes does not exist")
                    continue
                actual_hash = f"sha256:{hashlib.sha256(fpath.read_bytes()).hexdigest()}"
                if actual_hash != expected_hash:
                    errors.append(f"Cryptographic hash mismatch for protocol file {fname}: expected {expected_hash}, got {actual_hash}")
        except Exception as e:
            errors.append(f"Failed to verify protocol hashes: {e}")

        # 3. Load Protocol YAMLs
        try:
            exp_yaml = yaml.safe_load((self.protocol_dir / "experiment.yaml").read_text(encoding="utf-8"))
            models_yaml = yaml.safe_load((self.protocol_dir / "models.yaml").read_text(encoding="utf-8"))
            sampling_yaml = yaml.safe_load((self.protocol_dir / "sampling.yaml").read_text(encoding="utf-8"))
            policy_yaml = yaml.safe_load((self.protocol_dir / "agent_policy.yaml").read_text(encoding="utf-8"))
            verif_yaml = yaml.safe_load((self.protocol_dir / "verification.yaml").read_text(encoding="utf-8"))
        except Exception as e:
            errors.append(f"Failed to parse protocol YAML files: {e}")
            return ValidationReport(is_valid=False, errors=errors, warnings=warnings)

        # 4. Load Manifest Files
        manifest_file = self.study_dir / "manifest.json"
        model_manifest_file = self.study_dir / "model_manifest.json"
        matrix_file = self.study_dir / "execution_matrix.json"

        if not manifest_file.exists():
            errors.append(f"Missing experiment manifest: {manifest_file}")
        if not model_manifest_file.exists():
            errors.append(f"Missing model manifest: {model_manifest_file}")

        if errors:
            return ValidationReport(is_valid=False, errors=errors, warnings=warnings)

        try:
            manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
            model_manifest_data = json.loads(model_manifest_file.read_text(encoding="utf-8"))
        except Exception as e:
            errors.append(f"Failed to parse study manifests: {e}")
            return ValidationReport(is_valid=False, errors=errors, warnings=warnings)

        # 5. Check Total Runs & Task Count
        proto_total_runs = exp_yaml.get("total_planned_runs", 0)
        sampling_total_runs = sampling_yaml.get("sampling_plan", {}).get("total_runs", 0)
        manifest_total_runs = manifest_data.get("total_runs", 0)

        if proto_total_runs != 100:
            errors.append(f"experiment.yaml total_planned_runs is {proto_total_runs}, expected 100")
        if sampling_total_runs != 100:
            errors.append(f"sampling.yaml total_runs is {sampling_total_runs}, expected 100")
        if manifest_total_runs != 100:
            errors.append(f"manifest.json total_runs is {manifest_total_runs}, expected 100")

        sampling_tasks = sampling_yaml.get("sampling_plan", {}).get("tasks_covered", 0)
        manifest_tasks = manifest_data.get("sampling_design", {}).get("tasks_selected", 0)
        if sampling_tasks != 50 or manifest_tasks != 50:
            errors.append(f"Task count mismatch: sampling says {sampling_tasks}, manifest says {manifest_tasks}")

        # 6. Check Temperatures & Max Turns
        sampling_temp = sampling_yaml.get("execution_parameters", {}).get("temperatures", {}).get("default")
        manifest_temp = manifest_data.get("sampling_design", {}).get("temperature")
        if sampling_temp != 0.2:
            errors.append(f"sampling.yaml default temperature is {sampling_temp}, expected 0.2")
        if manifest_temp != 0.2:
            errors.append(f"manifest.json temperature is {manifest_temp}, expected 0.2")

        sampling_max_turns = sampling_yaml.get("execution_parameters", {}).get("max_turns")
        policy_turns = policy_yaml.get("iteration_budget")
        manifest_max_turns = manifest_data.get("sampling_design", {}).get("max_turns")
        if sampling_max_turns != 8:
            errors.append(f"sampling.yaml max_turns is {sampling_max_turns}, expected 8")
        if policy_turns != 8:
            errors.append(f"agent_policy.yaml iteration_budget is {policy_turns}, expected 8")
        if manifest_max_turns != 8:
            errors.append(f"manifest.json max_turns is {manifest_max_turns}, expected 8")

        # 7. Check Tool Set & Schemas
        policy_tools = [t.get("name") for t in policy_yaml.get("tools", [])]
        manifest_tools = manifest_data.get("invariants_and_controls", {}).get("tool_set", [])
        if sorted(policy_tools) != sorted(EXPECTED_TOOLS):
            errors.append(f"agent_policy.yaml tools {policy_tools} != expected {EXPECTED_TOOLS}")
        if sorted(manifest_tools) != sorted(EXPECTED_TOOLS):
            errors.append(f"manifest.json tools {manifest_tools} != expected {EXPECTED_TOOLS}")

        # 8. Check System Prompt and Policy Hashes
        py_sp_hash = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()
        yaml_sp = policy_yaml.get("system_prompt", "")
        yaml_sp_hash = hashlib.sha256(yaml_sp.encode("utf-8")).hexdigest()
        manifest_sp_hash = manifest_data.get("invariants_and_controls", {}).get("system_prompt_hash")

        if py_sp_hash != yaml_sp_hash:
            errors.append(f"SYSTEM_PROMPT in loop.py hash ({py_sp_hash}) != agent_policy.yaml hash ({yaml_sp_hash})")
        if manifest_sp_hash != yaml_sp_hash:
            errors.append(f"manifest.json system_prompt_hash ({manifest_sp_hash}) != agent_policy.yaml hash ({yaml_sp_hash})")

        # 9. Check Model Definitions & Authoritative Qwen Digest
        models_list = models_yaml.get("models", [])
        qwen_model_yaml = next((m for m in models_list if m.get("id") == "local_qwen_coder_7b"), None)
        if not qwen_model_yaml:
            errors.append("local_qwen_coder_7b missing from models.yaml")
        else:
            q_yaml_digest = qwen_model_yaml.get("immutable_identifier")
            if q_yaml_digest != AUTHORITATIVE_QWEN_DIGEST:
                errors.append(f"models.yaml Qwen digest mismatch: {q_yaml_digest} != {AUTHORITATIVE_QWEN_DIGEST}")

        if self.experiment_id != "empirical_100_local_v1":
            gemini_model_yaml = next((m for m in models_list if m.get("id") == "cloud_google_gemini_flash"), None)
            if not gemini_model_yaml:
                errors.append("cloud_google_gemini_flash missing from models.yaml")

            if self.experiment_id == "empirical_100_v1":
                openai_model_yaml = next((m for m in models_list if m.get("id") == "cloud_openai_gpt4o_mini"), None)
                if not openai_model_yaml:
                    errors.append("cloud_openai_gpt4o_mini missing from models.yaml")

        manifest_models = model_manifest_data.get("models", {})
        qwen_manifest = manifest_models.get("LOCAL_MODEL", {})
        q_manifest_digest = qwen_manifest.get("snapshot_id")
        if q_manifest_digest != AUTHORITATIVE_QWEN_DIGEST:
            errors.append(f"model_manifest.json Qwen digest mismatch: {q_manifest_digest} != {AUTHORITATIVE_QWEN_DIGEST}")

        if self.experiment_id != "empirical_100_local_v1":
            if "CLOUD_MODEL_B" not in manifest_models:
                errors.append("CLOUD_MODEL_B missing from model_manifest.json")

            if self.experiment_id == "empirical_100_v1":
                if "CLOUD_MODEL_A" not in manifest_models:
                    errors.append("CLOUD_MODEL_A missing from model_manifest.json")

        # 10. Validate Execution Matrix
        if matrix_file.exists():
            try:
                matrix = json.loads(matrix_file.read_text(encoding="utf-8"))
            except Exception as e:
                errors.append(f"Failed to read execution_matrix.json: {e}")
                matrix = []
        else:
            # Auto-generate matrix
            matrix = self.generate_authoritative_execution_matrix()
            matrix_file.write_text(json.dumps(matrix, indent=2), encoding="utf-8")

        if len(matrix) != 100:
            errors.append(f"Execution matrix has {len(matrix)} runs, expected 100")

        # Verify matrix allocation semantics
        m_counts = Counter(r["model_config_id"] for r in matrix)
        s_counts = Counter(r["seed"] for r in matrix)
        t_counts = Counter(r["track"] for r in matrix)
        tasks_in_matrix = Counter(r["task_id"] for r in matrix)

        if len(tasks_in_matrix) != 50:
            errors.append(f"Execution matrix covers {len(tasks_in_matrix)} tasks, expected 50")
        for tid, cnt in tasks_in_matrix.items():
            if cnt != 2:
                errors.append(f"Task {tid} has {cnt} runs in matrix, expected exactly 2")

        if s_counts[42] != 50 or s_counts[100] != 50:
            errors.append(f"Seed distribution not 50/50: {s_counts}")

        if self.experiment_id == "empirical_100_local_v1":
            if m_counts["LOCAL_MODEL"] != 100:
                errors.append(f"LOCAL_MODEL count {m_counts['LOCAL_MODEL']} != 100")
        elif self.experiment_id in ("empirical_100_v2", "empirical_100_v3"):
            if m_counts["LOCAL_MODEL"] != 50:
                errors.append(f"LOCAL_MODEL count {m_counts['LOCAL_MODEL']} != 50")
            if m_counts["CLOUD_MODEL_B"] != 50:
                errors.append(f"CLOUD_MODEL_B count {m_counts['CLOUD_MODEL_B']} != 50")
        else:
            if m_counts["LOCAL_MODEL"] != 32:
                errors.append(f"LOCAL_MODEL count {m_counts['LOCAL_MODEL']} != 32")
            if m_counts["CLOUD_MODEL_A"] != 38:
                errors.append(f"CLOUD_MODEL_A count {m_counts['CLOUD_MODEL_A']} != 38")
            if m_counts["CLOUD_MODEL_B"] != 30:
                errors.append(f"CLOUD_MODEL_B count {m_counts['CLOUD_MODEL_B']} != 30")

        if t_counts["track_1_core_frameworks"] != 40:
            errors.append(f"Track 1 runs {t_counts['track_1_core_frameworks']} != 40")
        if t_counts["track_2_scientific_computing"] != 24:
            errors.append(f"Track 2 runs {t_counts['track_2_scientific_computing']} != 24")
        if t_counts["track_3_ai_ml_systems"] != 36:
            errors.append(f"Track 3 runs {t_counts['track_3_ai_ml_systems']} != 36")

        # 11. Check Runner File (No fake adapters, no hardcoded divergence)
        runner_file = Path("scripts/run_empirical_100.py")
        if runner_file.exists():
            runner_code = runner_file.read_text(encoding="utf-8")
            if "StandardizedCloudAdapter" in runner_code:
                errors.append("StandardizedCloudAdapter detected in scripts/run_empirical_100.py! Must be removed.")
            if "dae161e27b0e90dd1856c8bb38de08465b871c504ca07d643912ca68d4ea547e" in runner_code:
                errors.append("Typo Qwen digest detected in scripts/run_empirical_100.py!")

        matrix_summary = {
            "total_runs": len(matrix),
            "model_counts": dict(m_counts),
            "seed_counts": dict(s_counts),
            "track_counts": dict(t_counts),
            "temperature": 0.2,
            "max_turns": 8,
            "qwen_digest": AUTHORITATIVE_QWEN_DIGEST,
        }

        return ValidationReport(
            is_valid=(len(errors) == 0),
            errors=errors,
            warnings=warnings,
            matrix_summary=matrix_summary,
        )


def validate_semantic_protocol(study_id: str = "empirical_100_v1") -> Tuple[bool, List[str]]:
    validator = SemanticProtocolValidator(experiment_id=study_id)
    report = validator.validate()
    return report.is_valid, report.errors
