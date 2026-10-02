class TreeNode:
    def __init__(self, value, children=None):
        self.value = value
        self.children = children or []

def serialize_tree(node: TreeNode, seen=None):
    # BUG: mutable default / missing seen set tracking leads to infinite loop on cycle
    return {
        "value": node.value,
        "children": [serialize_tree(c) for c in node.children]
    }
