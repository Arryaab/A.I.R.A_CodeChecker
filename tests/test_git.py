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

def test_create_commit_snapshot_fail_closed(sample_git_repo: Path):
    with pytest.raises(RuntimeError, match="Failed to create hermetic git snapshot"):
        with create_commit_snapshot(sample_git_repo, commit_ref="non_existent_ref_12345"):
            pass

def test_git_show_object_fail_closed(sample_git_repo: Path):
    from aegis.integrations.git import _git_show_object
    with pytest.raises(RuntimeError, match="Commit-pure verification error"):
        _git_show_object(sample_git_repo, "HEAD", "non_existent_file_xyz.py")

def test_parse_unified_diff_and_apply(sample_git_repo: Path, tmp_path: Path):
    from aegis.integrations.git import parse_unified_diff, apply_patch_file
    
    # Generate unified diff between HEAD~1 and HEAD
    res = subprocess.run(
        ["git", "diff", "-M", "HEAD~1..HEAD"],
        cwd=sample_git_repo,
        capture_output=True,
        text=True,
        check=True
    )
    raw_diff = res.stdout
    
    affected, patches = parse_unified_diff(sample_git_repo, raw_diff, base_ref="HEAD~1")
    assert "f1.py" in affected
    assert "f3.py" in affected
    assert "to_delete.py" in affected or "to_rename.py" in affected or "renamed.py" in affected
    
    patch_file = tmp_path / "change.patch"
    patch_file.write_text(raw_diff, encoding="utf-8")
    
    with create_commit_snapshot(sample_git_repo, commit_ref="HEAD~1") as snap_dir:
        # Pre-patch checks
        assert (snap_dir / "f1.py").read_text(encoding="utf-8") == "print('f1 v1')"
        assert not (snap_dir / "f3.py").exists()
        assert (snap_dir / "to_delete.py").exists()
        
        # Apply patch hermetically
        apply_patch_file(snap_dir, patch_file)
        
        # Post-patch verification
        assert (snap_dir / "f1.py").read_text(encoding="utf-8").strip() == "print('f1 v2')"
        assert (snap_dir / "f3.py").exists()
        assert not (snap_dir / "to_delete.py").exists()

def test_apply_patch_file_fail_closed(tmp_path: Path):
    from aegis.integrations.git import apply_patch_file
    bad_patch = tmp_path / "corrupt.patch"
    bad_patch.write_text("invalid diff header\n@@ bogus @@\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="(Failed to apply patch|Strict patch check failed)"):
        apply_patch_file(tmp_path, bad_patch)



