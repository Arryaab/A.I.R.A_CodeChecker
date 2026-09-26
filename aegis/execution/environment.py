from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

MANIFEST_FILENAMES = [
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "poetry.lock",
    "Pipfile",
    "Pipfile.lock",
    "environment.yml",
    "environment.yaml",
]

@dataclass
class EnvironmentFingerprint:
    python_version: str
    platform: str
    dependency_manifests: List[str] = field(default_factory=list)
    dependency_lock_hash: str = ""
    environment_fingerprint: str = ""
    sandbox: str = "docker"

def inspect_repository_environment(repo_dir: Path) -> EnvironmentFingerprint:
    """
    Inspects a repository to discover dependency manifests, calculate a deterministic
    dependency lock hash, and generate an immutable environment fingerprint.
    """
    found_manifests = []
    hasher = hashlib.sha256()

    for name in sorted(MANIFEST_FILENAMES):
        manifest_path = repo_dir / name
        if manifest_path.exists() and manifest_path.is_file():
            found_manifests.append(name)
            hasher.update(name.encode("utf-8"))
            try:
                content = manifest_path.read_bytes().replace(b"\r\n", b"\n")
                hasher.update(content)
            except Exception:
                pass

    if found_manifests:
        dependency_lock_hash = hasher.hexdigest()
    else:
        dependency_lock_hash = hashlib.sha256(b"NO_MANIFESTS_PRESENT").hexdigest()

    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    fp_hasher = hashlib.sha256()
    fp_hasher.update(py_ver.encode("utf-8"))
    fp_hasher.update(sys.platform.encode("utf-8"))
    fp_hasher.update(dependency_lock_hash.encode("utf-8"))
    environment_fingerprint = fp_hasher.hexdigest()

    return EnvironmentFingerprint(
        python_version=py_ver,
        platform=sys.platform,
        dependency_manifests=found_manifests,
        dependency_lock_hash=dependency_lock_hash,
        environment_fingerprint=environment_fingerprint,
        sandbox="docker"
    )

def generate_reproducible_dockerfile(
    repo_dir: Path,
    base_image: str = "python:3.11-slim"
) -> str:
    """
    Constructs a minimal Dockerfile to pre-install dependencies into an immutable
    environment image before sandbox execution runs with network disabled (--network none).
    """
    lines = [
        f"FROM {base_image}",
        "WORKDIR /workspace",
        "RUN pip install --no-cache-dir pytest",
    ]
    if (repo_dir / "requirements.txt").exists():
        lines.extend([
            "COPY requirements.txt /tmp/requirements.txt",
            "RUN pip install --no-cache-dir -r /tmp/requirements.txt",
        ])
    elif (repo_dir / "pyproject.toml").exists():
        lines.extend([
            "COPY pyproject.toml /workspace/pyproject.toml",
            "RUN pip install --no-cache-dir -e . || true",
        ])

    lines.append("COPY . /workspace")
    return "\n".join(lines) + "\n"
