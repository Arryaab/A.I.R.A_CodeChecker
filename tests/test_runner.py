"""Tests for aegis.execution.runner — verifying the test runner itself.

These tests run the runner against our sample_project and verify
that the returned TestResult has correct values for every field.

Why test the runner? Because every later stage trusts the runner's
output. If the runner incorrectly reports "all tests passed" when
they didn't, the entire repair loop is broken. Trust starts here.
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aegis.execution.runner import run_tests, PYTEST_EXIT_OK, PYTEST_EXIT_TESTS_FAILED

# Path to the sample project with one passing and one failing test.
SAMPLE_PROJECT = Path(__file__).resolve().parent.parent / "examples" / "sample_project"


@pytest.fixture(scope="module")
def sample_result():
    return run_tests(SAMPLE_PROJECT)

class TestRunnerWithFailures:
    """Test the runner against sample_project (which has 1 pass, 1 fail)."""

    def test_result_is_not_passed(self, sample_result):
        """Overall result should be 'not passed' because one test fails."""
        assert sample_result.passed is False

    def test_exit_code_is_one(self, sample_result):
        """Pytest exit code 1 means 'some tests failed'."""
        assert sample_result.exit_code == PYTEST_EXIT_TESTS_FAILED

    def test_counts(self, sample_result):
        """Should report exactly 1 passed and 1 failed."""
        assert sample_result.tests_passed == 1
        assert sample_result.tests_failed == 1
        assert sample_result.tests_error == 0

    def test_duration_is_positive(self, sample_result):
        """Duration should be a positive number (tests take real time)."""
        assert sample_result.duration_seconds > 0

    def test_stdout_is_captured(self, sample_result):
        """stdout should contain pytest output including test names."""
        assert "test_add" in sample_result.stdout
        assert "test_subtract" in sample_result.stdout

    def test_summary_line_is_extracted(self, sample_result):
        """Summary line should mention both passed and failed counts."""
        assert "1 failed" in sample_result.summary_line
        assert "1 passed" in sample_result.summary_line

    def test_failure_messages_extracted(self, sample_result):
        """Should extract at least one failure block about test_subtract."""
        assert len(sample_result.failure_messages) >= 1
        # The failure block should mention the assertion error.
        failure_text = "\n".join(sample_result.failure_messages)
        assert "subtract" in failure_text.lower()

    def test_invalid_directory_raises(self):
        """Passing a nonexistent directory should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            run_tests("/nonexistent/directory/that/does/not/exist")


class TestRunnerWithAllPassing:
    """Test the runner against a project where ALL tests pass.

    We create a temporary project on disk, run the runner, and
    verify the result shows full success.
    """

    def test_all_passing(self, tmp_path):
        """When all tests pass, result.passed should be True."""
        # Create a tiny passing project in a temporary directory.
        test_file = tmp_path / "test_simple.py"
        test_file.write_text("def test_one():\n    assert 1 + 1 == 2\n")

        result = run_tests(tmp_path)

        assert result.passed is True
        assert result.exit_code == PYTEST_EXIT_OK
        assert result.tests_passed == 1
        assert result.tests_failed == 0
        assert result.failure_messages == []
