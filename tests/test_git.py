import subprocess
from pathlib import Path
import pytest
from aegis.integrations.git import get_git_diff, create_commit_snapshot

@pytest.fixture
def sample_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "AegisTester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@aegis.dev"], cwd=repo, check=True, capture_output=True)
    
    # Commit 1
    (repo / "f1.py").write_text("print('f1 v1')", encoding="utf-8")
    (repo / "f2.py").write_text("print('f2 v1')", encoding="utf-8")
    (repo / "to_delete.py").write_text("print('del')", encoding="utf-8")
    (repo / "to_rename.py").write_text("print('rename')", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "commit 1"], cwd=repo, check=True, capture_output=True)
    
    # Commit 2: modify f1, add f3, delete to_delete, rename to_rename
    (repo / "f1.py").write_text("print('f1 v2')", encoding="utf-8")
    (repo / "f3.py").write_text("print('f3 new')", encoding="utf-8")
    (repo / "to_delete.py").unlink()
    subprocess.run(["git", "mv", "to_rename.py", "renamed.py"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "commit 2"], cwd=repo, check=True, capture_output=True)
    
    return repo

def test_get_git_diff(sample_git_repo: Path):
    change = get_git_diff(sample_git_repo, base="HEAD~1", head="HEAD")
    assert "f1.py" in change.modified_files
    assert "f3.py" in change.added_files
    assert "to_delete.py" in change.deleted_files
    assert any(old == "to_rename.py" and new == "renamed.py" for old, new in change.renamed_files)
    assert "f1.py" in change.patches
    assert "f3.py" in change.patches
    assert "to_delete.py" in change.patches
    assert "renamed.py" in change.patches

def test_create_commit_snapshot(sample_git_repo: Path):
    with create_commit_snapshot(sample_git_repo, commit_ref="HEAD") as snapshot_dir:
        assert snapshot_dir.exists()
        assert (snapshot_dir / "f1.py").read_text(encoding="utf-8") == "print('f1 v2')"
        assert (snapshot_dir / "f3.py").exists()
        assert (snapshot_dir / "renamed.py").exists()
        assert not (snapshot_dir / "to_delete.py").exists()
        assert not (snapshot_dir / ".git").exists()
