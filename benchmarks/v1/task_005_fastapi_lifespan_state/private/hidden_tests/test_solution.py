from solution import AppState

def test_state_mutation():
    app_state = AppState()
    app_state.set("count", 42)
    assert app_state.get("count") == 42
    assert app_state.get("missing", "default") == "default"
