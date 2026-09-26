import ast
import random
import copy
from typing import List, Tuple

class MutationTester(ast.NodeTransformer):
    """
    Adversarial verification: Mutates the AST of a Python file to test
    if the test suite is robust enough to catch the regression.
    """
    def __init__(self):
        self.mutations = 0
        self.max_mutations = 1

    def visit_Compare(self, node):
        self.generic_visit(node)
        if self.mutations >= self.max_mutations:
            return node
            
        if random.random() < 0.5:
            # Swap operators
            for i, op in enumerate(node.ops):
                if isinstance(op, ast.Eq):
                    node.ops[i] = ast.NotEq()
                    self.mutations += 1
                elif isinstance(op, ast.NotEq):
                    node.ops[i] = ast.Eq()
                    self.mutations += 1
                elif isinstance(op, ast.Lt):
                    node.ops[i] = ast.LtE()
                    self.mutations += 1
                elif isinstance(op, ast.Gt):
                    node.ops[i] = ast.GtE()
                    self.mutations += 1
        return node

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if self.mutations >= self.max_mutations:
            return node
            
        if random.random() < 0.5:
            if isinstance(node.op, ast.Add):
                node.op = ast.Sub()
                self.mutations += 1
            elif isinstance(node.op, ast.Sub):
                node.op = ast.Add()
                self.mutations += 1
            elif isinstance(node.op, ast.Mult):
                node.op = ast.Div()
                self.mutations += 1
        return node

def generate_mutations(source_code: str, num_mutants: int = 3) -> List[str]:
    """Generate multiple mutant versions of the source code."""
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []
        
    mutants = []
    for _ in range(num_mutants):
        # We need a fresh copy of the tree for each mutation pass
        tree_copy = copy.deepcopy(tree)
        tester = MutationTester()
        mutated_tree = tester.visit(tree_copy)
        ast.fix_missing_locations(mutated_tree)
        
        if tester.mutations > 0:
            mutants.append(ast.unparse(mutated_tree))
            
    return list(set(mutants)) # return unique mutants

from dataclasses import dataclass
from pathlib import Path
from aegis.execution.runner import run_tests

@dataclass
class MutationScoreResult:
    total_mutants: int
    killed_mutants: int
    survived_mutants: int
    score: float  # 0.0 to 1.0

def run_mutation_tests(
    project_dir: Path,
    target_files: List[str],
    max_mutants_per_file: int = 2,
    timeout: int = 15
) -> MutationScoreResult:
    """
    Executes actual mutation testing:
    Applies AST mutants to project files, runs pytest against them,
    and calculates empirical mutation score (killed / total).
    """
    total = 0
    killed = 0
    survived = 0

    for rel_path in target_files:
        f_path = project_dir / rel_path
        if not f_path.exists() or f_path.suffix != ".py" or "test_" in f_path.name:
            continue

        orig_code = f_path.read_text(encoding="utf-8", errors="replace")
        mutants = generate_mutations(orig_code, num_mutants=max_mutants_per_file)

        for mutant in mutants:
            total += 1
            try:
                # Write mutant to disk
                f_path.write_text(mutant, encoding="utf-8")
                # Run test suite against mutant
                res = run_tests(project_dir, timeout=timeout)
                if not res.passed:
                    # Test failed -> mutant was killed (Good test suite!)
                    killed += 1
                else:
                    # Test passed -> mutant survived (Test suite missed the regression!)
                    survived += 1
            except Exception:
                killed += 1
            finally:
                # Restore original file
                f_path.write_text(orig_code, encoding="utf-8")

    score = (killed / total) if total > 0 else 1.0
    return MutationScoreResult(
        total_mutants=total,
        killed_mutants=killed,
        survived_mutants=survived,
        score=score
    )
