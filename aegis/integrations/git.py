from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple

@dataclass
class PatchChange:
    """Structured representation of a single file's change."""
    path: str
    old_content: str = ""
    new_content: str = ""
    added_lines: List[str] = field(default_factory=list)
    deleted_lines: List[str] = field(default_factory=list)
    status: str = "M"  # A, M, D, R, C
    old_path: Optional[str] = None  # Populated for renames

@dataclass
class GitChange:
    base: str
    head: str
    modified_files: List[str] = field(default_factory=list)
    added_files: List[str] = field(default_factory=list)
    deleted_files: List[str] = field(default_factory=list)
    renamed_files: List[Tuple[str, str]] = field(default_factory=list)  # (old_path, new_path)
    raw_diff: str = ""
    file_diffs: Dict[str, str] = field(default_factory=dict)
    patches: Dict[str, PatchChange] = field(default_factory=dict)

def get_git_diff(repo_dir: Path, base: str = "HEAD~1", head: str = "HEAD") -> GitChange:
    """
    Extract commit-pure changed files, diffs, and structured PatchChanges between base and head commits.
    Reconstructs both base and head content directly from the git object database (git show).
    """
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

    # 2. Get status list with rename detection (-M)
    res_status = subprocess.run(
        ["git", "diff", "--name-status", "-M", f"{base}..{head}"],
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
    renamed: List[Tuple[str, str]] = []
    
    for line in res_status.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.strip().split("\t")
        if len(parts) >= 2:
            status = parts[0]
            if status.startswith("R") and len(parts) >= 3:
                old_p, new_p = parts[1].replace("\\", "/"), parts[2].replace("\\", "/")
                renamed.append((old_p, new_p))
            elif status.startswith("M"):
                modified.append(parts[1].replace("\\", "/"))
            elif status.startswith("A"):
                added.append(parts[1].replace("\\", "/"))
            elif status.startswith("D"):
                deleted.append(parts[1].replace("\\", "/"))

    # 3. Extract per-file unified diff hunks
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

    # 4. Construct commit-pure PatchChange for each file
    patches: Dict[str, PatchChange] = {}
    
    # Process Modified and Added files
    for f in set(modified + added):
        diff_text = file_diffs.get(f, "")
        added_lines = [l[1:] for l in diff_text.splitlines() if l.startswith("+") and not l.startswith("+++")]
        deleted_lines = [l[1:] for l in diff_text.splitlines() if l.startswith("-") and not l.startswith("---")]
        
        # Commit-pure HEAD content from git show
        new_content = ""
        res_head = subprocess.run(
            ["git", "show", f"{head}:{f}"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        if res_head.returncode == 0:
            new_content = res_head.stdout
        else:
            # Fallback to working tree if head is working tree
            p = repo_dir / f
            if p.exists() and p.is_file():
                new_content = p.read_text(encoding="utf-8", errors="replace")

        # Commit-pure BASE content from git show
        old_content = ""
        if f not in added:
            res_base = subprocess.run(
                ["git", "show", f"{base}:{f}"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            if res_base.returncode == 0:
                old_content = res_base.stdout

        status = "A" if f in added else "M"
        patches[f] = PatchChange(
            path=f,
            old_content=old_content,
            new_content=new_content,
            added_lines=added_lines,
            deleted_lines=deleted_lines,
            status=status
        )

    # Process Renamed files
    for old_p, new_p in renamed:
        diff_text = file_diffs.get(new_p, "")
        added_lines = [l[1:] for l in diff_text.splitlines() if l.startswith("+") and not l.startswith("+++")]
        deleted_lines = [l[1:] for l in diff_text.splitlines() if l.startswith("-") and not l.startswith("---")]
        
        old_content = ""
        res_base = subprocess.run(["git", "show", f"{base}:{old_p}"], cwd=repo_dir, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res_base.returncode == 0:
            old_content = res_base.stdout
            
        new_content = ""
        res_head = subprocess.run(["git", "show", f"{head}:{new_p}"], cwd=repo_dir, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res_head.returncode == 0:
            new_content = res_head.stdout

        patches[new_p] = PatchChange(
            path=new_p,
            old_content=old_content,
            new_content=new_content,
            added_lines=added_lines,
            deleted_lines=deleted_lines,
            status="R",
            old_path=old_p
        )

    # Process Deleted files
    for f in deleted:
        old_content = ""
        res_base = subprocess.run(["git", "show", f"{base}:{f}"], cwd=repo_dir, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res_base.returncode == 0:
            old_content = res_base.stdout
            
        patches[f] = PatchChange(
            path=f,
            old_content=old_content,
            new_content="",
            added_lines=[],
            deleted_lines=old_content.splitlines(),
            status="D"
        )

    return GitChange(
        base=base,
        head=head,
        modified_files=modified,
        added_files=added,
        deleted_files=deleted,
        renamed_files=renamed,
        raw_diff=raw_diff,
        file_diffs=file_diffs,
        patches=patches
    )

import tempfile
import io
import tarfile
from contextlib import contextmanager
from typing import Generator

@contextmanager
def create_commit_snapshot(repo_dir: Path, commit_ref: str = "HEAD") -> Generator[Path, None, None]:
    """
    Creates an immutable, hermetic snapshot of the exact commit_ref in an ephemeral directory.
    Guarantees that test execution and mutation testing never contaminate or read from
    the developer's uncommitted/dirty working tree.

    Fails closed: If git archive fails (e.g. invalid ref or uncommitted changes), an error
    is raised immediately rather than falling back to copying the dirty working tree.
    """
    with tempfile.TemporaryDirectory(prefix="aegis_snapshot_") as temp_dir:
        temp_path = Path(temp_dir)
        try:
            res = subprocess.run(
                ["git", "archive", "--format=tar", commit_ref],
                cwd=repo_dir,
                capture_output=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.decode("utf-8", errors="replace").strip() if e.stderr else str(e)
            raise RuntimeError(
                f"Failed to create hermetic git snapshot for ref '{commit_ref}' in {repo_dir}: {err_msg}. "
                "Aegis refuses to fall back to uncommitted working tree."
            ) from e
        except Exception as e:
            raise RuntimeError(
                f"Unexpected error creating snapshot for ref '{commit_ref}' in {repo_dir}: {e}"
            ) from e

        try:
            with tarfile.open(fileobj=io.BytesIO(res.stdout)) as tar:
                tar.extractall(temp_path)
        except Exception as e:
            raise RuntimeError(f"Failed to extract git archive for ref '{commit_ref}': {e}") from e

        yield temp_path
