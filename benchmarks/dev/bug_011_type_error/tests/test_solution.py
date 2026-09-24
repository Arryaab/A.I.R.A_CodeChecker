from solution import stringify_list

def test_stringify_pass():
    assert stringify_list(['a', 'b']) == 'a,b'

def test_stringify_fail():
    assert stringify_list([1, 2, 3]) == '1,2,3'
