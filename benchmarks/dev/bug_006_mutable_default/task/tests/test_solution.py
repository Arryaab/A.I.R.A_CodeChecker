from solution import append_to_list

def test_append_pass():
    assert append_to_list(1, [2]) == [2, 1]

def test_append_fail():
    l1 = append_to_list(1)
    l2 = append_to_list(2)
    assert l2 == [2]
