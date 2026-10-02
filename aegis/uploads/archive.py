import os
import shutil
import tempfile
import zipfile
import tarfile
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

MAX_ARCHIVE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_EXTRACTED_SIZE = 200 * 1024 * 1024  # 200MB
MAX_FILE_COUNT = 5000
MAX_PATH_LENGTH = 256
MAX_SINGLE_FILE_SIZE = 25 * 1024 * 1024  # 25MB

SENSITIVE_PATTERNS = {'.env', '.pem', '.key', 'id_rsa'}

@dataclass
class ExtractionResult:
    success: bool
    extract_dir: Optional[Path] = None
    file_count: int = 0
    total_bytes: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    root_dir: Optional[Path] = None

def _is_sensitive(filename: str) -> bool:
    return any(filename.endswith(pattern) for pattern in SENSITIVE_PATTERNS)

def secure_cleanup(path: Path) -> None:
    """Securely deletes extracted files."""
    if path.exists() and path.is_dir():
        shutil.rmtree(path, ignore_errors=True)

def extract_archive(archive_path: Path, base_path: Optional[Path] = None) -> ExtractionResult:
    if not archive_path.exists():
        return ExtractionResult(success=False, errors=["Archive not found"])

    if archive_path.stat().st_size > MAX_ARCHIVE_SIZE:
        return ExtractionResult(success=False, errors=["Archive size exceeds 50MB limit"])

    extract_dir = Path(tempfile.mkdtemp(prefix='aira_project_', dir=base_path))
    result = ExtractionResult(success=True, extract_dir=extract_dir)

    try:
        if str(archive_path).endswith('.zip'):
            _extract_zip(archive_path, extract_dir, result)
        elif str(archive_path).endswith('.tar.gz') or str(archive_path).endswith('.tgz'):
            _extract_tar(archive_path, extract_dir, result)
        else:
            result.success = False
            result.errors.append("Unsupported archive format. Use .zip, .tar.gz, or .tgz")

        if not result.success:
            secure_cleanup(extract_dir)
            result.extract_dir = None
            return result

        # Auto-detect project root
        _detect_root(extract_dir, result)

    except Exception as e:
        secure_cleanup(extract_dir)
        return ExtractionResult(success=False, errors=[f"Extraction failed: {str(e)}"])

    return result

def _check_security(path_str: str, file_size: int, is_dir: bool, result: ExtractionResult) -> bool:
    if ".." in path_str or path_str.startswith("/") or path_str.startswith("\\"):
        result.errors.append(f"Security violation: path traversal detected in '{path_str}'")
        return False

    if len(path_str) > MAX_PATH_LENGTH:
        result.errors.append(f"Path too long: '{path_str}'")
        return False

    if _is_sensitive(path_str):
        result.errors.append(f"Sensitive file detected: '{path_str}'")
        return False

    if file_size > MAX_SINGLE_FILE_SIZE:
        result.errors.append(f"File too large: '{path_str}'")
        return False

    result.total_bytes += file_size
    if result.total_bytes > MAX_EXTRACTED_SIZE:
        result.errors.append("Total extracted size exceeds 200MB limit")
        return False

    if not is_dir:
        result.file_count += 1
        if result.file_count > MAX_FILE_COUNT:
            result.errors.append("Total file count exceeds 5000 limit")
            return False

    return True

def _extract_zip(archive_path: Path, extract_dir: Path, result: ExtractionResult) -> None:
    with zipfile.ZipFile(archive_path, 'r') as zf:
        for info in zf.infolist():
            # Check for symlink/device file using external_attr
            # the upper 16 bits map to unix file attributes
            unix_attr = info.external_attr >> 16
            if unix_attr:
                if stat.S_ISLNK(unix_attr) or stat.S_ISCHR(unix_attr) or stat.S_ISBLK(unix_attr):
                    result.errors.append(f"Security violation: symlink or device file '{info.filename}'")
                    result.success = False
                    return

            if not _check_security(info.filename, info.file_size, info.is_dir(), result):
                result.success = False
                return

            zf.extract(info, extract_dir)

def _extract_tar(archive_path: Path, extract_dir: Path, result: ExtractionResult) -> None:
    with tarfile.open(archive_path, 'r:gz') as tf:
        for info in tf:
            if info.issym() or info.islnk() or info.isblk() or info.ischr():
                result.errors.append(f"Security violation: symlink or device file '{info.name}'")
                result.success = False
                return

            if not _check_security(info.name, info.size, info.isdir(), result):
                result.success = False
                return

            tf.extract(info, extract_dir)

def _detect_root(extract_dir: Path, result: ExtractionResult) -> None:
    items = list(extract_dir.iterdir())
    if len(items) == 1 and items[0].is_dir():
        result.root_dir = items[0]
    else:
        result.root_dir = extract_dir
