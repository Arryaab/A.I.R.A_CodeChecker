from solution import word_frequency

def test_freq_pass():
    assert word_frequency('hello world') == {'hello': 1, 'world': 1}

def test_freq_fail():
    assert word_frequency('hello hello') == {'hello': 2}
