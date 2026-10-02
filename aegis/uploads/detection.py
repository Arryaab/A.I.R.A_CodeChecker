import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict

import ast
import re

IGNORE_DIRS = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', '.tox', 'user_tests'}

@dataclass
class FrameworkDetection:
    framework: str
    confidence: float
    test_files: List[str] = field(default_factory=list)
    discovered_tests: List[str] = field(default_factory=list)
    discovered_count: int = 0
    config_files: List[str] = field(default_factory=list)
    details: Dict = field(default_factory=dict)

def detect_framework(project_root: Path) -> FrameworkDetection:
    test_files = []
    config_files = []
    pytest_score = 0.0
    unittest_score = 0.0

    pytest_configs = {'conftest.py', 'pytest.ini'}

    # Check for pytest in requirements.txt or pyproject.toml
    req_path = project_root / 'requirements.txt'
    if req_path.exists():
        content = req_path.read_text(errors='ignore')
        if 'pytest' in content:
            pytest_score += 0.3
            config_files.append('requirements.txt')

    toml_path = project_root / 'pyproject.toml'
    if toml_path.exists():
        content = toml_path.read_text(errors='ignore')
        if 'pytest' in content or '[tool.pytest]' in content:
            pytest_score += 0.4
            config_files.append('pyproject.toml')

    setup_cfg = project_root / 'setup.cfg'
    if setup_cfg.exists():
        content = setup_cfg.read_text(errors='ignore')
        if 'pytest' in content or '[tool:pytest]' in content:
            pytest_score += 0.3
            config_files.append('setup.cfg')

def get_pytest_repo_config(project_root: Path) -> dict:
    """Reads repository-specific pytest configuration to respect testpaths and norecursedirs."""
    config = {
        "testpaths": [],
        "norecursedirs": ['fixtures', '.*', 'build', 'dist', '*.egg', 'user_tests', 'node_modules', '.venv', 'venv'],
        "python_files": ['test_*.py', '*_test.py']
    }
    # Check pyproject.toml
    toml_path = project_root / 'pyproject.toml'
    if toml_path.exists():
        try:
            import tomllib
            doc = tomllib.loads(toml_path.read_text(encoding='utf-8', errors='ignore'))
            pytest_cfg = doc.get("tool", {}).get("pytest", {}).get("ini_options", {})
            if "testpaths" in pytest_cfg:
                tp = pytest_cfg["testpaths"]
                config["testpaths"] = [tp] if isinstance(tp, str) else list(tp)
            if "norecursedirs" in pytest_cfg:
                nrd = pytest_cfg["norecursedirs"]
                config["norecursedirs"].extend([nrd] if isinstance(nrd, str) else list(nrd))
        except Exception:
            pass

    # Check pytest.ini, setup.cfg, or tox.ini
    for ini_name in ('pytest.ini', 'setup.cfg', 'tox.ini'):
        ini_path = project_root / ini_name
        if ini_path.exists():
            try:
                import configparser
                cp = configparser.ConfigParser()
                cp.read(ini_path, encoding='utf-8')
                sec = "pytest" if cp.has_section("pytest") else ("tool:pytest" if cp.has_section("tool:pytest") else None)
                if sec:
                    if cp.has_option(sec, "testpaths"):
                        config["testpaths"].extend(cp.get(sec, "testpaths").split())
                    if cp.has_option(sec, "norecursedirs"):
                        config["norecursedirs"].extend(cp.get(sec, "norecursedirs").split())
            except Exception:
                pass

    return config

