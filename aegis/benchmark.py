from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

@dataclass
class BenchmarkBug:
    bug_id: str
    buggy_dir: Path
    visible_tests_dir: Path
    hidden_tests_dir: Path | None
    metadata: dict = field(default_factory=dict)
    description: str = ""

class Benchmark:
    def __init__(self, name: str, bugs: list[BenchmarkBug]):
        self.name = name
        self.bugs = bugs

    @classmethod
    def load(cls, benchmark_dir: Path | str) -> Benchmark:
        """Load benchmark from directory."""
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

            bug_id = metadata.get("bug_id", bug_dir.name)
            description = metadata.get("description", "")

            bugs.append(BenchmarkBug(
                bug_id=bug_id,
                buggy_dir=buggy_dir,
                visible_tests_dir=visible_tests_dir,
                hidden_tests_dir=hidden_tests_dir if hidden_tests_dir.exists() else None,
                metadata=metadata,
                description=description
            ))

        # Sort by bug_id
        bugs.sort(key=lambda b: b.bug_id)
        return cls(name=benchmark_dir.name, bugs=bugs)

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
