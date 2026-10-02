import pytest
from solution import AVLTree

def check_avl_invariants(tree, node):
    if not node:
        return
    bal = tree.get_balance(node)
    assert abs(bal) <= 1, f"Node {node.key} has invalid balance factor {bal}"
    check_avl_invariants(tree, node.left)
    check_avl_invariants(tree, node.right)

def test_oracle_mass_avl_invariants():
    tree = AVLTree()
    root = None
    import random
    rng = random.Random(42)
    for v in rng.sample(range(1000), 50):
        root = tree.insert(root, v)
    check_avl_invariants(tree, root)
