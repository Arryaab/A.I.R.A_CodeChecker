from solution import TreeNode, serialize_tree

def test_serialize_tree_simple():
    root = TreeNode(1, [TreeNode(2), TreeNode(3)])
    res = serialize_tree(root)
    assert res["value"] == 1
    assert len(res["children"]) == 2
