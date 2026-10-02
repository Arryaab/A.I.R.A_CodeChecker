from solution import TreeNode, serialize_tree

def test_serialize_tree_with_cycle():
    n1 = TreeNode(10)
    n2 = TreeNode(20, [n1])
    n1.children.append(n2)
    res = serialize_tree(n1)
    assert res["value"] == 10
    assert res["children"][0]["children"][0]["ref"] is True
