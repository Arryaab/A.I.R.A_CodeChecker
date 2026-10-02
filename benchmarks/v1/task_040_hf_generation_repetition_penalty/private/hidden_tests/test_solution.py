from solution import apply_repetition_penalty

def test_positive_logit_penalized():
    logits = [3.0, -1.0]
    res = apply_repetition_penalty(logits, seen_tokens={0}, penalty=1.5)
    assert res[0] == 2.0
