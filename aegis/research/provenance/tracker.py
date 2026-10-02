from __future__ import annotations

import ast
import difflib
import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class AstSymbolDelta:
    functions_added: List[str] = field(default_factory=list)
    functions_deleted: List[str] = field(default_factory=list)
    functions_modified: List[str] = field(default_factory=list)
    classes_added: List[str] = field(default_factory=list)
    classes_deleted: List[str] = field(default_factory=list)


@dataclass
class ProvenanceRecord:
    task_id: str
    base_snapshot_sha256: str
    head_snapshot_sha256: str
    patch_sha256: str
    patch_diff: str
    modified_files: List[str]
    added_files: List[str]
    deleted_files: List[str]
    lines_added: int
    lines_deleted: int
    net_churn: int
    ast_delta: AstSymbolDelta
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    prompt_hashes: Dict[str, str] = field(default_factory=dict)
    environment_fingerprint: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


def compute_content_sha256(content: str | bytes) -> str:
    """Computes SHA-256 of string or bytes."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def compute_directory_sha256(dir_path: Path) -> str:
    """Computes a deterministic SHA-256 hash of a directory's file tree."""
    dir_path = Path(dir_path).resolve()
    if not dir_path.exists():
        return hashlib.sha256(b"").hexdigest()

    hasher = hashlib.sha256()
    # Sort all files by relative path for determinism
    files = sorted([f for f in dir_path.rglob("*") if f.is_file()])
    for f in files:
        if "__pycache__" in f.parts or f.suffix == ".pyc" or ".pytest_cache" in f.parts:
            continue
        rel_str = str(f.relative_to(dir_path)).replace("\\", "/")
        hasher.update(rel_str.encode("utf-8"))
        try:
            hasher.update(f.read_bytes())
        except Exception:
            pass
    return hasher.hexdigest()


def _extract_symbols(code: str, filename: str) -> Dict[str, str]:
    """Extract top-level functions and classes with their normalized code."""
    symbols: Dict[str, str] = {}
    try:
        tree = ast.parse(code, filename=filename)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                symbols[node.name] = ast.unparse(node)
    except Exception:
        pass
    return symbols


def compute_ast_symbol_delta(base_code: str, head_code: str, filename: str) -> AstSymbolDelta:
    base_syms = _extract_symbols(base_code, filename)
    head_syms = _extract_symbols(head_code, filename)

    added_funcs = []
    deleted_funcs = []
    modified_funcs = []
    added_classes = []
    deleted_classes = []

    for name, code in head_syms.items():
        if name not in base_syms:
            added_funcs.append(name)
        elif code != base_syms[name]:
            modified_funcs.append(name)

    for name in base_syms:
        if name not in head_syms:
            deleted_funcs.append(name)

    return AstSymbolDelta(
        functions_added=sorted(added_funcs),
        functions_deleted=sorted(deleted_funcs),
        functions_modified=sorted(modified_funcs),
        classes_added=sorted(added_classes),
        classes_deleted=sorted(deleted_classes),
    )


