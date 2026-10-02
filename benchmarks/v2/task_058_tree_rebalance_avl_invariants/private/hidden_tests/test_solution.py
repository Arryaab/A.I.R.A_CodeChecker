import pytest
from solution import AVLTree

def test_zigzag_left_right_insertion():
    tree = AVLTree()
    root = None
    for k in [30, 10, 20]:
        root = tree.insert(root, k)
    assert tree.get_balance(root) in (-1, 0, 1)
    assert root.key == 20

def test_zigzag_right_left_insertion():
    tree = AVLTree()
    root = None
    for k in [10, 30, 20]:
        root = tree.insert(root, k)
    assert tree.get_balance(root) in (-1, 0, 1)
    assert root.key == 20
