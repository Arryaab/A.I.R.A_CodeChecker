from solution import sample_token

def test_temperature_zero_greedy_argmax():
    logits = [1.2, 5.8, 3.4]
    assert sample_token(logits, temperature=0.0) == 1
