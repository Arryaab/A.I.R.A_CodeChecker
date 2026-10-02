from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from aegis.research.trace.schema import ResearchTrace, validate_research_trace


@dataclass
class ExperimentManifest:
    experiment_id: str
    created_at: str
    tasks: List[str]
    model_configs: List[Dict[str, Any]]
    seeds: List[int]
    total_expected_runs: int
    completed_runs: List[str] = field(default_factory=list)
    failed_runs: List[str] = field(default_factory=list)
    status: str = "IN_PROGRESS"  # IN_PROGRESS, COMPLETED, INTERRUPTED
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ExperimentStorage:
    """Manages persistence, checkpointing, and resume operations for research experiments."""

    @staticmethod
    def init_experiment(
        exp_dir: Path,
        experiment_id: str,
        tasks: List[str],
        model_configs: List[Dict[str, Any]],
        seeds: List[int],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExperimentManifest:
        exp_dir = Path(exp_dir).resolve()
        exp_dir.mkdir(parents=True, exist_ok=True)
        (exp_dir / "runs").mkdir(parents=True, exist_ok=True)

        manifest_file = exp_dir / "manifest.json"
        if manifest_file.exists():
            existing = ExperimentStorage.load_manifest(exp_dir)
            if existing.status == "COMPLETED":
                raise PermissionError(f"Experiment '{experiment_id}' in {exp_dir} is COMPLETED and cannot be re-initialized or modified.")
            if tasks:
                existing.tasks = tasks
            if model_configs:
                existing.model_configs = model_configs
            if seeds:
                existing.seeds = seeds
            existing.total_expected_runs = len(existing.tasks) * len(existing.model_configs) * len(existing.seeds)
            ExperimentStorage.save_manifest(existing, exp_dir)
            return existing

        total_runs = len(tasks) * len(model_configs) * len(seeds)
        manifest = ExperimentManifest(
            experiment_id=experiment_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            tasks=tasks,
            model_configs=model_configs,
            seeds=seeds,
            total_expected_runs=total_runs,
            completed_runs=[],
            failed_runs=[],
            status="IN_PROGRESS",
            metadata=metadata or {},
        )
        ExperimentStorage.save_manifest(manifest, exp_dir)
        return manifest

    @staticmethod
    def save_manifest(manifest: ExperimentManifest, exp_dir: Path) -> None:
        exp_dir = Path(exp_dir).resolve()
        manifest_file = exp_dir / "manifest.json"
        manifest_file.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")

    @staticmethod
    def load_manifest(exp_dir: Path) -> ExperimentManifest:
        exp_dir = Path(exp_dir).resolve()
        manifest_file = exp_dir / "manifest.json"
        if not manifest_file.exists():
            raise FileNotFoundError(f"Manifest not found in {exp_dir}")
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
        return ExperimentManifest(**data)

    @staticmethod
    def save_run_trace(trace: ResearchTrace, exp_dir: Path) -> Path:
        exp_dir = Path(exp_dir).resolve()
        runs_dir = exp_dir / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)

        manifest_file = exp_dir / "manifest.json"
        if manifest_file.exists():
            manifest = ExperimentStorage.load_manifest(exp_dir)
            if manifest.status == "COMPLETED":
                raise PermissionError(f"Cannot save run to completed experiment '{manifest.experiment_id}'.")

        trace_file = runs_dir / f"{trace.run_id}.json"
        if trace_file.exists():
            raise FileExistsError(f"Run trace '{trace.run_id}' already exists in {exp_dir} and cannot be overwritten.")

        trace_dict = trace.to_dict()
        is_valid, errors = validate_research_trace(trace_dict)
        if not is_valid:
            raise ValueError(f"Trace validation failed: {errors}")

        trace_file.write_text(json.dumps(trace_dict, indent=2), encoding="utf-8")

        # Update manifest checkpoint
        try:
            manifest = ExperimentStorage.load_manifest(exp_dir)
            if trace.run_id not in manifest.completed_runs:
                manifest.completed_runs.append(trace.run_id)
            if len(manifest.completed_runs) >= manifest.total_expected_runs:
                manifest.status = "COMPLETED"
            ExperimentStorage.save_manifest(manifest, exp_dir)
        except Exception:
            pass

        return trace_file

    @staticmethod
    def load_run_trace(trace_path: Path) -> Dict[str, Any]:
        trace_path = Path(trace_path).resolve()
        return json.loads(trace_path.read_text(encoding="utf-8"))

    @staticmethod
    def get_completed_run_ids(exp_dir: Path) -> Set[str]:
        exp_dir = Path(exp_dir).resolve()
        runs_dir = exp_dir / "runs"
        if not runs_dir.exists():
            return set()
        return {f.stem for f in runs_dir.glob("*.json")}
