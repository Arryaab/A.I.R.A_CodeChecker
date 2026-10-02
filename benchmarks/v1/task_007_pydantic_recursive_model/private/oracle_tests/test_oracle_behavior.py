import pytest
from solution import TreeNode, serialize_tree

def test_oracle_happy_path_acyclic_tree():
    leaf1 = TreeNode(1)
    leaf2 = TreeNode(2)
    root = TreeNode(10, [leaf1, leaf2])
    res = serialize_tree(root)
    assert res["value"] == 10
    assert len(res["children"]) == 2
    assert res["children"][0]["value"] == 1
    assert res["children"][1]["value"] == 2

def test_oracle_boundary_single_node():
    node = TreeNode(42)
    res = serialize_tree(node)
    assert res == {"value": 42, "children": []}

def test_oracle_negative_cyclic_reference():
    n1 = TreeNode(10)
    n2 = TreeNode(20, [n1])
    n1.children.append(n2)
    res = serialize_tree(n1)
    assert res["value"] == 10
    assert res["children"][0]["children"][0]["ref"] is True

def test_oracle_regression_self_loop():
    loop_node = TreeNode(99)
    loop_node.children.append(loop_node)
    res = serialize_tree(loop_node)
    assert res["value"] == 99
    assert res["children"][0]["ref"] is True
