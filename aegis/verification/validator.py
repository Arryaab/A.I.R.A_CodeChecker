from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


def validate_python(code: str, filename: str = "<generated>") -> ValidationResult:
    """Use ast.parse() to validate Python source code syntax."""
    try:
        ast.parse(code, filename=filename)
        return ValidationResult(valid=True)
    except SyntaxError as e:
        error_msg = f"Syntax error in {filename} at line {e.lineno}, column {e.offset}: {e.msg}"
        return ValidationResult(valid=False, errors=[error_msg])
    except Exception as e:
        return ValidationResult(valid=False, errors=[f"Unexpected error parsing {filename}: {str(e)}"])


def validate_patch(patch: dict[str, str], project_dir: Path) -> ValidationResult:
    """Validate a patch dict:
    - All paths are relative
    - No path traversal (no ..)
    - Paths stay inside project_dir
    - No modification of test files (test_*.py)
    - All Python files pass ast.parse()
    """
    errors = []
    
    for filepath_str, code in patch.items():
        filepath = Path(filepath_str)
        
        if filepath.is_absolute():
            errors.append(f"Path must be relative, got absolute: {filepath_str}")
            continue
            
        if ".." in filepath.parts:
            errors.append(f"Path traversal detected in path: {filepath_str}")
            continue
            
        full_path = (project_dir / filepath).resolve()
        
        try:
            # Check if full_path is actually within project_dir
            full_path.relative_to(project_dir.resolve())
        except ValueError:
            errors.append(f"Path outside project directory: {filepath_str}")
            continue
            
        if filepath.name.startswith("test_") and filepath.name.endswith(".py"):
            errors.append(f"Modifying test files is not allowed: {filepath_str}")
            continue
            
        if filepath.suffix == ".py":
            result = validate_python(code, filename=filepath_str)
            if not result.valid:
                errors.extend(result.errors)
                
    if errors:
        return ValidationResult(valid=False, errors=errors)
    return ValidationResult(valid=True)
