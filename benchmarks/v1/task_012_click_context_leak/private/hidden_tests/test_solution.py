from solution import Context

def test_child_inherits_parent_values():
    parent = Context({"debug": True})
    child = parent.child()
    assert child.data["debug"] is True
