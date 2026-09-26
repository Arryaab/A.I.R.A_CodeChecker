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
    "Pipfile",
    "environment.yml",
    "environment.yaml",
]

LOCK_FILENAMES = [
    "uv.lock",
    "poetry.lock",
    "Pipfile.lock",
    "pdm.lock",
]

@dataclass
class RequestedEnvironment:
    python_version: str
    platform: str
    dependency_manifests: List[str] = field(default_factory=list)
    dependency_manifest_hash: str = ""
    resolved_dependency_lock_hash: Optional[str] = None
    dependency_lock_hash: str = ""
    environment_fingerprint: str = ""

@dataclass
class ExecutedEnvironment:
    sandbox_engine: str  # "docker" or "host"
    sandbox_image: str   # container image tag or "host"
    python_version: str  # executed runtime python version
    platform: str        # executed runtime platform
    network_isolated: bool
    container_id: Optional[str] = None

@dataclass
class EnvironmentFingerprint:
    python_version: str
    platform: str
    dependency_manifests: List[str] = field(default_factory=list)
    dependency_manifest_hash: str = ""
    resolved_dependency_lock_hash: Optional[str] = None
    dependency_lock_hash: str = ""  # Backward-compatible alias/mirror of dependency_manifest_hash
    environment_fingerprint: str = ""
    sandbox: str = "docker"

    def to_requested_dict(self) -> dict:
        return {
            "python_version": self.python_version,
            "platform": self.platform,
            "dependency_manifests": self.dependency_manifests,
            "dependency_manifest_hash": self.dependency_manifest_hash,
            "resolved_dependency_lock_hash": self.resolved_dependency_lock_hash,
            "dependency_lock_hash": self.dependency_lock_hash,
            "environment_fingerprint": self.environment_fingerprint,
        }

def resolve_executed_environment(
    use_docker: bool,
    docker_image: str,
    host_env: EnvironmentFingerprint,
    container_id: Optional[str] = None,
) -> ExecutedEnvironment:
    if use_docker:
        return ExecutedEnvironment(
            sandbox_engine="docker",
            sandbox_image=docker_image,
            python_version="3.11-slim",
            platform="linux",
            network_isolated=True,
            container_id=container_id,
        )
    return ExecutedEnvironment(
        sandbox_engine="host",
        sandbox_image="host",
        python_version=host_env.python_version,
        platform=host_env.platform,
        network_isolated=False,
        container_id=None,
    )

def inspect_repository_environment(repo_dir: Path) -> EnvironmentFingerprint:
    """
    Inspects a repository to discover dependency manifests, calculate deterministic
    manifest and resolved lock hashes, and generate an immutable environment fingerprint.
    """
    found_manifests = []
    manifest_hasher = hashlib.sha256()

    for name in sorted(MANIFEST_FILENAMES):
        manifest_path = repo_dir / name
        if manifest_path.exists() and manifest_path.is_file():
            found_manifests.append(name)
            manifest_hasher.update(name.encode("utf-8"))
            try:
                content = manifest_path.read_bytes().replace(b"\r\n", b"\n")
                manifest_hasher.update(content)
            except Exception:
                pass

    if found_manifests:
        dependency_manifest_hash = manifest_hasher.hexdigest()
    else:
        dependency_manifest_hash = hashlib.sha256(b"NO_MANIFESTS_PRESENT").hexdigest()

    # Inspect lockfiles
    found_locks = []
    lock_hasher = hashlib.sha256()
    for name in sorted(LOCK_FILENAMES):
        lock_path = repo_dir / name
        if lock_path.exists() and lock_path.is_file():
            found_locks.append(name)
            lock_hasher.update(name.encode("utf-8"))
            try:
                content = lock_path.read_bytes().replace(b"\r\n", b"\n")
                lock_hasher.update(content)
            except Exception:
                pass

    if found_locks:
        resolved_dependency_lock_hash = lock_hasher.hexdigest()
    else:
        resolved_dependency_lock_hash = None

    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    fp_hasher = hashlib.sha256()
    fp_hasher.update(py_ver.encode("utf-8"))
    fp_hasher.update(sys.platform.encode("utf-8"))
    fp_hasher.update(dependency_manifest_hash.encode("utf-8"))
    if resolved_dependency_lock_hash:
        fp_hasher.update(resolved_dependency_lock_hash.encode("utf-8"))
    environment_fingerprint = fp_hasher.hexdigest()

    return EnvironmentFingerprint(
        python_version=py_ver,
        platform=sys.platform,
        dependency_manifests=found_manifests,
        dependency_manifest_hash=dependency_manifest_hash,
        resolved_dependency_lock_hash=resolved_dependency_lock_hash,
        dependency_lock_hash=dependency_manifest_hash,
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
            "RUN pip install --no-cache-dir -e .",
        ])
    elif (repo_dir / "setup.py").exists():
        lines.extend([
            "COPY setup.py /workspace/setup.py",
            "RUN pip install --no-cache-dir -e .",
        ])

    lines.append("COPY . /workspace")
    return "\n".join(lines) + "\n"

def build_sandbox_environment_image(
    repo_dir: Path,
    base_image: str = "python:3.11-slim"
) -> str:
    """
    Builds a reproducible container image for the repository snapshot if dependency manifests exist.
    Fails closed with RuntimeError if docker build fails.
    Returns the tagged image name or 'aegis-sandbox:latest' if no custom manifests are present.
    """
    import subprocess
    from aegis.execution.sandbox import is_docker_available

    has_manifests = any((repo_dir / m).exists() for m in ["requirements.txt", "pyproject.toml", "setup.py"])
    if not has_manifests:
        return "aegis-sandbox:latest"

    env = inspect_repository_environment(repo_dir)
    image_tag = f"aegis-env-{env.dependency_manifest_hash[:12]}"

    if not is_docker_available():
        raise RuntimeError(
            "Aegis Security Failure: Docker sandbox is required for executing changes with custom dependencies, "
            "but the Docker daemon is unavailable."
        )

    # Check if image already exists locally
    inspect_res = subprocess.run(
        ["docker", "image", "inspect", image_tag],
        capture_output=True,
        text=True
    )
    if inspect_res.returncode == 0:
        return image_tag

    # Build image using generated Dockerfile
    dockerfile_content = generate_reproducible_dockerfile(repo_dir, base_image=base_image)
    build_res = subprocess.run(
        ["docker", "build", "-t", image_tag, "-f", "-", str(repo_dir)],
        input=dockerfile_content,
        text=True,
        capture_output=True
    )
    if build_res.returncode != 0:
        err = build_res.stderr.strip() if build_res.stderr else f"exit code {build_res.returncode}"
        raise RuntimeError(
            f"Aegis Security Failure: Failed to build reproducible sandbox environment image '{image_tag}':\n{err}"
        )

    return image_tag
