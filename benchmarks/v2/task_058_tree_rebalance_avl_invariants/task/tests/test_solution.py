import pytest
from solution import AVLTree

def test_simple_sequential_insert():
    tree = AVLTree()
    root = None
    for k in [10, 20, 30]:
        root = tree.insert(root, k)
    assert tree.get_balance(root) in (-1, 0, 1)
