import ast
import copy
from typing import List, Tuple
from dataclasses import dataclass
from pathlib import Path
from aegis.execution.runner import run_tests

class DeterministicMutator(ast.NodeTransformer):
    """
    Adversarial verification: Deterministically mutates the target-th operator
    in the AST of a Python file to guarantee full reproducibility.
    """
    def __init__(self, target_index: int):
        self.target_index = target_index
        self.current_index = 0
        self.mutated = False

    def visit_Compare(self, node):
        self.generic_visit(node)
        if self.mutated:
            return node
            
        for i, op in enumerate(node.ops):
            if self.current_index == self.target_index:
                if isinstance(op, ast.Eq):
                    node.ops[i] = ast.NotEq()
                elif isinstance(op, ast.NotEq):
                    node.ops[i] = ast.Eq()
                elif isinstance(op, ast.Lt):
                    node.ops[i] = ast.LtE()
                elif isinstance(op, ast.LtE):
                    node.ops[i] = ast.Lt()
                elif isinstance(op, ast.Gt):
                    node.ops[i] = ast.GtE()
                elif isinstance(op, ast.GtE):
                    node.ops[i] = ast.Gt()
                self.mutated = True
                break
            self.current_index += 1
        return node

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if self.mutated:
            return node
            
        if self.current_index == self.target_index:
            if isinstance(node.op, ast.Add):
                node.op = ast.Sub()
            elif isinstance(node.op, ast.Sub):
                node.op = ast.Add()
            elif isinstance(node.op, ast.Mult):
                node.op = ast.Div()
            elif isinstance(node.op, ast.Div):
                node.op = ast.Mult()
            self.mutated = True
        self.current_index += 1
        return node

def generate_mutations(source_code: str, num_mutants: int = 3) -> List[str]:
    """
    Deterministically generate up to num_mutants unique mutant versions of source code.
    Mutates nodes in consistent sequential AST order.
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []
        
    mutants = []
    seen = {source_code}
    
    # Try successive indices until we reach num_mutants or exhaust operators
    for idx in range(num_mutants * 3):
        tree_copy = copy.deepcopy(tree)
        mutator = DeterministicMutator(target_index=idx)
        mutated_tree = mutator.visit(tree_copy)
        ast.fix_missing_locations(mutated_tree)
        
        if mutator.mutated:
            code = ast.unparse(mutated_tree)
            if code not in seen:
                seen.add(code)
                mutants.append(code)
                if len(mutants) >= num_mutants:
                    break
                    
    return mutants

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
    Executes deterministic mutation testing:
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
