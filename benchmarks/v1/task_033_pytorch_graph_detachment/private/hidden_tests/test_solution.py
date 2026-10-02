from solution import Node, square_node, backward

def test_gradient_zero_input():
    x = Node(0.0)
    y = square_node(x)
    backward(y)
    assert x.grad == 0.0
