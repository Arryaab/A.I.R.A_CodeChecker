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

import tempfile
import shutil
from typing import Optional

@dataclass
class MutationScoreResult:
    total_mutants: int
    killed_mutants: int
    survived_mutants: int
    invalid_mutants: int = 0
    infra_errors: int = 0
    score: Optional[float] = None  # 0.0 to 1.0, or None if no valid mutants

def run_mutation_tests(
    project_dir: Path,
    target_files: List[str],
    max_mutants_per_file: int = 2,
    timeout: int = 15,
    use_docker: bool = False,
    require_sandbox: bool = False,
) -> MutationScoreResult:
    """
    Executes deterministic mutation testing with fresh snapshot isolation per mutant.
    Classifies outcomes into:
      - KILLED: Test suite failed as expected when mutation was introduced.
      - SURVIVED: Test suite passed despite the defect (test suite gap).
      - INVALID: Mutation caused syntax/import error.
      - INFRA_ERROR: Test execution encountered runner/sandbox infrastructure failure.
    The empirical mutation score denominator is strictly (killed + survived).
    """
    total = 0
    killed = 0
    survived = 0
    invalid = 0
    infra_errors = 0

    from aegis.execution.sandbox import run_tests_sandboxed

    for rel_path in target_files:
        f_path = project_dir / rel_path
        if not f_path.exists() or f_path.suffix != ".py" or "test_" in f_path.name:
            continue

        orig_code = f_path.read_text(encoding="utf-8", errors="replace")
        mutants = generate_mutations(orig_code, num_mutants=max_mutants_per_file)

        for mutant in mutants:
            total += 1
            # Execute mutant in an isolated fresh copy
            with tempfile.TemporaryDirectory() as td:
                snap_dir = Path(td) / "mutant_snap"
                shutil.copytree(project_dir, snap_dir, ignore=shutil.ignore_patterns(".git", ".pytest_cache", "__pycache__", ".aegis"))
                target_in_snap = snap_dir / rel_path
                
                try:
                    # Check syntax of mutant
                    ast.parse(mutant)
                except SyntaxError:
                    invalid += 1
                    continue

                target_in_snap.write_text(mutant, encoding="utf-8")

                try:
                    res = run_tests_sandboxed(
                        snap_dir,
                        timeout=timeout,
                        use_docker=use_docker,
                        require_sandbox=require_sandbox
                    )
                    tr = res.test_result
                    if tr.exit_code == 2:  # internal pytest error / usage error
                        invalid += 1
                    elif not tr.passed:
                        # Test suite failed -> mutant killed
                        killed += 1
                    else:
                        # Test suite passed -> mutant survived
                        survived += 1
                except Exception:
                    infra_errors += 1

    valid_evaluated = killed + survived
    score = (killed / valid_evaluated) if valid_evaluated > 0 else None

    return MutationScoreResult(
        total_mutants=total,
        killed_mutants=killed,
        survived_mutants=survived,
        invalid_mutants=invalid,
        infra_errors=infra_errors,
        score=round(score, 3) if score is not None else None
    )
