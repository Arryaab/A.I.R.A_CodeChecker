from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Optional

@dataclass
class PatchChange:
    """Structured representation of a single file's change."""
    path: str
    old_content: str = ""
    new_content: str = ""
    added_lines: List[str] = field(default_factory=list)
    deleted_lines: List[str] = field(default_factory=list)
    status: str = "M"  # A, M, D, R

@dataclass
class GitChange:
    base: str
    head: str
    modified_files: List[str] = field(default_factory=list)
    added_files: List[str] = field(default_factory=list)
    deleted_files: List[str] = field(default_factory=list)
    raw_diff: str = ""
    file_diffs: Dict[str, str] = field(default_factory=dict)
    patches: Dict[str, PatchChange] = field(default_factory=dict)

def get_git_diff(repo_dir: Path, base: str = "HEAD~1", head: str = "HEAD") -> GitChange:
    """Extract changed files, diffs, and structured PatchChanges between base and head commits."""
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
            status, filepath = parts[0], parts[1].replace("\\", "/")
            if status.startswith("M"):
                modified.append(filepath)
            elif status.startswith("A"):
                added.append(filepath)
            elif status.startswith("D"):
                deleted.append(filepath)

    # 3. Extract per-file diffs
    file_diffs: Dict[str, str] = {}
    current_file = None
    current_lines = []
    
    for line in raw_diff.splitlines():
        if line.startswith("diff --git"):
            if current_file and current_lines:
                file_diffs[current_file] = "\n".join(current_lines)
            parts = line.split()
            if len(parts) >= 4:
                current_file = parts[3].replace("b/", "", 1).replace("\\", "/")
                current_lines = [line]
        else:
            if current_file:
                current_lines.append(line)
                
    if current_file and current_lines:
        file_diffs[current_file] = "\n".join(current_lines)

    # 4. Construct structured PatchChange for each file
    patches: Dict[str, PatchChange] = {}
    all_files = set(modified + added)
    
    for f in all_files:
        diff_text = file_diffs.get(f, "")
        added_lines = []
        deleted_lines = []
        
        for line in diff_text.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                added_lines.append(line[1:])
            elif line.startswith("-") and not line.startswith("---"):
                deleted_lines.append(line[1:])
                
        # Reconstruct new content from current working tree
        file_path = repo_dir / f
        new_content = ""
        if file_path.exists() and file_path.is_file():
            try:
                new_content = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass

        # Fetch old content via git show
        old_content = ""
        if f not in added:
            try:
                res_show = subprocess.run(
                    ["git", "show", f"{base}:{f}"],
                    cwd=repo_dir,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace"
                )
                if res_show.returncode == 0:
                    old_content = res_show.stdout
            except Exception:
                pass

        status = "A" if f in added else "M"
        patches[f] = PatchChange(
            path=f,
            old_content=old_content,
            new_content=new_content,
            added_lines=added_lines,
            deleted_lines=deleted_lines,
            status=status
        )

    return GitChange(
        base=base,
        head=head,
        modified_files=modified,
        added_files=added,
        deleted_files=deleted,
        raw_diff=raw_diff,
        file_diffs=file_diffs,
        patches=patches
    )
