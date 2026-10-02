from solution import Node, square_node, backward

def test_gradient_propagates_to_input():
    x = Node(3.0)
    y = square_node(x)
    backward(y)
    assert x.grad == 6.0
