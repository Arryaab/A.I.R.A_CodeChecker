import subprocess
from pathlib import Path
from aegis.integrations.git import get_git_diff

def test_get_git_diff():
    repo_dir = Path(__file__).resolve().parent.parent
    # Test diff between HEAD~1 and HEAD
    change = get_git_diff(repo_dir, base="HEAD~1", head="HEAD")
    assert isinstance(change.modified_files, list)
    assert isinstance(change.added_files, list)
    assert isinstance(change.deleted_files, list)
    assert isinstance(change.renamed_files, list)
    assert isinstance(change.patches, dict)
    assert change.base == "HEAD~1"
    assert change.head == "HEAD"
