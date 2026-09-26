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

def test_git_verification_executes_head_not_base(tmp_path: Path):
    import json
    import sys

    repo = tmp_path / "head_not_base_repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@aegis.dev"], cwd=repo, check=True, capture_output=True)

    # Commit 1 (BASE): calc.py returns 1. test_calc.py expects 2 (fails on BASE, passes on HEAD)
    (repo / "calc.py").write_text("def get_value():\n    return 1\n", encoding="utf-8")
    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_calc.py").write_text("from calc import get_value\n\ndef test_val():\n    assert get_value() == 2\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "base commit with buggy get_value() returning 1"], cwd=repo, check=True, capture_output=True)

    # Commit 2 (HEAD): calc.py returns 2. test_calc.py now passes!
    (repo / "calc.py").write_text("def get_value():\n    return 2\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "fix get_value() to return 2"], cwd=repo, check=True, capture_output=True)

    # Run Aegis verification comparing BASE (HEAD~1) and HEAD
    out_dir = tmp_path / "runs"
    cmd = [
        sys.executable, "-m", "aegis.cli", "verify",
        "--project-dir", str(repo),
        "--base", "HEAD~1",
        "--head", "HEAD",
        "--tier", "fast",
        "--output-dir", str(out_dir),
        "--unsafe-local"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")

    # Report verification
    report_file = out_dir / "report.json"
    assert report_file.exists(), f"Report file not generated. Stderr: {res.stderr}\nStdout: {res.stdout}"
    report = json.loads(report_file.read_text(encoding="utf-8"))

    # If Aegis mistakenly executed BASE, get_value() returned 1 and targeted_tests failed.
    # Because Aegis correctly executes HEAD, get_value() returns 2 and targeted_tests passed!
    assert report["verification"]["targeted_tests"]["passed"] is True
    assert "QUALIFIED" in report["decision"]["technical_verdict"]

    # Also verify requested_environment and executed_environment in provenance
    assert "requested_environment" in report["provenance"]
    assert "executed_environment" in report["provenance"]

def test_diff_mode_applies_patch_before_environment_build(tmp_path: Path):
    import json
    import sys

    repo = tmp_path / "diff_repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@aegis.dev"], cwd=repo, check=True, capture_output=True)

    # Base commit
    (repo / "calc.py").write_text("def compute():\n    return 10\n", encoding="utf-8")
    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_calc.py").write_text("from calc import compute\ndef test_compute():\n    assert compute() == 20\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "base commit"], cwd=repo, check=True, capture_output=True)

    # Create patch modifying calc.py to return 20 and adding requirements.txt
    patch_file = tmp_path / "fix.diff"
    patch_content = (
        "--- a/calc.py\n"
        "+++ b/calc.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def compute():\n"
        "-    return 10\n"
        "+    return 20\n"
        "--- /dev/null\n"
        "+++ b/requirements.txt\n"
        "@@ -0,0 +1 @@\n"
        "+pytest>=7.0.0\n"
    )
    patch_file.write_text(patch_content, encoding="utf-8")

    out_dir = tmp_path / "diff_runs"
    cmd = [
        sys.executable, "-m", "aegis.cli", "verify",
        "--project-dir", str(repo),
        "--diff", str(patch_file),
        "--base", "HEAD",
        "--tier", "fast",
        "--output-dir", str(out_dir),
        "--unsafe-local"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")

    report_file = out_dir / "report.json"
    assert report_file.exists(), f"Stderr: {res.stderr}\nStdout: {res.stdout}"
    report = json.loads(report_file.read_text(encoding="utf-8"))

    # Verified targeted test passes on patched code
    assert report["verification"]["targeted_tests"]["passed"] is True
    # Verified environment inspection detected requirements.txt from the applied patch
    assert "requirements.txt" in report["provenance"]["environment"]["dependency_manifests"]



