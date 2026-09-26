from __future__ import annotations

import sys
import os
from pathlib import Path
from aegis.verification.validator import validate_python, validate_patch


def test_valid_python():
    code = "def foo():\n    return 42"
    result = validate_python(code)
    assert result.valid is True
    assert not result.errors


def test_invalid_python():
    code = "def foo():\nreturn 42"  # Indentation error
    result = validate_python(code)
    assert result.valid is False
    assert len(result.errors) > 0


def test_validate_patch_accepts_valid():
    patch = {"src/app.py": "x = 1\n"}
    project_dir = Path("/tmp/project")
    result = validate_patch(patch, project_dir)
    assert result.valid is True


def test_validate_patch_catches_absolute_path():
    patch = {"C:/etc/passwd": "root:x:0:0:"}
    project_dir = Path("/tmp/project")
    result = validate_patch(patch, project_dir)
    assert result.valid is False
    assert any("absolute" in err for err in result.errors)


def test_validate_patch_catches_path_traversal():
    patch = {"../src/app.py": "x = 1\n"}
    project_dir = Path("/tmp/project")
    result = validate_patch(patch, project_dir)
    assert result.valid is False
    assert any("traversal" in err for err in result.errors)


def test_validate_patch_catches_test_modification():
    patch = {"tests/test_app.py": "def test_foo(): pass\n"}
    project_dir = Path("/tmp/project")
    result = validate_patch(patch, project_dir)
    assert result.valid is False
    assert any("test files" in err for err in result.errors)


def test_validate_patch_invalid_python():
    patch = {"src/app.py": "def foo()\n"}
    project_dir = Path("/tmp/project")
    result = validate_patch(patch, project_dir)
    assert result.valid is False
    assert any("Syntax error" in err or "parsing" in err for err in result.errors)
