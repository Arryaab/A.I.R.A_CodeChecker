from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set

@dataclass
class GitChange:
    base: str
    head: str
    modified_files: List[str] = field(default_factory=list)
    added_files: List[str] = field(default_factory=list)
    deleted_files: List[str] = field(default_factory=list)
    raw_diff: str = ""
    file_diffs: Dict[str, str] = field(default_factory=dict)

def get_git_diff(repo_dir: Path, base: str = "HEAD~1", head: str = "HEAD") -> GitChange:
    """Extract changed files and diffs between base and head commits."""
    # 1. Get raw unified diff
    res_diff = subprocess.run(
        ["git", "diff", f"{base}..{head}"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True
    )
    raw_diff = res_diff.stdout

    # 2. Get status list
    res_status = subprocess.run(
        ["git", "diff", "--name-status", f"{base}..{head}"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True
    )
    
    modified = []
    added = []
    deleted = []
    
    for line in res_status.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.strip().split(maxsplit=1)
        if len(parts) == 2:
            status, filepath = parts[0], parts[1]
            if status.startswith("M"):
                modified.append(filepath)
            elif status.startswith("A"):
                added.append(filepath)
            elif status.startswith("D"):
                deleted.append(filepath)

    # 3. Extract per-file diffs
    file_diffs = {}
    current_file = None
    current_lines = []
    
    for line in raw_diff.splitlines():
        if line.startswith("diff --git"):
            if current_file and current_lines:
                file_diffs[current_file] = "\n".join(current_lines)
            parts = line.split()
            # diff --git a/file b/file
            if len(parts) >= 4:
                current_file = parts[3].replace("b/", "", 1)
                current_lines = [line]
        else:
            if current_file:
                current_lines.append(line)
                
    if current_file and current_lines:
        file_diffs[current_file] = "\n".join(current_lines)

    return GitChange(
        base=base,
        head=head,
        modified_files=modified,
        added_files=added,
        deleted_files=deleted,
        raw_diff=raw_diff,
        file_diffs=file_diffs
    )
