import pytest
from solution import Node, square_node, backward

def test_oracle_happy_path_backward_gradient():
    x = Node(3.0)
    y = square_node(x)
    backward(y)
    assert x.grad == 6.0

def test_oracle_happy_path_chain():
    x = Node(2.0)
    y = square_node(x)
    z = square_node(y)
    backward(z)
    assert z.val == 16.0
    assert x.grad == 32.0

def test_oracle_boundary_zero():
    x = Node(0.0)
    y = square_node(x)
    backward(y)
    assert x.grad == 0.0
