from solution import Context

def test_child_context_mutation_does_not_leak():
    parent = Context({"env": "prod"})
    child = parent.child()
    child.data["env"] = "staging"
    assert parent.data["env"] == "prod"
