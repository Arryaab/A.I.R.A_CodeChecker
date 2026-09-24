from __future__ import annotations

import pytest
from pathlib import Path
from aegis.patcher import copy_project, parse_llm_patch, apply_patch

def test_copy_project(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "test.txt").write_text("hello")
    
    dest = copy_project(src)
    assert dest.exists()
    assert (dest / "test.txt").read_text() == "hello"

def test_parse_llm_patch_raw_json():
    response = '{"patch": {"solution.py": "def foo(): pass"}}'
    patch = parse_llm_patch(response)
    assert patch == {"solution.py": "def foo(): pass"}

def test_parse_llm_patch_fenced_json():
    response = "```json\n{\"patch\": {\"solution.py\": \"def foo(): pass\"}}\n```"
    patch = parse_llm_patch(response)
    assert patch == {"solution.py": "def foo(): pass"}
    
def test_parse_llm_patch_invalid():
    with pytest.raises(ValueError, match="Could not find parseable JSON"):
        parse_llm_patch("No JSON here")

def test_apply_patch_writes_files(tmp_path):
    patch = {"solution.py": "def foo(): pass"}
    result = apply_patch(tmp_path, patch, validate=False, protect_tests=False)
    assert result.success
    assert (tmp_path / "solution.py").read_text() == "def foo(): pass"

def test_apply_patch_rejects_path_traversal(tmp_path):
    patch = {"../solution.py": "def foo(): pass"}
    result = apply_patch(tmp_path, patch, validate=False, protect_tests=False)
    assert not result.success
    assert any("Path traversal" in e for e in result.validation_errors)

def test_apply_patch_rejects_test_modification(tmp_path):
    patch = {"test_solution.py": "def foo(): pass"}
    result = apply_patch(tmp_path, patch, validate=False, protect_tests=True)
    assert not result.success
    assert any("Cannot modify test file" in e for e in result.validation_errors)
