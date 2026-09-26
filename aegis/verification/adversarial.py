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
