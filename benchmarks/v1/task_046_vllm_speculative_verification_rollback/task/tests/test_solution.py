from solution import verify_draft_tokens

def test_stop_on_first_mismatch():
    draft = [10, 20, 30, 40]
    target = [10, 99, 30, 40]
    accepted, rollback = verify_draft_tokens(draft, target)
    assert accepted == [10]
    assert rollback == 3