def detect_framework(project_root: Path) -> FrameworkDetection:
    test_files = []
    config_files = []
    pytest_score = 0.0
    unittest_score = 0.0

    pytest_configs = {'conftest.py', 'pytest.ini'}
    repo_cfg = get_pytest_repo_config(project_root)
    configured_testpaths = repo_cfg["testpaths"]
    ignore_patterns = set(IGNORE_DIRS) | set(repo_cfg["norecursedirs"])

    # Check for pytest in requirements.txt or pyproject.toml
    req_path = project_root / 'requirements.txt'
    if req_path.exists():
        content = req_path.read_text(errors='ignore')
        if 'pytest' in content:
            pytest_score += 0.3
            config_files.append('requirements.txt')

    toml_path = project_root / 'pyproject.toml'
    if toml_path.exists():
        content = toml_path.read_text(errors='ignore')
        if 'pytest' in content or '[tool.pytest]' in content:
            pytest_score += 0.4
            config_files.append('pyproject.toml')

    setup_cfg = project_root / 'setup.cfg'
    if setup_cfg.exists():
        content = setup_cfg.read_text(errors='ignore')
        if 'pytest' in content or '[tool:pytest]' in content:
            pytest_score += 0.3
            config_files.append('setup.cfg')

    tox_ini = project_root / 'tox.ini'
    if tox_ini.exists():
        content = tox_ini.read_text(errors='ignore')
        if 'pytest' in content:
            pytest_score += 0.3
            config_files.append('tox.ini')

    # Search for test files respecting configured testpaths if present
    search_dirs = [project_root / tp for tp in configured_testpaths] if configured_testpaths else [project_root]
    for s_dir in search_dirs:
        if not s_dir.exists():
            continue
        for root, dirs, files in os.walk(s_dir):
            dirs[:] = [d for d in dirs if not any(ign in d for ign in ignore_patterns)]
            try:
                rel_root = Path(root).relative_to(project_root)
            except ValueError:
                continue

            for f in files:
                rel_path = str(rel_root / f if rel_root != Path('.') else f).replace('\\', '/')

                if f in pytest_configs:
                    pytest_score += 0.3
                    config_files.append(rel_path)

                if (f.startswith('test_') and f.endswith('.py')) or f.endswith('_test.py'):
                    test_files.append(rel_path)

                    if any(part in ('tests', 'test') for part in rel_root.parts):
                        pytest_score += 0.1

                    try:
                        content = (Path(root) / f).read_text(errors='ignore')
                        if 'import pytest' in content or 'from pytest' in content:
                            pytest_score += 0.3
                        if 'import unittest' in content or 'unittest.TestCase' in content:
                            unittest_score += 0.5
                    except Exception:
                        pass

    # Normalize scores and decide
    framework = 'UNSUPPORTED_PROJECT'
    confidence = 0.0

    if pytest_score > unittest_score and pytest_score > 0.2:
        framework = 'pytest'
        confidence = min(1.0, pytest_score)
    elif unittest_score > 0:
        framework = 'unittest'
        confidence = min(1.0, unittest_score)
    elif test_files:
        framework = 'pytest'
        confidence = 0.5

    discovered_tests = discover_project_tests(project_root, test_files)

    return FrameworkDetection(
        framework=framework,
        confidence=confidence,
        test_files=test_files,
        discovered_tests=discovered_tests,
        discovered_count=len(discovered_tests),
        config_files=config_files,
        details={'pytest_score': pytest_score, 'unittest_score': unittest_score}
    )

def discover_project_tests(project_root: Path, test_files: List[str] | None = None) -> List[str]:
    """
    Authoritative test discovery for standalone projects.
    First tries executing pytest --collect-only in the environment for 100% exact node IDs.
    Falls back to AST inspection (functions, methods, classes) if pytest collection cannot run.
    """
    # 1. Authoritative pytest collection
    try:
        import subprocess, sys
        cmd = [
            sys.executable, "-m", "pytest",
            "-o", "addopts=",
            "--collect-only", "-q",
            "-p", "no:cacheprovider",
            "--ignore=user_tests"
        ]
        res = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=15
        )
        collected = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if "::" in line and not line.startswith("<") and not line.startswith("=") and not line.startswith("user_tests"):
                collected.append(line.replace('\\', '/'))
        if collected:
            return collected
    except Exception:
        pass

    # 2. Fallback AST discovery respecting repository configuration
    repo_cfg = get_pytest_repo_config(project_root)
    configured_testpaths = repo_cfg["testpaths"]
    ignore_patterns = set(IGNORE_DIRS) | set(repo_cfg["norecursedirs"])

    if test_files is None:
        found = []
        search_dirs = [project_root / tp for tp in configured_testpaths] if configured_testpaths else [project_root]
        for s_dir in search_dirs:
            if not s_dir.exists():
                continue
            for root, dirs, files in os.walk(s_dir):
                dirs[:] = [d for d in dirs if not any(ign in d for ign in ignore_patterns)]
                try:
                    rel_root = Path(root).relative_to(project_root)
                except ValueError:
                    continue
                for f in files:
                    if (f.startswith('test_') and f.endswith('.py')) or f.endswith('_test.py'):
                        rel_p = str(rel_root / f if rel_root != Path('.') else f).replace('\\', '/')
                        found.append(rel_p)
        test_files = found

    discovered = []
    for tf in test_files:
        norm_tf = str(tf).replace('\\', '/')
        full_path = project_root / norm_tf
        if not full_path.exists():
            continue
        try:
            code = full_path.read_text(encoding='utf-8', errors='ignore')
            tree = ast.parse(code, filename=str(full_path))
            for node in tree.body:
                if isinstance(node, ast.FunctionDef) and (node.name.startswith('test_') or node.name.endswith('_test')):
                    discovered.append(f"{norm_tf}::{node.name}")
                elif isinstance(node, ast.ClassDef):
                    # Any test class (starts/ends with Test, or contains Test)
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef) and (item.name.startswith('test_') or item.name.endswith('_test')):
                            discovered.append(f"{norm_tf}::{node.name}::{item.name}")
        except Exception:
            try:
                code = full_path.read_text(encoding='utf-8', errors='ignore')
                fn_matches = re.findall(r'def\s+(test_[a-zA-Z0-9_]+)\s*\(', code)
                for fn in fn_matches:
                    discovered.append(f"{norm_tf}::{fn}")
            except Exception:
                pass

    return discovered
