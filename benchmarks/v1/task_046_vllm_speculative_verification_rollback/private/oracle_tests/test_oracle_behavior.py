import pytest
from solution import verify_draft_tokens

def test_oracle_happy_path_break_on_first_mismatch():
    draft = [10, 20, 30, 40]
    target = [10, 99, 30, 40]
    accepted, rollback = verify_draft_tokens(draft, target)
    assert accepted == [10]
    assert rollback == 3

def test_oracle_boundary_all_tokens_match():
    draft = [1, 2, 3]
    target = [1, 2, 3]
    accepted, rollback = verify_draft_tokens(draft, target)
    assert accepted == [1, 2, 3]
    assert rollback == 0

def test_oracle_boundary_first_token_mismatches():
    draft = [9, 2]
    target = [1, 2]
    accepted, rollback = verify_draft_tokens(draft, target)
    assert accepted == []
    assert rollback == 2
