import os
from pathlib import Path

def resolve_safe_extract_path(dest_dir: str, member_filename: str) -> str:
    """Calculates extraction path ensuring no breakout from dest_dir."""
    # BUG: Simply joins paths without verifying whether resolved path is inside dest_dir
    dest_path = os.path.abspath(dest_dir)
    target = os.path.join(dest_path, member_filename)
    return target