class ProvenanceTracker:
    """Extracts unified diffs, cryptographic hashes, and AST deltas from candidate runs."""

    @staticmethod
    def extract_provenance(
        task_id: str,
        base_dir: Path,
        head_dir: Path,
        metadata: Optional[Dict[str, Any]] = None,
        prompt_hashes: Optional[Dict[str, str]] = None,
        environment_fingerprint: Optional[Dict[str, Any]] = None,
    ) -> ProvenanceRecord:
        base_dir = Path(base_dir).resolve()
        head_dir = Path(head_dir).resolve()

        base_sha = compute_directory_sha256(base_dir)
        head_sha = compute_directory_sha256(head_dir)

        # Collect all files
        base_files: Dict[str, Path] = {}
        for f in sorted(base_dir.rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts and f.suffix != ".pyc" and ".pytest_cache" not in f.parts:
                rel = str(f.relative_to(base_dir)).replace("\\", "/")
                base_files[rel] = f

        head_files: Dict[str, Path] = {}
        for f in sorted(head_dir.rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts and f.suffix != ".pyc" and ".pytest_cache" not in f.parts:
                rel = str(f.relative_to(head_dir)).replace("\\", "/")
                head_files[rel] = f

        all_rel_paths = sorted(set(base_files.keys()) | set(head_files.keys()))

        diff_chunks: List[str] = []
        modified_files: List[str] = []
        added_files: List[str] = []
        deleted_files: List[str] = []

        total_lines_added = 0
        total_lines_deleted = 0

        total_added_funcs: List[str] = []
        total_del_funcs: List[str] = []
        total_mod_funcs: List[str] = []

        for rel in all_rel_paths:
            base_file = base_files.get(rel)
            head_file = head_files.get(rel)

            if base_file and not head_file:
                # Deleted
                deleted_files.append(rel)
                base_text = base_file.read_text(encoding="utf-8", errors="replace")
                base_lines = base_text.splitlines(keepends=True)
                diff = difflib.unified_diff(
                    base_lines,
                    [],
                    fromfile=f"a/{rel}",
                    tofile="/dev/null",
                )
                chunk = "".join(diff)
                diff_chunks.append(chunk)
                total_lines_deleted += len(base_lines)

            elif not base_file and head_file:
                # Added
                added_files.append(rel)
                head_text = head_file.read_text(encoding="utf-8", errors="replace")
                head_lines = head_text.splitlines(keepends=True)
                diff = difflib.unified_diff(
                    [],
                    head_lines,
                    fromfile="/dev/null",
                    tofile=f"b/{rel}",
                )
                chunk = "".join(diff)
                diff_chunks.append(chunk)
                total_lines_added += len(head_lines)

            elif base_file and head_file:
                base_bytes = base_file.read_bytes()
                head_bytes = head_file.read_bytes()
                if base_bytes != head_bytes:
                    modified_files.append(rel)
                    base_text = base_file.read_text(encoding="utf-8", errors="replace")
                    head_text = head_file.read_text(encoding="utf-8", errors="replace")
                    base_lines = base_text.splitlines(keepends=True)
                    head_lines = head_text.splitlines(keepends=True)

                    diff = list(
                        difflib.unified_diff(
                            base_lines,
                            head_lines,
                            fromfile=f"a/{rel}",
                            tofile=f"b/{rel}",
                        )
                    )
                    diff_chunks.append("".join(diff))

                    for l in diff:
                        if l.startswith("+") and not l.startswith("+++"):
                            total_lines_added += 1
                        elif l.startswith("-") and not l.startswith("---"):
                            total_lines_deleted += 1

                    if rel.endswith(".py"):
                        ast_delta = compute_ast_symbol_delta(base_text, head_text, rel)
                        total_added_funcs.extend(ast_delta.functions_added)
                        total_del_funcs.extend(ast_delta.functions_deleted)
                        total_mod_funcs.extend(ast_delta.functions_modified)

        full_diff = "\n".join(diff_chunks)
        patch_sha = compute_content_sha256(full_diff)

        combined_ast_delta = AstSymbolDelta(
            functions_added=sorted(total_added_funcs),
            functions_deleted=sorted(total_del_funcs),
            functions_modified=sorted(total_mod_funcs),
        )

        return ProvenanceRecord(
            task_id=task_id,
            base_snapshot_sha256=base_sha,
            head_snapshot_sha256=head_sha,
            patch_sha256=patch_sha,
            patch_diff=full_diff,
            modified_files=modified_files,
            added_files=added_files,
            deleted_files=deleted_files,
            lines_added=total_lines_added,
            lines_deleted=total_lines_deleted,
            net_churn=total_lines_added + total_lines_deleted,
            ast_delta=combined_ast_delta,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
            prompt_hashes=prompt_hashes or {},
            environment_fingerprint=environment_fingerprint or {},
        )
