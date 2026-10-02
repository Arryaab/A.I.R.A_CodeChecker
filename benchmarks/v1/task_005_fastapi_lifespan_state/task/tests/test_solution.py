from solution import AppState

def test_state_clear_preserves_internal_dict_identity():
    app_state = AppState()
    ref = app_state._state
    app_state.set("db", "connected")
    app_state.clear()
    assert app_state.get("db") is None
    assert app_state._state is ref
