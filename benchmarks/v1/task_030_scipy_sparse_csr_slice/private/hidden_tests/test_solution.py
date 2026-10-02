from solution import csr_row_slice

def test_valid_csr_row_slice():
    indptr = [0, 2, 3]
    indices = [0, 2, 1]
    data = [5.0, 8.0, 3.0]
    cols, vals = csr_row_slice(indptr, indices, data, 0)
    assert cols == [0, 2]
    assert vals == [5.0, 8.0]
