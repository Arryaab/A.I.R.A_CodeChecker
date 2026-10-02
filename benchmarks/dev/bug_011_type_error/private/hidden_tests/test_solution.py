from solution import stringify_list

def test_hidden_1():
    assert stringify_list([]) == ''

def test_hidden_2():
    assert stringify_list([True, None]) == 'True,None'
