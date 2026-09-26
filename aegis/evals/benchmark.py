from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

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

            buggy_dir = bug_dir / "buggy"
            visible_tests_dir = bug_dir / "tests"
            hidden_tests_dir = bug_dir / "hidden_tests"
            metadata_file = bug_dir / "metadata.json"
            provenance_file = bug_dir / "provenance.json"
            problem_file = bug_dir / "problem.md"
            oracle_file = bug_dir / "oracle_patch.diff"

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
                problem_statement=problem_statement,
                description=description,
                oracle_patch_path=oracle_file if oracle_file.exists() else None,
            ))

        bugs.sort(key=lambda b: b.bug_id)
        return cls(name=benchmark_dir.name, bugs=bugs)

    def validate(self) -> list[ValidationIssue]:
        """Validates benchmark task integrity against canonical schema."""
        issues: list[ValidationIssue] = []
        for bug in self.bugs:
            # Check metadata
            if not bug.metadata:
                issues.append(ValidationIssue(bug.bug_id, "Missing or invalid metadata.json"))
            else:
                if not bug.metadata.get("bug_id") and not bug.metadata.get("id"):
                    issues.append(ValidationIssue(bug.bug_id, "metadata.json missing 'bug_id' or 'id'"))
                if not bug.metadata.get("category"):
                    issues.append(ValidationIssue(bug.bug_id, "metadata.json missing 'category'"))
            # Check buggy code syntax
            if not bug.buggy_dir.exists():
                issues.append(ValidationIssue(bug.bug_id, "Missing 'buggy/' code directory"))
            else:
                py_files = list(bug.buggy_dir.glob("*.py"))
                if not py_files:
                    issues.append(ValidationIssue(bug.bug_id, "No Python files found in 'buggy/' directory"))
                for py_f in py_files:
                    try:
                        import ast
                        ast.parse(py_f.read_text(encoding="utf-8", errors="replace"))
                    except SyntaxError as e:
                        issues.append(ValidationIssue(bug.bug_id, f"Syntax error in buggy/{py_f.name}: {e}"))
            # Check visible tests
            if not bug.visible_tests_dir.exists() or not list(bug.visible_tests_dir.glob("test_*.py")):
                issues.append(ValidationIssue(bug.bug_id, "Missing tests/ directory or no visible test files"))
            # Check hidden evaluator
            if not bug.hidden_tests_dir or not bug.hidden_tests_dir.exists():
                issues.append(ValidationIssue(bug.bug_id, "Missing private hidden_tests/ directory", severity="WARNING"))
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
