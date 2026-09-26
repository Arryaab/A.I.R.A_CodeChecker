from pathlib import Path
from aegis.evals.test_selection import TestSelector

def test_test_selector_by_name(tmp_path):
    # Setup mock repo
    (tmp_path / "auth.py").write_text("def login(): pass")
    (tmp_path / "test_auth.py").write_text("def test_login(): pass")
    (tmp_path / "test_payment.py").write_text("def test_pay(): pass")
    
    selector = TestSelector(tmp_path)
    selected = selector.select_tests_for_patch(["auth.py"])
    
    assert "test_auth.py" in selected
    assert "test_payment.py" not in selected

def test_test_selector_by_import(tmp_path):
    # Setup mock repo where test name doesn't match, but it imports the module
    (tmp_path / "user.py").write_text("def get_user(): pass")
    (tmp_path / "test_suite_regression.py").write_text("from user import get_user\ndef test_suite(): pass")
    (tmp_path / "test_unrelated.py").write_text("def test_other(): pass")
    
    selector = TestSelector(tmp_path)
    selected = selector.select_tests_for_patch(["user.py"])
    
    assert "test_suite_regression.py" in selected
    assert "test_unrelated.py" not in selected
