from __future__ import annotations

import json
import logging
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aegis.verification.validator import validate_patch

logger = logging.getLogger(__name__)

@dataclass
class PatchResult:
    success: bool
    patched_dir: Path
    files_modified: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)

def copy_project(source_dir: Path, dest_dir: Path | None = None) -> Path:
    """Copy project to a temporary directory. If dest_dir is None, create a temp dir."""
    if dest_dir is None:
        temp_dir = tempfile.mkdtemp(prefix='aegis_')
        dest_dir = Path(temp_dir)
    else:
        dest_dir = Path(dest_dir)
        if dest_dir.exists():
            shutil.rmtree(dest_dir)

    shutil.copytree(source_dir, dest_dir, dirs_exist_ok=True)
    return dest_dir

def parse_llm_patch(llm_response: str) -> dict[str, str]:
    """Parse the LLM response text to extract a patch dict.
    
    Handles raw JSON, JSON wrapped in ```json ... ``` code fences,
    or JSON wrapped in ``` ... ```.
    
    Returns a dict mapping relative file paths to new file contents.
    """
    text = llm_response.strip()
    
    # Try parsing directly
    try:
        data = json.loads(text)
        if "patch" not in data:
            raise ValueError("JSON response missing 'patch' key.")
        return data["patch"]
    except json.JSONDecodeError:
        pass

    # Try extracting from code fences
    json_pattern = re.compile(r'```(?:json)?\s*(.*?)\s*```', re.DOTALL)
    match = json_pattern.search(text)
    if not match:
        raise ValueError("Could not find parseable JSON in LLM response.")

    extracted = match.group(1).strip()
    try:
        data = json.loads(extracted)
        if "patch" not in data:
            raise ValueError("Extracted JSON missing 'patch' key.")
        return data["patch"]
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse extracted JSON: {e}")

def apply_patch(
    project_dir: Path,
    patch: dict[str, str],
    *,
    validate: bool = True,
    protect_tests: bool = True,
) -> PatchResult:
    """Apply a whole-file replacement patch to a project directory."""
    project_dir = Path(project_dir).resolve()
    
    if validate:
        val_result = validate_patch(patch, project_dir)
        if not val_result.valid:
            return PatchResult(
                success=False,
                patched_dir=project_dir,
                validation_errors=val_result.errors
            )

    files_modified = []
    validation_errors = []

    for rel_path_str, content in patch.items():
        if protect_tests and "test_" in Path(rel_path_str).name:
            validation_errors.append(f"Cannot modify test file: {rel_path_str}")
            continue
            
        file_path = (project_dir / rel_path_str).resolve()
        
        # Security check: ensure path is within project_dir
        try:
            file_path.relative_to(project_dir)
        except ValueError:
            validation_errors.append(f"Path traversal attempted: {rel_path_str}")
            continue

        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        files_modified.append(rel_path_str)

    success = len(validation_errors) == 0
    return PatchResult(
        success=success,
        patched_dir=project_dir,
        files_modified=files_modified,
        validation_errors=validation_errors
    )
