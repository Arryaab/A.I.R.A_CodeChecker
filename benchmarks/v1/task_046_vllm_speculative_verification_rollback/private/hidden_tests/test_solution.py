from solution import verify_draft_tokens

def test_all_draft_tokens_accepted():
    draft = [1, 2, 3]
    target = [1, 2, 3]
    accepted, rollback = verify_draft_tokens(draft, target)
    assert accepted == [1, 2, 3]
    assert rollback == 0
