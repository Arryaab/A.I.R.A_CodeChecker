from solution import sample_token

def test_positive_temperature():
    logits = [0.1, 0.9, 0.4]
    assert sample_token(logits, temperature=0.7) == 1
