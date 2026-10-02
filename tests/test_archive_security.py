"""
Tests for archive and repository security, preventing credential exposure.
Directives: P0-J, P0-K.
"""

import os
import re
import subprocess
from pathlib import Path
import pytest


FORBIDDEN_SECRET_PATTERNS = [
    r"AIza[0-9A-Za-z-_]{35}",           # Standard Google API Key
    r"AQ\.[0-9A-Za-z-_]{20,}",          # Alternate Google / Gemini format
    r"sk-[0-9A-Za-z]{20,}",             # OpenAI API Key
    r"ghp_[0-9A-Za-z]{36}",             # GitHub Personal Access Token
]

SENSITIVE_FILENAME_PATTERNS = [
    r"^\.env$",
    r"^\.env\..+$",
    r".*\.pem$",
    r".*\.key$",
    r".*id_rsa.*",
]


def test_dotenv_is_gitignored():
    """Verify that .env is explicitly gitignored."""
    project_root = Path(__file__).resolve().parent.parent
    gitignore_path = project_root / ".gitignore"
    assert gitignore_path.exists(), ".gitignore must exist"
    content = gitignore_path.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines()]
    assert ".env" in lines, ".env must be explicitly listed in .gitignore"


def test_git_tracked_files_contain_no_plaintext_secrets():
    """Scan all files tracked by git to ensure no real secrets are committed."""
    try:
        tracked_output = subprocess.check_output(
            ["git", "ls-files"], text=True, stderr=subprocess.PIPE
        )
    except Exception:
        pytest.skip("Git CLI not available or not in a git repository.")

    project_root = Path(__file__).resolve().parent.parent
    tracked_files = [line.strip() for line in tracked_output.splitlines() if line.strip()]

    leaks = []
    compiled_patterns = [re.compile(p) for p in FORBIDDEN_SECRET_PATTERNS]

    # Whitelist of test/dummy occurrences
    whitelist_indicators = ["dummy", "example", "sk-test-key", "test_key", "sk-ant-api", "PLACEHOLDER"]

    for rel_path in tracked_files:
        full_path = project_root / rel_path
        if not full_path.exists() or full_path.is_dir():
            continue
        try:
            text = full_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for line_no, line in enumerate(text.splitlines(), 1):
            if any(w in line for w in whitelist_indicators):
                continue
            for pattern in compiled_patterns:
                if pattern.search(line):
                    leaks.append(f"{rel_path}:{line_no}: Potential credential pattern match")

    assert not leaks, f"Credential leaks detected in git-tracked files: {leaks}"


def test_archive_packaging_fails_on_secret_bearing_patterns(tmp_path):
    """Verify that any archive packaging routine rejects files matching sensitive patterns."""
    def validate_files_for_packaging(file_paths: list[str]) -> list[str]:
        violations = []
        for fp in file_paths:
            fname = Path(fp).name
            for pat in SENSITIVE_FILENAME_PATTERNS:
                if re.match(pat, fname, re.IGNORECASE):
                    violations.append(f"Forbidden sensitive file in packaging list: {fp}")
        return violations

    # Test clean file list
    clean_files = [
        "aegis/core.py",
        "pyproject.toml",
        "README.md",
        "benchmarks/manifest.json",
    ]
    assert len(validate_files_for_packaging(clean_files)) == 0

    # Test tainted file list
    tainted_files = clean_files + [
        ".env",
        ".env.local",
        "secret.key",
        "cert.pem",
    ]
    violations = validate_files_for_packaging(tainted_files)
    assert len(violations) == 4
    assert any(".env" in v for v in violations)


def test_traces_and_manifests_do_not_contain_raw_api_keys():
    """Verify that existing traces and manifests contain no live keys."""
    project_root = Path(__file__).resolve().parent.parent
    check_dirs = [
        project_root / "experiments",
        project_root / "configs",
    ]
    compiled_patterns = [re.compile(p) for p in FORBIDDEN_SECRET_PATTERNS]
    leaks = []

    for d in check_dirs:
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if p.is_file() and p.suffix in (".json", ".yaml", ".yml", ".md"):
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                for line_no, line in enumerate(text.splitlines(), 1):
                    if "test" in line or "dummy" in line or "example" in line:
                        continue
                    for pat in compiled_patterns:
                        if pat.search(line):
                            leaks.append(f"{p.relative_to(project_root)}:{line_no}")

    assert not leaks, f"Raw secrets found in configuration/protocol files: {leaks}"


# ============================================================================
# Section 33 Explicit Archive Security Tests
# ============================================================================

def test_archive_rejects_relative_path_traversal(tmp_path):
    """Verify extract_archive rejects ../escape.py path traversal."""
    from aegis.uploads.archive import extract_archive
    import zipfile
    bad_zip = tmp_path / "traversal.zip"
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("../escape.py", "print('pwned')")
    res = extract_archive(bad_zip)
    assert not res.success
    assert any("path traversal" in err.lower() for err in res.errors)


def test_archive_rejects_absolute_path(tmp_path):
    """Verify extract_archive rejects absolute path /escape.py."""
    from aegis.uploads.archive import extract_archive
    import zipfile
    bad_zip = tmp_path / "absolute.zip"
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("/escape.py", "print('pwned')")
    res = extract_archive(bad_zip)
    assert not res.success
    assert any("path traversal" in err.lower() for err in res.errors)


def test_archive_rejects_symlink_escape(tmp_path):
    """Verify extract_archive rejects symlink archives."""
    from aegis.uploads.archive import extract_archive
    import tarfile
    bad_tar = tmp_path / "symlink.tar.gz"
    with tarfile.open(bad_tar, "w:gz") as tf:
        info = tarfile.TarInfo(name="symlink_link.py")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        tf.addfile(info)
    res = extract_archive(bad_tar)
    assert not res.success
    assert any("symlink" in err.lower() for err in res.errors)


def test_archive_rejects_oversized_file(tmp_path):
    """Verify extract_archive rejects archives containing uncompressed files > 25MB."""
    from aegis.uploads.archive import extract_archive, MAX_SINGLE_FILE_SIZE
    import zipfile
    bad_zip = tmp_path / "oversized_file.zip"
    with zipfile.ZipFile(bad_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("huge.bin", b"\x00" * (MAX_SINGLE_FILE_SIZE + 1024))
    res = extract_archive(bad_zip)
    assert not res.success
    assert any("file too large" in err.lower() for err in res.errors)


def test_archive_rejects_many_files(tmp_path):
    """Verify extract_archive rejects archives exceeding 5000 files limit."""
    from aegis.uploads.archive import extract_archive, MAX_FILE_COUNT
    import zipfile
    bad_zip = tmp_path / "many_files.zip"
    with zipfile.ZipFile(bad_zip, "w") as zf:
        for i in range(MAX_FILE_COUNT + 10):
            zf.writestr(f"file_{i}.txt", "x")
    res = extract_archive(bad_zip)
    assert not res.success
    assert any("file count exceeds" in err.lower() for err in res.errors)
