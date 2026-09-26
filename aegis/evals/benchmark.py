from __future__ import annotations

import ast
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import yaml

logger = logging.getLogger(__name__)

@dataclass
class ValidationIssue:
    bug_id: str
    issue: str
    severity: str = "ERROR"

@dataclass
class BenchmarkBug:
    bug_id: str
    buggy_dir: Path
    visible_tests_dir: Path
    hidden_tests_dir: Path | None
    metadata: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)
    constraints: dict = field(default_factory=dict)
    problem_statement: str = ""
    description: str = ""
    oracle_patch_path: Path | None = None
    task_dir: Path | None = None
    private_dir: Path | None = None

class Benchmark:
    def __init__(self, name: str, bugs: list[BenchmarkBug]):
        self.name = name
        self.bugs = bugs

    @classmethod
    def load(cls, benchmark_dir: Path | str) -> Benchmark:
        """Load benchmark tasks from directory."""
        benchmark_dir = Path(benchmark_dir)
        if not benchmark_dir.exists() or not benchmark_dir.is_dir():
            raise ValueError(f"Benchmark directory not found: {benchmark_dir}")

        bugs = []
        for bug_dir in sorted(benchmark_dir.iterdir()):
            if not bug_dir.is_dir():
                continue

            if (bug_dir / "task").exists() and (bug_dir / "task").is_dir():
                # Canonical Public Workspace vs Private Evaluator Architecture
                task_dir = bug_dir / "task"
                private_dir = bug_dir / "private"

                buggy_dir = task_dir / "buggy"
                visible_tests_dir = task_dir / "tests"
                metadata_file = task_dir / "metadata.json"
                problem_file = task_dir / "problem.md"

                hidden_tests_dir = private_dir / "hidden_tests"
                provenance_file = private_dir / "provenance.json"
                constraints_file = private_dir / "constraints.yaml"
                oracle_file = private_dir / "oracle_patch.diff"
            else:
                # Flat task structure
                task_dir = bug_dir
                private_dir = bug_dir / "private" if (bug_dir / "private").exists() else bug_dir

                buggy_dir = bug_dir / "buggy"
                visible_tests_dir = bug_dir / "tests"
                metadata_file = bug_dir / "metadata.json"
                problem_file = bug_dir / "problem.md"

                hidden_tests_dir = private_dir / "hidden_tests" if (private_dir / "hidden_tests").exists() else (bug_dir / "hidden_tests")
                provenance_file = private_dir / "provenance.json" if (private_dir / "provenance.json").exists() else (bug_dir / "provenance.json")
                constraints_file = private_dir / "constraints.yaml" if (private_dir / "constraints.yaml").exists() else (bug_dir / "constraints.yaml")
                oracle_file = private_dir / "oracle_patch.diff" if (private_dir / "oracle_patch.diff").exists() else (bug_dir / "oracle_patch.diff")

            if not buggy_dir.exists() or not visible_tests_dir.exists():
                logger.warning(f"Skipping {bug_dir.name}: missing 'buggy' or 'tests' directory")
                continue

            metadata = {}
            if metadata_file.exists():
                try:
                    with open(metadata_file, "r", encoding="utf-8") as f:
                        metadata = json.load(f)
                except json.JSONDecodeError:
                    logger.warning(f"Malformed metadata.json in {bug_dir.name}")

            provenance = {}
            if provenance_file.exists():
                try:
                    with open(provenance_file, "r", encoding="utf-8") as f:
                        provenance = json.load(f)
                except json.JSONDecodeError:
                    pass

            constraints = {}
            if constraints_file.exists():
                try:
                    loaded = yaml.safe_load(constraints_file.read_text(encoding="utf-8", errors="replace"))
                    if isinstance(loaded, dict):
                        constraints = loaded
                except Exception:
                    pass

            problem_statement = ""
            if problem_file.exists():
                problem_statement = problem_file.read_text(encoding="utf-8", errors="replace")

            bug_id = metadata.get("bug_id", metadata.get("id", bug_dir.name))
            description = metadata.get("description", "")

            bugs.append(BenchmarkBug(
                bug_id=bug_id,
                buggy_dir=buggy_dir,
                visible_tests_dir=visible_tests_dir,
                hidden_tests_dir=hidden_tests_dir if hidden_tests_dir.exists() else None,
                metadata=metadata,
                provenance=provenance,
                constraints=constraints,
                problem_statement=problem_statement,
                description=description,
                oracle_patch_path=oracle_file if oracle_file.exists() else None,
                task_dir=task_dir,
                private_dir=private_dir,
            ))

        bugs.sort(key=lambda b: b.bug_id)
        return cls(name=benchmark_dir.name, bugs=bugs)

    def validate(self) -> list[ValidationIssue]:
        """Validates benchmark task integrity against canonical AegisBench schema."""
        issues: list[ValidationIssue] = []
        for bug in self.bugs:
            # 1. Public metadata
            if not bug.metadata:
                issues.append(ValidationIssue(bug.bug_id, "Missing or invalid metadata.json"))
            else:
                if not bug.metadata.get("bug_id") and not bug.metadata.get("id"):
                    issues.append(ValidationIssue(bug.bug_id, "metadata.json missing 'bug_id' or 'id'"))
                if not bug.metadata.get("category"):
                    issues.append(ValidationIssue(bug.bug_id, "metadata.json missing 'category'"))
                if not bug.metadata.get("difficulty"):
                    issues.append(ValidationIssue(bug.bug_id, "metadata.json missing 'difficulty'"))

            # 2. Public problem description
            if not bug.problem_statement or not bug.problem_statement.strip():
                issues.append(ValidationIssue(bug.bug_id, "Missing or empty public problem.md description"))

            # 3. Public buggy code syntax
            if not bug.buggy_dir.exists():
                issues.append(ValidationIssue(bug.bug_id, "Missing 'buggy/' code directory"))
            else:
                py_files = list(bug.buggy_dir.glob("*.py"))
                if not py_files:
                    issues.append(ValidationIssue(bug.bug_id, "No Python files found in 'buggy/' directory"))
                for py_f in py_files:
                    try:
                        ast.parse(py_f.read_text(encoding="utf-8", errors="replace"))
                    except SyntaxError as e:
                        issues.append(ValidationIssue(bug.bug_id, f"Syntax error in buggy/{py_f.name}: {e}"))

            # 4. Public visible tests
            if not bug.visible_tests_dir.exists() or not list(bug.visible_tests_dir.glob("test_*.py")):
                issues.append(ValidationIssue(bug.bug_id, "Missing visible tests/ directory or no test_*.py files found"))

            # 5. Private Evaluator artifacts (hidden tests, provenance, constraints, oracle patch)
            if not bug.hidden_tests_dir or not bug.hidden_tests_dir.exists() or not list(bug.hidden_tests_dir.glob("test_*.py")):
                issues.append(ValidationIssue(bug.bug_id, "Missing private hidden_tests/ directory or hidden test files"))

            if not bug.provenance:
                issues.append(ValidationIssue(bug.bug_id, "Missing or invalid private provenance.json"))
            else:
                if not bug.provenance.get("repository") and not bug.provenance.get("source"):
                    issues.append(ValidationIssue(bug.bug_id, "provenance.json missing 'repository' or 'source'"))
                if not bug.provenance.get("base_commit"):
                    issues.append(ValidationIssue(bug.bug_id, "provenance.json missing 'base_commit'"))

            if not bug.constraints:
                issues.append(ValidationIssue(bug.bug_id, "Missing or invalid private constraints.yaml"))

            if not bug.oracle_patch_path or not bug.oracle_patch_path.exists() or not bug.oracle_patch_path.read_text(encoding="utf-8").strip():
                issues.append(ValidationIssue(bug.bug_id, "Missing private oracle_patch.diff ground-truth fix"))

            # 6. Benchmark Contamination / Leakage Guardrail
            if bug.task_dir and bug.task_dir.exists():
                for forbidden in ["hidden_tests", "oracle_patch.diff", "provenance.json", "constraints.yaml"]:
                    if (bug.task_dir / forbidden).exists():
                        issues.append(ValidationIssue(
                            bug.bug_id,
                            f"Benchmark contamination error: Private evaluator artifact '{forbidden}' leaked into public task directory!"
                        ))

        return issues

    def __len__(self) -> int:
        return len(self.bugs)

    def __iter__(self) -> Iterator[BenchmarkBug]:
        return iter(self.bugs)
        
    def __getitem__(self, index: int) -> BenchmarkBug:
        return self.bugs[index]

    def summary(self) -> str:
        with_hidden = sum(1 for b in self.bugs if b.hidden_tests_dir)
        return f"Benchmark '{self.name}': {len(self.bugs)} bugs total, {with_hidden} with hidden tests."

    def filter(self, category: str) -> Benchmark:
        filtered_bugs = [b for b in self.bugs if b.metadata.get("category") == category]
        return Benchmark(name=f"{self.name} (filtered: {category})", bugs=filtered_bugs)
