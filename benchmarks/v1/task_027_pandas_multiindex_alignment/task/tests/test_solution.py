from solution import align_multiindex_data

def test_multiindex_outer_join():
    d1 = {("A", 1): 10}
    d2 = {("B", 2): 20}
    res = align_multiindex_data(d1, d2)
    assert res == {("A", 1): 10, ("B", 2): 20}
