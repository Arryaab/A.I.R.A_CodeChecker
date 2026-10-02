from solution import apply_repetition_penalty

def test_negative_logit_penalized_correctly():
    logits = [2.0, -2.0]
    res = apply_repetition_penalty(logits, seen_tokens={1}, penalty=1.5)
    assert res[1] == -3.0
