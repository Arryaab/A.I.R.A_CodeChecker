"""Tests for aegis.runner — verifying the test runner itself.

These tests run the runner against our sample_project and verify
that the returned TestResult has correct values for every field.

Why test the runner? Because every later stage trusts the runner's
output. If the runner incorrectly reports "all tests passed" when
they didn't, the entire repair loop is broken. Trust starts here.
"""

import sys
from pathlib import Path

# Add the aegis package to the import path so we can import runner.
# In a real installed package, this wouldn't be needed, but for
# development it lets us run tests directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "aegis"))

from runner import run_tests, PYTEST_EXIT_OK, PYTEST_EXIT_TESTS_FAILED


# Path to the sample project with one passing and one failing test.
SAMPLE_PROJECT = Path(__file__).resolve().parent.parent / "examples" / "sample_project"


class TestRunnerWithFailures:
    """Test the runner against sample_project (which has 1 pass, 1 fail)."""

    def test_result_is_not_passed(self):
        """Overall result should be 'not passed' because one test fails."""
        result = run_tests(SAMPLE_PROJECT)
        assert result.passed is False

    def test_exit_code_is_one(self):
        """Pytest exit code 1 means 'some tests failed'."""
        result = run_tests(SAMPLE_PROJECT)
        assert result.exit_code == PYTEST_EXIT_TESTS_FAILED

    def test_counts(self):
        """Should report exactly 1 passed and 1 failed."""
        result = run_tests(SAMPLE_PROJECT)
        assert result.tests_passed == 1
        assert result.tests_failed == 1
        assert result.tests_error == 0

    def test_duration_is_positive(self):
        """Duration should be a positive number (tests take real time)."""
        result = run_tests(SAMPLE_PROJECT)
        assert result.duration_seconds > 0

    def test_stdout_is_captured(self):
        """stdout should contain pytest output including test names."""
        result = run_tests(SAMPLE_PROJECT)
        assert "test_add" in result.stdout
        assert "test_subtract" in result.stdout

    def test_summary_line_is_extracted(self):
        """Summary line should mention both passed and failed counts."""
        result = run_tests(SAMPLE_PROJECT)
        assert "1 failed" in result.summary_line
        assert "1 passed" in result.summary_line

    def test_failure_messages_extracted(self):
        """Should extract at least one failure block about test_subtract."""
        result = run_tests(SAMPLE_PROJECT)
        assert len(result.failure_messages) >= 1
        # The failure block should mention the assertion error.
        failure_text = "\n".join(result.failure_messages)
        assert "subtract" in failure_text.lower()

    def test_invalid_directory_raises(self):
        """Passing a nonexistent directory should raise FileNotFoundError."""
        import pytest
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
