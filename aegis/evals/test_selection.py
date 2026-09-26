import ast
from pathlib import Path
from typing import List, Set, Dict

class TestSelector:
    """
    Intelligent Test Selection:
    Analyzes modified files and selects the minimum sufficient set of test files
    based on naming conventions, symbol usage, and AST import graphs.
    """
    __test__ = False
    
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir

    def select_tests_for_patch(self, modified_files: List[str]) -> List[str]:
        """
        Given a list of modified files (relative paths), returns a prioritized list
        of test files that should be executed first.
        """
        all_candidates = list(self.project_dir.rglob("test_*.py"))
        all_tests = []
        for t in all_candidates:
            parts = [p.lower() for p in t.relative_to(self.project_dir).parts]
            if any(p in parts for p in ("benchmarks", "benchmark", "venv", ".venv", ".git", ".pytest_cache", "site-packages", "data")):
                continue
            all_tests.append(t)

        if not all_tests:
            return []
            
        selected_tests: Set[str] = set()
        
        # 1. Direct name matching heuristic (e.g. auth.py -> test_auth.py)
        for mod_file in modified_files:
            stem = Path(mod_file).stem
            for test_path in all_tests:
                if stem in test_path.stem:
                    selected_tests.add(str(test_path.relative_to(self.project_dir)))

        # 2. AST Import analysis heuristic: which tests import the modified file's module?
        for mod_file in modified_files:
            mod_module = Path(mod_file).stem
            for test_path in all_tests:
                try:
                    tree = ast.parse(test_path.read_text(encoding="utf-8"))
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                if mod_module in alias.name:
                                    selected_tests.add(str(test_path.relative_to(self.project_dir)))
                        elif isinstance(node, ast.ImportFrom):
                            if node.module and mod_module in node.module:
                                selected_tests.add(str(test_path.relative_to(self.project_dir)))
                except Exception:
                    pass

        # If heuristics found specific tests, return them; otherwise run all tests
        if selected_tests:
            return sorted(list(selected_tests))
        return [str(t.relative_to(self.project_dir)) for t in all_tests]
