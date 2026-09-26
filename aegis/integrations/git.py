from __future__ import annotations

import subprocess
import sys
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

def _git_show_object(repo_dir: Path, ref: str, file_path: str) -> str:
    """
    Reconstructs exact file content from a specific Git reference.
    Fails closed: If the Git object cannot be reconstructed exactly, raises RuntimeError
    instead of falling back to the uncommitted working tree.
    """
    res = subprocess.run(
        ["git", "show", f"{ref}:{file_path}"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    if res.returncode != 0:
        err = res.stderr.strip() if res.stderr else f"git show returned exit code {res.returncode}"
        raise RuntimeError(
            f"Commit-pure verification error: Failed to reconstruct Git object '{ref}:{file_path}' ({err}). "
            "Aegis refuses to fall back to the uncommitted working tree."
        )
    return res.stdout

def apply_patch_file(target_dir: Path, diff_path: Path) -> None:
    """
    Hermetically applies a unified diff patch to a target directory using git apply.
    Performs a strict pre-check (--check) and fails closed if the patch cannot be applied cleanly.
    """
    check_res = subprocess.run(
        ["git", "apply", "--check", "--ignore-space-change", "--ignore-whitespace", str(diff_path.resolve())],
        cwd=target_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    if check_res.returncode != 0:
        err = check_res.stderr.strip() if check_res.stderr else f"git apply --check failed with code {check_res.returncode}"
        raise RuntimeError(
            f"Commit-pure verification error: Strict patch check failed for '{diff_path.name}'. "
            f"The patch cannot be reproduced exactly against the immutable base snapshot ({err})."
        )

    res = subprocess.run(
        ["git", "apply", "--ignore-space-change", "--ignore-whitespace", str(diff_path.resolve())],
        cwd=target_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    if res.returncode != 0:
        err = res.stderr.strip() if res.stderr else f"git apply exited with code {res.returncode}"
        raise RuntimeError(
            f"Commit-pure verification error: Failed to apply patch '{diff_path.name}' to immutable snapshot ({err})."
        )

def parse_unified_diff(
    repo_dir: Path,
    raw_diff: str,
    base_ref: str = "HEAD"
) -> Tuple[List[str], Dict[str, PatchChange]]:
    """
    Parses unified diff text, identifying affected files, hunks, and base content.
    Base content is reconstructed from base_ref via git show (fail-closed).
    Supports git diffs, unified diffs, quoted paths with spaces, additions, modifications, and deletions.
    Fails closed if a non-added base object cannot be reconstructed.
    """
    import shlex
    file_diffs: Dict[str, List[str]] = {}
    current_file = None
    last_old_file = None
    pending_header_lines: List[str] = []
    
    for line in raw_diff.splitlines():
        if line.startswith("diff --git "):
            rem = line[len("diff --git "):].strip()
            if rem.startswith('"'):
                try:
                    parts = shlex.split(rem)
                    if len(parts) >= 2:
                        b_path = parts[1]
                        current_file = b_path[2:] if b_path.startswith("b/") else b_path
                        current_file = current_file.replace("\\", "/")
                except Exception:
                    current_file = None
            else:
                if " b/" in rem:
                    idx = rem.rfind(" b/")
                    current_file = rem[idx + 3:].replace("\\", "/")
                else:
                    parts = rem.split()
                    if len(parts) >= 2:
                        b_path = parts[1]
                        current_file = (b_path[2:] if b_path.startswith("b/") else b_path).replace("\\", "/")

            pending_header_lines = [line]
            continue
        elif line.startswith("--- "):
            raw = line[4:].strip()
            if raw.startswith('"') and raw.endswith('"'):
                raw = raw[1:-1]
            raw_path = raw.split("\t")[0].strip()
            if raw_path.startswith("a/"):
                last_old_file = raw_path[2:].replace("\\", "/")
            elif raw_path == "/dev/null":
                last_old_file = None
            else:
                last_old_file = raw_path.replace("\\", "/")
            pending_header_lines.append(line)
            continue
        elif line.startswith("+++ "):
            raw = line[4:].strip()
            if raw.startswith('"') and raw.endswith('"'):
                raw = raw[1:-1]
            raw_path = raw.split("\t")[0].strip()
            if raw_path == "/dev/null":
                current_file = last_old_file
            elif raw_path.startswith("b/"):
                current_file = raw_path[2:].replace("\\", "/")
            else:
                current_file = raw_path.replace("\\", "/")

            if current_file:
                if current_file not in file_diffs:
                    file_diffs[current_file] = []
                file_diffs[current_file].extend(pending_header_lines)
                file_diffs[current_file].append(line)
            pending_header_lines = []
            continue
        else:
            if current_file:
                if pending_header_lines:
                    if current_file not in file_diffs:
                        file_diffs[current_file] = []
                    file_diffs[current_file].extend(pending_header_lines)
                    pending_header_lines = []
                file_diffs[current_file].append(line)

    affected_files = list(file_diffs.keys())
    patches: Dict[str, PatchChange] = {}

    for f, lines in file_diffs.items():
        added_lines = [l[1:] for l in lines if l.startswith("+") and not l.startswith("+++")]
        deleted_lines = [l[1:] for l in lines if l.startswith("-") and not l.startswith("---")]
        
        is_added = any(l.startswith("--- /dev/null") or "new file mode" in l for l in lines)
        is_deleted = any(l.startswith("+++ /dev/null") or "deleted file mode" in l for l in lines)
        
        rename_from = None
        for l in lines:
            if l.startswith("rename from "):
                rename_from = l[len("rename from "):].strip().replace("\\", "/")
                break

        if is_added:
            old_content = ""
            status = "A"
        elif is_deleted:
            try:
                old_content = _git_show_object(repo_dir, base_ref, f)
            except Exception as e:
                raise RuntimeError(
                    f"Commit-pure verification error: Cannot reconstruct deleted base object '{f}' at ref '{base_ref}': {e}"
                )
            status = "D"
        elif rename_from:
            try:
                old_content = _git_show_object(repo_dir, base_ref, rename_from)
            except Exception as e:
                raise RuntimeError(
                    f"Commit-pure verification error: Cannot reconstruct renamed base object '{rename_from}' at ref '{base_ref}': {e}"
                )
            status = "R"
        else:
            try:
                old_content = _git_show_object(repo_dir, base_ref, f)
            except Exception as e:
                raise RuntimeError(
                    f"Commit-pure verification error: Cannot reconstruct modified base object '{f}' at ref '{base_ref}': {e}"
                )
            status = "M"

        patches[f] = PatchChange(
            path=f,
            old_content=old_content,
            new_content="",  # Populated from patched snapshot
            added_lines=added_lines,
            deleted_lines=deleted_lines,
            status=status
        )

    return affected_files, patches

def get_git_diff(repo_dir: Path, base: str = "HEAD~1", head: str = "HEAD") -> GitChange:
    """
    Extract commit-pure changed files, diffs, and structured PatchChanges between base and head commits.
    Reconstructs both base and head content directly from the git object database (git show).
    Fails closed on unsupported changes: binary files, symlinks, submodules, and permission changes.
    """
    # 1a. Check for unsupported Git changes (binary files)
    res_numstat = subprocess.run(
        ["git", "diff", "--numstat", f"{base}..{head}"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True
    )
    unsupported_changes: List[str] = []
    for line in res_numstat.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 3 and parts[0] == "-" and parts[1] == "-":
            unsupported_changes.append(f"Binary file modification: {parts[2]}")

    # 1b. Check for unsupported Git changes (symlinks, submodules, mode changes, typechanges)
    res_raw = subprocess.run(
        ["git", "diff", "--raw", f"{base}..{head}"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True
    )
    for line in res_raw.stdout.splitlines():
        if not line.startswith(":"):
            continue
        meta, sep, path = line.partition("\t")
        tokens = meta.strip().split()
        if len(tokens) >= 5:
            old_mode = tokens[0][1:]
            new_mode = tokens[1]
            status = tokens[4]
            if "120000" in (old_mode, new_mode):
                unsupported_changes.append(f"Symlink modification: {path}")
            elif "160000" in (old_mode, new_mode):
                unsupported_changes.append(f"Git submodule modification: {path}")
            elif status == "T":
                unsupported_changes.append(f"File typechange: {path}")
            elif old_mode != "000000" and new_mode != "000000" and old_mode != new_mode:
                unsupported_changes.append(f"File permission/mode change ({old_mode} -> {new_mode}): {path}")

    if unsupported_changes:
        raise RuntimeError(
            f"Commit-pure verification error: Unsupported Git change(s) detected in range {base}..{head}: "
            f"{'; '.join(unsupported_changes)}. Aegis fails closed on unverified binary, symlink, submodule, "
            f"and permission changes."
        )

    # 2. Get raw unified diff
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

    # 3. Get status list with rename detection (-M)
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
        
        # Commit-pure HEAD content from git show (fail closed)
        new_content = _git_show_object(repo_dir, head, f)

        # Commit-pure BASE content from git show (fail closed)
        old_content = _git_show_object(repo_dir, base, f) if f not in added else ""

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
        
        old_content = _git_show_object(repo_dir, base, old_p)
        new_content = _git_show_object(repo_dir, head, new_p)

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
        old_content = _git_show_object(repo_dir, base, f)
            
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
                if sys.version_info >= (3, 12):
                    tar.extractall(temp_path, filter="data")
                else:
                    tar.extractall(temp_path)
        except Exception as e:
            raise RuntimeError(f"Failed to extract git archive for ref '{commit_ref}': {e}") from e

        yield temp_path
