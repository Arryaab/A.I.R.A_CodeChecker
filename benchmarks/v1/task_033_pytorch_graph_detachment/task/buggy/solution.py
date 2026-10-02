class Node:
    def __init__(self, val, grad=0.0, prev=None):
        self.val = val
        self.grad = grad
        self.prev = prev or []

def square_node(x: Node) -> Node:
    # BUG: creates new detached node without setting prev linkage
    return Node(x.val ** 2, prev=[])

def backward(out: Node):
    out.grad = 1.0
    queue = [out]
    while queue:
        curr = queue.pop(0)
        for p in curr.prev:
            p.grad += curr.grad * (2 * p.val)
            queue.append(p)
