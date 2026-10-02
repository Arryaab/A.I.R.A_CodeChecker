import pytest
from solution import AppState

def test_oracle_happy_path_set_get():
    state = AppState()
    state.set("port", 8000)
    assert state.get("port") == 8000

def test_oracle_boundary_missing_key():
    state = AppState()
    assert state.get("nonexistent") is None
    assert state.get("nonexistent", "default") == "default"

def test_oracle_regression_identity_preservation():
    state = AppState()
    external_ref = state._state
    state.set("key1", "val1")
    state.clear()
    assert state._state is external_ref
    assert len(external_ref) == 0

def test_oracle_interaction_repopulation():
    state = AppState()
    alias = state._state
    state.set("a", 1)
    state.clear()
    state.set("b", 2)
    assert alias.get("b") == 2
    assert "a" not in alias
