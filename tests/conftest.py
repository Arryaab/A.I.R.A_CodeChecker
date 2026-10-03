import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Workaround for Python 3.14 on Windows where Path.unlink() on directory junctions raises WinError 5
try:
    import _pytest.pathlib
    _orig_cleanup = _pytest.pathlib.cleanup_dead_symlinks
    def _safe_cleanup_dead_symlinks(root):
        try:
            _orig_cleanup(root)
        except (PermissionError, OSError):
            pass
    _pytest.pathlib.cleanup_dead_symlinks = _safe_cleanup_dead_symlinks
except (ImportError, AttributeError):
    pass
